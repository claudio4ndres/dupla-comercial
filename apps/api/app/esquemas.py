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


# Conversación con Javo (003) ------------------------------------------------
# El front usa `t1`/`t2` (tipo confirmado en pantalla), distinto del `tipo_1`/
# `tipo_2` que persiste el clasificador. Se mantienen separados a propósito.
TipoConversacion = Literal["t1", "t2"]


class MensajeConversacion(BaseModel):
    """Un turno del chat tal como lo envía el front: `rol` es `usuario`, `javo` o
    `sistema`; el servicio lo normaliza al formato `user`/`assistant` de Anthropic."""

    rol: str
    contenido: str


class EntradaConversacion(BaseModel):
    """Cuerpo de `POST /conversaciones/responder`: el tipo confirmado y el historial.

    `solicitud_id` viaja para trazabilidad/futuro (persistencia), pero el endpoint
    es sin estado: hoy no lee ni escribe datos de empresa.
    """

    tipo: TipoConversacion
    mensajes: list[MensajeConversacion]
    solicitud_id: str | None = None


class RespuestaConversacion(BaseModel):
    """Respuesta del endpoint: el texto que Javo le muestra al usuario."""

    texto: str
