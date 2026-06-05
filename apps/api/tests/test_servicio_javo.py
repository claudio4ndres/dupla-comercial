"""Tests del servicio de conversación con Javo (003 · T1).

El cliente Anthropic se INYECTA y se MOCKEA: cero red, cero tokens (regla #3). Aquí
verificamos el enrutado a Sonnet, el prompt caching, la guía por tipo y la
normalización del historial al formato que exige la API de Anthropic.
"""
import asyncio

import pytest

from app.esquemas import MensajeConversacion
from app.servicios.javo import MODELO_CONVERSACION, responder_javo
from tests.dobles import ClienteAnthropicQueFalla, ClienteAnthropicTextoFake


def _historial_t1():
    return [
        MensajeConversacion(
            rol="javo",
            contenido="¡Hola! Leí el correo de Zona Espiga. Es una cotización concreta.",
        ),
        MensajeConversacion(rol="usuario", contenido="Son 3 días de activación"),
    ]


def test_responde_con_sonnet_y_system_cacheado():
    # CA1: usa el modelo Sonnet (chat) con el system prompt cacheado y devuelve el texto.
    cliente = ClienteAnthropicTextoFake("Perfecto, dejo catering + 2 promotores...")
    texto = asyncio.run(responder_javo("t1", _historial_t1(), cliente))

    assert texto == "Perfecto, dejo catering + 2 promotores..."
    llamada = cliente.llamadas[-1]
    assert llamada["model"] == MODELO_CONVERSACION
    assert "sonnet" in MODELO_CONVERSACION  # enrutar por costo: el chat usa Sonnet
    # Prompt caching del system prompt (regla #4).
    assert llamada["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_normaliza_historial_empezando_en_user():
    # CA2: el historial parte con Javo (assistant); Anthropic exige empezar en `user`
    # y alternar. El servicio normaliza para no romper la API.
    cliente = ClienteAnthropicTextoFake()
    asyncio.run(responder_javo("t1", _historial_t1(), cliente))

    mensajes = cliente.llamadas[-1]["messages"]
    assert mensajes[0]["role"] == "user"
    roles = [m["role"] for m in mensajes]
    assert all(a != b for a, b in zip(roles, roles[1:]))  # alterna, sin repetidos
    assert any(m["role"] == "assistant" for m in mensajes)  # el intro se preserva


def test_tipo_2_usa_guia_creativa_distinta():
    # CA3: el system de t2 es creativo (ofrece buscar en internet solo si lo piden) y
    # difiere del de t1.
    cliente_t2 = ClienteAnthropicTextoFake()
    asyncio.run(
        responder_javo(
            "t2",
            [MensajeConversacion(rol="javo", contenido="¡Hola! Es un pedido de ideas.")],
            cliente_t2,
        )
    )
    system_t2 = cliente_t2.llamadas[-1]["system"][0]["text"].lower()
    assert "internet" in system_t2

    cliente_t1 = ClienteAnthropicTextoFake()
    asyncio.run(responder_javo("t1", _historial_t1(), cliente_t1))
    system_t1 = cliente_t1.llamadas[-1]["system"][0]["text"].lower()
    assert system_t2 != system_t1


def test_llm_caido_propaga_excepcion():
    # CA4 (a nivel de servicio): si el cliente Anthropic lanza, el servicio propaga
    # (el endpoint lo convierte en 502).
    cliente = ClienteAnthropicQueFalla()
    with pytest.raises(Exception):
        asyncio.run(responder_javo("t1", _historial_t1(), cliente))
