"""Tests del endpoint GET /integraciones/correo (estado de la conexión de correo).

Cubre:
- CA1: sin integración → {proveedor:null, estado:null, casilla:null}.
- CA2: con integración conectada → proveedor='gmail', estado='conectado', casilla.
- CA5: la respuesta NUNCA expone token_ref ni ningún token.

El repositorio de integraciones y la empresa del usuario se inyectan vía
`dependency_overrides` con dobles en memoria (CA6: cero Gmail/OAuth real).
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_empresa_actual,
    obtener_repositorio_integraciones,
)
from app.main import app
from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def _cliente_http(repo, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_repositorio_integraciones] = lambda: repo
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def _integracion(**kwargs):
    base = dict(
        id=uuid4(),
        empresa_id=EMPRESA_A,
        proveedor="gmail",
        token_ref="secreto://capsulab/gmail-refresh",
        casilla="hola@capsulab.cl",
        cursor="hist-1",
        estado="conectado",
    )
    base.update(kwargs)
    return Integracion(**base)


def test_sin_integracion_devuelve_todo_nulo():
    # CA1: una empresa sin casilla conectada ve todo en null (la Bandeja pinta
    # los botones de "conectar").
    repo = RepositorioIntegracionesEnMemoria([])
    http = _cliente_http(repo)

    r = http.get("/integraciones/correo")

    assert r.status_code == 200
    assert r.json() == {"proveedor": None, "estado": None, "casilla": None}


def test_con_integracion_conectada_devuelve_estado():
    # CA2: con la casilla conectada, la Bandeja pinta "Escuchando · gmail".
    repo = RepositorioIntegracionesEnMemoria([_integracion()])
    http = _cliente_http(repo)

    r = http.get("/integraciones/correo")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["proveedor"] == "gmail"
    assert cuerpo["estado"] == "conectado"
    assert cuerpo["casilla"] == "hola@capsulab.cl"


def test_la_respuesta_nunca_expone_tokens():
    # CA5: ni el token_ref ni ningún token salen del backend hacia el front.
    repo = RepositorioIntegracionesEnMemoria(
        [_integracion(token_ref="secreto://capsulab/gmail-refresh")]
    )
    http = _cliente_http(repo)

    r = http.get("/integraciones/correo")

    assert r.status_code == 200
    assert "token_ref" not in r.json()
    assert "token" not in r.json()
    assert "secreto://capsulab/gmail-refresh" not in r.text


def test_solo_ve_la_integracion_de_su_empresa():
    # Multi-tenant: el usuario de la empresa A jamás ve la casilla de la empresa B.
    repo = RepositorioIntegracionesEnMemoria([_integracion(empresa_id=EMPRESA_B)])
    http = _cliente_http(repo, empresa_id=EMPRESA_A)

    r = http.get("/integraciones/correo")

    assert r.status_code == 200
    assert r.json() == {"proveedor": None, "estado": None, "casilla": None}
