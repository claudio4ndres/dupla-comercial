"""Diagnóstico READ-ONLY de Drive: POST /interno/drive/diagnostico (interno).

Endpoint service-to-service (X-Poller-Token, como el poller) que comprueba si el
token de Google de una empresa TIENE acceso a Drive, sin escribir nada. Todo
mockeado vía `app.dependency_overrides`: cero red, cero credenciales reales (CLAUDE.md
§6). Verifica:

* con integración gmail + cliente que lista 2 carpetas → 200, `acceso=True`, 2 carpetas;
* sin integración gmail conectada → `acceso=False` y `motivo` con "sin integración";
* si el cliente Drive revienta (p.ej. 403 de scope) → `acceso=False` y `motivo` con el
  tipo del error (para distinguir un problema de permisos de otros fallos);
* sin el header `X-Poller-Token` → 403 (sólo Cloud Scheduler / service-to-service, T12).
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_fabrica_cliente_drive,
    obtener_repositorio_integraciones_servicio,
    obtener_secreto_poller,
)
from app.main import app
from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.rutas.interno import verificar_credencial_servicio
from app.servicios.drive_real import ArchivoDrive

EMPRESA = uuid4()
SECRETO = "secreto-poller-de-prueba"


def _integracion_gmail(empresa_id):
    return Integracion(
        id=uuid4(),
        empresa_id=empresa_id,
        proveedor="gmail",
        token_ref=f"secreto://gmail-{empresa_id}",
        casilla=f"casilla-{empresa_id}@x.cl",
        estado="conectado",
    )


class _ClienteDriveFake:
    """Doble del `ClienteDriveReal`: devuelve carpetas fijas (cero red)."""

    def __init__(self, carpetas):
        self._carpetas = carpetas

    async def listar_carpetas(self):
        return self._carpetas


class _ClienteDriveQueRevienta:
    """Doble que simula un Drive sin acceso (p.ej. 403 de scope)."""

    async def listar_carpetas(self):
        raise RuntimeError("403 Forbidden: insufficientPermissions")


class _FabricaDriveFake:
    """Doble de la fábrica: ignora la integración y entrega el cliente que se le pasó."""

    def __init__(self, cliente):
        self._cliente = cliente

    def crear(self, integracion):
        return self._cliente


def _cliente_http(repo_integraciones, fabrica_drive, *, con_auth=False):
    app.dependency_overrides[obtener_repositorio_integraciones_servicio] = (
        lambda: repo_integraciones
    )
    app.dependency_overrides[obtener_fabrica_cliente_drive] = lambda: fabrica_drive
    if con_auth:
        # Probamos la protección REAL: sólo inyectamos el secreto esperado.
        app.dependency_overrides[obtener_secreto_poller] = lambda: SECRETO
    else:
        # Nos saltamos la auth para enfocar la lógica del diagnóstico.
        app.dependency_overrides[verificar_credencial_servicio] = lambda: None
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_diagnostico_con_acceso_devuelve_las_carpetas():
    repo_int = RepositorioIntegracionesEnMemoria([_integracion_gmail(EMPRESA)])
    fabrica = _FabricaDriveFake(
        _ClienteDriveFake(
            [
                ArchivoDrive(
                    id="carpeta-1",
                    nombre="Capsulab · Operaciones",
                    tipo_mime="application/vnd.google-apps.folder",
                ),
                ArchivoDrive(
                    id="carpeta-2",
                    nombre="Tarifarios",
                    tipo_mime="application/vnd.google-apps.folder",
                ),
            ]
        )
    )
    http = _cliente_http(repo_int, fabrica)

    r = http.post(f"/interno/drive/diagnostico?empresa_id={EMPRESA}")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["acceso"] is True
    assert cuerpo["motivo"] is None
    assert cuerpo["carpetas"] == [
        {"id": "carpeta-1", "nombre": "Capsulab · Operaciones"},
        {"id": "carpeta-2", "nombre": "Tarifarios"},
    ]


def test_diagnostico_sin_integracion_gmail_no_tiene_acceso():
    repo_int = RepositorioIntegracionesEnMemoria([])  # sin integración gmail
    fabrica = _FabricaDriveFake(_ClienteDriveFake([]))
    http = _cliente_http(repo_int, fabrica)

    r = http.post(f"/interno/drive/diagnostico?empresa_id={EMPRESA}")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["acceso"] is False
    assert "sin integración" in cuerpo["motivo"]
    assert cuerpo["carpetas"] == []


def test_diagnostico_cliente_que_revienta_reporta_el_error_sin_acceso():
    repo_int = RepositorioIntegracionesEnMemoria([_integracion_gmail(EMPRESA)])
    fabrica = _FabricaDriveFake(_ClienteDriveQueRevienta())
    http = _cliente_http(repo_int, fabrica)

    r = http.post(f"/interno/drive/diagnostico?empresa_id={EMPRESA}")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["acceso"] is False
    # El motivo trae el tipo del error → distingue un 403 de scope de otros fallos.
    assert "RuntimeError" in cuerpo["motivo"]
    assert cuerpo["carpetas"] == []


def test_diagnostico_sin_credencial_de_servicio_devuelve_403():
    repo_int = RepositorioIntegracionesEnMemoria([_integracion_gmail(EMPRESA)])
    fabrica = _FabricaDriveFake(_ClienteDriveFake([]))
    http = _cliente_http(repo_int, fabrica, con_auth=True)

    r = http.post(f"/interno/drive/diagnostico?empresa_id={EMPRESA}")  # sin header

    assert r.status_code == 403
