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
    obtener_repositorio_conversaciones,
    obtener_repositorio_propuestas,
    obtener_repositorio_solicitudes,
)
from app.main import app
from app.repositorios.conversaciones import RepositorioConversacionesEnMemoria
from app.repositorios.propuestas import (
    ComponentePropuesta,
    Propuesta,
    RepositorioPropuestasEnMemoria,
    TareaPropuesta,
)
from app.repositorios.solicitudes import RepositorioSolicitudesEnMemoria, Solicitud

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def _cliente_http(repo, empresa_id=EMPRESA_A, repo_sol=None):
    app.dependency_overrides[obtener_repositorio_propuestas] = lambda: repo
    # Una ÚNICA conversación en memoria reutilizada entre requests: así dos POST a la
    # misma solicitud caen sobre la MISMA conversación (clave de la idempotencia de #4).
    conversaciones = RepositorioConversacionesEnMemoria()
    app.dependency_overrides[obtener_repositorio_conversaciones] = lambda: conversaciones
    app.dependency_overrides[obtener_repositorio_solicitudes] = (
        lambda: repo_sol if repo_sol is not None else RepositorioSolicitudesEnMemoria()
    )
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
                proveedor="ISABEL",
                cantidad=6,
                dias=4,
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
    assert cuerpo["componentes"][0]["proveedor"] == "ISABEL"
    assert cuerpo["componentes"][0]["dias"] == 4
    assert cuerpo["tareas"][0]["grupo"] == "RRHH"
    assert cuerpo["tareas"][0]["vencimiento"] == "3 días"


def test_post_persiste_la_propuesta_que_armo_javo():
    # Write-path (gap bloqueante de la auditoría): 'Generar propuesta' PERSISTE los
    # componentes + tareas que Javo armó en el chat. Antes sólo hacía GET → 404 con
    # datos reales; ahora la conversación baja a una propuesta real.
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([])
    http = _cliente_http(repo)

    r = http.post(
        f"/solicitudes/{sol}/propuesta",
        json={
            "tipo": "t1",
            "componentes": [
                {
                    "nombre": "Promotoras",
                    "detalle": "3 tiendas",
                    "cantidad": 6,
                    "dias": 3,
                    "valor_unitario": 240000,
                    "proveedor": "Eventos Pro",
                }
            ],
            "tareas": [
                {"nombre": "Reclutar 6 promotoras", "area": "RRHH", "plazo": "3 días"}
            ],
        },
    )

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado"] == "borrador"
    assert cuerpo["total"] == 6 * 3 * 240000  # cantidad × días × valor
    assert cuerpo["componentes"][0]["proveedor"] == "Eventos Pro"
    assert cuerpo["componentes"][0]["dias"] == 3
    assert cuerpo["tareas"][0]["grupo"] == "RRHH"  # area → grupo
    assert cuerpo["tareas"][0]["vencimiento"] == "3 días"  # plazo → vencimiento
    assert "empresa_id" not in cuerpo  # CA5

    # Y queda PERSISTIDA: el GET ahora la devuelve (antes daba 404 con datos reales).
    g = http.get(f"/solicitudes/{sol}/propuesta")
    assert g.status_code == 200
    assert g.json()["total"] == 6 * 3 * 240000


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


# ── #4 · idempotencia (clic doble en "Generar propuesta") ────────────────────
def _cuerpo_crear():
    return {
        "tipo": "t1",
        "componentes": [
            {"nombre": "Promotoras", "cantidad": 6, "dias": 3, "valor_unitario": 240000}
        ],
        "tareas": [{"nombre": "Reclutar promotoras", "area": "RRHH"}],
    }


def test_post_dos_veces_no_duplica_la_propuesta():
    # #4 (Sev ALTA) · dos clics seguidos en "Generar propuesta" sobre la MISMA solicitud
    # NO deben crear 2 propuestas: la segunda reemplaza a la primera (misma conversación).
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([])
    http = _cliente_http(repo)

    r1 = http.post(f"/solicitudes/{sol}/propuesta", json=_cuerpo_crear())
    r2 = http.post(f"/solicitudes/{sol}/propuesta", json=_cuerpo_crear())

    assert r1.status_code == 200
    assert r2.status_code == 200
    # La lista de la empresa tiene UNA sola propuesta para esa solicitud (no dos).
    propuestas = http.get("/propuestas").json()
    de_la_sol = [p for p in propuestas if p["solicitud_id"] == str(sol)]
    assert len(de_la_sol) == 1


# ── #7 · ciclo de vida ───────────────────────────────────────────────────────
def test_crear_propuesta_avanza_estado_de_la_solicitud_a_propuesta():
    # #7 · al generar la propuesta, la solicitud avanza de 'nueva' a 'propuesta'.
    sol_id = uuid4()
    repo = RepositorioPropuestasEnMemoria([])
    repo_sol = RepositorioSolicitudesEnMemoria(
        [Solicitud(id=sol_id, empresa_id=EMPRESA_A, cuerpo="x", estado="nueva")]
    )
    http = _cliente_http(repo, repo_sol=repo_sol)

    r = http.post(f"/solicitudes/{sol_id}/propuesta", json=_cuerpo_crear())

    assert r.status_code == 200
    actualizada = repo_sol.por_id(sol_id)
    assert actualizada.estado == "propuesta"


def test_patch_estado_aprueba_la_propuesta():
    # #7 · transición válida borrador→aprobada vía PATCH /solicitudes/{id}/propuesta/estado.
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    http = _cliente_http(repo)

    r = http.patch(f"/solicitudes/{sol}/propuesta/estado", json={"estado": "aprobada"})

    assert r.status_code == 200
    assert r.json()["estado"] == "aprobada"
    # Y queda persistida: el GET la devuelve ya aprobada.
    assert http.get(f"/solicitudes/{sol}/propuesta").json()["estado"] == "aprobada"


def test_patch_estado_transicion_invalida_es_409():
    # #7 · no se puede saltar de borrador directo a enviada (hay que aprobar primero).
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    http = _cliente_http(repo)

    r = http.patch(f"/solicitudes/{sol}/propuesta/estado", json={"estado": "enviada"})

    assert r.status_code == 409


def test_patch_estado_valor_no_valido_es_422():
    # #7 · un estado fuera del enum (borrador|aprobada|enviada) lo rechaza Pydantic.
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    http = _cliente_http(repo)

    r = http.patch(f"/solicitudes/{sol}/propuesta/estado", json={"estado": "cancelada"})

    assert r.status_code == 422


def test_patch_estado_sin_propuesta_es_404():
    # #7 · transicionar una solicitud sin propuesta → 404.
    repo = RepositorioPropuestasEnMemoria([])
    http = _cliente_http(repo)

    r = http.patch(f"/solicitudes/{uuid4()}/propuesta/estado", json={"estado": "aprobada"})

    assert r.status_code == 404


def test_patch_estado_aislamiento_no_toca_propuesta_de_otra_empresa():
    # La propuesta es de la empresa B; el usuario es de la A → 404 (no la ve ni la mueve).
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol, empresa_id=EMPRESA_B)])
    http = _cliente_http(repo, empresa_id=EMPRESA_A)

    r = http.patch(f"/solicitudes/{sol}/propuesta/estado", json={"estado": "aprobada"})

    assert r.status_code == 404
