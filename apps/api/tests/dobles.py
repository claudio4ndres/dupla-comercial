"""Dobles de prueba reutilizables (no tocan la red ni gastan tokens)."""


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
