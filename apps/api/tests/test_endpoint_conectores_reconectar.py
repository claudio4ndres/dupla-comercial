"""Spec 010 · CA3 · GET /interno/conectores/reconectar (observabilidad del operador).

Endpoint INTERNO (service-to-service, protegido por `verificar_credencial_servicio`)
que lista las integraciones en `estado='reconectar'` para que el operador se entere sin
mirar filas a mano. Decisión #1 del Gerente TI: endpoint interno (opción a).

Invariantes (CA3/CA7):
* devuelve SÓLO las 'reconectar', cada una con {empresa_id, proveedor, estado};
* NUNCA expone `token_ref` ni datos de negocio (lo garantiza el `response_model`);
* sin la credencial de servicio → 403.
Todo mockeado (cero red, cero credenciales reales — CA8).
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_repositorio_integraciones_servicio,
    obtener_secreto_poller,
)
from app.main import app
from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.rutas.interno import verificar_credencial_servicio

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()
SECRETO = "secreto-poller-de-prueba"


def _integ(proveedor, empresa_id, estado):
    return Integracion(
        id=uuid4(),
        empresa_id=empresa_id,
        proveedor=proveedor,
        token_ref=f"secreto://{proveedor}-{empresa_id}",  # NO debe salir nunca
        casilla=f"casilla-{empresa_id}@x.cl",
        estado=estado,
    )


def _cliente_http(repo_integraciones, *, con_auth=False):
    app.dependency_overrides[obtener_repositorio_integraciones_servicio] = (
        lambda: repo_integraciones
    )
    if con_auth:
        app.dependency_overrides[obtener_secreto_poller] = lambda: SECRETO
    else:
        app.dependency_overrides[verificar_credencial_servicio] = lambda: None
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_lista_solo_las_reconectar_con_empresa_proveedor_y_estado():
    repo = RepositorioIntegracionesEnMemoria(
        [
            _integ("gmail", EMPRESA_A, "reconectar"),
            _integ("clickup", EMPRESA_A, "conectado"),  # NO debe aparecer
            _integ("gmail", EMPRESA_B, "conectado"),    # NO debe aparecer
            _integ("clickup", EMPRESA_B, "reconectar"),
        ]
    )
    http = _cliente_http(repo)

    r = http.get("/interno/conectores/reconectar")

    assert r.status_code == 200
    cuerpo = r.json()
    # Sólo las 'reconectar'.
    claves = {(i["empresa_id"], i["proveedor"]) for i in cuerpo}
    assert claves == {
        (str(EMPRESA_A), "gmail"),
        (str(EMPRESA_B), "clickup"),
    }
    assert all(i["estado"] == "reconectar" for i in cuerpo)


def test_no_expone_token_ref_ni_datos_de_negocio():
    # Aislamiento (CA7): la señal jamás incluye el token ni la casilla.
    repo = RepositorioIntegracionesEnMemoria(
        [_integ("gmail", EMPRESA_A, "reconectar")]
    )
    http = _cliente_http(repo)

    r = http.get("/interno/conectores/reconectar")

    assert r.status_code == 200
    item = r.json()[0]
    assert set(item.keys()) == {"empresa_id", "proveedor", "estado"}
    assert "token_ref" not in item
    assert "casilla" not in item
    # Defensa extra: el token jamás aparece en el cuerpo crudo.
    assert "secreto://" not in r.text


def test_sin_reconectar_devuelve_lista_vacia():
    repo = RepositorioIntegracionesEnMemoria(
        [_integ("gmail", EMPRESA_A, "conectado")]
    )
    http = _cliente_http(repo)

    r = http.get("/interno/conectores/reconectar")

    assert r.status_code == 200
    assert r.json() == []


def test_sin_credencial_de_servicio_devuelve_403():
    repo = RepositorioIntegracionesEnMemoria(
        [_integ("gmail", EMPRESA_A, "reconectar")]
    )
    http = _cliente_http(repo, con_auth=True)

    r = http.get("/interno/conectores/reconectar")  # sin header

    assert r.status_code == 403
