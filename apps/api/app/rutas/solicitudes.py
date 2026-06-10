"""Rutas de solicitudes."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.dependencias import (
    obtener_cliente_anthropic,
    obtener_empresa_actual,
    obtener_repositorio_propuestas,
    obtener_repositorio_solicitudes,
)
from app.esquemas import (
    ComponentePropuestaSalida,
    PropuestaDetalle,
    ResultadoClasificacion,
    SolicitudListada,
    TareaPropuestaSalida,
)
from app.servicios.clasificador import clasificar_solicitud
from app.servicios.exportador_excel import (
    LineaCotizacion,
    generar_excel_cotizacion,
)

# Media-type oficial de un .xlsx (OOXML).
_MEDIA_XLSX = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])

_TIPOS_VALIDOS = ("tipo_1", "tipo_2")


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


@router.get("/{solicitud_id}/cotizacion.xlsx")
async def descargar_cotizacion_excel(
    solicitud_id: UUID,
    margen: float = 0.40,
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
