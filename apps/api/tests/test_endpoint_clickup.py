"""Tests de los endpoints del conector ClickUp.

  * GET /clickup/listas → lista PLANA {id, nombre, espacio} de las listas reales del
    usuario (para el selector de la UI). Sin token configurado → 200 con [] (el front
    muestra "conecta ClickUp"). Si ClickUp cae → 502.
  * POST /solicitudes/{id}/tareas/clickup → crea las tareas de la propuesta como
    tareas reales en la lista elegida (query `lista_id`) o, si no viene, en la lista
    por defecto (`settings.clickup_list_id`). Sin lista → 400. Sin propuesta → 404.
    Si ClickUp cae → 502. Devuelve {"creadas": N}.

Todo con dobles en memoria: cero red, cero ClickUp real (CA: las APIs externas se
mockean). El cliente ClickUp se inyecta con un doble vía `app.dependency_overrides`;
el token real del `.env` NUNCA se usa (en el worktree ni siquiera existe).
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import Settings, obtener_settings
from app.dependencias import (
    obtener_cliente_clickup,
    obtener_empresa_actual,
    obtener_repositorio_propuestas,
)
from app.main import app
from app.repositorios.propuestas import (
    ComponentePropuesta,
    Propuesta,
    RepositorioPropuestasEnMemoria,
    TareaPropuesta,
)
from app.servicios.clickup_real import ErrorClickUp, ListaClickUp

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


class ClienteClickUpFake:
    """Doble del ClienteClickUp: devuelve listas fijas y registra cada tarea creada
    (lista, nombre, descripción) para verificar el cableado. Cero red. `tiene_token`
    en True: representa una empresa con el conector YA conectado."""

    tiene_token = True

    def __init__(self, listas=None):
        self._listas = listas if listas is not None else []
        self.creadas: list[tuple[str, str, str]] = []

    async def listar_listas(self):
        return list(self._listas)

    async def crear_tarea(self, list_id, nombre, descripcion=""):
        self.creadas.append((list_id, nombre, descripcion))
        return f"id-{len(self.creadas)}"


class ClienteClickUpQueFalla:
    """Doble que simula una caída de ClickUp (token inválido, 5xx, red): lanza.
    Tiene token (está "conectado"), pero ClickUp responde error."""

    tiene_token = True

    async def listar_listas(self):
        raise ErrorClickUp("ClickUp respondió 500 al pedir /team")

    async def crear_tarea(self, list_id, nombre, descripcion=""):
        raise ErrorClickUp("ClickUp respondió 500 al crear la tarea")


def teardown_function():
    app.dependency_overrides.clear()


def _http(*, clickup=None, repo=None, empresa_id=EMPRESA_A, settings=None):
    if clickup is not None:
        app.dependency_overrides[obtener_cliente_clickup] = lambda: clickup
    if repo is not None:
        app.dependency_overrides[obtener_repositorio_propuestas] = lambda: repo
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    if settings is not None:
        # Fija la lista por defecto (fallback del POST) sin tocar el `.env`: el
        # endpoint lee `settings.clickup_list_id` vía la dependencia obtener_settings.
        app.dependency_overrides[obtener_settings] = lambda: settings
    return TestClient(app)


def _propuesta(solicitud_id, empresa_id=EMPRESA_A, tareas=None):
    return Propuesta(
        id=uuid4(),
        empresa_id=empresa_id,
        solicitud_id=solicitud_id,
        total=1000,
        estado="borrador",
        componentes=[ComponentePropuesta(nombre="Promotoras", cantidad=2)],
        tareas=tareas
        if tareas is not None
        else [
            TareaPropuesta(
                nombre="Reclutar 6 promotoras",
                grupo="RRHH",
                responsable="Coordinación",
                vencimiento="3 días",
            ),
            TareaPropuesta(nombre="Comprar insumos", grupo="Compras"),
        ],
    )


# ── GET /clickup/listas ──────────────────────────────────────────────────────


def test_listas_devuelve_forma_plana():
    clickup = ClienteClickUpFake(
        listas=[
            ListaClickUp(id="L1", nombre="Backlog", espacio="Marketing"),
            ListaClickUp(id="L2", nombre="Sampling", espacio="Marketing"),
        ]
    )
    http = _http(clickup=clickup)

    r = http.get("/clickup/listas")

    assert r.status_code == 200
    assert r.json() == [
        {"id": "L1", "nombre": "Backlog", "espacio": "Marketing"},
        {"id": "L2", "nombre": "Sampling", "espacio": "Marketing"},
    ]


def test_listas_sin_token_devuelve_200_y_lista_vacia():
    # El cliente real se construye con token vacío (sin .env). El endpoint detecta
    # que no hay token y NO llama a ClickUp: devuelve [] para que el front muestre
    # "conecta ClickUp". Reproducimos el cliente sin token con el real.
    from app.servicios.clickup_real import ClienteClickUp

    app.dependency_overrides[obtener_cliente_clickup] = lambda: ClienteClickUp("")
    app.dependency_overrides[obtener_empresa_actual] = lambda: EMPRESA_A
    http = TestClient(app)

    r = http.get("/clickup/listas")

    assert r.status_code == 200
    assert r.json() == []


def test_listas_si_clickup_cae_devuelve_502():
    http = _http(clickup=ClienteClickUpQueFalla())

    r = http.get("/clickup/listas")

    assert r.status_code == 502


# ── POST /solicitudes/{id}/tareas/clickup ────────────────────────────────────


def test_enviar_crea_una_tarea_por_cada_tarea_de_la_propuesta():
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    clickup = ClienteClickUpFake()
    http = _http(clickup=clickup, repo=repo)

    r = http.post(f"/solicitudes/{sol}/tareas/clickup?lista_id=L99")

    assert r.status_code == 200
    assert r.json() == {"creadas": 2}
    # Se crearon en la lista elegida (query param), no en el fallback.
    assert [c[0] for c in clickup.creadas] == ["L99", "L99"]
    nombres = [c[1] for c in clickup.creadas]
    assert "Reclutar 6 promotoras" in nombres
    assert "Comprar insumos" in nombres
    # La descripción concatena grupo · responsable · vencimiento.
    desc_reclutar = next(c[2] for c in clickup.creadas if c[1] == "Reclutar 6 promotoras")
    assert "RRHH" in desc_reclutar
    assert "Coordinación" in desc_reclutar
    assert "3 días" in desc_reclutar


def test_enviar_usa_lista_por_defecto_si_no_viene_query():
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    clickup = ClienteClickUpFake()
    settings = Settings(_env_file=None, clickup_list_id="LISTA_DEFAULT")
    http = _http(clickup=clickup, repo=repo, settings=settings)

    r = http.post(f"/solicitudes/{sol}/tareas/clickup")

    assert r.status_code == 200
    assert r.json() == {"creadas": 2}
    assert {c[0] for c in clickup.creadas} == {"LISTA_DEFAULT"}


def test_enviar_sin_lista_ni_defecto_devuelve_400():
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    clickup = ClienteClickUpFake()
    settings = Settings(_env_file=None, clickup_list_id="")  # sin fallback
    http = _http(clickup=clickup, repo=repo, settings=settings)

    r = http.post(f"/solicitudes/{sol}/tareas/clickup")

    assert r.status_code == 400
    assert clickup.creadas == []  # no se intentó crear nada


def test_enviar_sin_propuesta_devuelve_404():
    repo = RepositorioPropuestasEnMemoria([])
    clickup = ClienteClickUpFake()
    http = _http(clickup=clickup, repo=repo)

    r = http.post(f"/solicitudes/{uuid4()}/tareas/clickup?lista_id=L1")

    assert r.status_code == 404


def test_enviar_aislamiento_multi_tenant_propuesta_de_otra_empresa_es_404():
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol, empresa_id=EMPRESA_B)])
    clickup = ClienteClickUpFake()
    http = _http(clickup=clickup, repo=repo, empresa_id=EMPRESA_A)

    r = http.post(f"/solicitudes/{sol}/tareas/clickup?lista_id=L1")

    assert r.status_code == 404


def test_enviar_si_clickup_cae_devuelve_502():
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    http = _http(clickup=ClienteClickUpQueFalla(), repo=repo)

    r = http.post(f"/solicitudes/{sol}/tareas/clickup?lista_id=L1")

    assert r.status_code == 502
