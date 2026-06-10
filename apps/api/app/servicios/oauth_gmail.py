"""Construcción de la URL de consentimiento de Google (sólo lectura) y contrato del
canje del `code` por credenciales.

Armar la URL es lógica real y vive aquí (testeable sin red): scopes de sólo-lectura
`gmail.readonly` (leer el correo) + `drive.readonly` (leer la carpeta del Drive de la
empresa para alimentar el catálogo/panel Recursos), más `access_type=offline` +
`prompt=consent` para obtener un refresh token. Lo único específico del entorno
(client_id, redirect_uri) entra por config inyectable. El canje del `code` (T8) usa
un `ClienteOAuthGoogle` mockeado.
"""
from typing import Protocol
from urllib.parse import urlencode

from pydantic import BaseModel

SCOPE_GMAIL_LECTURA = "https://www.googleapis.com/auth/gmail.readonly"
# Sólo-lectura del Drive: permite listar Y leer el contenido de los archivos de la
# carpeta de la empresa (se usa `drive.readonly` en lugar de `drive.metadata.readonly`
# para poder leer el contenido de los recursos más adelante, no sólo sus nombres).
SCOPE_DRIVE_LECTURA = "https://www.googleapis.com/auth/drive.readonly"
URL_AUTORIZACION_GOOGLE = "https://accounts.google.com/o/oauth2/v2/auth"


class ConfigOAuthGmail(BaseModel):
    """Datos del cliente OAuth de Google (no son secretos del usuario)."""

    client_id: str
    redirect_uri: str
    url_post_conexion: str = "/"  # a dónde vuelve el navegador tras conectar
    # Base del endpoint de autorización. Por defecto el real de Google; se puede
    # apuntar a un simulador local (demo/staging) sin alterar el resto del flujo.
    url_autorizacion: str = URL_AUTORIZACION_GOOGLE


def construir_url_consentimiento(config: ConfigOAuthGmail, state: str) -> str:
    """Arma la URL de consentimiento con los scopes de sólo-lectura (gmail + drive,
    separados por espacio como exige OAuth de Google) y el `state` anti-CSRF."""
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": f"{SCOPE_GMAIL_LECTURA} {SCOPE_DRIVE_LECTURA}",
        "state": state,
        "access_type": "offline",  # necesario para recibir un refresh token
        "prompt": "consent",
    }
    return f"{config.url_autorizacion}?{urlencode(params)}"


class CredencialesGmail(BaseModel):
    """Resultado del canje del `code`: el refresh token (secreto) y la casilla
    conectada. El access token es efímero y no se persiste aquí."""

    refresh_token: str
    casilla: str


class ClienteOAuthGoogle(Protocol):
    async def canjear_codigo(self, code: str) -> CredencialesGmail: ...
