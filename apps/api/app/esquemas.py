"""Esquemas Pydantic compartidos por la API."""
from typing import Literal

from pydantic import BaseModel

TipoSolicitud = Literal["tipo_1", "tipo_2"]


class ResultadoClasificacion(BaseModel):
    """Resultado de clasificar y resumir una solicitud."""

    resumen: str
    tipo: TipoSolicitud


class EstadoCorreo(BaseModel):
    """Estado de la conexión de correo de una empresa, tal como lo consume el front.

    Es deliberadamente plano y NUNCA incluye `token_ref` ni ningún token (CA5):
    al usarlo como `response_model`, FastAPI descarta cualquier otro campo.
    """

    proveedor: str | None = None
    estado: str | None = None
    casilla: str | None = None


class UrlConsentimiento(BaseModel):
    """URL de consentimiento OAuth a la que el front redirige al usuario (T7)."""

    url: str


class ResumenPoller(BaseModel):
    """Resumen de una corrida del poller interno (cuántas casillas y solicitudes)."""

    empresas_procesadas: int
    solicitudes_creadas: int
