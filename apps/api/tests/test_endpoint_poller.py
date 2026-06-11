"""Tests del poller interno POST /interno/poller/correo (T10/T11/T12).

T10 (CA3 e2e, mockeado): 1 integración con 2 correos → 2 solicitudes en su bandeja.
T11: con empresas A y B, cada solicitud lleva el empresa_id de SU integración (jamás
     se cruzan); si A falla el token, B se procesa igual (CA7 a nivel de poller).
T12: el endpoint sólo acepta la credencial de servicio (sin ella → 403; con ella → 200).
"""
import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_cliente_anthropic,
    obtener_fabrica_cliente_gmail,
    obtener_repositorio_integraciones_servicio,
    obtener_repositorio_solicitudes_servicio,
    obtener_secreto_poller,
)
from app.main import app
from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.repositorios.solicitudes import RepositorioSolicitudesEnMemoria
from app.rutas.interno import verificar_credencial_servicio
from app.servicios.gmail import MensajeCorreo
from tests.dobles import (
    ClienteAnthropicFake,
    ClienteGmailFake,
    ClienteGmailQueFallaAuth,
    FabricaClienteGmailFake,
)

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()
SECRETO = "secreto-poller-de-prueba"


def _integracion(empresa_id, cursor=None):
    return Integracion(
        id=uuid4(),
        empresa_id=empresa_id,
        proveedor="gmail",
        token_ref=f"secreto://gmail-{empresa_id}",
        casilla=f"casilla-{empresa_id}@x.cl",
        cursor=cursor,
        estado="conectado",
    )


def _mensaje(msg_id, **kwargs):
    base = dict(
        gmail_msg_id=msg_id,
        remitente="Alguien",
        correo_origen="a@x.cl",
        asunto="Asunto",
        cuerpo="Cuerpo",
    )
    base.update(kwargs)
    return MensajeCorreo(**base)


def _cliente_http(repo_integraciones, repo_solicitudes, fabrica, *, con_auth=False):
    app.dependency_overrides[obtener_repositorio_integraciones_servicio] = (
        lambda: repo_integraciones
    )
    app.dependency_overrides[obtener_repositorio_solicitudes_servicio] = (
        lambda: repo_solicitudes
    )
    app.dependency_overrides[obtener_fabrica_cliente_gmail] = lambda: fabrica
    # Mockea el clasificador (Haiku): el poller NO debe llamar a Anthropic real en
    # tests (CLAUDE.md §6). Devuelve una clasificación fija para cada correo.
    app.dependency_overrides[obtener_cliente_anthropic] = lambda: ClienteAnthropicFake(
        {"resumen": "Resumen de prueba", "tipo": "tipo_1"}
    )
    if con_auth:
        # Probamos la protección REAL: sólo inyectamos el secreto esperado.
        app.dependency_overrides[obtener_secreto_poller] = lambda: SECRETO
    else:
        # T10/T11: nos saltamos la auth para enfocar la lógica de ingesta.
        app.dependency_overrides[verificar_credencial_servicio] = lambda: None
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_poller_ingiere_dos_correos_en_una_bandeja():
    # T10 / CA3 extremo a extremo (mockeado).
    repo_int = RepositorioIntegracionesEnMemoria([_integracion(EMPRESA_A)])
    repo_sol = RepositorioSolicitudesEnMemoria([])
    fabrica = FabricaClienteGmailFake(
        {
            EMPRESA_A: ClienteGmailFake(
                [_mensaje("a-1"), _mensaje("a-2")], nuevo_cursor="cur-A"
            ),
        }
    )
    http = _cliente_http(repo_int, repo_sol, fabrica)

    r = http.post("/interno/poller/correo")

    assert r.status_code == 200
    assert r.json() == {"empresas_procesadas": 1, "solicitudes_creadas": 2}
    creadas = list(repo_sol._por_id.values())
    assert len(creadas) == 2
    assert all(s.empresa_id == EMPRESA_A for s in creadas)
    # El poller clasifica al ingerir (Haiku mockeado) → tipo + resumen poblados.
    assert all(s.tipo == "tipo_1" and s.estado == "nueva" for s in creadas)
    assert all(s.resumen == "Resumen de prueba" for s in creadas)


def test_poller_no_cruza_tenants_y_aisla_fallos():
    # T11: A falla el token; B se procesa igual; cada solicitud con su empresa_id.
    repo_int = RepositorioIntegracionesEnMemoria(
        [_integracion(EMPRESA_A), _integracion(EMPRESA_B)]
    )
    repo_sol = RepositorioSolicitudesEnMemoria([])
    fabrica = FabricaClienteGmailFake(
        {
            EMPRESA_A: ClienteGmailQueFallaAuth(),
            EMPRESA_B: ClienteGmailFake(
                [_mensaje("b-1"), _mensaje("b-2")], nuevo_cursor="cur-B"
            ),
        }
    )
    http = _cliente_http(repo_int, repo_sol, fabrica)

    r = http.post("/interno/poller/correo")

    assert r.status_code == 200
    # Ambas casillas se recorren; sólo B crea solicitudes.
    assert r.json() == {"empresas_procesadas": 2, "solicitudes_creadas": 2}
    creadas = list(repo_sol._por_id.values())
    assert {s.empresa_id for s in creadas} == {EMPRESA_B}  # A jamás aparece
    # A quedó 'reconectar' (CA7); B sigue 'conectado'.
    integ_a = asyncio.run(repo_int.obtener_por_empresa(EMPRESA_A))
    integ_b = asyncio.run(repo_int.obtener_por_empresa(EMPRESA_B))
    assert integ_a.estado == "reconectar"
    assert integ_b.estado == "conectado"


def test_poller_sin_credencial_de_servicio_devuelve_403():
    # T12: sin el header del secreto compartido, 403.
    repo_int = RepositorioIntegracionesEnMemoria([])
    repo_sol = RepositorioSolicitudesEnMemoria([])
    http = _cliente_http(repo_int, repo_sol, FabricaClienteGmailFake({}), con_auth=True)

    r = http.post("/interno/poller/correo")  # sin header

    assert r.status_code == 403


def test_poller_con_credencial_de_servicio_devuelve_200():
    # T12: con el header correcto, pasa.
    repo_int = RepositorioIntegracionesEnMemoria([])
    repo_sol = RepositorioSolicitudesEnMemoria([])
    http = _cliente_http(repo_int, repo_sol, FabricaClienteGmailFake({}), con_auth=True)

    r = http.post("/interno/poller/correo", headers={"X-Poller-Token": SECRETO})

    assert r.status_code == 200
    assert r.json() == {"empresas_procesadas": 0, "solicitudes_creadas": 0}


class _GmailRevienta:
    """Cliente Gmail que lanza un error NO-auth (p. ej. Secret Manager con un
    token_ref roto). La ingesta sólo atrapa el de auth, así que este sube al poller,
    que debe aislarlo (defensa en profundidad multi-tenant)."""

    async def listar_nuevos(self, cursor):
        raise RuntimeError("Secret Manager: token_ref inusable")


def test_poller_aisla_error_inesperado_y_no_revienta():
    # El caso real del token viejo tras migrar a Secret Manager: una empresa revienta
    # con un error inesperado → se marca 'reconectar' y se SIGUE con las demás (no 500).
    repo_int = RepositorioIntegracionesEnMemoria(
        [_integracion(EMPRESA_A), _integracion(EMPRESA_B)]
    )
    repo_sol = RepositorioSolicitudesEnMemoria([])
    fabrica = FabricaClienteGmailFake(
        {
            EMPRESA_A: _GmailRevienta(),
            EMPRESA_B: ClienteGmailFake([_mensaje("b-1")], nuevo_cursor="cur-B"),
        }
    )
    http = _cliente_http(repo_int, repo_sol, fabrica)

    r = http.post("/interno/poller/correo")

    assert r.status_code == 200  # NO 500 aunque A reviente
    assert r.json() == {"empresas_procesadas": 2, "solicitudes_creadas": 1}
    integ_a = asyncio.run(repo_int.obtener_por_empresa(EMPRESA_A))
    integ_b = asyncio.run(repo_int.obtener_por_empresa(EMPRESA_B))
    assert integ_a.estado == "reconectar"  # la que reventó
    assert integ_b.estado == "conectado"  # la sana sigue ok
