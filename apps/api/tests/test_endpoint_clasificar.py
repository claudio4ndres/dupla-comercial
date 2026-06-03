"""Tests del endpoint POST /solicitudes/{id}/clasificar.

Cubre CA1 (devuelve resumen+tipo y persiste), CA4 (no cambia estado), idempotencia
(segunda llamada no regasta el LLM) y T4 (aislamiento multi-tenant: empresa A no
puede tocar solicitudes de empresa B). El repositorio, el cliente Anthropic y la
empresa del usuario se inyectan vía `dependency_overrides` con dobles en memoria.
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
from tests.dobles import ClienteAnthropicFake, ClienteAnthropicQueFalla

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def _cliente_http(repo, anthropic, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_repositorio_solicitudes] = lambda: repo
    app.dependency_overrides[obtener_cliente_anthropic] = lambda: anthropic
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def _solicitud(**kwargs):
    base = dict(
        id=uuid4(),
        empresa_id=EMPRESA_A,
        remitente="Zona Espiga",
        asunto="Cotización sopaipillas",
        cuerpo="Hola Javo, cotizar sopaipillas afuera del Metro.",
    )
    base.update(kwargs)
    return Solicitud(**base)


def test_clasificar_devuelve_resumen_y_tipo_y_persiste():
    # CA1
    sol = _solicitud()
    repo = RepositorioSolicitudesEnMemoria([sol])
    anthropic = ClienteAnthropicFake(
        {"resumen": "Sampling de sopaipillas, 5 horas.", "tipo": "tipo_1"}
    )
    http = _cliente_http(repo, anthropic)

    r = http.post(f"/solicitudes/{sol.id}/clasificar")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["resumen"].strip() != ""
    assert cuerpo["tipo"] in ("tipo_1", "tipo_2")
    guardada = repo.por_id(sol.id)
    assert guardada.resumen == "Sampling de sopaipillas, 5 horas."
    assert guardada.tipo == "tipo_1"


def test_clasificar_no_cambia_el_estado():
    # CA4
    sol = _solicitud(estado="nueva")
    repo = RepositorioSolicitudesEnMemoria([sol])
    anthropic = ClienteAnthropicFake({"resumen": "x", "tipo": "tipo_2"})
    http = _cliente_http(repo, anthropic)

    http.post(f"/solicitudes/{sol.id}/clasificar")

    assert repo.por_id(sol.id).estado == "nueva"


def test_clasificar_es_idempotente_no_regasta_tokens():
    # Idempotencia: si ya está clasificada, no se llama al LLM.
    sol = _solicitud(resumen="Resumen previo.", tipo="tipo_1")
    repo = RepositorioSolicitudesEnMemoria([sol])
    anthropic = ClienteAnthropicFake({"resumen": "NO USAR", "tipo": "tipo_2"})
    http = _cliente_http(repo, anthropic)

    r = http.post(f"/solicitudes/{sol.id}/clasificar")

    assert r.status_code == 200
    assert r.json() == {"resumen": "Resumen previo.", "tipo": "tipo_1"}
    assert len(anthropic.llamadas) == 0


def test_clasificar_solicitud_inexistente_devuelve_404():
    repo = RepositorioSolicitudesEnMemoria([])
    anthropic = ClienteAnthropicFake({"resumen": "x", "tipo": "tipo_1"})
    http = _cliente_http(repo, anthropic)

    r = http.post(f"/solicitudes/{uuid4()}/clasificar")

    assert r.status_code == 404


def test_no_clasifica_solicitud_de_otra_empresa_devuelve_404():
    # T4 · Aislamiento multi-tenant: empresa A no puede tocar solicitud de empresa B.
    sol_b = _solicitud(empresa_id=EMPRESA_B)
    repo = RepositorioSolicitudesEnMemoria([sol_b])
    anthropic = ClienteAnthropicFake({"resumen": "x", "tipo": "tipo_1"})
    http = _cliente_http(repo, anthropic, empresa_id=EMPRESA_A)

    r = http.post(f"/solicitudes/{sol_b.id}/clasificar")

    assert r.status_code == 404
    assert len(anthropic.llamadas) == 0


def test_error_del_llm_devuelve_502_y_no_persiste():
    # T6 · Si el SDK de Anthropic cae, el endpoint responde 502 (no un 500 crudo)
    # y la solicitud NO queda clasificada a medias.
    sol = _solicitud()
    repo = RepositorioSolicitudesEnMemoria([sol])
    anthropic = ClienteAnthropicQueFalla()
    http = _cliente_http(repo, anthropic)

    r = http.post(f"/solicitudes/{sol.id}/clasificar")

    assert r.status_code == 502
    guardada = repo.por_id(sol.id)
    assert guardada.resumen is None
    assert guardada.tipo == "sin_clasificar"
