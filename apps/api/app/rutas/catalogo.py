"""Rutas del catálogo del Drive de la empresa.

`GET /catalogo/recursos` alimenta el panel "Recursos · Drive" del chat. Sólo de la
empresa del usuario (aislamiento multi-tenant por RLS; la empresa sale del JWT).

Origen de los datos (Drive real v1):
* si la empresa tiene una integración Gmail/Google conectada, lista los NOMBRES
  REALES de los archivos de su carpeta del Drive (vía `ClienteDriveReal`, que refresca
  el token de la empresa — regla de oro #3, el secreto sólo en el backend);
* si no hay integración/token, o el Drive falla, cae al catálogo SEMBRADO (los
  `origen` de la tabla `catalogo`). El panel nunca se rompe por un fallo del Drive.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends

from app.config import obtener_settings
from app.dependencias import (
    obtener_empresa_actual,
    obtener_fabrica_cliente_drive,
    obtener_repositorio_catalogo,
    obtener_repositorio_integraciones,
)

router = APIRouter(prefix="/catalogo", tags=["catalogo"])

logger = logging.getLogger(__name__)


@router.get("/recursos", response_model=list[str])
async def listar_recursos(
    repo=Depends(obtener_repositorio_catalogo),
    integraciones=Depends(obtener_repositorio_integraciones),
    fabrica_drive=Depends(obtener_fabrica_cliente_drive),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> list[str]:
    """Recursos del Drive de la empresa: nombres REALES si hay Drive conectado, o el
    catálogo sembrado como respaldo."""
    integracion = await integraciones.obtener_por_empresa(empresa_id)
    if integracion is not None and integracion.token_ref:
        try:
            cliente = fabrica_drive.crear(integracion)
            archivos = await cliente.listar_archivos(
                obtener_settings().drive_folder_id
            )
            # El Drive respondió (aunque sea vacío): es la fuente de verdad.
            return [a.nombre for a in archivos]
        except Exception:
            # Token revocado/expirado, carpeta inaccesible, red caída… No rompemos el
            # panel: caemos al catálogo sembrado.
            logger.warning(
                "Drive no disponible para la empresa %s; uso el catálogo sembrado",
                empresa_id,
                exc_info=True,
            )
    return await repo.recursos(empresa_id)
