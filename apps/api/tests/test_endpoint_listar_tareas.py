"""Tests del endpoint GET /tareas (lista las tareas de la empresa).

El front necesita leer las tareas reales (la sección "Tareas") en vez del mock.
Este endpoint devuelve SÓLO las tareas de la empresa del usuario (aislamiento
multi-tenant, RLS) con la forma plana del contrato:
`{nombre, grupo, responsable, vencimiento}`. NUNCA viaja `empresa_id` (CA5). Sin
tareas → lista vacía. Sin token → 401.

El repositorio y la empresa del usuario se inyectan vía `dependency_overrides` con
dobles en memoria (cero red, cero LLM).
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_empresa_actual,
    obtener_repositorio_tareas,
)
from app.main import app
from app.repositorios.tareas import (
    RepositorioTareasEnMemoria,
    TareaResumen,
)

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def _cliente_http(repo, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_repositorio_tareas] = lambda: repo
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def _tarea(empresa_id=EMPRESA_A, **kwargs):
    base = dict(
        empresa_id=empresa_id,
        nombre="Reclutar 6 promotoras",
        grupo="RRHH",
        responsable="Coordinación",
        vencimiento="3 días",
    )
    base.update(kwargs)
    return TareaResumen(**base)


def test_listar_devuelve_las_tareas_de_la_empresa():
    t1 = _tarea(nombre="Reclutar promotoras", grupo="RRHH")
    t2 = _tarea(nombre="Cotizar catering", grupo="Producción", responsable=None)
    repo = RepositorioTareasEnMemoria([t1, t2])
    http = _cliente_http(repo)

    r = http.get("/tareas")

    assert r.status_code == 200
    cuerpo = r.json()
    assert isinstance(cuerpo, list)
    assert len(cuerpo) == 2
    nombres = {item["nombre"] for item in cuerpo}
    assert nombres == {"Reclutar promotoras", "Cotizar catering"}
    item = next(i for i in cuerpo if i["nombre"] == "Reclutar promotoras")
    assert item["grupo"] == "RRHH"
    assert item["responsable"] == "Coordinación"
    assert item["vencimiento"] == "3 días"
    # Los campos opcionales viajan como null cuando faltan.
    otro = next(i for i in cuerpo if i["nombre"] == "Cotizar catering")
    assert otro["responsable"] is None


def test_listar_sin_tareas_devuelve_lista_vacia():
    repo = RepositorioTareasEnMemoria([])
    http = _cliente_http(repo)

    r = http.get("/tareas")

    assert r.status_code == 200
    assert r.json() == []


def test_listar_solo_devuelve_tareas_de_la_empresa_actual():
    # Aislamiento multi-tenant: la empresa A no ve las tareas de la B.
    t_a = _tarea(empresa_id=EMPRESA_A, nombre="De A")
    t_b = _tarea(empresa_id=EMPRESA_B, nombre="De B")
    repo = RepositorioTareasEnMemoria([t_a, t_b])
    http = _cliente_http(repo, empresa_id=EMPRESA_A)

    r = http.get("/tareas")

    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo) == 1
    assert cuerpo[0]["nombre"] == "De A"


def test_listar_nunca_expone_empresa_id():
    # CA5 · La respuesta es plana para el front: sin empresa_id ni referencias internas.
    repo = RepositorioTareasEnMemoria([_tarea()])
    http = _cliente_http(repo)

    item = http.get("/tareas").json()[0]

    assert "empresa_id" not in item


def test_listar_sin_token_devuelve_401():
    # Sin sobrescribir `obtener_empresa_actual`: la auth real exige el Bearer.
    repo = RepositorioTareasEnMemoria([_tarea()])
    app.dependency_overrides[obtener_repositorio_tareas] = lambda: repo
    http = TestClient(app)

    r = http.get("/tareas")

    assert r.status_code == 401
