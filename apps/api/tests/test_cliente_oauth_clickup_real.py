"""T3 (Spec 009) · Cliente OAuth real de ClickUp (canje del `code`) **sin red**.

Transporte httpx mockeado: canjea el `code` por un access token
(`POST api.clickup.com/api/v2/oauth/token` con client_id + client_secret + code).
Devuelve `CredencialesClickUp{access_token}`; el token nunca sale de aquí hacia el
front (lo guarda el `AlmacenSecretos`). ClickUp no entrega refresh token.
"""
import httpx

from app.servicios.oauth_clickup import CredencialesClickUp
from app.servicios.oauth_clickup_real import (
    ClienteOAuthClickUpReal,
    ErrorAutenticacionClickUp,
)

CLIENT_ID = "client-id-de-prueba"
CLIENT_SECRET = "client-secret-de-prueba"
REDIRECT = "https://api/clickup/callback"


def _ruteador(registro: list, *, token_status=200, con_token=True):
    def handler(req: httpx.Request) -> httpx.Response:
        registro.append(req)
        if token_status != 200:
            return httpx.Response(token_status, json={"err": "OAUTH_017"})
        cuerpo = {"access_token": "clk_access_fresco"} if con_token else {}
        return httpx.Response(200, json=cuerpo)

    return handler


def _cliente(handler):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ClienteOAuthClickUpReal(CLIENT_ID, CLIENT_SECRET, REDIRECT, cliente=http)


async def test_canjear_codigo_devuelve_access_token():
    registro: list = []
    creds = await _cliente(_ruteador(registro)).canjear_codigo("code-de-clickup")

    assert isinstance(creds, CredencialesClickUp)
    assert creds.access_token == "clk_access_fresco"
    # El canje mandó el code + las credenciales de la app al endpoint de token.
    req = registro[0]
    assert req.url.path.endswith("/oauth/token")
    cuerpo = req.content.decode()
    assert "code-de-clickup" in cuerpo
    assert CLIENT_ID in cuerpo
    assert CLIENT_SECRET in cuerpo


async def test_codigo_invalido_lanza_error_de_autenticacion():
    registro: list = []
    try:
        await _cliente(_ruteador(registro, token_status=400)).canjear_codigo("malo")
        assert False, "debía lanzar ErrorAutenticacionClickUp"
    except ErrorAutenticacionClickUp:
        pass


async def test_sin_access_token_lanza_error_de_autenticacion():
    registro: list = []
    try:
        await _cliente(_ruteador(registro, con_token=False)).canjear_codigo("code")
        assert False, "debía lanzar ErrorAutenticacionClickUp"
    except ErrorAutenticacionClickUp:
        pass
