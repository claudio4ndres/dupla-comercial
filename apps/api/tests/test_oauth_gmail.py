"""Tests unitarios de la URL de consentimiento de Gmail (sin red, sin credenciales).

Cubre dos cosas: (1) por defecto apunta al endpoint real de Google con el scope
MÍNIMO `gmail.readonly` y `access_type=offline` (para obtener refresh token); y
(2) la base de autorización es configurable, lo que permite enchufar un simulador
local en la demo sin tocar el resto del flujo OAuth.
"""
from urllib.parse import parse_qs, urlparse

from app.servicios.oauth_gmail import (
    SCOPE_GMAIL_LECTURA,
    URL_AUTORIZACION_GOOGLE,
    ConfigOAuthGmail,
    construir_url_consentimiento,
)


def _config(**kwargs):
    base = dict(client_id="cid-demo", redirect_uri="https://app.test/callback")
    base.update(kwargs)
    return ConfigOAuthGmail(**base)


def _base(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}"


def test_url_por_defecto_apunta_a_google_con_scope_minimo():
    url = construir_url_consentimiento(_config(), state="st-123")

    assert _base(url) == URL_AUTORIZACION_GOOGLE
    q = parse_qs(urlparse(url).query)
    assert q["scope"] == [SCOPE_GMAIL_LECTURA]  # sólo lectura (mínimo privilegio)
    assert q["state"] == ["st-123"]  # anti-CSRF
    assert q["access_type"] == ["offline"]  # necesario para el refresh token
    assert q["redirect_uri"] == ["https://app.test/callback"]


def test_url_autorizacion_configurable_para_demo():
    # En la demo apuntamos a un simulador local; el resto del contrato no cambia.
    url = construir_url_consentimiento(
        _config(url_autorizacion="http://localhost:8000/demo/google/consentir"),
        state="st-xyz",
    )

    assert _base(url) == "http://localhost:8000/demo/google/consentir"
    q = parse_qs(urlparse(url).query)
    assert q["state"] == ["st-xyz"]
    assert q["scope"] == [SCOPE_GMAIL_LECTURA]
