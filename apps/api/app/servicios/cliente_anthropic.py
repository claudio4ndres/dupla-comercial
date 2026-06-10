"""Cliente Anthropic mínimo sobre **httpx** (reemplaza al SDK `anthropic`).

Por qué no el SDK: `anthropic` importa ~1800 módulos (arma muchísimos modelos
Pydantic al cargar) y en frío tardaba MINUTOS en esta máquina, frenando CADA
arranque del backend y el primer llamado a Javo. La llamada al LLM en sí es una
petición HTTP de ~2 s. Aquí hablamos directo con la Messages API usando httpx (ya
es dependencia del proyecto), exponiendo SOLO la superficie que usan los servicios:

    cliente.messages.create(**kwargs) -> respuesta con `.content`
    (lista de bloques con `.type` y `.input`/`.text`, igual que el SDK).

Sin red al construir (como los repos Supabase): el `AsyncClient` se inyecta en los
tests con transporte mockeado; en prod se crea uno por llamada.
"""
from types import SimpleNamespace

import httpx

# Endpoint y versión estables de la Messages API de Anthropic.
URL_BASE = "https://api.anthropic.com"
VERSION_API = "2023-06-01"
TIMEOUT_SEGUNDOS = 60.0


class _Mensajes:
    """Espejo del `cliente.messages` del SDK: solo implementa `create`."""

    def __init__(
        self,
        api_key: str,
        cliente: httpx.AsyncClient | None,
        base_url: str,
        version: str,
        timeout: float,
    ):
        self._api_key = api_key
        self._cliente = cliente  # inyectable para tests; en prod se crea por llamada
        self._base = base_url.rstrip("/")
        self._version = version
        self._timeout = timeout

    async def create(self, **payload):
        """POST /v1/messages con el `payload` tal cual (model/messages/tools/...).

        Mapea la respuesta JSON a objetos con atributos para que los servicios
        accedan `bloque.type`, `bloque.input`, `bloque.text` como con el SDK. El
        `input` de un bloque `tool_use` se deja como dict (es lo que consume
        `ResultadoClasificacion(**input)`). Un status de error propaga como
        `httpx.HTTPStatusError` → la ruta lo convierte en 502."""
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._version,
            "content-type": "application/json",
        }
        url = self._base + "/v1/messages"
        if self._cliente is not None:
            resp = await self._cliente.post(url, headers=headers, json=payload)
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as cliente:
                resp = await cliente.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        datos = resp.json()
        bloques = [SimpleNamespace(**bloque) for bloque in datos.get("content", [])]
        return SimpleNamespace(**{**datos, "content": bloques})


class ClienteAnthropicHttpx:
    """Cliente con la interfaz mínima `.messages.create(...)` que usan los servicios.

    `cliente` (httpx.AsyncClient) es opcional: se inyecta en tests con transporte
    mockeado; en prod se omite y cada llamada abre su propio cliente."""

    def __init__(
        self,
        api_key: str,
        *,
        cliente: httpx.AsyncClient | None = None,
        base_url: str = URL_BASE,
        version: str = VERSION_API,
        timeout: float = TIMEOUT_SEGUNDOS,
    ):
        self.api_key = api_key
        self.messages = _Mensajes(api_key, cliente, base_url, version, timeout)
