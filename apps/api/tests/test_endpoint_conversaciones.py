"""Tests del endpoint POST /conversaciones/responder (003 · T2).

Cubre CA5 (200 con `{ texto }` usando el cliente Anthropic mockeado) y CA4 (si el
LLM cae, el endpoint responde 502, nunca un 500 crudo; el front cae a su respuesta
offline). El cliente Anthropic se inyecta vía `dependency_overrides` (regla #3: cero
red, cero tokens). El endpoint es sin estado: no toca repos ni empresa.
"""
from fastapi.testclient import TestClient

from app.dependencias import obtener_cliente_anthropic
from app.main import app
from tests.dobles import ClienteAnthropicQueFalla, ClienteAnthropicTextoFake


def _cliente_http(anthropic):
    app.dependency_overrides[obtener_cliente_anthropic] = lambda: anthropic
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def _payload(tipo="t1"):
    return {
        "solicitud_id": "demo-1",
        "tipo": tipo,
        "mensajes": [
            {"rol": "javo", "contenido": "¡Hola! Leí el correo de Zona Espiga."},
            {"rol": "usuario", "contenido": "Son 3 días de activación"},
        ],
    }


def test_responder_devuelve_200_con_texto():
    # CA5: con el cliente mockeado, el endpoint responde 200 con `{ texto }`.
    anthropic = ClienteAnthropicTextoFake("Perfecto, dejo catering + 2 promotores...")
    http = _cliente_http(anthropic)

    r = http.post("/conversaciones/responder", json=_payload())

    assert r.status_code == 200
    assert r.json() == {"texto": "Perfecto, dejo catering + 2 promotores..."}
    assert len(anthropic.llamadas) == 1


def test_error_del_llm_devuelve_502():
    # CA4: si el SDK de Anthropic cae, el endpoint responde 502 (no un 500 crudo).
    anthropic = ClienteAnthropicQueFalla()
    http = _cliente_http(anthropic)

    r = http.post("/conversaciones/responder", json=_payload())

    assert r.status_code == 502
