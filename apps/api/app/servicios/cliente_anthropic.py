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

Spec 012 · Resiliencia: los errores TRANSITORIOS de la API (429 rate limit,
500/529 sobrecarga, 408 y fallos de red/timeout) se reintentan con espera
exponencial + jitter, respetando `Retry-After` cuando viene. Los errores del
request (400/401/403/404/422) NO se reintentan. Agotados los intentos se relanza
la última excepción → las rutas siguen convirtiendo en 502 (contrato intacto).
"""
import asyncio
import random
from types import SimpleNamespace

import httpx

# Endpoint y versión estables de la Messages API de Anthropic.
URL_BASE = "https://api.anthropic.com"
VERSION_API = "2023-06-01"
TIMEOUT_SEGUNDOS = 60.0

# Status transitorios que vale la pena reintentar (429/529 traen Retry-After).
_STATUS_REINTENTABLES = {408, 429, 500, 529}
# Reintentos por defecto (además del intento original) y base del backoff.
REINTENTOS = 2
ESPERA_BASE_SEGUNDOS = 1.0


class _Mensajes:
    """Espejo del `cliente.messages` del SDK: solo implementa `create`."""

    def __init__(
        self,
        api_key: str,
        cliente: httpx.AsyncClient | None,
        base_url: str,
        version: str,
        timeout: float,
        reintentos: int,
        espera_base: float,
        dormir,
    ):
        self._api_key = api_key
        self._cliente = cliente  # inyectable para tests; en prod se crea por llamada
        self._base = base_url.rstrip("/")
        self._version = version
        self._timeout = timeout
        self._reintentos = reintentos
        self._espera_base = espera_base
        self._dormir = dormir  # inyectable: los tests registran sin dormir de verdad

    async def _post(self, url: str, headers: dict, payload: dict) -> httpx.Response:
        if self._cliente is not None:
            return await self._cliente.post(url, headers=headers, json=payload)
        async with httpx.AsyncClient(timeout=self._timeout) as cliente:
            return await cliente.post(url, headers=headers, json=payload)

    def _espera(self, intento: int, resp: httpx.Response | None) -> float:
        """Cuánto esperar antes del reintento `intento` (0-indexado).

        `Retry-After` de la API manda (429/529 lo traen); si no viene, backoff
        exponencial con jitter para desincronizar llamadas paralelas (el poller
        clasifica con Semaphore(5))."""
        if resp is not None:
            retry_after = resp.headers.get("retry-after")
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass  # formato fecha u otro: cae al backoff propio
        base = self._espera_base * (2**intento)
        return base + random.uniform(0, base * 0.5)

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

        resp: httpx.Response | None = None
        for intento in range(self._reintentos + 1):
            try:
                resp = await self._post(url, headers, payload)
            except (httpx.TimeoutException, httpx.ConnectError):
                # Fallo de red transitorio: reintentar; en el último intento, propagar.
                if intento == self._reintentos:
                    raise
                await self._dormir(self._espera(intento, None))
                continue
            if (
                resp.status_code in _STATUS_REINTENTABLES
                and intento < self._reintentos
            ):
                await self._dormir(self._espera(intento, resp))
                continue
            break

        assert resp is not None  # el bucle siempre asigna o relanza
        resp.raise_for_status()
        datos = resp.json()
        bloques = [SimpleNamespace(**bloque) for bloque in datos.get("content", [])]
        return SimpleNamespace(**{**datos, "content": bloques})


class ClienteAnthropicHttpx:
    """Cliente con la interfaz mínima `.messages.create(...)` que usan los servicios.

    `cliente` (httpx.AsyncClient) es opcional: se inyecta en tests con transporte
    mockeado; en prod se omite y cada llamada abre su propio cliente. `dormir` es
    el hook de espera entre reintentos (asyncio.sleep en prod; un doble en tests)."""

    def __init__(
        self,
        api_key: str,
        *,
        cliente: httpx.AsyncClient | None = None,
        base_url: str = URL_BASE,
        version: str = VERSION_API,
        timeout: float = TIMEOUT_SEGUNDOS,
        reintentos: int = REINTENTOS,
        espera_base: float = ESPERA_BASE_SEGUNDOS,
        dormir=asyncio.sleep,
    ):
        self.api_key = api_key
        self.messages = _Mensajes(
            api_key, cliente, base_url, version, timeout, reintentos, espera_base, dormir
        )
