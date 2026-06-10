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


def _cliente(handler):
    transporte = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transporte)
    return ClienteAnthropicHttpx(API_KEY, cliente=http)


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
    # Un 5xx de la API debe propagar como excepción httpx para que la ruta lo
    # convierta en 502 (igual que cuando el SDK lanzaba).
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"type": "error", "error": {"message": "boom"}})

    with pytest.raises(httpx.HTTPStatusError):
        await _cliente(handler).messages.create(
            model="x", max_tokens=1, messages=[{"role": "user", "content": "z"}]
        )
