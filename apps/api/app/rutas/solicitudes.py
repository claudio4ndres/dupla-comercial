"""Rutas de solicitudes."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.dependencias import (
    obtener_cliente_anthropic,
    obtener_empresa_actual,
    obtener_repositorio_solicitudes,
)
from app.esquemas import ResultadoClasificacion
from app.servicios.clasificador import clasificar_solicitud

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])

_TIPOS_VALIDOS = ("tipo_1", "tipo_2")


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
