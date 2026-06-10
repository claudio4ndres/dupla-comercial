"""Tests del endpoint GET /miembros (roster del equipo de la empresa, 0006).

El front necesita leer los miembros reales para poblar el selector "Asignado a" de
la pantalla de Tareas. Este endpoint devuelve SÓLO los miembros de la empresa del
usuario (aislamiento multi-tenant, RLS) con la forma plana del contrato:
`{id, nombre, rol}`. NUNCA viaja `empresa_id` (CA5). Sin miembros → lista vacía.
Sin token → 401.

El repositorio y la empresa del usuario se inyectan vía `dependency_overrides` con
dobles en memoria (cero red, cero LLM).
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_empresa_actual,
    obtener_repositorio_miembros,
)
from app.main import app
from app.repositorios.miembros import Miembro, RepositorioMiembrosEnMemoria

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def _cliente_http(repo, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_repositorio_miembros] = lambda: repo
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def _miembro(empresa_id=EMPRESA_A, **kwargs):
    base = dict(
        id=uuid4(),
        empresa_id=empresa_id,
        nombre="Gabriela Lillo",
        rol="RRHH",
    )
    base.update(kwargs)
    return Miembro(**base)


def test_listar_devuelve_los_miembros_de_la_empresa():
    m1 = _miembro(nombre="Gabriela Lillo", rol="RRHH")
    m2 = _miembro(nombre="Bruno Soto", rol="Producción")
    repo = RepositorioMiembrosEnMemoria([m1, m2])
    http = _cliente_http(repo)

    r = http.get("/miembros")

    assert r.status_code == 200
    cuerpo = r.json()
    assert isinstance(cuerpo, list)
    assert len(cuerpo) == 2
    nombres = {item["nombre"] for item in cuerpo}
    assert nombres == {"Gabriela Lillo", "Bruno Soto"}
    item = next(i for i in cuerpo if i["nombre"] == "Gabriela Lillo")
    assert item["rol"] == "RRHH"
    assert "id" in item  # el id viaja (para el value del <option>)


def test_listar_sin_miembros_devuelve_lista_vacia():
    repo = RepositorioMiembrosEnMemoria([])
    http = _cliente_http(repo)

    r = http.get("/miembros")

    assert r.status_code == 200
    assert r.json() == []


def test_listar_solo_devuelve_miembros_de_la_empresa_actual():
    # Aislamiento multi-tenant: la empresa A no ve los miembros de la B.
    m_a = _miembro(empresa_id=EMPRESA_A, nombre="De A")
    m_b = _miembro(empresa_id=EMPRESA_B, nombre="De B")
    repo = RepositorioMiembrosEnMemoria([m_a, m_b])
    http = _cliente_http(repo, empresa_id=EMPRESA_A)

    r = http.get("/miembros")

    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo) == 1
    assert cuerpo[0]["nombre"] == "De A"


def test_listar_nunca_expone_empresa_id():
    # CA5 · La respuesta es plana para el front: sin empresa_id ni referencias internas.
    repo = RepositorioMiembrosEnMemoria([_miembro()])
    http = _cliente_http(repo)

    item = http.get("/miembros").json()[0]

    assert "empresa_id" not in item


def test_listar_sin_token_devuelve_401():
    # Sin sobrescribir `obtener_empresa_actual`: la auth real exige el Bearer.
    repo = RepositorioMiembrosEnMemoria([_miembro()])
    app.dependency_overrides[obtener_repositorio_miembros] = lambda: repo
    http = TestClient(app)

    r = http.get("/miembros")

    assert r.status_code == 401
