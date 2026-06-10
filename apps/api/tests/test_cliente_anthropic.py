"""T7a · El proveedor real del cliente Anthropic.

Construye un `ClienteAnthropicHttpx` (cliente sobre httpx, sin el SDK) con la API
key tomada de `Settings` (variables de entorno). NO hace llamadas de red: solo
verifica que el cliente queda cableado con la key correcta (respeta CA5 y el
presupuesto: cero tokens en tests).

Nota: ya NO se importa el SDK `anthropic` aquí (ni en ningún lado de prod), porque
su import en frío tardaba minutos; ver `app/servicios/cliente_anthropic.py`.
"""
from app.config import obtener_settings
from app.dependencias import obtener_cliente_anthropic
from app.servicios.cliente_anthropic import ClienteAnthropicHttpx


def test_obtener_cliente_anthropic_usa_la_key_de_settings(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy-para-test")
    obtener_settings.cache_clear()
    obtener_cliente_anthropic.cache_clear()

    cliente = obtener_cliente_anthropic()

    assert isinstance(cliente, ClienteAnthropicHttpx)
    assert cliente.api_key == "sk-ant-dummy-para-test"
