"""TR3 · Cliente OAuth real de Google (canje del `code`) **sin red**.

Transporte httpx mockeado: canjea el `code` del consentimiento por tokens
(`authorization_code` grant) y resuelve la casilla con `users.getProfile` (scope
`gmail.readonly` alcanza). Devuelve `CredencialesGmail{refresh_token, casilla}`;
el refresh token nunca sale de aquí hacia el front (lo guarda el `AlmacenSecretos`).
"""
import httpx

from app.servicios.gmail import ErrorAutenticacionGmail
from app.servicios.oauth_gmail import CredencialesGmail
from app.servicios.oauth_gmail_real import ClienteOAuthGoogleReal

CLIENT_ID = "client-id-de-prueba"
CLIENT_SECRET = "client-secret-de-prueba"
REDIRECT = "https://api/integraciones/correo/gmail/callback"


def _ruteador(registro: list, *, token_status=200, con_refresh=True):
    def handler(req: httpx.Request) -> httpx.Response:
        registro.append(req)
        if req.url.path.endswith("/token"):
            if token_status != 200:
                return httpx.Response(token_status, json={"error": "invalid_grant"})
            cuerpo = {"access_token": "ya29.fresco", "expires_in": 3599}
            if con_refresh:
                cuerpo["refresh_token"] = "refresh-nuevo"
            return httpx.Response(200, json=cuerpo)
        # users.getProfile
        return httpx.Response(200, json={"emailAddress": "ventas@capsulab.cl",
                                         "historyId": "111"})

    return handler


def _cliente(handler):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ClienteOAuthGoogleReal(CLIENT_ID, CLIENT_SECRET, REDIRECT, cliente=http)


async def test_canjear_codigo_devuelve_refresh_y_casilla():
    registro: list = []
    creds = await _cliente(_ruteador(registro)).canjear_codigo("code-de-google")

    assert isinstance(creds, CredencialesGmail)
    assert creds.refresh_token == "refresh-nuevo"
    assert creds.casilla == "ventas@capsulab.cl"
    # El canje usó authorization_code con el code y el redirect_uri registrados.
    token_req = next(r for r in registro if r.url.path.endswith("/token"))
    cuerpo = token_req.content.decode()
    assert "code-de-google" in cuerpo
    assert "authorization_code" in cuerpo
    assert "callback" in cuerpo  # el redirect_uri viajó en el canje


async def test_codigo_invalido_lanza_error_de_autenticacion():
    registro: list = []
    try:
        await _cliente(_ruteador(registro, token_status=400)).canjear_codigo("malo")
        assert False, "debía lanzar ErrorAutenticacionGmail"
    except ErrorAutenticacionGmail:
        pass
    # No fue al profile tras fallar el canje.
    assert not any(r.url.path.endswith("/profile") for r in registro)


async def test_sin_refresh_token_lanza_error_de_autenticacion():
    # Si Google no devuelve refresh_token (consentimiento ya dado sin prompt), avisa.
    registro: list = []
    try:
        await _cliente(_ruteador(registro, con_refresh=False)).canjear_codigo("code")
        assert False, "debía lanzar ErrorAutenticacionGmail"
    except ErrorAutenticacionGmail:
        pass
