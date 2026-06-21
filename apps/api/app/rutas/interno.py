"""Rutas internas (service-to-service), NO expuestas al front.

El poller las dispara Cloud Scheduler (TR4). Recorre las integraciones `gmail` y, por
cada empresa, ingiere sus correos nuevos. Corre con `service role` (sin JWT → la RLS
no aplica), así que la `empresa_id` se fija SIEMPRE desde cada integración: jamás se
infiere del ambiente y jamás se cruzan tenants (T11).
"""
import asyncio
import logging
import secrets as _secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from app.dependencias import (
    obtener_cliente_anthropic,
    obtener_fabrica_cliente_drive,
    obtener_fabrica_cliente_gmail,
    obtener_repositorio_integraciones_servicio,
    obtener_repositorio_solicitudes_servicio,
    obtener_secreto_poller,
)
from app.esquemas import (
    CarpetaDrive,
    ConectorReconectar,
    DiagnosticoDrive,
    ResumenPoller,
    ResumenReproceso,
)
from app.servicios.clasificador import clasificar_solicitud
from app.servicios.gmail import ErrorAutenticacionGmail
from app.servicios.ingesta_correo import ingerir_correos_nuevos
from app.servicios.observabilidad import avisar_reconectar
from app.servicios.reprocesar import reprocesar_correos

router = APIRouter(prefix="/interno", tags=["interno"])

_LOG = logging.getLogger(__name__)


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


@router.get("/conectores/reconectar", response_model=list[ConectorReconectar])
async def conectores_reconectar(
    repo_integraciones=Depends(obtener_repositorio_integraciones_servicio),
    _=Depends(verificar_credencial_servicio),
) -> list[ConectorReconectar]:
    """Observabilidad del operador (CA3): lista las integraciones en 'reconectar' para
    que ninguna empresa quede días caída sin que nadie se entere.

    Es un canal de OPERADOR (service-role, protegido por la credencial de servicio), así
    que cruza empresas a propósito; pero devuelve SÓLO `(empresa_id, proveedor, estado)`
    vía el `response_model` → JAMÁS expone `token_ref` ni datos de negocio (regla de oro
    #3, CA7). Sin la credencial → 403."""
    integraciones = await repo_integraciones.listar_por_estado("reconectar")
    return [
        ConectorReconectar(
            empresa_id=str(i.empresa_id),
            proveedor=i.proveedor,
            estado=i.estado,
        )
        for i in integraciones
    ]


@router.post("/poller/correo", response_model=ResumenPoller)
async def poller_correo(
    repo_integraciones=Depends(obtener_repositorio_integraciones_servicio),
    repo_solicitudes=Depends(obtener_repositorio_solicitudes_servicio),
    fabrica_gmail=Depends(obtener_fabrica_cliente_gmail),
    cliente_anthropic=Depends(obtener_cliente_anthropic),
    _=Depends(verificar_credencial_servicio),
) -> ResumenPoller:
    """Recorre las casillas `gmail` conectadas e ingiere los correos nuevos de cada
    una, clasificándolos con Haiku (resumen + tipo) para que la bandeja muestre una
    descripción real. El fallo de una empresa (token expirado) no corta a las demás:
    el servicio de ingesta lo absorbe y la marca 'reconectar' (CA7)."""

    async def clasificar(cuerpo: str):
        return await clasificar_solicitud(cuerpo, cliente_anthropic)

    integraciones = await repo_integraciones.listar_por_proveedor("gmail")

    # Semáforo para limitar la concurrencia del poller (rate-limit Anthropic + Gmail).
    semaforo = asyncio.Semaphore(5)

    async def procesar(integracion):
        """Procesa una integración dentro del semáforo. Aísla fallos por empresa."""
        async with semaforo:
            # Defensa en profundidad multi-tenant: una empresa que falle NO debe tumbar
            # el poll de las demás. PERO el estado 'reconectar' es SÓLO para fallos de
            # AUTH (token expirado/revocado): marcarlo por un 409 de BD u otro error de
            # infraestructura es incorrecto y le pide al usuario reconectar tokens sanos.
            try:
                gmail = fabrica_gmail.crear(integracion)
                resultado = await ingerir_correos_nuevos(
                    integracion,
                    gmail,
                    repo_solicitudes,
                    repo_integraciones,
                    clasificar=clasificar,
                )
                return resultado.creadas
            except ErrorAutenticacionGmail:
                # Credenciales rotas: el usuario debe reconectar.
                _LOG.warning(
                    "Poller: la empresa %s tiene la sesión de Gmail caída; "
                    "se marca 'reconectar' y se sigue.",
                    integracion.empresa_id,
                )
                # Sólo la fila gmail (#5): no tocar la integración clickup de la empresa.
                await repo_integraciones.marcar_estado(
                    integracion.empresa_id, "reconectar", "gmail"
                )
                # CA5 (Spec 010): señal para el operador. Best-effort — la envolvemos
                # para que un fallo de la alerta JAMÁS tumbe el poll de las demás empresas.
                try:
                    avisar_reconectar(integracion.empresa_id, "gmail", "auth_invalida")
                except Exception:  # noqa: BLE001 — la alerta no puede cortar el poller
                    _LOG.exception("Poller: falló avisar_reconectar; se sigue igual.")
                return 0
            except Exception:  # noqa: BLE001 — aislar el fallo de una empresa
                # Error NO-auth (409 de BD, Secret Manager, red…): se aísla y se sigue,
                # SIN tocar el estado de la integración (sus credenciales están sanas).
                _LOG.exception(
                    "Poller: la empresa %s falló por un error NO-auth; se aísla y se "
                    "sigue SIN marcar 'reconectar' (las credenciales están sanas).",
                    integracion.empresa_id,
                )
                return 0

    resultados = await asyncio.gather(*[procesar(i) for i in integraciones])
    empresas_procesadas = len(integraciones)
    solicitudes_creadas = sum(resultados)

    return ResumenPoller(
        empresas_procesadas=empresas_procesadas,
        solicitudes_creadas=solicitudes_creadas,
    )


@router.post("/reprocesar/correo", response_model=ResumenReproceso)
async def reprocesar_correo(
    repo_integraciones=Depends(obtener_repositorio_integraciones_servicio),
    repo_solicitudes=Depends(obtener_repositorio_solicitudes_servicio),
    fabrica_gmail=Depends(obtener_fabrica_cliente_gmail),
    cliente_anthropic=Depends(obtener_cliente_anthropic),
    _=Depends(verificar_credencial_servicio),
) -> ResumenReproceso:
    """Re-baja y re-clasifica las solicitudes 'sin_clasificar' de todas las casillas
    gmail conectadas. Sirve para correos ingeridos ANTES del fix de clasificación (sin
    descripción) o donde Haiku se cayó. Idempotente y re-corrible; aísla por empresa."""

    async def clasificar(cuerpo: str):
        return await clasificar_solicitud(cuerpo, cliente_anthropic)

    integraciones = await repo_integraciones.listar_por_proveedor("gmail")
    revisadas = 0
    reclasificadas = 0
    for integracion in integraciones:
        try:
            gmail = fabrica_gmail.crear(integracion)
            res = await reprocesar_correos(
                integracion,
                gmail,
                repo_solicitudes,
                repo_integraciones,
                clasificar,
            )
            revisadas += res.revisadas
            reclasificadas += res.reclasificadas
        except ErrorAutenticacionGmail:
            _LOG.warning(
                "Reproceso: la empresa %s tiene la sesión de Gmail caída; se marca 'reconectar'.",
                integracion.empresa_id,
            )
            await repo_integraciones.marcar_estado(
                integracion.empresa_id, "reconectar", "gmail"
            )
        except Exception:  # noqa: BLE001 — aislar el fallo de una empresa
            _LOG.exception(
                "Reproceso: la empresa %s falló por un error NO-auth; se aísla SIN marcar 'reconectar' (credenciales sanas).",
                integracion.empresa_id,
            )
    return ResumenReproceso(revisadas=revisadas, reclasificadas=reclasificadas)


@router.post("/drive/diagnostico", response_model=DiagnosticoDrive)
async def diagnostico_drive(
    empresa_id: UUID,
    repo_integraciones=Depends(obtener_repositorio_integraciones_servicio),
    fabrica_drive=Depends(obtener_fabrica_cliente_drive),
    _=Depends(verificar_credencial_servicio),
) -> DiagnosticoDrive:
    """Diagnóstico READ-ONLY: ¿el token de Google de `empresa_id` tiene acceso a Drive?

    No escribe nada: sólo lista las CARPETAS del Drive de la empresa (el scope/refresh
    cuelgan del OAuth de gmail). Sirve para depurar la conexión Drive por empresa antes
    de configurar su carpeta:

    * sin integración gmail conectada (o sin `token_ref`) → `acceso=False` con motivo;
    * si lista bien → `acceso=True` + las carpetas (id/nombre) para configurar la de la
      empresa;
    * si el cliente revienta (p.ej. un 403 de scope, refresh revocado, red caída) → se
      atrapa y se reporta el TIPO de error en `motivo`, para distinguir un problema de
      permisos de otros fallos. Nunca tumba al llamador (no propaga 500)."""
    integracion = await repo_integraciones.obtener_por_empresa_y_proveedor(
        empresa_id, "gmail"
    )
    if integracion is None or not integracion.token_ref:
        return DiagnosticoDrive(
            acceso=False,
            motivo="sin integración gmail conectada",
            carpetas=[],
        )
    try:
        cliente = fabrica_drive.crear(integracion)
        carpetas = await cliente.listar_carpetas()
        return DiagnosticoDrive(
            acceso=True,
            motivo=None,
            carpetas=[CarpetaDrive(id=c.id, nombre=c.nombre) for c in carpetas],
        )
    except Exception as exc:  # noqa: BLE001 — diagnóstico: reporta el fallo, no lo propaga
        return DiagnosticoDrive(
            acceso=False,
            motivo=f"{type(exc).__name__}: {str(exc)[:200]}",
            carpetas=[],
        )
