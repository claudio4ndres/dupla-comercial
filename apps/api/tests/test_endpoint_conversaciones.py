"""Tests del endpoint POST /conversaciones/responder (003 + 005).

CA5: 200 con `{ texto, componentes, fuentes }` usando el cliente Anthropic mockeado.
CA4: si el LLM cae, el endpoint responde 502 (nunca un 500 crudo). 005: el endpoint
ahora **requiere auth** (la empresa se resuelve del JWT, porque Javo consulta el
catálogo del Drive con RLS) → sin token, 401.

Todo se inyecta vía `dependency_overrides` (regla #3: cero red, cero tokens).
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_cliente_anthropic,
    obtener_cliente_drive_conversacion,
    obtener_empresa_actual,
    obtener_proveedor_busqueda,
    obtener_repositorio_catalogo,
)
from app.main import app
from app.repositorios.catalogo import RepositorioCatalogoEnMemoria
from app.servicios.busqueda_internet import ProveedorBusquedaCurado
from tests.dobles import (
    ClienteAnthropicGuionFake,
    ClienteAnthropicQueFalla,
    ClienteAnthropicTextoFake,
    respuesta_texto,
    respuesta_tool_use,
)

EMPRESA = uuid4()


class _ArchivoFake:
    def __init__(self, id, nombre, tipo_mime):
        self.id = id
        self.nombre = nombre
        self.tipo_mime = tipo_mime


class _DriveFake:
    """Doble del ClienteDriveReal para el endpoint: registra las consultas."""

    def __init__(self, archivos=None):
        self._archivos = archivos or []
        self.consultas: list = []

    async def buscar_archivos(self, consulta):
        self.consultas.append(consulta)
        return list(self._archivos)

    async def leer_documento(self, file_id, tipo_mime):
        return ""


def _cliente_http(anthropic, *, con_empresa=True, drive=None):
    app.dependency_overrides[obtener_cliente_anthropic] = lambda: anthropic
    app.dependency_overrides[obtener_repositorio_catalogo] = (
        lambda: RepositorioCatalogoEnMemoria([])
    )
    app.dependency_overrides[obtener_proveedor_busqueda] = lambda: ProveedorBusquedaCurado()
    app.dependency_overrides[obtener_cliente_drive_conversacion] = lambda: drive
    if con_empresa:
        app.dependency_overrides[obtener_empresa_actual] = lambda: EMPRESA
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def _payload(tipo="t1"):
    return {
        "solicitud_id": "demo-1",
        "tipo": tipo,
        "mensajes": [
            {"rol": "javo", "contenido": "¡Hola! Leí el correo de Zona Espiga."},
            {"rol": "usuario", "contenido": "Son 3 días de activación"},
        ],
    }


def test_responder_devuelve_200_con_texto():
    # CA5: con el cliente mockeado, el endpoint responde 200 con la forma enriquecida.
    anthropic = ClienteAnthropicTextoFake("Perfecto, dejo catering + 2 promotores...")
    http = _cliente_http(anthropic)

    r = http.post(
        "/conversaciones/responder", json=_payload(), headers={"Authorization": "Bearer x"}
    )

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["texto"] == "Perfecto, dejo catering + 2 promotores..."
    assert cuerpo["componentes"] == [] and cuerpo["fuentes"] == []
    assert len(anthropic.llamadas) == 1


def test_error_del_llm_devuelve_502():
    # CA4: si el cliente Anthropic cae, el endpoint responde 502 (no un 500 crudo).
    http = _cliente_http(ClienteAnthropicQueFalla())

    r = http.post(
        "/conversaciones/responder", json=_payload(), headers={"Authorization": "Bearer x"}
    )

    assert r.status_code == 502


def test_sin_token_devuelve_401():
    # 005: el endpoint pasa a requerir auth (la empresa sale del JWT para la RLS).
    http = _cliente_http(ClienteAnthropicTextoFake(), con_empresa=False)

    r = http.post("/conversaciones/responder", json=_payload())  # sin Authorization

    assert r.status_code == 401


def test_endpoint_cablea_el_drive_real_a_javo():
    # Wiring: el endpoint construye el cliente Drive de la empresa y se lo pasa a Javo,
    # así `buscar_en_drive` consulta el DRIVE REAL (no la tabla catalogo).
    drive = _DriveFake(
        archivos=[
            _ArchivoFake("doc1", "Tarifario 2026",
                         "application/vnd.google-apps.document")
        ]
    )
    anthropic = ClienteAnthropicGuionFake(
        [
            respuesta_tool_use("buscar_en_drive", {"consulta": "tarifario"}),
            respuesta_texto("Encontré el tarifario en tu Drive."),
        ]
    )
    http = _cliente_http(anthropic, drive=drive)

    r = http.post(
        "/conversaciones/responder", json=_payload(), headers={"Authorization": "Bearer x"}
    )

    assert r.status_code == 200
    assert r.json()["texto"] == "Encontré el tarifario en tu Drive."
    assert drive.consultas == ["tarifario"]  # Javo buscó en el Drive REAL


def test_endpoint_sin_drive_no_rompe():
    # Empresa sin integración Gmail/Drive: la dependencia devuelve None y el endpoint
    # responde igual (las tools de Drive degradan limpio dentro de Javo).
    anthropic = ClienteAnthropicTextoFake("Pásame el valor; no tengo el Drive conectado.")
    http = _cliente_http(anthropic, drive=None)

    r = http.post(
        "/conversaciones/responder", json=_payload(), headers={"Authorization": "Bearer x"}
    )

    assert r.status_code == 200
    assert r.json()["texto"] == "Pásame el valor; no tengo el Drive conectado."
