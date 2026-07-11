"""Cliente Anthropic real sobre **httpx** (sin el SDK `anthropic`).

Motivación: el SDK `anthropic` arrastra ~1800 módulos y su import en frío tardaba
MINUTOS en esta máquina, frenando cada arranque/primer llamado. La llamada al LLM
en sí es una petición HTTP de ~2 s. Este cliente habla directo con la Messages API
con httpx (ya usado en todo el proyecto), exponiendo la MISMA interfaz mínima que
consumen los servicios: `cliente.messages.create(**kwargs)` → respuesta con
`.content` = lista de bloques con `.type` y `.input`/`.text`.

Cero red y cero tokens: se inyecta un transporte httpx mockeado (igual que los
repos Supabase). El test extremo-a-extremo real se cubre al usar el backend.
"""
import json

import httpx
import pytest

from app.servicios.cliente_anthropic import ClienteAnthropicHttpx

API_KEY = "sk-ant-test"


class DormirFake:
    """Doble de `asyncio.sleep`: registra las esperas sin dormir de verdad."""

    def __init__(self):
        self.esperas: list[float] = []

    async def __call__(self, segundos: float) -> None:
        self.esperas.append(segundos)


def _cliente(handler, *, dormir=None, **kwargs):
    transporte = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transporte)
    return ClienteAnthropicHttpx(
        API_KEY, cliente=http, dormir=dormir or DormirFake(), **kwargs
    )


async def test_create_pega_a_messages_con_headers_y_mapea_tool_use():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["metodo"] = req.method
        visto["url"] = str(req.url)
        visto["x-api-key"] = req.headers.get("x-api-key")
        visto["version"] = req.headers.get("anthropic-version")
        visto["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "registrar_clasificacion",
                        "input": {"resumen": "ok", "tipo": "tipo_1"},
                    }
                ]
            },
        )

    cli = _cliente(handler)
    resp = await cli.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=[
            {"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}
        ],
        tools=[{"name": "registrar_clasificacion"}],
        tool_choice={"type": "tool", "name": "registrar_clasificacion"},
        messages=[{"role": "user", "content": "hola"}],
    )

    # Pega al endpoint correcto, con los headers de auth y versión de la API.
    assert visto["metodo"] == "POST"
    assert visto["url"].endswith("/v1/messages")
    assert visto["x-api-key"] == API_KEY
    assert visto["version"]  # se envía alguna versión de la API
    # El payload viaja tal cual (model/messages/tools/...).
    assert visto["body"]["model"] == "claude-haiku-4-5"
    assert visto["body"]["messages"] == [{"role": "user", "content": "hola"}]
    assert visto["body"]["tool_choice"]["name"] == "registrar_clasificacion"
    # La respuesta se mapea como el SDK: bloque con .type y .input.
    bloque = resp.content[0]
    assert bloque.type == "tool_use"
    assert bloque.name == "registrar_clasificacion"
    assert bloque.input == {"resumen": "ok", "tipo": "tipo_1"}


async def test_create_mapea_bloque_de_texto():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"content": [{"type": "text", "text": "Hola, soy Javo"}]}
        )

    resp = await _cliente(handler).messages.create(
        model="claude-sonnet-4-5",
        max_tokens=16,
        messages=[{"role": "user", "content": "hi"}],
    )
    bloque = resp.content[0]
    assert bloque.type == "text"
    assert bloque.text == "Hola, soy Javo"


async def test_create_propaga_error_http_como_excepcion():
    # Un 5xx PERSISTENTE de la API debe propagar como excepción httpx para que la
    # ruta lo convierta en 502 (igual que cuando el SDK lanzaba), aun con reintentos.
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"type": "error", "error": {"message": "boom"}})

    with pytest.raises(httpx.HTTPStatusError):
        await _cliente(handler).messages.create(
            model="x", max_tokens=1, messages=[{"role": "user", "content": "z"}]
        )


# ── Spec 012 · Reintentos con backoff ante errores transitorios ───────────────


def _respuesta_ok() -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})


async def test_429_con_retry_after_reintenta_y_responde():
    # CA1: 429 con Retry-After → espera lo indicado, reintenta y devuelve el 200.
    intentos = []

    def handler(req: httpx.Request) -> httpx.Response:
        intentos.append(1)
        if len(intentos) == 1:
            return httpx.Response(429, headers={"retry-after": "0.5"}, json={})
        return _respuesta_ok()

    dormir = DormirFake()
    resp = await _cliente(handler, dormir=dormir).messages.create(
        model="x", max_tokens=1, messages=[{"role": "user", "content": "z"}]
    )

    assert resp.content[0].text == "ok"
    assert len(intentos) == 2
    assert dormir.esperas == [0.5]  # respeta Retry-After, no el backoff propio


async def test_529_persistente_agota_reintentos_y_relanza():
    # CA2: sobrecarga permanente → HTTPStatusError tras reintentos+1 intentos.
    intentos = []

    def handler(req: httpx.Request) -> httpx.Response:
        intentos.append(1)
        return httpx.Response(529, json={})

    with pytest.raises(httpx.HTTPStatusError):
        await _cliente(handler, reintentos=2).messages.create(
            model="x", max_tokens=1, messages=[{"role": "user", "content": "z"}]
        )
    assert len(intentos) == 3  # intento original + 2 reintentos


async def test_400_no_se_reintenta():
    # CA3: error del payload (no transitorio) → falla al primer intento.
    intentos = []

    def handler(req: httpx.Request) -> httpx.Response:
        intentos.append(1)
        return httpx.Response(400, json={"type": "error"})

    with pytest.raises(httpx.HTTPStatusError):
        await _cliente(handler).messages.create(
            model="x", max_tokens=1, messages=[{"role": "user", "content": "z"}]
        )
    assert len(intentos) == 1


async def test_error_de_red_se_reintenta():
    # CA4: ConnectError transitorio → reintenta y devuelve la respuesta.
    intentos = []

    def handler(req: httpx.Request) -> httpx.Response:
        intentos.append(1)
        if len(intentos) == 1:
            raise httpx.ConnectError("red caída", request=req)
        return _respuesta_ok()

    resp = await _cliente(handler).messages.create(
        model="x", max_tokens=1, messages=[{"role": "user", "content": "z"}]
    )
    assert resp.content[0].text == "ok"
    assert len(intentos) == 2


async def test_backoff_exponencial_sin_retry_after():
    # CA5: sin Retry-After las esperas crecen exponencialmente (base 2) y no se
    # duerme de verdad (el DormirFake solo registra).
    intentos = []

    def handler(req: httpx.Request) -> httpx.Response:
        intentos.append(1)
        if len(intentos) <= 2:
            return httpx.Response(500, json={})
        return _respuesta_ok()

    dormir = DormirFake()
    resp = await _cliente(handler, dormir=dormir, espera_base=1.0).messages.create(
        model="x", max_tokens=1, messages=[{"role": "user", "content": "z"}]
    )

    assert resp.content[0].text == "ok"
    assert len(dormir.esperas) == 2
    # Exponencial con jitter: cada espera parte de base·2^intento y crece.
    assert 1.0 <= dormir.esperas[0] < 2.0
    assert 2.0 <= dormir.esperas[1] < 4.0
