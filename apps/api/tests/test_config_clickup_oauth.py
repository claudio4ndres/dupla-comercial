"""T8 (Spec 009) · Config de la app OAuth de ClickUp en `Settings`.

`Settings` carga `clickup_client_id` / `clickup_client_secret` / `clickup_redirect_uri`
(vacíos por defecto: sin valores reales en tests/CI, como las creds de Google). La
dependencia `obtener_config_oauth_clickup` arma `ConfigOAuthClickUp` desde `Settings`.
"""
from app.config import Settings
from app.servicios.oauth_clickup import ConfigOAuthClickUp


def test_settings_trae_campos_clickup_oauth_vacios_por_defecto():
    s = Settings(_env_file=None)

    assert s.clickup_client_id == ""
    assert s.clickup_client_secret == ""
    assert s.clickup_redirect_uri == ""


def test_settings_lee_los_campos_clickup_oauth():
    s = Settings(
        _env_file=None,
        clickup_client_id="cid",
        clickup_client_secret="secreto",
        clickup_redirect_uri="https://api/clickup/callback",
    )

    assert s.clickup_client_id == "cid"
    assert s.clickup_client_secret == "secreto"
    assert s.clickup_redirect_uri == "https://api/clickup/callback"


def test_obtener_config_oauth_clickup_arma_config_desde_settings(monkeypatch):
    # La dependencia construye ConfigOAuthClickUp con las creds de Settings + el
    # frontend_url como destino post-conexión (espejo de obtener_config_oauth_gmail).
    from app import dependencias

    s = Settings(
        _env_file=None,
        clickup_client_id="cid-x",
        clickup_client_secret="secreto-x",
        clickup_redirect_uri="https://api/clickup/callback",
        frontend_url="https://app.test/conectores",
    )
    monkeypatch.setattr(dependencias, "obtener_settings", lambda: s)

    config = dependencias.obtener_config_oauth_clickup()

    assert isinstance(config, ConfigOAuthClickUp)
    assert config.client_id == "cid-x"
    assert config.client_secret == "secreto-x"
    assert config.redirect_uri == "https://api/clickup/callback"
    assert config.url_post_conexion == "https://app.test/conectores"
