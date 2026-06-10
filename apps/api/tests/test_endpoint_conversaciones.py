"""Tests del endpoint POST /conversaciones/responder (003 + 005).

CA5: 200 con `{ texto, componentes, fuentes }` usando el cliente Anthropic mockeado.
CA4: si el LLM cae, el endpoint responde 502 (nunca un 500 crudo). 005: el endpoint
ahora **requiere auth** (la empresa se resuelve del JWT, porque Javo consulta el
catálogo del Drive con RLS) → sin token, 401.

Todo se inyecta vía `dependency_overrides` (regla #3: cero red, cero tokens).
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_cliente_anthropic,
    obtener_empresa_actual,
    obtener_proveedor_busqueda,
    obtener_repositorio_catalogo,
)
from app.main import app
from app.repositorios.catalogo import RepositorioCatalogoEnMemoria
from app.servicios.busqueda_internet import ProveedorBusquedaCurado
from tests.dobles import ClienteAnthropicQueFalla, ClienteAnthropicTextoFake

EMPRESA = uuid4()


def _cliente_http(anthropic, *, con_empresa=True):
    app.dependency_overrides[obtener_cliente_anthropic] = lambda: anthropic
    app.dependency_overrides[obtener_repositorio_catalogo] = (
        lambda: RepositorioCatalogoEnMemoria([])
    )
    app.dependency_overrides[obtener_proveedor_busqueda] = lambda: ProveedorBusquedaCurado()
    if con_empresa:
        app.dependency_overrides[obtener_empresa_actual] = lambda: EMPRESA
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
    # CA5: con el cliente mockeado, el endpoint responde 200 con la forma enriquecida.
    anthropic = ClienteAnthropicTextoFake("Perfecto, dejo catering + 2 promotores...")
    http = _cliente_http(anthropic)

    r = http.post(
        "/conversaciones/responder", json=_payload(), headers={"Authorization": "Bearer x"}
    )

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["texto"] == "Perfecto, dejo catering + 2 promotores..."
    assert cuerpo["componentes"] == [] and cuerpo["fuentes"] == []
    assert len(anthropic.llamadas) == 1


def test_error_del_llm_devuelve_502():
    # CA4: si el cliente Anthropic cae, el endpoint responde 502 (no un 500 crudo).
    http = _cliente_http(ClienteAnthropicQueFalla())

    r = http.post(
        "/conversaciones/responder", json=_payload(), headers={"Authorization": "Bearer x"}
    )

    assert r.status_code == 502


def test_sin_token_devuelve_401():
    # 005: el endpoint pasa a requerir auth (la empresa sale del JWT para la RLS).
    http = _cliente_http(ClienteAnthropicTextoFake(), con_empresa=False)

    r = http.post("/conversaciones/responder", json=_payload())  # sin Authorization

    assert r.status_code == 401
