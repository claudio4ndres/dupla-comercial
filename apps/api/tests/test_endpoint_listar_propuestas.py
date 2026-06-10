"""Tests del endpoint GET /propuestas (lista las propuestas de la empresa).

El front necesita leer las propuestas reales (la sección "Propuestas") en vez del
mock. Este endpoint devuelve SÓLO las propuestas de la empresa del usuario
(aislamiento multi-tenant, RLS) con la forma plana en español del contrato:
`{id, solicitud_id, total, estado, asunto, remitente}`. `asunto`/`remitente` salen
de la solicitud ligada (propuesta→conversación→solicitud). NUNCA viaja
`empresa_id` (CA5). Sin propuestas → lista vacía. Sin token → 401.

El repositorio y la empresa del usuario se inyectan vía `dependency_overrides` con
dobles en memoria (cero red, cero LLM).
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_empresa_actual,
    obtener_repositorio_propuestas,
)
from app.main import app
from app.repositorios.propuestas import (
    Propuesta,
    PropuestaResumen,
    RepositorioPropuestasEnMemoria,
)

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def _cliente_http(repo, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_repositorio_propuestas] = lambda: repo
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def _propuesta(empresa_id=EMPRESA_A, solicitud_id=None, **kwargs):
    base = dict(
        id=uuid4(),
        empresa_id=empresa_id,
        solicitud_id=solicitud_id or uuid4(),
        total=5190000,
        estado="borrador",
    )
    base.update(kwargs)
    prop = Propuesta(**base)
    return PropuestaResumen(
        id=prop.id,
        empresa_id=prop.empresa_id,
        solicitud_id=prop.solicitud_id,
        total=prop.total,
        estado=prop.estado,
        asunto=kwargs.get("asunto", "Sampling sopaipillas"),
        remitente=kwargs.get("remitente", "Zona Espiga"),
    )


def test_listar_devuelve_las_propuestas_de_la_empresa():
    sol1 = uuid4()
    p1 = _propuesta(solicitud_id=sol1, asunto="Sopaipillas", remitente="Zona Espiga")
    p2 = _propuesta(
        asunto="Fórmula 1", remitente="Marca X", total=8000000, estado="aprobada"
    )
    repo = RepositorioPropuestasEnMemoria([p1, p2])
    http = _cliente_http(repo)

    r = http.get("/propuestas")

    assert r.status_code == 200
    cuerpo = r.json()
    assert isinstance(cuerpo, list)
    assert len(cuerpo) == 2
    asuntos = {item["asunto"] for item in cuerpo}
    assert asuntos == {"Sopaipillas", "Fórmula 1"}
    item = next(i for i in cuerpo if i["asunto"] == "Sopaipillas")
    assert item["id"] == str(p1.id)
    assert item["solicitud_id"] == str(sol1)
    assert item["total"] == 5190000
    assert item["estado"] == "borrador"
    assert item["remitente"] == "Zona Espiga"


def test_listar_sin_propuestas_devuelve_lista_vacia():
    repo = RepositorioPropuestasEnMemoria([])
    http = _cliente_http(repo)

    r = http.get("/propuestas")

    assert r.status_code == 200
    assert r.json() == []


def test_listar_solo_devuelve_propuestas_de_la_empresa_actual():
    # Aislamiento multi-tenant: la empresa A no ve las propuestas de la B.
    p_a = _propuesta(empresa_id=EMPRESA_A, asunto="De A")
    p_b = _propuesta(empresa_id=EMPRESA_B, asunto="De B")
    repo = RepositorioPropuestasEnMemoria([p_a, p_b])
    http = _cliente_http(repo, empresa_id=EMPRESA_A)

    r = http.get("/propuestas")

    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo) == 1
    assert cuerpo[0]["asunto"] == "De A"


def test_listar_nunca_expone_empresa_id():
    # CA5 · La respuesta es plana para el front: sin empresa_id ni referencias internas.
    repo = RepositorioPropuestasEnMemoria([_propuesta()])
    http = _cliente_http(repo)

    item = http.get("/propuestas").json()[0]

    assert "empresa_id" not in item


def test_listar_sin_token_devuelve_401():
    # Sin sobrescribir `obtener_empresa_actual`: la auth real exige el Bearer.
    repo = RepositorioPropuestasEnMemoria([_propuesta()])
    app.dependency_overrides[obtener_repositorio_propuestas] = lambda: repo
    http = TestClient(app)

    r = http.get("/propuestas")

    assert r.status_code == 401
