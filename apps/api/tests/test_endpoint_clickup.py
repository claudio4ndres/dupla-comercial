"""Tests de los endpoints del conector ClickUp.

  * GET /clickup/listas → lista PLANA {id, nombre, espacio} de las listas reales del
    usuario (para el selector de la UI). Sin token configurado → 200 con [] (el front
    muestra "conecta ClickUp"). Si ClickUp cae → 502.
  * POST /solicitudes/{id}/tareas/clickup → crea las tareas de la propuesta como
    tareas reales en la lista elegida (query `lista_id`). Sin `lista_id` → 400 (#6: NO
    hay fallback global; jamás se manda a la lista de otra empresa). Sin propuesta →
    404. Si ClickUp cae → 502. Devuelve {"creadas": N}.

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
    obtener_repositorio_integraciones,
    obtener_repositorio_propuestas,
    obtener_repositorio_solicitudes,
)
from app.main import app
from app.repositorios.integraciones import RepositorioIntegracionesEnMemoria
from app.repositorios.propuestas import (
    ComponentePropuesta,
    Propuesta,
    RepositorioPropuestasEnMemoria,
    TareaPropuesta,
)
from app.repositorios.solicitudes import RepositorioSolicitudesEnMemoria, Solicitud
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


def _http(*, clickup=None, repo=None, empresa_id=EMPRESA_A, settings=None, repo_sol=None):
    if clickup is not None:
        app.dependency_overrides[obtener_cliente_clickup] = lambda: clickup
    if repo is not None:
        app.dependency_overrides[obtener_repositorio_propuestas] = lambda: repo
    # GET /clickup/listas resuelve el repo de integraciones para el auto-heal (#5):
    # un repo en memoria vacío por defecto (sin integración clickup → el auto-heal es
    # no-op). Los tests de auto-heal viven en test_endpoint_clickup_oauth.py.
    app.dependency_overrides[obtener_repositorio_integraciones] = (
        lambda: RepositorioIntegracionesEnMemoria([])
    )
    # Repo de solicitudes en memoria (el envío a ClickUp avanza su estado a 'enviada',
    # #7): por defecto uno vacío; los tests que verifican el avance inyectan el suyo.
    app.dependency_overrides[obtener_repositorio_solicitudes] = (
        lambda: repo_sol if repo_sol is not None else RepositorioSolicitudesEnMemoria()
    )
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
    app.dependency_overrides[obtener_repositorio_integraciones] = (
        lambda: RepositorioIntegracionesEnMemoria([])
    )
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


def test_enviar_a_clickup_avanza_estados_a_enviada():
    # #7 · al mandar las tareas a ClickUp (el envío real), la propuesta Y la solicitud
    # avanzan a 'enviada' (cierran el ciclo de vida).
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    repo_sol = RepositorioSolicitudesEnMemoria(
        [Solicitud(id=sol, empresa_id=EMPRESA_A, cuerpo="x", estado="propuesta")]
    )
    clickup = ClienteClickUpFake()
    http = _http(clickup=clickup, repo=repo, repo_sol=repo_sol)

    r = http.post(f"/solicitudes/{sol}/tareas/clickup?lista_id=L99")

    assert r.status_code == 200
    assert repo_sol.por_id(sol).estado == "enviada"
    # La propuesta también quedó 'enviada' (el GET la devuelve así).
    detalle = http.get(f"/solicitudes/{sol}/propuesta").json()
    assert detalle["estado"] == "enviada"


def test_enviar_usa_el_asignado_del_body_en_la_descripcion():
    # El front manda `asignados` = {nombre_de_tarea → persona}. Por cada tarea cuyo
    # nombre esté en el mapa, la descripción lleva esa persona (no el `responsable`).
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    clickup = ClienteClickUpFake()
    http = _http(clickup=clickup, repo=repo)

    r = http.post(
        f"/solicitudes/{sol}/tareas/clickup?lista_id=L99",
        json={"asignados": {"Reclutar 6 promotoras": "Gabriela Lillo"}},
    )

    assert r.status_code == 200
    assert r.json() == {"creadas": 2}
    desc_reclutar = next(c[2] for c in clickup.creadas if c[1] == "Reclutar 6 promotoras")
    # La persona elegida en el selector viaja en la descripción.
    assert "Gabriela Lillo" in desc_reclutar
    # No se filtra el `responsable` original cuando hay un asignado explícito.
    assert "Coordinación" not in desc_reclutar
    # Sigue concatenando grupo y vencimiento.
    assert "RRHH" in desc_reclutar
    assert "3 días" in desc_reclutar


def test_enviar_sin_asignado_para_una_tarea_cae_al_responsable():
    # Si `asignados` no trae el nombre de una tarea, se mantiene el comportamiento
    # actual: la descripción usa el `responsable` de la propuesta.
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    clickup = ClienteClickUpFake()
    http = _http(clickup=clickup, repo=repo)

    # Solo asigna "Comprar insumos"; "Reclutar 6 promotoras" queda sin asignar.
    r = http.post(
        f"/solicitudes/{sol}/tareas/clickup?lista_id=L99",
        json={"asignados": {"Comprar insumos": "Diego Rojas"}},
    )

    assert r.status_code == 200
    desc_reclutar = next(c[2] for c in clickup.creadas if c[1] == "Reclutar 6 promotoras")
    assert "Coordinación" in desc_reclutar  # cae al responsable original
    desc_comprar = next(c[2] for c in clickup.creadas if c[1] == "Comprar insumos")
    assert "Diego Rojas" in desc_comprar  # el asignado elegido


def test_enviar_sin_body_mantiene_comportamiento_actual():
    # El body es OPCIONAL: sin él (como hoy), la firma existente sigue funcionando.
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    clickup = ClienteClickUpFake()
    http = _http(clickup=clickup, repo=repo)

    r = http.post(f"/solicitudes/{sol}/tareas/clickup?lista_id=L99")

    assert r.status_code == 200
    assert r.json() == {"creadas": 2}
    desc_reclutar = next(c[2] for c in clickup.creadas if c[1] == "Reclutar 6 promotoras")
    assert "Coordinación" in desc_reclutar


def test_enviar_sin_lista_devuelve_400_no_manda_a_lista_ajena():
    # #6 · Se ELIMINÓ el fallback global `settings.clickup_list_id`: si no viene
    # `lista_id`, el endpoint responde 400 ("elige una lista") en vez de mandar a una
    # lista por defecto que podría ser de OTRA empresa. Aunque haya un clickup_list_id
    # global configurado, NO se usa (jamás se manda a una lista ajena).
    sol = uuid4()
    repo = RepositorioPropuestasEnMemoria([_propuesta(sol)])
    clickup = ClienteClickUpFake()
    # Aunque exista un global, NO debe usarse como destino.
    settings = Settings(_env_file=None, clickup_list_id="LISTA_DE_OTRA_EMPRESA")
    http = _http(clickup=clickup, repo=repo, settings=settings)

    r = http.post(f"/solicitudes/{sol}/tareas/clickup")

    assert r.status_code == 400
    assert clickup.creadas == []  # no se intentó crear nada en ninguna lista


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
