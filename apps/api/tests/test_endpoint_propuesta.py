"""Tests del endpoint GET /solicitudes/{id}/propuesta (la cotización de la demo).

El front necesita leer la cotización real (componentes valorizados + tareas) en
vez del mock. El endpoint devuelve la forma plana en español SÓLO de la empresa
del usuario (aislamiento multi-tenant) y NUNCA `empresa_id` (CA5). Sin propuesta
para esa solicitud → 404 (el front cae a su fallback).

El repositorio y la empresa del usuario se inyectan con dobles en memoria
(cero red, cero LLM).
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_empresa_actual,
    obtener_repositorio_propuestas,
)
from app.main import app
from app.repositorios.propuestas import (
    ComponentePropuesta,
    Propuesta,
    RepositorioPropuestasEnMemoria,
    TareaPropuesta,
)

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def _cliente_http(repo, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_repositorio_propuestas] = lambda: repo
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def _propuesta(solicitud_id, empresa_id=EMPRESA_A):
    return Propuesta(
        id=uuid4(),
        empresa_id=empresa_id,
        solicitud_id=solicitud_id,
        total=5190000,
        estado="borrador",
        componentes=[
            ComponentePropuesta(
                nombre="Promotoras uniformadas",
                detalle="6h/día × 4 días · 3 tiendas",
                cantidad=6,
                valor_unitario=240000,
            )
        ],
        tareas=[
            TareaPropuesta(
                nombre="Reclutar 6 promotoras",
                grupo="RRHH",
                responsable="Coordinación",
                vencimiento="3 días",
            )
        ],
    )


def test_devuelve_la_propuesta_de_la_solicitud():
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    http = _cliente_http(repo)

    r = http.get(f"/solicitudes/{sol}/propuesta")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado"] == "borrador"
    assert cuerpo["total"] == 5190000
    assert cuerpo["componentes"][0]["nombre"] == "Promotoras uniformadas"
    assert cuerpo["componentes"][0]["valor_unitario"] == 240000
    assert cuerpo["componentes"][0]["cantidad"] == 6
    assert cuerpo["tareas"][0]["grupo"] == "RRHH"
    assert cuerpo["tareas"][0]["vencimiento"] == "3 días"


def test_sin_propuesta_devuelve_404():
    repo = RepositorioPropuestasEnMemoria([])
    http = _cliente_http(repo)

    r = http.get(f"/solicitudes/{uuid4()}/propuesta")

    assert r.status_code == 404


def test_aislamiento_multi_tenant_no_ve_propuesta_de_otra_empresa():
    # La propuesta es de la empresa B; el usuario es de la A → 404 (no la ve).
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol, empresa_id=EMPRESA_B)])
    http = _cliente_http(repo, empresa_id=EMPRESA_A)

    r = http.get(f"/solicitudes/{sol}/propuesta")

    assert r.status_code == 404


def test_respuesta_nunca_expone_empresa_id():
    # CA5 · forma plana para el front: sin empresa_id ni referencias internas.
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    http = _cliente_http(repo)

    cuerpo = http.get(f"/solicitudes/{sol}/propuesta").json()

    assert "empresa_id" not in cuerpo
    assert "solicitud_id" not in cuerpo
