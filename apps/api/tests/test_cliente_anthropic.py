"""T7a · El proveedor real del cliente Anthropic (CABLEADO REAL · DIFERIDO).

Igual que TR1–TR4 de la spec 002, el cliente real `AsyncAnthropic` se cablea en
una tarea de integración aparte. Este test describe el comportamiento esperado
—construir el cliente con la API key de `Settings`, SIN red (respeta CA5 y el
presupuesto: cero tokens en tests)— pero queda OMITIDO hasta que existan
`app.config.obtener_settings` y el proveedor real en `app.dependencias`.

Las importaciones reales van dentro del test (no en el tope del módulo) para que
la colección de pytest no se rompa mientras el cableado siga pendiente.
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="Cableado real del cliente Anthropic pendiente (spec 001 · T7a)"
)


def test_obtener_cliente_anthropic_usa_la_key_de_settings(monkeypatch):
    from anthropic import AsyncAnthropic

    from app.config import obtener_settings
    from app.dependencias import obtener_cliente_anthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy-para-test")
    obtener_settings.cache_clear()
    obtener_cliente_anthropic.cache_clear()

    cliente = obtener_cliente_anthropic()

    assert isinstance(cliente, AsyncAnthropic)
    assert cliente.api_key == "sk-ant-dummy-para-test"
