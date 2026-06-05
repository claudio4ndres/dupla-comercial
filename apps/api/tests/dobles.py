"""Dobles de prueba reutilizables (no tocan la red ni gastan tokens)."""
from app.servicios.gmail import ErrorAutenticacionGmail, MensajeCorreo
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


class ClienteGmailQueFallaAuth:
    """Doble que simula un refresh token expirado/revocado: al leer lanza
    `ErrorAutenticacionGmail` (CA7). Igual registra la llamada."""

    def __init__(self):
        self.llamadas: list = []

    async def listar_nuevos(self, cursor: str | None):
        self.llamadas.append(cursor)
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
