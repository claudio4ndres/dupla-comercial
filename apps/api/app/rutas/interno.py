"""Rutas internas (service-to-service), NO expuestas al front.

El poller las dispara Cloud Scheduler (TR4). Recorre las integraciones `gmail` y, por
cada empresa, ingiere sus correos nuevos. Corre con `service role` (sin JWT → la RLS
no aplica), así que la `empresa_id` se fija SIEMPRE desde cada integración: jamás se
infiere del ambiente y jamás se cruzan tenants (T11).
"""
import secrets as _secrets

from fastapi import APIRouter, Depends, Header, HTTPException

from app.dependencias import (
    obtener_fabrica_cliente_gmail,
    obtener_repositorio_integraciones,
    obtener_repositorio_solicitudes,
    obtener_secreto_poller,
)
from app.esquemas import ResumenPoller
from app.servicios.ingesta_correo import ingerir_correos_nuevos

router = APIRouter(prefix="/interno", tags=["interno"])


def verificar_credencial_servicio(
    x_poller_token: str | None = Header(default=None),
    secreto_esperado: str = Depends(obtener_secreto_poller),
) -> None:
    """Sólo Cloud Scheduler / service-to-service (T12). Compara un secreto compartido
    en tiempo constante; sin credencial válida → 403. En real puede ser OIDC."""
    if x_poller_token is None or not _secrets.compare_digest(
        x_poller_token, secreto_esperado
    ):
        raise HTTPException(status_code=403, detail="credencial de servicio inválida")


@router.post("/poller/correo", response_model=ResumenPoller)
async def poller_correo(
    repo_integraciones=Depends(obtener_repositorio_integraciones),
    repo_solicitudes=Depends(obtener_repositorio_solicitudes),
    fabrica_gmail=Depends(obtener_fabrica_cliente_gmail),
    _=Depends(verificar_credencial_servicio),
) -> ResumenPoller:
    """Recorre las casillas `gmail` conectadas e ingiere los correos nuevos de cada
    una. El fallo de una empresa (token expirado) no corta a las demás: el servicio
    de ingesta lo absorbe y la marca 'reconectar' (CA7)."""
    integraciones = await repo_integraciones.listar_por_proveedor("gmail")
    empresas_procesadas = 0
    solicitudes_creadas = 0
    for integracion in integraciones:
        gmail = fabrica_gmail.crear(integracion)
        resultado = await ingerir_correos_nuevos(
            integracion, gmail, repo_solicitudes, repo_integraciones
        )
        empresas_procesadas += 1
        solicitudes_creadas += resultado.creadas
    return ResumenPoller(
        empresas_procesadas=empresas_procesadas,
        solicitudes_creadas=solicitudes_creadas,
    )
