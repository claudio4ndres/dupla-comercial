"""Tests del endpoint POST /integraciones/correo/gmail/iniciar (T7).

Arranca el consentimiento de Google: devuelve la {url} a la que el front redirige.
La url DEBE pedir el scope mínimo `gmail.readonly` y llevar un `state` anti-CSRF que
queda registrado (ligado a la empresa) para validarse luego en el callback (T8).
OAuth va mockeado vía config inyectada: cero llamadas reales (CA6).
"""
import asyncio
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_almacen_estado_oauth,
    obtener_config_oauth_gmail,
    obtener_empresa_actual,
)
from app.main import app
from app.repositorios.estado_oauth import AlmacenEstadoOAuthEnMemoria
from app.servicios.oauth_gmail import ConfigOAuthGmail

EMPRESA_A = uuid4()


def _cliente_http(almacen, empresa_id=EMPRESA_A):
    config = ConfigOAuthGmail(
        client_id="cid-de-prueba",
        redirect_uri="https://app.de-prueba/integraciones/correo/gmail/callback",
    )
    app.dependency_overrides[obtener_config_oauth_gmail] = lambda: config
    app.dependency_overrides[obtener_almacen_estado_oauth] = lambda: almacen
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def _state_de(url: str) -> str:
    return parse_qs(urlparse(url).query)["state"][0]


def test_iniciar_devuelve_url_con_scope_minimo_y_state_registrado():
    almacen = AlmacenEstadoOAuthEnMemoria()
    http = _cliente_http(almacen, empresa_id=EMPRESA_A)

    r = http.post("/integraciones/correo/gmail/iniciar")

    assert r.status_code == 200
    url = r.json()["url"]

    # scope mínimo de sólo-lectura (nunca pedimos más de lo necesario).
    assert "gmail.readonly" in url

    # el state viaja en la url...
    state = _state_de(url)
    assert state != ""

    # ...y quedó registrado ligado a ESTA empresa (anti-CSRF, se valida en T8).
    assert asyncio.run(almacen.consumir(state)) == EMPRESA_A


def test_dos_inicios_generan_states_distintos():
    # Cada inicio usa un state nuevo (anti-replay / anti-CSRF).
    almacen = AlmacenEstadoOAuthEnMemoria()
    http = _cliente_http(almacen)

    s1 = _state_de(http.post("/integraciones/correo/gmail/iniciar").json()["url"])
    s2 = _state_de(http.post("/integraciones/correo/gmail/iniciar").json()["url"])

    assert s1 != s2
