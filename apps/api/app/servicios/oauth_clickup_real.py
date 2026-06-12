"""Implementación REAL del canje del `code` de ClickUp por un access token (Spec 009).

Cierra el flujo OAuth del callback: cambia el `code` del consentimiento por un
`access_token` (`POST https://api.clickup.com/api/v2/oauth/token` con client_id +
client_secret + code). Implementa el `Protocol` `ClienteOAuthClickUp`, así el endpoint
de callback no cambia: en test usa el doble, en prod este cliente real.

El `access_token` se devuelve para que el backend lo guarde en `AlmacenSecretos`; NUNCA
viaja al front (CA5). Sin red en los tests (transporte httpx mockeado). ClickUp no
entrega refresh token (aclaración #4).
"""
import httpx

from app.servicios.oauth_clickup import URL_TOKEN_CLICKUP, CredencialesClickUp


class ErrorAutenticacionClickUp(Exception):
    """Falla al canjear el `code` de ClickUp por el access token."""


class ClienteOAuthClickUpReal:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        *,
        cliente: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._cliente = cliente

    def _http(self) -> httpx.AsyncClient:
        return self._cliente or httpx.AsyncClient()

    async def canjear_codigo(self, code: str) -> CredencialesClickUp:
        http = self._http()
        try:
            resp = await http.post(
                URL_TOKEN_CLICKUP,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                    # ClickUp acepta redirect_uri en el canje (consistente con el consent).
                    "redirect_uri": self._redirect_uri,
                },
            )
            if resp.status_code != 200:
                raise ErrorAutenticacionClickUp(
                    f"ClickUp rechazó el canje del code ({resp.status_code})"
                )
            datos = resp.json()
            access = datos.get("access_token")
            if not access:
                raise ErrorAutenticacionClickUp(
                    "ClickUp no devolvió access_token en el canje"
                )
            return CredencialesClickUp(access_token=access)
        finally:
            if self._cliente is None:
                await http.aclose()
