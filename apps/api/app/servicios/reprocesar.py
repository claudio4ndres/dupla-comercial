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


async def reprocesar_correos(
    integracion: Integracion,
    gmail: ClienteGmail,
    repo_solicitudes: RepositorioSolicitudes,
    repo_integraciones: RepositorioIntegraciones,
    clasificar: Clasificador,
) -> ResultadoReproceso:
    """Re-baja TODOS los correos de UNA empresa y los pone al día EN SITIO.

    Por cada solicitud: re-baja el correo por su `gmail_msg_id` y actualiza
      - la **fecha real** de recepción (`creado_en`) → la bandeja se ordena bien,
      - el **cuerpo** (recupera texto de correos solo-HTML que entraron vacíos),
      - y, **sólo si estaba 'sin_clasificar'**, la clasificación (resumen + tipo).

    Conserva la clasificación de las que ya estaban resueltas (no re-clasifica de
    más). Si el refresh del token falla, marca 'reconectar' y corta (CA7). Si una
    clasificación puntual falla, deja esa pendiente y sigue. Idempotente y re-corrible.
    """
    todas = await repo_solicitudes.listar(integracion.empresa_id)
    reclasificadas = 0
    for sol in todas:
        if not sol.gmail_msg_id:
            continue  # sin id de Gmail no hay cómo re-bajar
        try:
            mensaje = await gmail.obtener_mensaje(sol.gmail_msg_id)
        except ErrorAutenticacionGmail:
            # Sólo la fila gmail (#5): no arrastrar la integración clickup de la empresa.
            await repo_integraciones.marcar_estado(
                integracion.empresa_id, "reconectar", "gmail"
            )
            break
        if mensaje is None:
            continue  # el correo ya no existe en Gmail
        resumen, tipo = sol.resumen, sol.tipo  # conservamos lo ya clasificado
        if sol.tipo == "sin_clasificar":
            # asunto + cuerpo: un correo con cuerpo vacío igual se clasifica por asunto.
            texto = f"{mensaje.asunto}\n\n{mensaje.cuerpo}".strip()
            try:
                clasif = await clasificar(texto)
                resumen, tipo = clasif.resumen, clasif.tipo
                reclasificadas += 1
            except Exception as exc:  # noqa: BLE001 — el LLM no debe tumbar el reproceso
                _LOG.warning(
                    "Reproceso: no se pudo clasificar %s (%s); sigue pendiente.",
                    sol.gmail_msg_id,
                    type(exc).__name__,
                )
        # Actualizamos SIEMPRE la fecha real + el cuerpo re-bajado (aunque no se
        # re-clasifique): es lo que ordena la bandeja por recencia.
        await repo_solicitudes.actualizar_reproceso(
            sol.id,
            integracion.empresa_id,
            cuerpo=mensaje.cuerpo,
            resumen=resumen,
            tipo=tipo,
            creado_en=mensaje.fecha,
        )
    return ResultadoReproceso(
        empresa_id=integracion.empresa_id,
        revisadas=len(todas),
        reclasificadas=reclasificadas,
    )
