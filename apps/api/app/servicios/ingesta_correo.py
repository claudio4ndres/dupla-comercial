"""Servicio de ingesta de correo: convierte los correos nuevos de UNA empresa en
`solicitudes`.

Trabaja contra interfaces (`ClienteGmail`, repositorios) que en los tests son dobles
en memoria (CA6: cero llamadas reales). Es el corazón del polling: el endpoint
interno lo invoca una vez por integración conectada.

IMPORTANTE (multi-tenant): la `empresa_id` se toma SIEMPRE de la integración y se
fija explícita en cada solicitud. El poller corre con `service role` (sin JWT → la
RLS no aplica), así que nunca debe inferir la empresa del ambiente.
"""
from uuid import UUID

from pydantic import BaseModel

from app.repositorios.integraciones import Integracion, RepositorioIntegraciones
from app.repositorios.solicitudes import RepositorioSolicitudes
from app.servicios.gmail import ClienteGmail, ErrorAutenticacionGmail


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
) -> ResultadoIngesta:
    """Lee los correos nuevos desde el `cursor` de la integración, crea una
    `solicitud` por cada correo nuevo (idempotente) y avanza el cursor.

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
        if await repo_solicitudes.crear_desde_correo(integracion.empresa_id, mensaje):
            creadas += 1

    await repo_integraciones.actualizar_cursor(integracion.empresa_id, nuevo_cursor)
    return ResultadoIngesta(
        empresa_id=integracion.empresa_id, creadas=creadas, estado="conectado"
    )
