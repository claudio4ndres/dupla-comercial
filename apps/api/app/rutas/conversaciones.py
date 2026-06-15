"""Rutas de conversación con Javo (003 + 005 + T13).

`POST /conversaciones/responder` es el corazón conversacional: recibe el tipo y el
historial, devuelve la respuesta de Javo (texto + componentes propuestos + fuentes)
generada con Sonnet en un loop de tool-use, y **persiste** el último turno del usuario
+ la respuesta de Javo (T13) para que el hilo sobreviva a un refresh. `GET
/conversaciones/{solicitud_id}` rehidrata ese hilo al abrir la solicitud.

**Requiere auth (005):** Javo consulta el **catálogo del Drive de la empresa** con la
RLS y la conversación se aísla por empresa, así que la empresa se resuelve del **JWT**
del usuario (`obtener_empresa_actual`). Sin token → 401. Si el LLM cae → 502 (el front
cae a su respuesta offline).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.dependencias import (
    obtener_cliente_anthropic,
    obtener_cliente_drive_conversacion,
    obtener_empresa_actual,
    obtener_proveedor_busqueda,
    obtener_repositorio_catalogo,
    obtener_repositorio_conversaciones,
)
from app.esquemas import (
    CotizacionBorrador,
    EntradaConversacion,
    MensajeConversacion,
    RespuestaConversacion,
)
from app.servicios.javo import responder_javo

router = APIRouter(prefix="/conversaciones", tags=["conversaciones"])


@router.get("/{solicitud_id}", response_model=list[MensajeConversacion])
async def historial(
    solicitud_id: UUID,
    repo=Depends(obtener_repositorio_conversaciones),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> list[MensajeConversacion]:
    """Hilo persistido del chat con Javo para esa solicitud (rehidratación, T13).

    Sólo el de la empresa del usuario (RLS). Sin conversación todavía → lista vacía
    (el front parte el chat desde cero). El `rol` va en el vocabulario del front
    (`usuario`/`javo`/`sistema`)."""
    mensajes = await repo.obtener_mensajes(solicitud_id, empresa_id)
    return [
        MensajeConversacion(rol=m.rol, contenido=m.contenido) for m in mensajes
    ]


@router.get("/{solicitud_id}/cotizacion", response_model=CotizacionBorrador)
async def cotizacion_en_curso(
    solicitud_id: UUID,
    repo=Depends(obtener_repositorio_conversaciones),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> CotizacionBorrador:
    """Borrador de la cotización EN CURSO del chat (0009): los componentes/tareas que
    Javo propuso y las fuentes que citó, persistidos junto a la conversación. El front
    lo usa para REPOBLAR el panel al rehidratar el hilo (antes el panel se perdía).

    Sólo el de la empresa del usuario (RLS). Sin borrador todavía → cotización vacía."""
    borrador = await repo.obtener_borrador(solicitud_id, empresa_id)
    if not borrador:
        return CotizacionBorrador()
    return CotizacionBorrador(**borrador)


@router.post("/responder", response_model=RespuestaConversacion)
async def responder(
    entrada: EntradaConversacion,
    cliente=Depends(obtener_cliente_anthropic),
    repo_catalogo=Depends(obtener_repositorio_catalogo),
    repo_conversaciones=Depends(obtener_repositorio_conversaciones),
    proveedor=Depends(obtener_proveedor_busqueda),
    cliente_drive=Depends(obtener_cliente_drive_conversacion),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> RespuestaConversacion:
    try:
        respuesta = await responder_javo(
            entrada.tipo,
            entrada.mensajes,
            cliente,
            repo_catalogo=repo_catalogo,
            proveedor_busqueda=proveedor,
            empresa_id=empresa_id,
            cliente_drive=cliente_drive,
        )
    except Exception as exc:
        # El LLM/herramientas son servicios externos: si caen, es un 502 (no un 500
        # crudo); el front ya cae a su respuesta offline al ver el error.
        raise HTTPException(
            status_code=502, detail="El servicio de conversación no está disponible"
        ) from exc

    # Persistencia (T13): sólo si el front mandó la solicitud a la que pertenece el
    # hilo. El front reenvía TODO el historial en cada turno, pero los turnos previos
    # ya quedaron persistidos por llamadas anteriores; aquí guardamos sólo lo NUEVO de
    # este turno: el último mensaje del usuario + la respuesta de Javo. Si no viene
    # `solicitud_id` (o no es un UUID real, p.ej. el "demo-1" de la demo sin estado),
    # el endpoint se comporta como antes (no persiste) y responde igual.
    solicitud = _solicitud_uuid(entrada.solicitud_id)
    if solicitud is not None:
        nuevos = []
        ultimo_usuario = next(
            (m for m in reversed(entrada.mensajes) if m.rol == "usuario"), None
        )
        if ultimo_usuario is not None:
            nuevos.append({"rol": "usuario", "contenido": ultimo_usuario.contenido})
        if respuesta.texto:
            nuevos.append({"rol": "javo", "contenido": respuesta.texto})
        if nuevos:
            await repo_conversaciones.guardar_turnos(
                solicitud, empresa_id, entrada.tipo, nuevos
            )

        # Persiste el BORRADOR de la cotización (0009): si Javo propuso componentes/
        # tareas o citó fuentes EN ESTE TURNO, guarda ese estado junto a la conversación
        # para que el panel sobreviva a un refresh / rehidratación. Si el turno fue solo
        # texto (no propuso nada), NO se pisa el borrador previo: la cotización en curso
        # se conserva (evita el bug de que el panel se vacíe al re-conversar).
        if respuesta.componentes or respuesta.tareas or respuesta.fuentes:
            await repo_conversaciones.guardar_borrador(
                solicitud,
                empresa_id,
                entrada.tipo,
                {
                    "componentes": [c.model_dump() for c in respuesta.componentes],
                    "tareas": [t.model_dump() for t in respuesta.tareas],
                    "fuentes": [f.model_dump() for f in respuesta.fuentes],
                },
            )

    return respuesta


def _solicitud_uuid(valor: str | None) -> UUID | None:
    """`solicitud_id` del body como UUID, o `None` si falta o no es un UUID válido
    (la demo manda ids tipo `demo-1`: en ese caso no se persiste)."""
    if not valor:
        return None
    try:
        return UUID(valor)
    except ValueError:
        return None
