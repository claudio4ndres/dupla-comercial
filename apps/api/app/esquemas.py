"""Esquemas Pydantic compartidos por la API."""
from typing import Literal

from pydantic import BaseModel

TipoSolicitud = Literal["tipo_1", "tipo_2"]


class ResultadoClasificacion(BaseModel):
    """Resultado de clasificar y resumir una solicitud."""

    resumen: str
    tipo: TipoSolicitud


class SolicitudListada(BaseModel):
    """Una solicitud tal como la lista la bandeja del front (GET /solicitudes).

    Forma plana y en español; el front mapea `tipo` (tipo_1/tipo_2/sin_clasificar)
    a sus códigos de UI (t1/t2/new). NUNCA incluye `empresa_id` ni `token_ref`: al
    construirla explícitamente, los campos internos quedan fuera (CA5).
    """

    id: str
    remitente: str = ""
    correo_origen: str | None = None
    asunto: str = ""
    cuerpo: str = ""
    resumen: str | None = None
    tipo: str = "sin_clasificar"
    estado: str = "nueva"


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


class ComponentePropuesto(BaseModel):
    """Un componente que Javo propone en el chat (005). NO se persiste aquí: el GP lo
    confirma y, al generar la propuesta, lo toma la spec 004 (CA10)."""

    nombre: str
    detalle: str | None = None
    cantidad: int = 1
    valor_unitario: float | None = None
    origen: str | None = None  # recurso del Drive de donde salió el valor


class Fuente(BaseModel):
    """Origen citable de un dato que usó Javo: recurso del Drive o resultado web (CA6)."""

    titulo: str
    referencia: str


class RespuestaConversacion(BaseModel):
    """Respuesta del endpoint: el texto de Javo + lo que propuso/citó en este turno.

    `componentes` y `fuentes` van vacíos salvo que Javo haya propuesto componentes o
    citado fuentes (Drive/internet) durante la conversación.
    """

    texto: str
    componentes: list[ComponentePropuesto] = []
    fuentes: list[Fuente] = []


# Propuesta / cotización (004) -----------------------------------------------
# Forma plana que consume el front (GET /solicitudes/{id}/propuesta). NUNCA trae
# `empresa_id` ni `solicitud_id`: al construirla explícitamente, lo interno queda
# fuera (CA5). El front mapea valor_unitario→valor, grupo→área, vencimiento→plazo.
class ComponentePropuestaSalida(BaseModel):
    nombre: str
    detalle: str | None = None
    cantidad: int = 1
    valor_unitario: float = 0


class TareaPropuestaSalida(BaseModel):
    nombre: str
    grupo: str | None = None
    responsable: str | None = None
    vencimiento: str | None = None


class PropuestaDetalle(BaseModel):
    """La cotización resuelta de una solicitud: componentes valorizados + tareas."""

    id: str
    total: float = 0
    estado: str = "borrador"
    componentes: list[ComponentePropuestaSalida] = []
    tareas: list[TareaPropuestaSalida] = []
