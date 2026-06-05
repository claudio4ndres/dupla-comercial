"""TR3 · Implementación REAL del canje del `code` de Google por credenciales.

Cierra el flujo OAuth del callback: cambia el `code` del consentimiento por un
`refresh_token` (grant `authorization_code`) y resuelve la casilla conectada con
`users.getProfile` (el scope `gmail.readonly` ya lo permite, así no pedimos scopes
extra). Implementa el `Protocol` `ClienteOAuthGoogle`, de modo que el endpoint de
callback no cambia: en test usa el doble, en prod este cliente real.

El `refresh_token` se devuelve para que el backend lo guarde en `AlmacenSecretos`;
NUNCA viaja al front (CA5). Sin red en los tests (transporte httpx mockeado).
"""
import httpx

from app.servicios.gmail import ErrorAutenticacionGmail
from app.servicios.gmail_real import BASE_GMAIL, URL_TOKEN_GOOGLE
from app.servicios.oauth_gmail import CredencialesGmail


class ClienteOAuthGoogleReal:
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

    async def canjear_codigo(self, code: str) -> CredencialesGmail:
        http = self._http()
        try:
            resp = await http.post(
                URL_TOKEN_GOOGLE,
                data={
                    "code": code,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": self._redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if resp.status_code != 200:
                raise ErrorAutenticacionGmail(
                    f"Google rechazó el canje del code ({resp.status_code})"
                )
            datos = resp.json()
            refresh = datos.get("refresh_token")
            access = datos.get("access_token")
            if not refresh:
                # Google sólo entrega refresh_token con access_type=offline +
                # prompt=consent (lo pedimos en la URL). Si falta, hay que reconsentir.
                raise ErrorAutenticacionGmail(
                    "Google no devolvió refresh_token (reconsentir con prompt=consent)"
                )
            casilla = await self._casilla(http, access)
            return CredencialesGmail(refresh_token=refresh, casilla=casilla)
        finally:
            if self._cliente is None:
                await http.aclose()

    async def _casilla(self, http: httpx.AsyncClient, access_token: str) -> str:
        resp = await http.get(
            f"{BASE_GMAIL}/profile",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json().get("emailAddress", "")
