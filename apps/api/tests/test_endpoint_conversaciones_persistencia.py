"""T13 · Persistencia del chat con Javo en los endpoints de conversación.

Cubre el endpoint NUEVO `GET /conversaciones/{solicitud_id}` (lee el hilo de la
empresa del usuario, RLS) y el cambio en `POST /conversaciones/responder` (ahora
PERSISTE el turno del usuario + la respuesta de Javo). Todo se inyecta con dobles en
memoria vía `dependency_overrides` (regla #3: cero red, cero tokens).
"""
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_cliente_anthropic,
    obtener_cliente_drive_conversacion,
    obtener_empresa_actual,
    obtener_proveedor_busqueda,
    obtener_repositorio_catalogo,
    obtener_repositorio_conversaciones,
)
from app.main import app
from app.repositorios.catalogo import RepositorioCatalogoEnMemoria
from app.repositorios.conversaciones import RepositorioConversacionesEnMemoria
from app.servicios.busqueda_internet import ProveedorBusquedaCurado
from tests.dobles import (
    ClienteAnthropicGuionFake,
    ClienteAnthropicTextoFake,
    respuesta_texto,
    respuesta_tool_use,
)

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def _cliente_http(repo, *, anthropic=None, empresa_id=EMPRESA_A, con_empresa=True):
    app.dependency_overrides[obtener_repositorio_conversaciones] = lambda: repo
    app.dependency_overrides[obtener_cliente_anthropic] = (
        lambda: anthropic or ClienteAnthropicTextoFake()
    )
    app.dependency_overrides[obtener_repositorio_catalogo] = (
        lambda: RepositorioCatalogoEnMemoria([])
    )
    app.dependency_overrides[obtener_proveedor_busqueda] = lambda: ProveedorBusquedaCurado()
    # Sin Drive cableado en estos tests (foco en la persistencia): None → las tools de
    # Drive degradan limpio dentro de Javo (no se toca Supabase/red).
    app.dependency_overrides[obtener_cliente_drive_conversacion] = lambda: None
    if con_empresa:
        app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


# ── GET /conversaciones/{solicitud_id} ───────────────────────────────────────
def test_get_sin_conversacion_devuelve_lista_vacia():
    repo = RepositorioConversacionesEnMemoria()
    http = _cliente_http(repo)

    r = http.get(f"/conversaciones/{uuid4()}", headers={"Authorization": "Bearer x"})

    assert r.status_code == 200
    assert r.json() == []


async def test_get_devuelve_los_mensajes_guardados_en_orden():
    sol = uuid4()
    repo = RepositorioConversacionesEnMemoria()
    await repo.guardar_turnos(
        sol,
        EMPRESA_A,
        "t1",
        [
            {"rol": "usuario", "contenido": "Son 3 días"},
            {"rol": "javo", "contenido": "Perfecto, dejo catering."},
        ],
    )
    http = _cliente_http(repo)

    r = http.get(f"/conversaciones/{sol}", headers={"Authorization": "Bearer x"})

    assert r.status_code == 200
    assert r.json() == [
        {"rol": "usuario", "contenido": "Son 3 días"},
        {"rol": "javo", "contenido": "Perfecto, dejo catering."},
    ]


def test_get_sin_token_devuelve_401():
    repo = RepositorioConversacionesEnMemoria()
    http = _cliente_http(repo, con_empresa=False)

    r = http.get(f"/conversaciones/{uuid4()}")  # sin Authorization

    assert r.status_code == 401


async def test_get_no_ve_la_conversacion_de_otra_empresa():
    # El hilo es de la empresa B; el usuario es de la A → no lo ve (emula RLS).
    sol = uuid4()
    repo = RepositorioConversacionesEnMemoria()
    await repo.guardar_turnos(sol, EMPRESA_B, "t1", [{"rol": "usuario", "contenido": "privado"}])
    http = _cliente_http(repo, empresa_id=EMPRESA_A)

    r = http.get(f"/conversaciones/{sol}", headers={"Authorization": "Bearer x"})

    assert r.status_code == 200
    assert r.json() == []


# ── POST /conversaciones/responder (ahora persiste) ──────────────────────────
def _payload(solicitud_id, tipo="t1"):
    return {
        "solicitud_id": solicitud_id,
        "tipo": tipo,
        "mensajes": [
            {"rol": "javo", "contenido": "¡Hola! Leí el correo."},
            {"rol": "usuario", "contenido": "Son 3 días de activación"},
        ],
    }


async def test_responder_persiste_el_turno_del_usuario_y_de_javo():
    sol = str(uuid4())
    repo = RepositorioConversacionesEnMemoria()
    anthropic = ClienteAnthropicTextoFake("Perfecto, dejo catering + 2 promotores.")
    http = _cliente_http(repo, anthropic=anthropic)

    r = http.post(
        "/conversaciones/responder",
        json=_payload(sol),
        headers={"Authorization": "Bearer x"},
    )

    # El contrato de respuesta NO cambia: sigue devolviendo el texto de Javo.
    assert r.status_code == 200
    assert r.json()["texto"] == "Perfecto, dejo catering + 2 promotores."

    # El último mensaje del usuario y la respuesta de Javo quedaron persistidos.
    guardados = await repo.obtener_mensajes(UUID(sol), EMPRESA_A)
    assert [(m.rol, m.contenido) for m in guardados] == [
        ("usuario", "Son 3 días de activación"),
        ("javo", "Perfecto, dejo catering + 2 promotores."),
    ]


async def test_responder_sin_solicitud_id_no_persiste_pero_responde():
    repo = RepositorioConversacionesEnMemoria()
    anthropic = ClienteAnthropicTextoFake("Respuesta sin estado.")
    http = _cliente_http(repo, anthropic=anthropic)

    payload = _payload(None)
    r = http.post(
        "/conversaciones/responder", json=payload, headers={"Authorization": "Bearer x"}
    )

    assert r.status_code == 200
    assert r.json()["texto"] == "Respuesta sin estado."
    # Sin solicitud_id no hay dónde persistir: el repo queda vacío.
    assert await repo.obtener_mensajes(uuid4(), EMPRESA_A) == []


# ── Persistencia del BORRADOR de la cotización (0009) ─────────────────────────
def _cliente_http_guion(repo, guion, *, empresa_id=EMPRESA_A):
    """Como `_cliente_http`, pero con un cliente Anthropic de GUION (para que Javo
    proponga componentes/tareas vía tool-use). El catálogo va vacío: basta que NO sea
    None (junto con la empresa) para habilitar las tools; las llamadas las dicta el guion."""
    app.dependency_overrides[obtener_repositorio_conversaciones] = lambda: repo
    app.dependency_overrides[obtener_cliente_anthropic] = lambda: ClienteAnthropicGuionFake(guion)
    app.dependency_overrides[obtener_repositorio_catalogo] = lambda: RepositorioCatalogoEnMemoria([])
    app.dependency_overrides[obtener_proveedor_busqueda] = lambda: ProveedorBusquedaCurado()
    app.dependency_overrides[obtener_cliente_drive_conversacion] = lambda: None
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


async def test_responder_persiste_el_borrador_de_la_cotizacion():
    # Javo propone componentes y tareas (tool-use) y luego cierra con texto. El endpoint
    # debe persistir ese borrador junto a la conversación (no solo el texto).
    sol = str(uuid4())
    repo = RepositorioConversacionesEnMemoria()
    guion = [
        respuesta_tool_use(
            "proponer_componentes",
            {"componentes": [{"nombre": "Promotoras", "cantidad": 6, "valor_unitario": 240000}]},
        ),
        respuesta_tool_use(
            "proponer_tareas",
            {"tareas": [{"nombre": "Reclutar 6 promotoras", "area": "RRHH"}]},
        ),
        respuesta_texto("Listo, dejo 6 promotoras y la tarea de reclutarlas."),
    ]
    http = _cliente_http_guion(repo, guion)

    r = http.post(
        "/conversaciones/responder", json=_payload(sol), headers={"Authorization": "Bearer x"}
    )
    assert r.status_code == 200

    borrador = await repo.obtener_borrador(UUID(sol), EMPRESA_A)
    assert borrador is not None
    assert [c["nombre"] for c in borrador["componentes"]] == ["Promotoras"]
    assert [t["nombre"] for t in borrador["tareas"]] == ["Reclutar 6 promotoras"]


async def test_responder_sin_propuestas_no_pisa_el_borrador_existente():
    # Si Javo responde SOLO con texto (no propone nada en este turno), el borrador previo
    # NO se borra: la cotización en curso se conserva (el bug del panel que se vacía).
    sol = str(uuid4())
    repo = RepositorioConversacionesEnMemoria()
    await repo.guardar_borrador(
        UUID(sol), EMPRESA_A, "t1", {"componentes": [{"nombre": "Promotoras"}], "tareas": [], "fuentes": []}
    )
    anthropic = ClienteAnthropicTextoFake("Sí, esas promotoras están perfectas.")
    http = _cliente_http(repo, anthropic=anthropic)

    r = http.post(
        "/conversaciones/responder", json=_payload(sol), headers={"Authorization": "Bearer x"}
    )
    assert r.status_code == 200

    # El borrador previo sigue intacto (no se pisó con uno vacío).
    borrador = await repo.obtener_borrador(UUID(sol), EMPRESA_A)
    assert borrador["componentes"] == [{"nombre": "Promotoras"}]


# ── GET /conversaciones/{solicitud_id}/cotizacion ────────────────────────────
async def test_get_cotizacion_devuelve_el_borrador_persistido():
    sol = uuid4()
    repo = RepositorioConversacionesEnMemoria()
    await repo.guardar_borrador(
        sol,
        EMPRESA_A,
        "t1",
        {
            "componentes": [{"nombre": "Promotoras", "cantidad": 6, "valor_unitario": 240000}],
            "tareas": [{"nombre": "Reclutar 6 promotoras", "area": "RRHH"}],
            "fuentes": [{"titulo": "Tarifario 2026", "referencia": "Drive: Tarifario 2026"}],
        },
    )
    http = _cliente_http(repo)

    r = http.get(f"/conversaciones/{sol}/cotizacion", headers={"Authorization": "Bearer x"})

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["componentes"][0]["nombre"] == "Promotoras"
    assert cuerpo["tareas"][0]["nombre"] == "Reclutar 6 promotoras"
    assert cuerpo["fuentes"][0]["titulo"] == "Tarifario 2026"


def test_get_cotizacion_sin_borrador_devuelve_vacio():
    repo = RepositorioConversacionesEnMemoria()
    http = _cliente_http(repo)

    r = http.get(f"/conversaciones/{uuid4()}/cotizacion", headers={"Authorization": "Bearer x"})

    assert r.status_code == 200
    assert r.json() == {"componentes": [], "tareas": [], "fuentes": []}


def test_get_cotizacion_sin_token_devuelve_401():
    repo = RepositorioConversacionesEnMemoria()
    http = _cliente_http(repo, con_empresa=False)

    r = http.get(f"/conversaciones/{uuid4()}/cotizacion")  # sin Authorization

    assert r.status_code == 401


async def test_get_cotizacion_no_ve_el_borrador_de_otra_empresa():
    # El borrador es de la empresa B; el usuario es de la A → no lo ve (emula RLS).
    sol = uuid4()
    repo = RepositorioConversacionesEnMemoria()
    await repo.guardar_borrador(
        sol, EMPRESA_B, "t1", {"componentes": [{"nombre": "privado"}], "tareas": [], "fuentes": []}
    )
    http = _cliente_http(repo, empresa_id=EMPRESA_A)

    r = http.get(f"/conversaciones/{sol}/cotizacion", headers={"Authorization": "Bearer x"})

    assert r.status_code == 200
    assert r.json() == {"componentes": [], "tareas": [], "fuentes": []}
