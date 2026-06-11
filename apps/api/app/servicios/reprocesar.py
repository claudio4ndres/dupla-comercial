"""Re-procesa solicitudes 'sin_clasificar': re-baja el correo (con el parser actual,
que incluye el fallback a HTML) y lo re-clasifica EN SITIO.

Sirve para correos que entraron ANTES del fix de clasificación (sin descripción), o
para un sync donde Haiku se cayó. Es idempotente y seguro de re-correr: sólo toca las
'sin_clasificar'; las que sigan sin poder clasificarse quedan igual para otro intento.

Cero red en tests: el cliente Gmail y el clasificador se inyectan (dobles).
"""
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel

from app.esquemas import ResultadoClasificacion
from app.repositorios.integraciones import Integracion, RepositorioIntegraciones
from app.repositorios.solicitudes import RepositorioSolicitudes
from app.servicios.gmail import ClienteGmail, ErrorAutenticacionGmail

_LOG = logging.getLogger(__name__)

# Mismo contrato que la ingesta: recibe el texto a clasificar y devuelve resumen+tipo.
Clasificador = Callable[[str], Awaitable[ResultadoClasificacion]]


class ResultadoReproceso(BaseModel):
    """Resumen de re-procesar una casilla: cuántas se revisaron y cuántas quedaron
    clasificadas."""

    empresa_id: UUID
    revisadas: int
    reclasificadas: int


async def reprocesar_sin_clasificar(
    integracion: Integracion,
    gmail: ClienteGmail,
    repo_solicitudes: RepositorioSolicitudes,
    repo_integraciones: RepositorioIntegraciones,
    clasificar: Clasificador,
) -> ResultadoReproceso:
    """Re-baja y re-clasifica las solicitudes 'sin_clasificar' de UNA empresa.

    Por cada una: re-baja el correo por su `gmail_msg_id` (recupera el cuerpo, incluso
    de correos solo-HTML que entraron vacíos), clasifica `asunto + cuerpo` y actualiza
    en sitio. Si el refresh del token falla, marca 'reconectar' y corta esta casilla
    (CA7). Si una clasificación puntual falla (LLM caído/correo vacío), la deja
    pendiente y sigue con las demás.
    """
    pendientes = await repo_solicitudes.listar_sin_clasificar(integracion.empresa_id)
    reclasificadas = 0
    for sol in pendientes:
        if not sol.gmail_msg_id:
            continue  # sin id de Gmail no hay cómo re-bajar
        try:
            mensaje = await gmail.obtener_mensaje(sol.gmail_msg_id)
        except ErrorAutenticacionGmail:
            await repo_integraciones.marcar_estado(integracion.empresa_id, "reconectar")
            break
        if mensaje is None:
            continue  # el correo ya no existe en Gmail
        # Clasificamos asunto + cuerpo: así un correo con cuerpo vacío igual se
        # clasifica por su asunto (que suele ser informativo).
        texto = f"{mensaje.asunto}\n\n{mensaje.cuerpo}".strip()
        try:
            clasif = await clasificar(texto)
        except Exception as exc:  # noqa: BLE001 — el LLM no debe tumbar el reproceso
            _LOG.warning(
                "Reproceso: no se pudo clasificar %s (%s); sigue pendiente.",
                sol.gmail_msg_id,
                type(exc).__name__,
            )
            continue
        await repo_solicitudes.actualizar_reproceso(
            sol.id,
            integracion.empresa_id,
            cuerpo=mensaje.cuerpo,
            resumen=clasif.resumen,
            tipo=clasif.tipo,
        )
        reclasificadas += 1
    return ResultadoReproceso(
        empresa_id=integracion.empresa_id,
        revisadas=len(pendientes),
        reclasificadas=reclasificadas,
    )
