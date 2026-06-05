"""Tests del endpoint DELETE /integraciones/correo (el "Cambiar") · T9.

Desconecta la casilla de la empresa: borra el secreto (refresh token) y elimina la
fila de `integraciones`. Tras el DELETE, GET /integraciones/correo vuelve a
proveedor:null (la Bandeja vuelve a ofrecer "conectar").
"""
import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_almacen_secretos,
    obtener_empresa_actual,
    obtener_repositorio_integraciones,
)
from app.main import app
from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.servicios.secretos import AlmacenSecretosEnMemoria

EMPRESA_A = uuid4()


def _cliente_http(repo, secretos, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_repositorio_integraciones] = lambda: repo
    app.dependency_overrides[obtener_almacen_secretos] = lambda: secretos
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_delete_borra_integracion_y_secreto_y_get_vuelve_a_null():
    secretos = AlmacenSecretosEnMemoria()
    token_ref = asyncio.run(secretos.guardar("gmail-refresh-A", "refresh-secreto"))
    integ = Integracion(
        id=uuid4(),
        empresa_id=EMPRESA_A,
        proveedor="gmail",
        token_ref=token_ref,
        casilla="hola@capsulab.cl",
        estado="conectado",
    )
    repo = RepositorioIntegracionesEnMemoria([integ])
    http = _cliente_http(repo, secretos)

    r = http.delete("/integraciones/correo")
    assert r.status_code == 204

    # El secreto se borró del almacén: no queda refresh token colgando.
    assert asyncio.run(secretos.obtener(token_ref)) is None

    # Y la Bandeja vuelve a "conectar" (todo null).
    g = http.get("/integraciones/correo")
    assert g.json() == {"proveedor": None, "estado": None, "casilla": None}


def test_delete_sin_integracion_es_idempotente():
    # Desconectar algo que no existe no es un error: responde 204 igual.
    repo = RepositorioIntegracionesEnMemoria([])
    secretos = AlmacenSecretosEnMemoria()
    http = _cliente_http(repo, secretos)

    r = http.delete("/integraciones/correo")

    assert r.status_code == 204
