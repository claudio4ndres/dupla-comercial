"""Tests del endpoint GET /catalogo/recursos (panel "Recursos · Drive" del chat).

Lista los recursos del Drive (origenes del catálogo) de la empresa del usuario. Sólo
de su empresa (aislamiento multi-tenant). El repo y la empresa se inyectan con dobles
en memoria (cero red).
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_empresa_actual,
    obtener_repositorio_catalogo,
)
from app.main import app
from app.repositorios.catalogo import ItemCatalogo, RepositorioCatalogoEnMemoria

EMPRESA_A = uuid4()


def _item(origen, empresa_id=EMPRESA_A):
    return ItemCatalogo(id=uuid4(), empresa_id=empresa_id, nombre="x", origen=origen)


def _cliente_http(repo, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_repositorio_catalogo] = lambda: repo
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_recursos_devuelve_los_origenes_de_la_empresa():
    repo = RepositorioCatalogoEnMemoria(
        [_item("Tarifario.xlsx"), _item("PRODUCCIÓN 3D"), _item("Tarifario.xlsx")]
    )
    http = _cliente_http(repo)

    r = http.get("/catalogo/recursos")

    assert r.status_code == 200
    cuerpo = r.json()
    assert isinstance(cuerpo, list)
    assert set(cuerpo) == {"PRODUCCIÓN 3D", "Tarifario.xlsx"}


def test_recursos_sin_catalogo_devuelve_lista_vacia():
    http = _cliente_http(RepositorioCatalogoEnMemoria([]))

    r = http.get("/catalogo/recursos")

    assert r.status_code == 200
    assert r.json() == []
