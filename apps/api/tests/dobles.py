"""Dobles de prueba reutilizables (no tocan la red ni gastan tokens)."""
from types import SimpleNamespace

from app.servicios.gmail import ErrorAutenticacionGmail, MensajeCorreo
from app.servicios.oauth_clickup import CredencialesClickUp
from app.servicios.oauth_gmail import CredencialesGmail


class _BloqueToolUse:
    """Imita un bloque `tool_use` de una respuesta del SDK de Anthropic."""

    type = "tool_use"

    def __init__(self, datos: dict):
        self.name = "registrar_clasificacion"
        self.input = datos


class _RespuestaFake:
    def __init__(self, datos: dict):
        self.content = [_BloqueToolUse(datos)]


class _MensajesFake:
    def __init__(self, datos: dict, registro: list):
        self._datos = datos
        self._registro = registro

    async def create(self, **kwargs):
        self._registro.append(kwargs)
        return _RespuestaFake(self._datos)


class ClienteAnthropicFake:
    """Doble del cliente AsyncAnthropic: devuelve un payload fijo y registra
    las llamadas para poder verificar que NO se gastó el LLM cuando no toca."""

    def __init__(self, datos: dict):
        self.llamadas: list = []
        self.messages = _MensajesFake(datos, self.llamadas)


class _BloqueTexto:
    """Imita un bloque `text` de una respuesta del SDK de Anthropic."""

    type = "text"

    def __init__(self, texto: str):
        self.text = texto


class _RespuestaTextoFake:
    def __init__(self, texto: str):
        self.content = [_BloqueTexto(texto)]


class _MensajesTextoFake:
    def __init__(self, texto: str, registro: list):
        self._texto = texto
        self._registro = registro

    async def create(self, **kwargs):
        self._registro.append(kwargs)
        return _RespuestaTextoFake(self._texto)


class ClienteAnthropicTextoFake:
    """Doble del cliente AsyncAnthropic para conversación: devuelve un texto fijo
    (bloque `text`) y registra las llamadas para verificar modelo/mensajes/system."""

    def __init__(self, texto: str = "Respuesta de Javo (demo)."):
        self.llamadas: list = []
        self.messages = _MensajesTextoFake(texto, self.llamadas)


class _MensajesQueFalla:
    def __init__(self, excepcion: Exception):
        self._excepcion = excepcion

    async def create(self, **kwargs):
        raise self._excepcion


class ClienteAnthropicQueFalla:
    """Doble del cliente AsyncAnthropic que simula una caída del SDK/servicio
    (timeout, 5xx de la API, etc.) lanzando una excepción al llamar al LLM."""

    def __init__(self, excepcion: Exception | None = None):
        self.messages = _MensajesQueFalla(
            excepcion or RuntimeError("fallo simulado del SDK de Anthropic")
        )


# ── Doble "guion" para el loop de tool-use de Javo (005) ─────────────────────
# Reproduce una SECUENCIA de respuestas: cada llamada a `messages.create` consume
# la siguiente. Mapea cada respuesta a objetos con `.content` (bloques con `.type`,
# `.id`, `.name`, `.input`, `.text`) y `.stop_reason`, igual que el cliente real.
def respuesta_texto(texto: str) -> dict:
    """Respuesta `end_turn` con un único bloque de texto."""
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": texto}]}


def respuesta_tool_use(nombre: str, entrada: dict, id: str = "t1") -> dict:
    """Respuesta `tool_use` con un único bloque de herramienta."""
    return {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": id, "name": nombre, "input": entrada}],
    }


class _MensajesGuion:
    def __init__(self, guion: list[dict], registro: list):
        self._guion = guion
        self._registro = registro

    async def create(self, **kwargs):
        self._registro.append(kwargs)
        datos = self._guion.pop(0)
        bloques = [SimpleNamespace(**bloque) for bloque in datos.get("content", [])]
        return SimpleNamespace(**{**datos, "content": bloques})


class ClienteAnthropicGuionFake:
    """Doble del cliente Anthropic que reproduce un GUION de respuestas (para el loop
    de tool-use). Registra los payloads en `llamadas` para verificar tools/mensajes."""

    def __init__(self, guion: list[dict]):
        self.llamadas: list = []
        self.messages = _MensajesGuion(list(guion), self.llamadas)


class ClienteGmailFake:
    """Doble del cliente de Gmail: devuelve una lista fija de mensajes y un cursor
    nuevo, y registra con qué cursor se le llamó (para verificar el avance). Cero
    red, cero credenciales reales (CA6)."""

    def __init__(
        self, mensajes: list[MensajeCorreo], nuevo_cursor: str | None = None
    ):
        self._mensajes = list(mensajes)
        self._nuevo_cursor = nuevo_cursor
        self.llamadas: list = []

    async def listar_nuevos(
        self, cursor: str | None
    ) -> tuple[list[MensajeCorreo], str | None]:
        self.llamadas.append(cursor)
        return list(self._mensajes), self._nuevo_cursor

    async def obtener_mensaje(self, gmail_msg_id: str) -> MensajeCorreo | None:
        # Re-baja un mensaje por id: si está en la lista lo devuelve; si no, uno con
        # cuerpo "recuperado" (simula el re-fetch con el fallback a HTML).
        for m in self._mensajes:
            if m.gmail_msg_id == gmail_msg_id:
                return m
        return MensajeCorreo(
            gmail_msg_id=gmail_msg_id,
            asunto="Correo re-bajado",
            cuerpo="Cuerpo recuperado del HTML al re-procesar.",
        )


class ClienteGmailQueFallaAuth:
    """Doble que simula un refresh token expirado/revocado: al leer lanza
    `ErrorAutenticacionGmail` (CA7). Igual registra la llamada."""

    def __init__(self):
        self.llamadas: list = []

    async def listar_nuevos(self, cursor: str | None):
        self.llamadas.append(cursor)
        raise ErrorAutenticacionGmail("refresh token expirado/revocado (simulado)")

    async def obtener_mensaje(self, gmail_msg_id: str):
        self.llamadas.append(gmail_msg_id)
        raise ErrorAutenticacionGmail("refresh token expirado/revocado (simulado)")


class ClienteOAuthGoogleFake:
    """Doble del cliente OAuth de Google: canjea el `code` por credenciales fijas y
    registra los códigos vistos (para verificar que no se canjea con state inválido).
    Cero red, cero credenciales reales (CA6)."""

    def __init__(self, credenciales: CredencialesGmail | None = None):
        self.credenciales = credenciales or CredencialesGmail(
            refresh_token="refresh-de-prueba", casilla="hola@capsulab.cl"
        )
        self.codigos_canjeados: list[str] = []

    async def canjear_codigo(self, code: str) -> CredencialesGmail:
        self.codigos_canjeados.append(code)
        return self.credenciales


class ClienteOAuthClickUpFake:
    """Doble del cliente OAuth de ClickUp: canjea el `code` por un access token fijo y
    registra los códigos vistos (para verificar que no se canjea con state inválido).
    Cero red, cero credenciales reales (CA8)."""

    def __init__(self, credenciales: CredencialesClickUp | None = None):
        self.credenciales = credenciales or CredencialesClickUp(
            access_token="access-de-prueba"
        )
        self.codigos_canjeados: list[str] = []

    async def canjear_codigo(self, code: str) -> CredencialesClickUp:
        self.codigos_canjeados.append(code)
        return self.credenciales


class FabricaClienteGmailFake:
    """Fábrica de clientes Gmail por empresa: devuelve el cliente ya fijado para la
    empresa de la integración (en el real, lo construye desde el token). Registra las
    empresas para las que se pidió un cliente. Cero red (CA6)."""

    def __init__(self, por_empresa: dict):
        self._por_empresa = por_empresa
        self.creados: list = []

    def crear(self, integracion):
        self.creados.append(integracion.empresa_id)
        return self._por_empresa[integracion.empresa_id]
