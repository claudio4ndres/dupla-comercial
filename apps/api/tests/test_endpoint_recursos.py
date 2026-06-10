"""Tests del endpoint GET /catalogo/recursos (panel "Recursos · Drive" del chat).

Lista los recursos del Drive de la empresa del usuario. Sólo de su empresa
(aislamiento multi-tenant). Todo se inyecta con dobles en memoria (cero red).

Comportamiento (Drive real v1):
* si la empresa tiene una integración Gmail/Google conectada, devuelve los NOMBRES
  REALES de los archivos de la carpeta del Drive (vía la fábrica de cliente Drive);
* si el Drive falla, o no hay integración/carpeta, cae al catálogo sembrado (los
  `origen` de la tabla `catalogo`) — el panel nunca se rompe.
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_empresa_actual,
    obtener_fabrica_cliente_drive,
    obtener_repositorio_catalogo,
    obtener_repositorio_integraciones,
)
from app.main import app
from app.repositorios.catalogo import ItemCatalogo, RepositorioCatalogoEnMemoria
from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.servicios.drive_real import ArchivoDrive
from app.servicios.gmail import ErrorAutenticacionGmail

EMPRESA_A = uuid4()


def _item(origen, empresa_id=EMPRESA_A):
    return ItemCatalogo(id=uuid4(), empresa_id=empresa_id, nombre="x", origen=origen)


def _integracion(empresa_id=EMPRESA_A):
    return Integracion(
        id=uuid4(), empresa_id=empresa_id, proveedor="gmail",
        token_ref="secreto://refresh", casilla="hola@capsulab.cl",
    )


class _ClienteDriveFalso:
    """Doble del cliente Drive: devuelve archivos fijos o levanta un error."""

    def __init__(self, *, archivos=None, error: Exception | None = None):
        self._archivos = archivos or []
        self._error = error

    async def listar_archivos(self, folder_id: str):
        if self._error is not None:
            raise self._error
        return list(self._archivos)


class _FabricaDriveFalsa:
    """Doble de `FabricaClienteDriveReal`: arma el cliente falso por integración."""

    def __init__(self, cliente):
        self._cliente = cliente

    def crear(self, integracion):
        return self._cliente


def _cliente_http(
    repo, *, empresa_id=EMPRESA_A, integraciones=None, fabrica_drive=None
):
    app.dependency_overrides[obtener_repositorio_catalogo] = lambda: repo
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    app.dependency_overrides[obtener_repositorio_integraciones] = (
        lambda: integraciones or RepositorioIntegracionesEnMemoria([])
    )
    if fabrica_drive is not None:
        app.dependency_overrides[obtener_fabrica_cliente_drive] = lambda: fabrica_drive
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


# --- Sin integración: cae al catálogo sembrado (comportamiento previo) ---------

def test_recursos_sin_integracion_devuelve_los_origenes_del_catalogo():
    repo = RepositorioCatalogoEnMemoria(
        [_item("Tarifario.xlsx"), _item("PRODUCCIÓN 3D"), _item("Tarifario.xlsx")]
    )
    http = _cliente_http(repo)  # sin integración Gmail conectada

    r = http.get("/catalogo/recursos")

    assert r.status_code == 200
    cuerpo = r.json()
    assert isinstance(cuerpo, list)
    assert set(cuerpo) == {"PRODUCCIÓN 3D", "Tarifario.xlsx"}


def test_recursos_sin_catalogo_ni_integracion_devuelve_lista_vacia():
    http = _cliente_http(RepositorioCatalogoEnMemoria([]))

    r = http.get("/catalogo/recursos")

    assert r.status_code == 200
    assert r.json() == []


# --- Con integración: nombres REALES de la carpeta del Drive ------------------

def test_recursos_con_drive_conectado_devuelve_nombres_reales():
    # El catálogo trae OTROS nombres: si saliera el catálogo, el test fallaría.
    repo = RepositorioCatalogoEnMemoria([_item("Sembrado.xlsx")])
    drive = _ClienteDriveFalso(
        archivos=[
            ArchivoDrive(id="f1", nombre="Tarifario 2026.xlsx",
                         tipo_mime="application/vnd.google-apps.spreadsheet"),
            ArchivoDrive(id="f2", nombre="Casos BTL",
                         tipo_mime="application/vnd.google-apps.folder"),
        ]
    )
    http = _cliente_http(
        repo,
        integraciones=RepositorioIntegracionesEnMemoria([_integracion()]),
        fabrica_drive=_FabricaDriveFalsa(drive),
    )

    r = http.get("/catalogo/recursos")

    assert r.status_code == 200
    assert r.json() == ["Tarifario 2026.xlsx", "Casos BTL"]


def test_recursos_drive_vacio_devuelve_lista_vacia():
    # Carpeta del Drive vacía → lista vacía (NO cae al catálogo: el Drive respondió).
    repo = RepositorioCatalogoEnMemoria([_item("Sembrado.xlsx")])
    http = _cliente_http(
        repo,
        integraciones=RepositorioIntegracionesEnMemoria([_integracion()]),
        fabrica_drive=_FabricaDriveFalsa(_ClienteDriveFalso(archivos=[])),
    )

    r = http.get("/catalogo/recursos")

    assert r.status_code == 200
    assert r.json() == []


# --- Resiliencia: si el Drive falla, cae al catálogo sembrado -----------------

def test_recursos_drive_falla_cae_al_catalogo():
    repo = RepositorioCatalogoEnMemoria([_item("Tarifario.xlsx"), _item("Casos")])
    drive = _ClienteDriveFalso(error=ErrorAutenticacionGmail("token revocado"))
    http = _cliente_http(
        repo,
        integraciones=RepositorioIntegracionesEnMemoria([_integracion()]),
        fabrica_drive=_FabricaDriveFalsa(drive),
    )

    r = http.get("/catalogo/recursos")

    assert r.status_code == 200  # el panel NO se rompe
    assert set(r.json()) == {"Casos", "Tarifario.xlsx"}
