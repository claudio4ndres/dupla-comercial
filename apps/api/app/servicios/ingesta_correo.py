"""Servicio de ingesta de correo: convierte los correos nuevos de UNA empresa en
`solicitudes`.

Trabaja contra interfaces (`ClienteGmail`, repositorios) que en los tests son dobles
en memoria (CA6: cero llamadas reales). Es el corazón del polling: el endpoint
interno lo invoca una vez por integración conectada.

IMPORTANTE (multi-tenant): la `empresa_id` se toma SIEMPRE de la integración y se
fija explícita en cada solicitud. El poller corre con `service role` (sin JWT → la
RLS no aplica), así que nunca debe inferir la empresa del ambiente.
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

# Clasificador inyectable: recibe el cuerpo del correo y devuelve resumen + tipo.
# Se inyecta (el endpoint lo liga al cliente Anthropic real; los tests, a un doble)
# para no acoplar la ingesta al SDK ni a la red (CA6).
Clasificador = Callable[[str], Awaitable[ResultadoClasificacion]]


class ResultadoIngesta(BaseModel):
    """Resumen de ingerir una casilla: cuántas solicitudes nuevas y en qué estado
    quedó la conexión."""

    empresa_id: UUID
    creadas: int
    estado: str  # 'conectado' | 'reconectar'


async def ingerir_correos_nuevos(
    integracion: Integracion,
    gmail: ClienteGmail,
    repo_solicitudes: RepositorioSolicitudes,
    repo_integraciones: RepositorioIntegraciones,
    clasificar: Clasificador | None = None,
) -> ResultadoIngesta:
    """Lee los correos nuevos desde el `cursor` de la integración, crea una
    `solicitud` por cada correo nuevo (idempotente) y avanza el cursor.

    Si se pasa `clasificar`, cada correo se resume y clasifica (Haiku) ANTES de
    guardarlo, así la bandeja muestra una descripción real en vez de quedar vacía.
    La clasificación es resiliente: si el LLM falla, el correo igual se ingiere
    ('sin_clasificar', sin resumen) para no perder correos (CA7-bis).

    Si el refresh del token falla (expirado/revocado), marca la integración como
    'reconectar' y devuelve sin lanzar: así el poller sigue con las demás empresas
    (CA7) y la bandeja refleja el estado sin caerse.
    """
    try:
        mensajes, nuevo_cursor = await gmail.listar_nuevos(integracion.cursor)
    except ErrorAutenticacionGmail:
        await repo_integraciones.marcar_estado(integracion.empresa_id, "reconectar")
        return ResultadoIngesta(
            empresa_id=integracion.empresa_id, creadas=0, estado="reconectar"
        )

    creadas = 0
    for mensaje in mensajes:
        resumen: str | None = None
        tipo = "sin_clasificar"
        if clasificar is not None:
            try:
                clasificacion = await clasificar(mensaje.cuerpo)
                resumen, tipo = clasificacion.resumen, clasificacion.tipo
            except Exception as exc:  # noqa: BLE001 — el LLM no debe tumbar la ingesta
                # Loggeamos el TIPO de fallo (red/rate-limit/clave inválida vs. correo
                # inclasificable): antes esto era indiagnosticable (auditoría #6). El
                # correo igual se ingiere 'sin_clasificar' para no perderlo.
                _LOG.warning(
                    "Clasificación falló para %s (%s): %s; se ingiere sin resumen.",
                    mensaje.gmail_msg_id,
                    type(exc).__name__,
                    exc,
                )
                resumen, tipo = None, "sin_clasificar"
        if await repo_solicitudes.crear_desde_correo(
            integracion.empresa_id, mensaje, resumen=resumen, tipo=tipo
        ):
            creadas += 1

    await repo_integraciones.actualizar_cursor(integracion.empresa_id, nuevo_cursor)
    # Auto-heal: un poll exitoso PRUEBA que el token sirve. Si la integración venía de
    # una falsa alarma pasada ('reconectar' por el bug del 409/404 ya corregido), la
    # devolvemos a 'conectado' sola — sin pedir reconexión manual ni SQL.
    if integracion.estado != "conectado":
        _LOG.info(
            "Ingesta: empresa %s polló OK viniendo de '%s'; se restaura a 'conectado'.",
            integracion.empresa_id,
            integracion.estado,
        )
        await repo_integraciones.marcar_estado(integracion.empresa_id, "conectado")
    return ResultadoIngesta(
        empresa_id=integracion.empresa_id, creadas=creadas, estado="conectado"
    )
