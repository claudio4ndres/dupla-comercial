"""Rutas de solicitudes."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.dependencias import (
    obtener_cliente_anthropic,
    obtener_cliente_clickup,
    obtener_empresa_actual,
    obtener_repositorio_conversaciones,
    obtener_repositorio_propuestas,
    obtener_repositorio_solicitudes,
)
from app.esquemas import (
    ComponentePropuestaSalida,
    CrearPropuestaEntrada,
    EnvioClickUpEntrada,
    PropuestaDetalle,
    ResultadoClasificacion,
    ResultadoEnvioClickUp,
    SolicitudListada,
    TareaPropuestaSalida,
    TransicionEstadoEntrada,
)
from app.repositorios.propuestas import ComponentePropuesta, TareaPropuesta
from app.servicios.clasificador import clasificar_solicitud
from app.servicios.exportador_excel import (
    LineaCotizacion,
    generar_excel_cotizacion,
)
from app.servicios.exportador_ppt import generar_ppt_cotizacion

# Media-type oficial de un .xlsx (OOXML).
_MEDIA_XLSX = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
# Media-type oficial de un .pptx (OOXML).
_MEDIA_PPTX = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])

_TIPOS_VALIDOS = ("tipo_1", "tipo_2")

# #7 · Ciclo de vida de la propuesta: desde cada estado, a cuáles se puede pasar.
# borrador → aprobada → enviada (no se salta pasos; quedarse en el mismo es no-op).
_TRANSICIONES_PROPUESTA: dict[str, set[str]] = {
    "borrador": {"borrador", "aprobada"},
    "aprobada": {"aprobada", "enviada"},
    "enviada": {"enviada"},
}


@router.get("", response_model=list[SolicitudListada])
async def listar_solicitudes(
    repo=Depends(obtener_repositorio_solicitudes),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> list[SolicitudListada]:
    """Bandeja de la empresa: las solicitudes que el poller ingirió desde el correo.

    Sólo las de la empresa del usuario (aislamiento multi-tenant, T4). Se construye
    una vista plana, así nunca viajan `empresa_id` ni referencias internas (CA5).
    """
    solicitudes = await repo.listar(empresa_id)
    return [
        SolicitudListada(
            id=str(s.id),
            remitente=s.remitente,
            correo_origen=s.correo_origen,
            asunto=s.asunto,
            cuerpo=s.cuerpo,
            resumen=s.resumen,
            tipo=s.tipo,
            estado=s.estado,
            # `creado_en` (timestamptz) → ISO 8601 para el front; None si la fila no la trae.
            recibido_en=s.creado_en.isoformat() if s.creado_en else None,
        )
        for s in solicitudes
    ]


@router.post("/{solicitud_id}/clasificar", response_model=ResultadoClasificacion)
async def clasificar(
    solicitud_id: UUID,
    repo=Depends(obtener_repositorio_solicitudes),
    cliente=Depends(obtener_cliente_anthropic),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> ResultadoClasificacion:
    solicitud = await repo.obtener(solicitud_id, empresa_id)
    if solicitud is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Idempotente: si ya está clasificada, devolvemos sin volver a gastar el LLM.
    if solicitud.resumen and solicitud.tipo in _TIPOS_VALIDOS:
        return ResultadoClasificacion(resumen=solicitud.resumen, tipo=solicitud.tipo)

    try:
        resultado = await clasificar_solicitud(solicitud.cuerpo, cliente)
    except Exception as exc:
        # El LLM es un servicio externo: si cae, es un 502 (no un 500 crudo) y
        # la solicitud queda sin clasificar para poder reintentar después.
        raise HTTPException(
            status_code=502, detail="El servicio de clasificación no está disponible"
        ) from exc

    await repo.guardar_clasificacion(
        solicitud_id, empresa_id, resultado.resumen, resultado.tipo
    )
    return resultado


@router.get("/{solicitud_id}/propuesta", response_model=PropuestaDetalle)
async def obtener_propuesta(
    solicitud_id: UUID,
    repo=Depends(obtener_repositorio_propuestas),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> PropuestaDetalle:
    """Cotización resuelta de la solicitud: componentes valorizados + tareas.

    Sólo de la empresa del usuario (RLS). Sin propuesta para esa solicitud → 404
    (el front cae a su fallback offline). La vista es plana: nunca viaja
    `empresa_id` ni referencias internas (CA5).
    """
    propuesta = await repo.obtener_por_solicitud(solicitud_id, empresa_id)
    if propuesta is None:
        raise HTTPException(status_code=404, detail="La solicitud no tiene propuesta")
    return PropuestaDetalle(
        id=str(propuesta.id),
        total=propuesta.total,
        estado=propuesta.estado,
        componentes=[
            ComponentePropuestaSalida(**c.model_dump()) for c in propuesta.componentes
        ],
        tareas=[TareaPropuestaSalida(**t.model_dump()) for t in propuesta.tareas],
    )


@router.post("/{solicitud_id}/propuesta", response_model=PropuestaDetalle)
async def crear_propuesta(
    solicitud_id: UUID,
    cuerpo: CrearPropuestaEntrada,
    repo=Depends(obtener_repositorio_propuestas),
    repo_conv=Depends(obtener_repositorio_conversaciones),
    repo_sol=Depends(obtener_repositorio_solicitudes),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> PropuestaDetalle:
    """Persiste la propuesta que Javo armó en el chat (componentes valorizados +
    tareas de ejecución), ligada a la conversación de la solicitud. La devuelve para
    que las pantallas Propuesta/Tareas y los exports (Excel/PPT/ClickUp) la usen.

    Antes esto NO existía: 'Generar propuesta' sólo hacía GET → 404 con datos reales
    (sólo funcionaba la demo sembrada). Ahora la conversación SÍ baja a propuesta.

    IDEMPOTENTE (#4): re-generar la propuesta sobre la misma solicitud NO duplica (la
    conversación se reutiliza por (solicitud, tipo) y el repo reemplaza en sitio). Al
    crearla, la solicitud avanza su `estado` a 'propuesta' (#7, ciclo de vida)."""
    conversacion_id = await repo_conv.obtener_o_crear_conversacion(
        solicitud_id, empresa_id, cuerpo.tipo
    )
    componentes = [
        ComponentePropuesta(
            nombre=c.nombre,
            detalle=c.detalle,
            proveedor=c.proveedor,
            origen=c.origen,
            cantidad=c.cantidad,
            dias=c.dias or 1,
            valor_unitario=c.valor_unitario or 0,
        )
        for c in cuerpo.componentes
    ]
    tareas = [
        TareaPropuesta(
            nombre=t.nombre,
            grupo=t.area,
            responsable=t.responsable,
            vencimiento=t.plazo,
        )
        for t in cuerpo.tareas
    ]
    propuesta = await repo.crear(
        empresa_id, solicitud_id, conversacion_id, componentes, tareas
    )
    # #7 · La solicitud avanza a 'propuesta' (CHECK de la tabla). Best-effort: si la
    # solicitud no existe en el store (p.ej. una demo sin fila), no rompe la creación.
    try:
        await repo_sol.actualizar_estado(solicitud_id, empresa_id, "propuesta")
    except KeyError:
        pass
    return PropuestaDetalle(
        id=str(propuesta.id),
        total=propuesta.total,
        estado=propuesta.estado,
        componentes=[
            ComponentePropuestaSalida(**c.model_dump()) for c in propuesta.componentes
        ],
        tareas=[TareaPropuestaSalida(**t.model_dump()) for t in propuesta.tareas],
    )


@router.patch("/{solicitud_id}/propuesta/estado", response_model=PropuestaDetalle)
async def transicionar_estado_propuesta(
    solicitud_id: UUID,
    cuerpo: TransicionEstadoEntrada,
    repo=Depends(obtener_repositorio_propuestas),
    repo_sol=Depends(obtener_repositorio_solicitudes),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> PropuestaDetalle:
    """#7 · Transiciona el estado de la propuesta: borrador → aprobada → enviada.

    Sólo de la empresa del usuario (RLS por su JWT). Sin propuesta para la solicitud →
    404. Transición inválida (saltarse pasos, p.ej. borrador→enviada, o retroceder) →
    409. El valor fuera del enum lo rechaza Pydantic (422) antes de llegar aquí.

    Si la propuesta pasa a 'enviada', la solicitud también avanza a 'enviada' (mantiene
    en sincronía el ciclo de vida de ambas)."""
    propuesta = await repo.obtener_por_solicitud(solicitud_id, empresa_id)
    if propuesta is None:
        raise HTTPException(status_code=404, detail="La solicitud no tiene propuesta")

    permitidos = _TRANSICIONES_PROPUESTA.get(propuesta.estado, set())
    if cuerpo.estado not in permitidos:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede pasar de '{propuesta.estado}' a '{cuerpo.estado}'",
        )

    actualizada = await repo.actualizar_estado(propuesta.id, empresa_id, cuerpo.estado)
    # #7 · Al enviar la propuesta, la solicitud también avanza a 'enviada' (best-effort).
    if cuerpo.estado == "enviada":
        try:
            await repo_sol.actualizar_estado(solicitud_id, empresa_id, "enviada")
        except KeyError:
            pass
    return PropuestaDetalle(
        id=str(actualizada.id),
        total=actualizada.total,
        estado=actualizada.estado,
        componentes=[
            ComponentePropuestaSalida(**c.model_dump()) for c in actualizada.componentes
        ],
        tareas=[TareaPropuestaSalida(**t.model_dump()) for t in actualizada.tareas],
    )


@router.get("/{solicitud_id}/cotizacion.xlsx")
async def descargar_cotizacion_excel(
    solicitud_id: UUID,
    # Fracción de margen [0, 1): margen=1 divide por cero y >1 da precios negativos.
    margen: float = Query(0.40, ge=0, lt=1),
    vista: str = "interno",
    repo=Depends(obtener_repositorio_propuestas),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> Response:
    """Descarga la cotización de la solicitud como `.xlsx` con el theme Capsulab (007).

    Reusa la propuesta persistida (spec 004) — sólo la de la empresa del usuario (RLS).
    Sin propuesta → 404. `valor_unitario` de cada componente es el COSTO unitario; el
    `margen` (query param, 0.40 por defecto) se aplica para el precio de venta. `días`
    no se persiste hoy (va 1). `vista`: `interno` (costos + margen, default) o `cliente`
    (solo precios de venta, sin exponer costos)."""
    vista_norm = "cliente" if vista == "cliente" else "interno"
    propuesta = await repo.obtener_por_solicitud(solicitud_id, empresa_id)
    if propuesta is None:
        raise HTTPException(status_code=404, detail="La solicitud no tiene propuesta")

    lineas = [
        LineaCotizacion(
            item=c.nombre,
            descripcion=c.detalle or "",
            proveedor=c.proveedor or "",
            cantidad=c.cantidad,
            dias=c.dias,
            valor_unitario=c.valor_unitario,
        )
        for c in propuesta.componentes
    ]
    contenido = generar_excel_cotizacion(
        lineas, titulo="Cotización", margen=margen, vista=vista_norm
    )
    return Response(
        content=contenido,
        media_type=_MEDIA_XLSX,
        headers={
            "Content-Disposition": (
                f'attachment; filename="cotizacion-{vista_norm}-{solicitud_id}.xlsx"'
            )
        },
    )


@router.get("/{solicitud_id}/propuesta.pptx")
async def descargar_propuesta_ppt(
    solicitud_id: UUID,
    # Fracción de margen [0, 1): margen=1 divide por cero y >1 da precios negativos.
    margen: float = Query(0.40, ge=0, lt=1),
    repo=Depends(obtener_repositorio_propuestas),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> Response:
    """Descarga la propuesta como un DECK `.pptx` con el theme Capsulab (T18).

    Es la **cara comercial** (vista cliente): solo precios de venta, sin costos ni
    margen (mismo criterio que el Excel cliente). Reusa la propuesta persistida
    (spec 004) — sólo la de la empresa del usuario (RLS). Sin propuesta → 404.
    `valor_unitario` de cada componente es el COSTO unitario; el `margen` (query
    param, 0.40 por defecto) se aplica para el precio de venta. `días` no se persiste
    hoy (va 1)."""
    propuesta = await repo.obtener_por_solicitud(solicitud_id, empresa_id)
    if propuesta is None:
        raise HTTPException(status_code=404, detail="La solicitud no tiene propuesta")

    lineas = [
        LineaCotizacion(
            item=c.nombre,
            descripcion=c.detalle or "",
            proveedor="",
            cantidad=c.cantidad,
            dias=getattr(c, "dias", 1) or 1,
            valor_unitario=c.valor_unitario,
        )
        for c in propuesta.componentes
    ]
    contenido = generar_ppt_cotizacion(lineas, titulo="Cotización", margen=margen)
    return Response(
        content=contenido,
        media_type=_MEDIA_PPTX,
        headers={
            "Content-Disposition": (
                f'attachment; filename="cotizacion-{solicitud_id}.pptx"'
            )
        },
    )


@router.post(
    "/{solicitud_id}/tareas/clickup", response_model=ResultadoEnvioClickUp
)
async def enviar_tareas_a_clickup(
    solicitud_id: UUID,
    lista_id: str | None = None,
    entrada: EnvioClickUpEntrada | None = None,
    repo=Depends(obtener_repositorio_propuestas),
    repo_sol=Depends(obtener_repositorio_solicitudes),
    clickup=Depends(obtener_cliente_clickup),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> ResultadoEnvioClickUp:
    """Crea las tareas de la propuesta como tareas REALES en ClickUp (conector).

    La lista destino la ELIGE el usuario en la UI y llega como query `lista_id`. Si no
    viene → 400 ("elige una lista"). NO hay fallback global (#6): un `CLICKUP_LIST_ID`
    compartido mandaría las tareas de una empresa a la lista de OTRA — jamás se manda a
    una lista ajena bajo ninguna circunstancia. La propuesta se lee SÓLO de la empresa
    del usuario (RLS); sin propuesta → 404. Si ClickUp cae → 502. Devuelve cuántas tareas
    se crearon. El token vive sólo en el backend (regla de oro #3).

    Body OPCIONAL `asignados` (0006): mapa nombre_de_tarea → persona asignada (el roster
    de `/miembros` que el usuario eligió en el selector de la pantalla de Tareas). Si una
    tarea está en el mapa, su persona viaja en la descripción de ClickUp; si no, cae a su
    `responsable` (comportamiento actual). El body es opcional: sin él, todo sigue igual."""
    lista_destino = lista_id
    if not lista_destino:
        raise HTTPException(
            status_code=400,
            detail="Elige una lista de ClickUp donde crear las tareas",
        )

    propuesta = await repo.obtener_por_solicitud(solicitud_id, empresa_id)
    if propuesta is None:
        raise HTTPException(status_code=404, detail="La solicitud no tiene propuesta")

    # Mapa de asignaciones que eligió el usuario (vacío si no vino body): nombre → persona.
    asignados = (entrada.asignados if entrada else None) or {}

    try:
        creadas = 0
        for tarea in propuesta.tareas:
            if asignados:
                # Con asignaciones: la persona elegida (o el responsable si no está en el
                # mapa) viaja rotulada como "Asignado:" en la descripción de la tarea.
                descripcion = (
                    f"{tarea.grupo or ''} · "
                    f"Asignado: {asignados.get(tarea.nombre) or tarea.responsable or ''} · "
                    f"{tarea.vencimiento or ''}"
                )
            else:
                # Sin body: comportamiento actual (grupo · responsable · vencimiento).
                descripcion = (
                    f"{tarea.grupo or ''} · {tarea.responsable or ''} · "
                    f"{tarea.vencimiento or ''}"
                )
            await clickup.crear_tarea(
                lista_destino, tarea.nombre, descripcion=descripcion
            )
            creadas += 1
    except Exception as exc:
        # ClickUp es un servicio externo: si cae, es un 502 (no un 500 crudo).
        raise HTTPException(
            status_code=502, detail="El servicio de ClickUp no está disponible"
        ) from exc

    # #7 · El envío a ClickUp es el "envío" real: cierra el ciclo de vida. La propuesta y
    # la solicitud avanzan a 'enviada'. Best-effort: si el store no tiene la fila (demo),
    # no rompe el resultado del envío, que ya se concretó en ClickUp.
    try:
        await repo.actualizar_estado(propuesta.id, empresa_id, "enviada")
    except KeyError:
        pass
    try:
        await repo_sol.actualizar_estado(solicitud_id, empresa_id, "enviada")
    except KeyError:
        pass

    return ResultadoEnvioClickUp(creadas=creadas)
