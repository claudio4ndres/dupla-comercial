"""T3 (Spec 009) · Servicio OAuth de ClickUp (sin red, sin credenciales).

Espejo de `test_oauth_gmail`:
  (1) `construir_url_consentimiento` apunta al consentimiento de ClickUp
      (`app.clickup.com/api`) y lleva `client_id`, `redirect_uri` y el `state` anti-CSRF.
  (2) la base de autorización es configurable (simulador local en demo/staging).
  (3) `ClienteOAuthClickUp.canjear_codigo` (doble) devuelve un `access_token`.

ClickUp NO usa scopes granulares ni `response_type` en el consentimiento (grant por
defecto); el access token es largo y NO trae refresh token (aclaraciones #3/#4).
"""
from urllib.parse import parse_qs, urlparse

from app.servicios.oauth_clickup import (
    URL_AUTORIZACION_CLICKUP,
    ConfigOAuthClickUp,
    CredencialesClickUp,
    construir_url_consentimiento,
)
from tests.dobles import ClienteOAuthClickUpFake


def _config(**kwargs):
    base = dict(
        client_id="cid-demo",
        client_secret="secreto-demo",
        redirect_uri="https://app.test/clickup/callback",
    )
    base.update(kwargs)
    return ConfigOAuthClickUp(**base)


def _base(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}"


def test_url_por_defecto_apunta_a_clickup_con_client_id_redirect_y_state():
    url = construir_url_consentimiento(_config(), state="st-123")

    assert _base(url) == URL_AUTORIZACION_CLICKUP
    q = parse_qs(urlparse(url).query)
    assert q["client_id"] == ["cid-demo"]
    assert q["redirect_uri"] == ["https://app.test/clickup/callback"]
    assert q["state"] == ["st-123"]  # anti-CSRF, se valida en el callback


def test_url_autorizacion_configurable_para_demo():
    # En la demo/staging apuntamos a un simulador local; el contrato no cambia.
    url = construir_url_consentimiento(
        _config(url_autorizacion="http://localhost:8000/demo/clickup/consentir"),
        state="st-xyz",
    )

    assert _base(url) == "http://localhost:8000/demo/clickup/consentir"
    q = parse_qs(urlparse(url).query)
    assert q["state"] == ["st-xyz"]
    assert q["client_id"] == ["cid-demo"]


async def test_canjear_codigo_doble_devuelve_access_token():
    # El doble representa el canje sin red: code → access_token (CA8).
    oauth = ClienteOAuthClickUpFake(
        CredencialesClickUp(access_token="tok-de-clickup")
    )

    cred = await oauth.canjear_codigo("code-123")

    assert cred.access_token == "tok-de-clickup"
    assert oauth.codigos_canjeados == ["code-123"]
