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
    # Fecha/hora de recepción del correo (ISO 8601), tomada de `creado_en`. El front
    # la formatea para la tarjeta de la bandeja; null si la fila no la trae.
    recibido_en: str | None = None


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

    Si viene `solicitud_id` (UUID real), el endpoint PERSISTE el turno nuevo del
    usuario + la respuesta de Javo en el hilo de esa solicitud (T13). Si falta o no es
    un UUID (p.ej. el `demo-1` de la demo sin estado), responde igual pero no persiste.
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
    dias: int | None = None  # tarifa POR DÍA × días (si aplica); si no, 1 día
    valor_unitario: float | None = None
    proveedor: str | None = None  # proveedor del catálogo del Drive
    origen: str | None = None  # recurso del Drive de donde salió el valor


class Fuente(BaseModel):
    """Origen citable de un dato que usó Javo: recurso del Drive o resultado web (CA6)."""

    titulo: str
    referencia: str


class TareaPropuesta(BaseModel):
    """Una tarea de EJECUCIÓN que Javo propone en el chat (la decide con criterio de
    comercial senior). El gestor la confirma; al generar la propuesta se persiste."""

    nombre: str
    area: str  # RRHH, Producción, Compras, Diseño, Logística, Comercial, Coordinación…
    plazo: str | None = None
    responsable: str | None = None


class RespuestaConversacion(BaseModel):
    """Respuesta del endpoint: el texto de Javo + lo que propuso/citó en este turno.

    `componentes`, `tareas` y `fuentes` van vacíos salvo que Javo haya propuesto
    componentes/tareas o citado fuentes (Drive/internet) durante la conversación.
    """

    texto: str
    componentes: list[ComponentePropuesto] = []
    tareas: list[TareaPropuesta] = []
    fuentes: list[Fuente] = []


class CrearPropuestaEntrada(BaseModel):
    """Cuerpo del POST que persiste la propuesta que Javo armó en el chat: sus
    componentes valorizados + las tareas de ejecución que propuso."""

    tipo: str = "t1"
    componentes: list[ComponentePropuesto] = []
    tareas: list[TareaPropuesta] = []


# Propuesta / cotización (004) -----------------------------------------------
# Forma plana que consume el front (GET /solicitudes/{id}/propuesta). NUNCA trae
# `empresa_id` ni `solicitud_id`: al construirla explícitamente, lo interno queda
# fuera (CA5). El front mapea valor_unitario→valor, grupo→área, vencimiento→plazo.
class ComponentePropuestaSalida(BaseModel):
    nombre: str
    detalle: str | None = None
    proveedor: str | None = None
    cantidad: int = 1
    dias: int = 1
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


# Lista de propuestas que consume la sección "Propuestas" del front (GET /propuestas).
# Forma plana: cabecera de la propuesta + `asunto`/`remitente` de la solicitud ligada.
# NUNCA trae `empresa_id` (CA5): al construirla explícitamente, lo interno queda fuera.
class PropuestaListada(BaseModel):
    id: str
    solicitud_id: str
    total: float = 0
    estado: str = "borrador"
    asunto: str = ""
    remitente: str = ""


# Lista de tareas que consume la sección "Tareas" del front (GET /tareas). Forma plana
# en español; NUNCA trae `empresa_id` (CA5). El front mapea grupo→área, vencimiento→plazo.
class TareaListada(BaseModel):
    nombre: str
    grupo: str | None = None
    responsable: str | None = None
    vencimiento: str | None = None


# Una lista de ClickUp para el SELECTOR de destino del conector (GET /clickup/listas).
# Forma plana: id (para crear la tarea), nombre y espacio (para orientar al usuario).
class ListaClickUpSalida(BaseModel):
    id: str
    nombre: str
    espacio: str = ""


# Cuerpo OPCIONAL del POST .../tareas/clickup (0006): el mapa de asignaciones que el
# usuario eligió en la pantalla de Tareas (nombre_de_tarea → persona asignada). Si no
# trae el nombre de una tarea, ésta cae a su `responsable` (comportamiento actual).
class EnvioClickUpEntrada(BaseModel):
    asignados: dict[str, str] | None = None


# Resultado de enviar las tareas de la propuesta a ClickUp (POST .../tareas/clickup):
# cuántas tareas se crearon en la lista elegida.
class ResultadoEnvioClickUp(BaseModel):
    creadas: int


# Un miembro del roster del equipo para el selector "Asignado a" (GET /miembros, 0006).
# Forma plana en español; NUNCA trae `empresa_id` (CA5). El front pre-selecciona el
# miembro cuyo `rol` calce con el área de la tarea.
class MiembroListado(BaseModel):
    id: str
    nombre: str
    rol: str
