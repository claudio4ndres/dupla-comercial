"""Construcción de la URL de consentimiento de ClickUp y contrato del canje del
`code` por un access token (Spec 009, espejo de `oauth_gmail`).

Armar la URL es lógica real y vive aquí (testeable sin red). ClickUp NO usa scopes
granulares estilo Google ni `response_type` en el consentimiento: el grant por defecto
da acceso a los workspaces que el usuario autorice (alcanza para listar team→space→
folder→list y crear tareas, aclaración #3). Lo específico del entorno (client_id,
client_secret, redirect_uri) entra por config inyectable. El canje del `code` (T5) usa
un `ClienteOAuthClickUp` mockeado en tests.

ClickUp entrega un access token de LARGA duración (no expira hasta revocación) y NO
trae refresh token (aclaración #4): por eso `CredencialesClickUp` sólo lleva el access
token, que se guarda en `AlmacenSecretos`. "Reconectar" se dispara por 401/revocación.
"""
from typing import Protocol
from urllib.parse import urlencode

from pydantic import BaseModel

# Consentimiento de ClickUp (el usuario autoriza la app y vuelve con `?code=...`).
URL_AUTORIZACION_CLICKUP = "https://app.clickup.com/api"
# Canje del `code` por el access token (grant de ClickUp).
URL_TOKEN_CLICKUP = "https://api.clickup.com/api/v2/oauth/token"


class ConfigOAuthClickUp(BaseModel):
    """Datos de la app OAuth de ClickUp (no son secretos del usuario final)."""

    client_id: str
    client_secret: str
    redirect_uri: str
    url_post_conexion: str = "/"  # a dónde vuelve el navegador tras conectar
    # Base del endpoint de autorización. Por defecto el real de ClickUp; se puede
    # apuntar a un simulador local (demo/staging) sin alterar el resto del flujo.
    url_autorizacion: str = URL_AUTORIZACION_CLICKUP


def construir_url_consentimiento(config: ConfigOAuthClickUp, state: str) -> str:
    """Arma la URL de consentimiento de ClickUp con `client_id`, `redirect_uri` y el
    `state` anti-CSRF. ClickUp no pide `scope` ni `response_type` (grant por defecto)."""
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "state": state,  # anti-CSRF: se valida en el callback
    }
    return f"{config.url_autorizacion}?{urlencode(params)}"


class CredencialesClickUp(BaseModel):
    """Resultado del canje del `code`: el access token (secreto, de larga duración).
    ClickUp no entrega refresh token; este access token se persiste en `AlmacenSecretos`."""

    access_token: str


class ClienteOAuthClickUp(Protocol):
    async def canjear_codigo(self, code: str) -> CredencialesClickUp: ...
