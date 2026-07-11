"""Spec 013 · Chips de sugerencia como acciones de PARTNER COMERCIAL.

`POST /conversaciones/{id}/sugerencias` genera 3 chips con Haiku. Si Haiku falla
(o devuelve menos de 3 líneas), el fallback ya no es genérico: ofrece acciones
comerciales (opciones de presupuesto, upsell, cierre). Cero red: cliente y repos
se inyectan con dobles vía `app.dependency_overrides`.
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_cliente_anthropic,
    obtener_empresa_actual,
    obtener_repositorio_solicitudes,
)
from app.main import app
from app.repositorios.solicitudes import RepositorioSolicitudesEnMemoria, Solicitud
from tests.dobles import ClienteAnthropicQueFalla, ClienteAnthropicTextoFake

EMPRESA = uuid4()


def _solicitud(sol_id):
    return Solicitud(
        id=sol_id,
        empresa_id=EMPRESA,
        remitente="Zona Espiga",
        asunto="Sampling sopaipillas",
        cuerpo="Queremos cotizar un sampling.",
        resumen="Sampling afuera del Metro.",
        tipo="tipo_1",
        estado="nueva",
    )


def _http(cliente_llm, solicitudes):
    app.dependency_overrides[obtener_repositorio_solicitudes] = lambda: solicitudes
    app.dependency_overrides[obtener_cliente_anthropic] = lambda: cliente_llm
    app.dependency_overrides[obtener_empresa_actual] = lambda: EMPRESA
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_haiku_ok_devuelve_los_3_chips_del_modelo():
    sol_id = uuid4()
    repo = RepositorioSolicitudesEnMemoria([_solicitud(sol_id)])
    llm = ClienteAnthropicTextoFake(
        "Dame 2 opciones de presupuesto\nSuma medición y fotos\nGenera la propuesta"
    )
    r = _http(llm, repo).post(
        f"/conversaciones/{sol_id}/sugerencias", json={"tipo": "t1"}
    )
    assert r.status_code == 200
    assert r.json()["chips"] == [
        "Dame 2 opciones de presupuesto",
        "Suma medición y fotos",
        "Genera la propuesta",
    ]


def test_haiku_caido_cae_al_fallback_comercial():
    # CA5: el fallback ofrece acciones de partner (presupuesto / upsell / cierre).
    sol_id = uuid4()
    repo = RepositorioSolicitudesEnMemoria([_solicitud(sol_id)])
    r = _http(ClienteAnthropicQueFalla(), repo).post(
        f"/conversaciones/{sol_id}/sugerencias", json={"tipo": "t1"}
    )
    assert r.status_code == 200
    chips = " ".join(r.json()["chips"]).lower()
    assert "presupuesto" in chips
    assert "propuesta" in chips
