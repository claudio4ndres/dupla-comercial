"""Tests unitarios de la URL de consentimiento de Google (sin red, sin credenciales).

Cubre tres cosas: (1) por defecto apunta al endpoint real de Google con los scopes
de sólo-lectura `gmail.readonly` + `drive.readonly` (mínimo necesario para leer el
correo y la carpeta del Drive de la empresa) y `access_type=offline` (para obtener
refresh token); (2) ambos scopes viajan separados por espacio (formato OAuth de
Google); y (3) la base de autorización es configurable, lo que permite enchufar un
simulador local en la demo sin tocar el resto del flujo OAuth.
"""
from urllib.parse import parse_qs, urlparse

from app.servicios.oauth_gmail import (
    SCOPE_DRIVE_LECTURA,
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


def test_url_por_defecto_apunta_a_google_con_scopes_gmail_y_drive():
    url = construir_url_consentimiento(_config(), state="st-123")

    assert _base(url) == URL_AUTORIZACION_GOOGLE
    q = parse_qs(urlparse(url).query)
    # Ambos scopes de sólo-lectura, separados por espacio (formato OAuth de Google):
    # gmail.readonly (leer el correo) + drive.readonly (leer la carpeta del Drive).
    scopes = q["scope"][0].split(" ")
    assert SCOPE_GMAIL_LECTURA in scopes
    assert SCOPE_DRIVE_LECTURA in scopes
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
    scopes = q["scope"][0].split(" ")
    assert SCOPE_GMAIL_LECTURA in scopes
    assert SCOPE_DRIVE_LECTURA in scopes
