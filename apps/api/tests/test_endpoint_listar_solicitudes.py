"""Tests del endpoint GET /solicitudes (lista la bandeja de la empresa).

El front necesita leer las solicitudes reales (las que el poller ingirió desde
Gmail) en vez del mock. Este endpoint devuelve SÓLO las solicitudes de la empresa
del usuario (aislamiento multi-tenant, T4) con la forma canónica en español
(`tipo_1`/`tipo_2`/`sin_clasificar`); el front mapea a sus códigos de UI.

El repositorio y la empresa del usuario se inyectan vía `dependency_overrides` con
dobles en memoria (CA6: cero llamadas reales).
"""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_empresa_actual,
    obtener_repositorio_solicitudes,
)
from app.main import app
from app.repositorios.solicitudes import RepositorioSolicitudesEnMemoria, Solicitud

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def _cliente_http(repo, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_repositorio_solicitudes] = lambda: repo
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def _solicitud(**kwargs):
    base = dict(
        id=uuid4(),
        empresa_id=EMPRESA_A,
        remitente="Zona Espiga",
        correo_origen="hola@zonaespiga.cl",
        asunto="Cotización sopaipillas",
        cuerpo="Hola Javo, cotizar sopaipillas afuera del Metro.",
    )
    base.update(kwargs)
    return Solicitud(**base)


def test_listar_devuelve_las_solicitudes_de_la_empresa():
    sol1 = _solicitud(asunto="Sopaipillas")
    sol2 = _solicitud(asunto="Fórmula 1", tipo="tipo_2", resumen="Idear campaña.")
    repo = RepositorioSolicitudesEnMemoria([sol1, sol2])
    http = _cliente_http(repo)

    r = http.get("/solicitudes")

    assert r.status_code == 200
    cuerpo = r.json()
    assert isinstance(cuerpo, list)
    assert len(cuerpo) == 2
    asuntos = {item["asunto"] for item in cuerpo}
    assert asuntos == {"Sopaipillas", "Fórmula 1"}
    # La forma canónica en español viaja tal cual; el front la mapea a t1/t2/new.
    item = next(i for i in cuerpo if i["asunto"] == "Fórmula 1")
    assert item["tipo"] == "tipo_2"
    assert item["resumen"] == "Idear campaña."
    assert item["correo_origen"] == "hola@zonaespiga.cl"
    assert "cuerpo" in item
    assert "id" in item


def test_listar_expone_la_fecha_de_recepcion_como_iso():
    # El front pinta la hora de cada correo: el endpoint debe exponer `creado_en`
    # de la tabla `solicitudes` como `recibido_en` en ISO 8601 (string).
    creado = datetime(2026, 6, 9, 12, 30, tzinfo=timezone.utc)
    sol = _solicitud(creado_en=creado)
    repo = RepositorioSolicitudesEnMemoria([sol])
    http = _cliente_http(repo)

    item = http.get("/solicitudes").json()[0]

    assert item["recibido_en"] == creado.isoformat()


def test_listar_sin_fecha_devuelve_recibido_en_nulo():
    # Si una fila no trae `creado_en` (p. ej. el doble en memoria), el campo viaja
    # como null y el front lo deja en blanco; nunca rompe la bandeja.
    sol = _solicitud()
    repo = RepositorioSolicitudesEnMemoria([sol])
    http = _cliente_http(repo)

    item = http.get("/solicitudes").json()[0]

    assert item["recibido_en"] is None


def test_listar_solo_devuelve_solicitudes_de_la_empresa_actual():
    # T4 · Aislamiento multi-tenant: la empresa A no ve las solicitudes de la B.
    sol_a = _solicitud(empresa_id=EMPRESA_A, asunto="De A")
    sol_b = _solicitud(empresa_id=EMPRESA_B, asunto="De B")
    repo = RepositorioSolicitudesEnMemoria([sol_a, sol_b])
    http = _cliente_http(repo, empresa_id=EMPRESA_A)

    r = http.get("/solicitudes")

    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo) == 1
    assert cuerpo[0]["asunto"] == "De A"


def test_listar_sin_solicitudes_devuelve_lista_vacia():
    repo = RepositorioSolicitudesEnMemoria([])
    http = _cliente_http(repo)

    r = http.get("/solicitudes")

    assert r.status_code == 200
    assert r.json() == []


def test_listar_nunca_expone_empresa_id_ni_token():
    # CA5 · La respuesta es plana para el front: sin empresa_id ni referencias internas.
    sol = _solicitud()
    repo = RepositorioSolicitudesEnMemoria([sol])
    http = _cliente_http(repo)

    item = http.get("/solicitudes").json()[0]

    assert "empresa_id" not in item
    assert "token_ref" not in item
