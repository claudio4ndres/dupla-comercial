"""Tests de los endpoints OAuth del conector ClickUp (Spec 009, T4-T7).

Espejo de los de Gmail (`rutas/integraciones.py`):
  * T4 · POST /clickup/iniciar  → {url} de consentimiento + `state` ligado a la empresa.
  * T5 · GET  /clickup/callback → valida state, canjea code (MOCK), guarda secreto +
         upsert integración (empresa_id DEL STATE), 302; state inválido → 400; token
         NUNCA en la respuesta (CA5).
  * T6 · GET  /clickup/estado   → {proveedor, estado} por EXISTENCIA de la integración
         clickup; sin integración → estado null ("Sin conectar"); token nunca (CA5).
  * T7 · DELETE /clickup         → borra secreto + fila clickup; idempotente (204).

Todo mockeado: el canje OAuth y ClickUp son dobles en memoria (CA8). Cero red.
"""
import asyncio
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_almacen_estado_oauth,
    obtener_almacen_secretos,
    obtener_cliente_clickup,
    obtener_cliente_oauth_clickup,
    obtener_config_oauth_clickup,
    obtener_empresa_actual,
    obtener_repositorio_integraciones,
    obtener_repositorio_integraciones_servicio,
)
from app.main import app
from app.repositorios.estado_oauth import AlmacenEstadoOAuthEnMemoria
from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.servicios.clickup_real import ErrorClickUp
from app.servicios.oauth_clickup import ConfigOAuthClickUp, CredencialesClickUp
from app.servicios.secretos import AlmacenSecretosEnMemoria
from tests.dobles import ClienteOAuthClickUpFake

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def teardown_function():
    app.dependency_overrides.clear()


def _config():
    return ConfigOAuthClickUp(
        client_id="cid-de-prueba",
        client_secret="secreto-de-prueba",
        redirect_uri="https://app.de-prueba/clickup/callback",
        url_post_conexion="https://app.de-prueba/conectores",
    )


def _integ_clickup(empresa_id=EMPRESA_A, **extra):
    base = dict(
        id=uuid4(),
        empresa_id=empresa_id,
        proveedor="clickup",
        token_ref="secreto://clickup-token",
        estado="conectado",
    )
    base.update(extra)
    return Integracion(**base)


# ── T4 · POST /clickup/iniciar ───────────────────────────────────────────────


def _http_iniciar(almacen, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_config_oauth_clickup] = lambda: _config()
    app.dependency_overrides[obtener_almacen_estado_oauth] = lambda: almacen
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def _state_de(url: str) -> str:
    return parse_qs(urlparse(url).query)["state"][0]


def test_iniciar_devuelve_url_con_client_id_y_state_ligado_a_la_empresa():
    almacen = AlmacenEstadoOAuthEnMemoria()
    http = _http_iniciar(almacen, empresa_id=EMPRESA_A)

    r = http.post("/clickup/iniciar")

    assert r.status_code == 200
    url = r.json()["url"]
    q = parse_qs(urlparse(url).query)
    assert q["client_id"] == ["cid-de-prueba"]  # la app OAuth de ClickUp
    state = _state_de(url)
    assert state != ""
    # El state quedó ligado a ESTA empresa (anti-CSRF; se valida en el callback).
    assert asyncio.run(almacen.consumir(state)) == EMPRESA_A


def test_iniciar_dos_veces_genera_states_distintos():
    almacen = AlmacenEstadoOAuthEnMemoria()
    http = _http_iniciar(almacen)

    s1 = _state_de(http.post("/clickup/iniciar").json()["url"])
    s2 = _state_de(http.post("/clickup/iniciar").json()["url"])

    assert s1 != s2


# ── T5 · GET /clickup/callback ───────────────────────────────────────────────


def _http_callback(estado, oauth, secretos, repo):
    app.dependency_overrides[obtener_config_oauth_clickup] = lambda: _config()
    app.dependency_overrides[obtener_almacen_estado_oauth] = lambda: estado
    app.dependency_overrides[obtener_cliente_oauth_clickup] = lambda: oauth
    app.dependency_overrides[obtener_almacen_secretos] = lambda: secretos
    app.dependency_overrides[obtener_repositorio_integraciones_servicio] = lambda: repo
    return TestClient(app)


def test_callback_persiste_integracion_clickup_y_redirige_sin_exponer_token():
    # CA2/CA5: canje mockeado, persiste integración clickup conectada con el empresa_id
    # DEL STATE y redirige 302 SIN que el access token salga por cuerpo ni headers.
    estado = AlmacenEstadoOAuthEnMemoria()
    asyncio.run(estado.guardar("state-valido", EMPRESA_A))
    oauth = ClienteOAuthClickUpFake(
        CredencialesClickUp(access_token="access-super-secreto")
    )
    secretos = AlmacenSecretosEnMemoria()
    repo = RepositorioIntegracionesEnMemoria([])
    http = _http_callback(estado, oauth, secretos, repo)

    r = http.get(
        "/clickup/callback?code=cod-xyz&state=state-valido",
        follow_redirects=False,
    )

    assert r.status_code == 302
    # CA5: ni en cuerpo ni en headers (incluido Location) viaja el token.
    assert "access-super-secreto" not in r.text
    assert "access-super-secreto" not in str(r.headers)

    # Persistió la integración clickup para la empresa ligada al state.
    integ = asyncio.run(repo.obtener_por_empresa_y_proveedor(EMPRESA_A, "clickup"))
    assert integ is not None
    assert integ.proveedor == "clickup"
    assert integ.estado == "conectado"
    # El token_ref es una referencia al secreto, NO el token en claro (CA5).
    assert "access-super-secreto" not in integ.token_ref
    # El code se canjeó vía el cliente mockeado (cero red, CA8).
    assert oauth.codigos_canjeados == ["cod-xyz"]
    # Y el access token quedó guardado en el almacén de secretos bajo ese token_ref.
    assert asyncio.run(secretos.obtener(integ.token_ref)) == "access-super-secreto"


def test_callback_usa_el_empresa_id_del_state_no_otro():
    # El empresa_id viene DEL STATE (no se infiere): si el state liga a B, la fila se
    # crea para B, jamás para A (no cruzar tenants en el callback sin JWT).
    estado = AlmacenEstadoOAuthEnMemoria()
    asyncio.run(estado.guardar("state-de-B", EMPRESA_B))
    oauth = ClienteOAuthClickUpFake()
    secretos = AlmacenSecretosEnMemoria()
    repo = RepositorioIntegracionesEnMemoria([])
    http = _http_callback(estado, oauth, secretos, repo)

    r = http.get(
        "/clickup/callback?code=c&state=state-de-B", follow_redirects=False
    )

    assert r.status_code == 302
    assert asyncio.run(repo.obtener_por_empresa_y_proveedor(EMPRESA_B, "clickup")) is not None
    assert asyncio.run(repo.obtener_por_empresa_y_proveedor(EMPRESA_A, "clickup")) is None


def test_callback_con_state_invalido_devuelve_400_y_no_persiste():
    estado = AlmacenEstadoOAuthEnMemoria()  # vacío: ningún state válido
    oauth = ClienteOAuthClickUpFake()
    secretos = AlmacenSecretosEnMemoria()
    repo = RepositorioIntegracionesEnMemoria([])
    http = _http_callback(estado, oauth, secretos, repo)

    r = http.get(
        "/clickup/callback?code=c&state=desconocido", follow_redirects=False
    )

    assert r.status_code == 400
    assert oauth.codigos_canjeados == []
    assert asyncio.run(repo.obtener_por_empresa_y_proveedor(EMPRESA_A, "clickup")) is None


# ── T6 · GET /clickup/estado ─────────────────────────────────────────────────


def _http_estado(repo, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_repositorio_integraciones] = lambda: repo
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def test_estado_sin_integracion_clickup_devuelve_null():
    # CA1: empresa que nunca conectó clickup → "Sin conectar" (estado null).
    repo = RepositorioIntegracionesEnMemoria([])
    http = _http_estado(repo)

    r = http.get("/clickup/estado")

    assert r.status_code == 200
    assert r.json() == {"proveedor": None, "estado": None}


def test_estado_con_integracion_clickup_devuelve_conectado():
    repo = RepositorioIntegracionesEnMemoria([_integ_clickup()])
    http = _http_estado(repo)

    r = http.get("/clickup/estado")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["proveedor"] == "clickup"
    assert cuerpo["estado"] == "conectado"


def test_estado_no_se_confunde_con_gmail():
    # Una empresa con SÓLO gmail (no clickup) sigue "Sin conectar" en ClickUp (CA1).
    repo = RepositorioIntegracionesEnMemoria(
        [Integracion(id=uuid4(), empresa_id=EMPRESA_A, proveedor="gmail",
                     token_ref="secreto://gmail")]
    )
    http = _http_estado(repo)

    r = http.get("/clickup/estado")

    assert r.status_code == 200
    assert r.json() == {"proveedor": None, "estado": None}


def test_estado_nunca_expone_token():
    # CA5: ni token_ref ni token salen en la respuesta de estado.
    repo = RepositorioIntegracionesEnMemoria(
        [_integ_clickup(token_ref="secreto://clickup/super-secreto")]
    )
    http = _http_estado(repo)

    r = http.get("/clickup/estado")

    assert "token_ref" not in r.json()
    assert "token" not in r.json()
    assert "super-secreto" not in r.text


def test_estado_solo_ve_la_integracion_de_su_empresa():
    # Multi-tenant: el clickup de B no aparece para A.
    repo = RepositorioIntegracionesEnMemoria([_integ_clickup(empresa_id=EMPRESA_B)])
    http = _http_estado(repo, empresa_id=EMPRESA_A)

    r = http.get("/clickup/estado")

    assert r.json() == {"proveedor": None, "estado": None}


# ── T7 · DELETE /clickup ─────────────────────────────────────────────────────


def _http_desconectar(repo, secretos, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_repositorio_integraciones] = lambda: repo
    app.dependency_overrides[obtener_almacen_secretos] = lambda: secretos
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def test_desconectar_borra_secreto_y_fila_clickup():
    # CA7: borra el secreto y la fila clickup de la empresa; vuelve a "Sin conectar".
    secretos = AlmacenSecretosEnMemoria()
    ref = asyncio.run(secretos.guardar(f"clickup-token-{EMPRESA_A}", "tok"))
    repo = RepositorioIntegracionesEnMemoria([_integ_clickup(token_ref=ref)])
    http = _http_desconectar(repo, secretos)

    r = http.delete("/clickup")

    assert r.status_code == 204
    assert asyncio.run(repo.obtener_por_empresa_y_proveedor(EMPRESA_A, "clickup")) is None
    assert asyncio.run(secretos.obtener(ref)) is None


def test_desconectar_no_toca_gmail_de_la_misma_empresa():
    # Desconectar clickup NO borra la integración de gmail de la empresa.
    secretos = AlmacenSecretosEnMemoria()
    ref_ck = asyncio.run(secretos.guardar(f"clickup-token-{EMPRESA_A}", "tok-ck"))
    gmail = Integracion(id=uuid4(), empresa_id=EMPRESA_A, proveedor="gmail",
                        token_ref="secreto://gmail")
    repo = RepositorioIntegracionesEnMemoria([gmail, _integ_clickup(token_ref=ref_ck)])
    http = _http_desconectar(repo, secretos)

    r = http.delete("/clickup")

    assert r.status_code == 204
    assert asyncio.run(repo.obtener_por_empresa_y_proveedor(EMPRESA_A, "clickup")) is None
    # Gmail sobrevive.
    assert asyncio.run(repo.obtener_por_empresa_y_proveedor(EMPRESA_A, "gmail")) is not None


def test_desconectar_sin_integracion_es_idempotente_204():
    # CA7: sin fila clickup, igual responde 204 (idempotente).
    secretos = AlmacenSecretosEnMemoria()
    repo = RepositorioIntegracionesEnMemoria([])
    http = _http_desconectar(repo, secretos)

    r = http.delete("/clickup")

    assert r.status_code == 204


# ── #5 · Auto-heal de ClickUp en GET /clickup/listas ─────────────────────────


class _ClickUpListasOK:
    """Doble de ClienteClickUp con token y listas: representa un token SANO."""

    tiene_token = True

    def __init__(self, listas=None):
        self._listas = listas or []

    async def listar_listas(self):
        return list(self._listas)


class _ClickUpListasFalla:
    """Doble que cae al pedir listas (token inválido/5xx): NO debe auto-sanar."""

    tiene_token = True

    async def listar_listas(self):
        raise ErrorClickUp("ClickUp respondió 500 al pedir /team")


def _http_listas(clickup, repo, empresa_id=EMPRESA_A):
    app.dependency_overrides[obtener_cliente_clickup] = lambda: clickup
    app.dependency_overrides[obtener_repositorio_integraciones] = lambda: repo
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def test_listas_ok_devuelve_clickup_de_reconectar_a_conectado():
    # #5 · Un /listas que responde OK PRUEBA que el token de ClickUp sirve. Si la
    # integración clickup venía 'reconectar' (colateral de un fallo de Gmail ya
    # corregido), se restaura a 'conectado' SOLA, igual que el auto-heal de Gmail.
    repo = RepositorioIntegracionesEnMemoria(
        [_integ_clickup(estado="reconectar")]
    )
    http = _http_listas(_ClickUpListasOK(), repo)

    r = http.get("/clickup/listas")

    assert r.status_code == 200
    integ = asyncio.run(repo.obtener_por_empresa_y_proveedor(EMPRESA_A, "clickup"))
    assert integ.estado == "conectado"  # se auto-sanó


def test_listas_ok_no_toca_la_fila_gmail_de_la_misma_empresa():
    # El auto-heal de ClickUp es POR proveedor: NO debe tocar la fila gmail (que
    # podría estar legítimamente en 'reconectar' por su propio token caído).
    gmail = Integracion(
        id=uuid4(), empresa_id=EMPRESA_A, proveedor="gmail",
        token_ref="secreto://gmail", estado="reconectar",
    )
    repo = RepositorioIntegracionesEnMemoria(
        [gmail, _integ_clickup(estado="reconectar")]
    )
    http = _http_listas(_ClickUpListasOK(), repo)

    r = http.get("/clickup/listas")

    assert r.status_code == 200
    integ_gmail = asyncio.run(
        repo.obtener_por_empresa_y_proveedor(EMPRESA_A, "gmail")
    )
    assert integ_gmail.estado == "reconectar"  # gmail intacto


def test_listas_ok_no_reescribe_si_ya_estaba_conectado():
    # Si ya estaba 'conectado', el endpoint NO necesita reescribir (no-op): el estado
    # se mantiene 'conectado'.
    repo = RepositorioIntegracionesEnMemoria(
        [_integ_clickup(estado="conectado")]
    )
    http = _http_listas(_ClickUpListasOK(), repo)

    r = http.get("/clickup/listas")

    assert r.status_code == 200
    integ = asyncio.run(repo.obtener_por_empresa_y_proveedor(EMPRESA_A, "clickup"))
    assert integ.estado == "conectado"


def test_listas_si_clickup_falla_no_auto_sana():
    # Si ClickUp CAE, el token NO está probado: la integración sigue 'reconectar'
    # (no se auto-sana por un fallo) y el endpoint responde 502.
    repo = RepositorioIntegracionesEnMemoria(
        [_integ_clickup(estado="reconectar")]
    )
    http = _http_listas(_ClickUpListasFalla(), repo)

    r = http.get("/clickup/listas")

    assert r.status_code == 502
    integ = asyncio.run(repo.obtener_por_empresa_y_proveedor(EMPRESA_A, "clickup"))
    assert integ.estado == "reconectar"  # NO se sanó
