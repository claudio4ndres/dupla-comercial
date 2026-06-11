"""TR1 · Implementación REAL del cliente de Gmail (sólo lectura) + refresh OAuth.

Habla con la API REST de Gmail vía `httpx` y refresca el access token a partir del
refresh token del usuario (que vive en `AlmacenSecretos`, regla de oro #3 — los
secretos sólo en el backend). Implementa el `Protocol` `ClienteGmail`, así que el
servicio de ingesta y el poller no cambian: les da igual si el cliente es el doble
de test o este real.

Estrategia de cursor (lo que pide TR1):
* con `cursor` → `users.history.list?startHistoryId=<cursor>` (incremental barato);
  el nuevo cursor es el `historyId` que devuelve la respuesta;
* sin `cursor` (primer sync) → fallback por fecha `q=after:<epoch>` y el cursor
  inicial se fija con el `historyId` actual de la casilla (`users.getProfile`).

Si el refresh del token falla (revocado/expirado) o no hay secreto, lanza
`ErrorAutenticacionGmail` para que la ingesta marque la integración como
'reconectar' sin caerse (CA7).
"""
import html
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

import httpx

from app.repositorios.integraciones import Integracion
from app.servicios.gmail import (
    ClienteGmail,
    ErrorAutenticacionGmail,
    FabricaClienteGmail,
    MensajeCorreo,
)

_LOG = logging.getLogger(__name__)

# Cota dura del primer sync: aunque se pagine, no ingerimos un inbox gigantesco de
# golpe (cada correo paga una clasificación Haiku). Si hay más, se loggea (no callado).
TOPE_PRIMER_SYNC = 100

URL_TOKEN_GOOGLE = "https://oauth2.googleapis.com/token"
BASE_GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"


def _decodificar_cuerpo(data: str) -> str:
    """Decodifica el `body.data` de Gmail (base64url, a veces sin relleno)."""
    import base64

    relleno = "=" * (-len(data) % 4)
    crudo = base64.urlsafe_b64decode(data + relleno)
    return crudo.decode("utf-8", "replace")


def _extraer_texto_plano(payload: dict) -> str:
    """Busca el primer `text/plain` en el payload (plano o multipart)."""
    mime = payload.get("mimeType", "")
    cuerpo = payload.get("body", {})
    if mime.startswith("text/plain") and cuerpo.get("data"):
        return _decodificar_cuerpo(cuerpo["data"])
    for parte in payload.get("parts", []) or []:
        texto = _extraer_texto_plano(parte)
        if texto:
            return texto
    return ""


def _strip_html(crudo: str) -> str:
    """HTML → texto plano aproximado (para clasificar correos solo-HTML). Quita
    <script>/<style>, los tags y colapsa espacios; no es un render fiel, pero da
    contenido clasificable en vez de un cuerpo vacío."""
    sin_bloques = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", crudo)
    sin_tags = re.sub(r"(?s)<[^>]+>", " ", sin_bloques)
    return re.sub(r"\s+", " ", html.unescape(sin_tags)).strip()


def _extraer_html(payload: dict) -> str:
    """Fallback cuando NO hay text/plain (correos solo-HTML: Uber, newsletters…):
    busca el primer text/html y lo limpia. Antes esto devolvía '' → cuerpo vacío →
    la clasificación fallaba con 400 (mensaje vacío a la API)."""
    mime = payload.get("mimeType", "")
    cuerpo = payload.get("body", {})
    if mime.startswith("text/html") and cuerpo.get("data"):
        return _strip_html(_decodificar_cuerpo(cuerpo["data"]))
    for parte in payload.get("parts", []) or []:
        texto = _extraer_html(parte)
        if texto:
            return texto
    return ""


def _a_mensaje(datos: dict) -> MensajeCorreo:
    """Mapea la respuesta de `users.messages.get` a nuestro `MensajeCorreo`."""
    payload = datos.get("payload", {})
    cabeceras = {
        h.get("name", "").lower(): h.get("value", "")
        for h in payload.get("headers", [])
    }
    nombre, correo = parseaddr(cabeceras.get("from", ""))
    return MensajeCorreo(
        gmail_msg_id=datos["id"],
        remitente=nombre,
        correo_origen=correo,
        asunto=cabeceras.get("subject", ""),
        # text/plain si existe; si no (correo solo-HTML), caemos al HTML limpiado.
        cuerpo=_extraer_texto_plano(payload) or _extraer_html(payload),
    )


class ClienteGmailReal:
    """Lee los correos nuevos de UNA casilla. Resuelve el refresh token de forma
    perezosa (en `listar_nuevos`, que es async) para que la fábrica pueda ser
    síncrona como exige el `Protocol`."""

    def __init__(
        self,
        *,
        almacen,
        token_ref: str,
        client_id: str,
        client_secret: str,
        casilla: str | None = None,
        cliente: httpx.AsyncClient | None = None,
        ventana_inicial_dias: int = 1,
    ) -> None:
        self._almacen = almacen
        self._token_ref = token_ref
        self._client_id = client_id
        self._client_secret = client_secret
        self.casilla = casilla
        self._cliente = cliente
        self._ventana = ventana_inicial_dias

    def _http(self) -> httpx.AsyncClient:
        return self._cliente or httpx.AsyncClient()

    async def _access_token(self, http: httpx.AsyncClient) -> str:
        """Canjea el refresh token por un access token efímero (refresh OAuth)."""
        refresh = await self._almacen.obtener(self._token_ref)
        if not refresh:
            raise ErrorAutenticacionGmail("No hay refresh token guardado")
        resp = await http.post(
            URL_TOKEN_GOOGLE,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        if resp.status_code != 200:
            raise ErrorAutenticacionGmail(
                f"Refresh rechazado por Google ({resp.status_code})"
            )
        access = resp.json().get("access_token")
        if not access:
            raise ErrorAutenticacionGmail("Google no devolvió access_token")
        return access

    async def listar_nuevos(
        self, cursor: str | None
    ) -> tuple[list[MensajeCorreo], str | None]:
        http = self._http()
        try:
            token = await self._access_token(http)
            cabeceras = {"Authorization": f"Bearer {token}"}
            if cursor:
                ids, nuevo_cursor = await self._ids_por_historial(http, cursor, cabeceras)
            else:
                ids, nuevo_cursor = await self._ids_iniciales(http, cabeceras)
            mensajes = [await self._obtener_mensaje(http, mid, cabeceras) for mid in ids]
            return mensajes, nuevo_cursor
        finally:
            if self._cliente is None:
                await http.aclose()

    async def obtener_mensaje(self, gmail_msg_id: str) -> MensajeCorreo | None:
        """Re-baja UN mensaje por id (re-procesar): re-extrae el cuerpo con el parser
        actual (incluye el fallback a HTML). Auth fallida → ErrorAutenticacionGmail."""
        http = self._http()
        try:
            token = await self._access_token(http)
            cabeceras = {"Authorization": f"Bearer {token}"}
            return await self._obtener_mensaje(http, gmail_msg_id, cabeceras)
        finally:
            if self._cliente is None:
                await http.aclose()

    async def _ids_por_historial(
        self, http: httpx.AsyncClient, cursor: str, cabeceras: dict
    ) -> tuple[list[str], str | None]:
        """Incremental: `users.history.list` desde el `cursor` (historyId). Si Gmail
        responde 404 (el `historyId` quedó demasiado viejo/invalidado — pasa tras días
        sin poll), RE-SINCRONIZA desde cero en vez de reventar con 500 (auditoría #8)."""
        resp = await http.get(
            f"{BASE_GMAIL}/history",
            params={"startHistoryId": cursor, "historyTypes": "messageAdded"},
            headers=cabeceras,
        )
        if resp.status_code == 404:
            _LOG.warning(
                "history.list devolvió 404 (historyId %s demasiado viejo): re-sync inicial.",
                cursor,
            )
            return await self._ids_iniciales(http, cabeceras)
        resp.raise_for_status()
        datos = resp.json()
        ids: list[str] = []
        for registro in datos.get("history", []) or []:
            for agregado in registro.get("messagesAdded", []) or []:
                msg_id = agregado.get("message", {}).get("id")
                if msg_id and msg_id not in ids:
                    ids.append(msg_id)
        # El nuevo cursor es el historyId más reciente (o el mismo si no hubo nada).
        nuevo_cursor = str(datos.get("historyId", cursor))
        return ids, nuevo_cursor

    async def _ids_iniciales(
        self, http: httpx.AsyncClient, cabeceras: dict
    ) -> tuple[list[str], str | None]:
        """Primer sync: fallback por fecha (`after:`), PAGINADO hasta TOPE_PRIMER_SYNC,
        y baseline del historyId. Sin paginar solo traía 50 (auditoría #9): un inbox
        grande salía truncado y los #51+ no los veía ni el incremental."""
        desde = datetime.now(timezone.utc) - timedelta(days=self._ventana)
        # Excluye el ruido (promos, redes sociales, foros y novedades/banco): deja el
        # inbox "Primary" (correspondencia real).
        consulta = (
            f"after:{int(desde.timestamp())} "
            "-category:promotions -category:social "
            "-category:forums -category:updates"
        )
        ids: list[str] = []
        page_token: str | None = None
        while len(ids) < TOPE_PRIMER_SYNC:
            params: dict = {"q": consulta, "maxResults": 100}
            if page_token:
                params["pageToken"] = page_token
            resp = await http.get(
                f"{BASE_GMAIL}/messages", params=params, headers=cabeceras
            )
            resp.raise_for_status()
            datos = resp.json()
            ids.extend(m["id"] for m in datos.get("messages", []) or [])
            page_token = datos.get("nextPageToken")
            if not page_token:
                break
        if page_token:  # quedaron correos sin traer: lo dejamos en el log (no callado)
            _LOG.info(
                "Primer sync: tope de %d correos alcanzado; el inbox tiene más.",
                TOPE_PRIMER_SYNC,
            )
        nuevo_cursor = await self._historyid_actual(http, cabeceras)
        return ids[:TOPE_PRIMER_SYNC], nuevo_cursor

    async def _historyid_actual(
        self, http: httpx.AsyncClient, cabeceras: dict
    ) -> str | None:
        resp = await http.get(f"{BASE_GMAIL}/profile", headers=cabeceras)
        resp.raise_for_status()
        valor = resp.json().get("historyId")
        return str(valor) if valor is not None else None

    async def _obtener_mensaje(
        self, http: httpx.AsyncClient, msg_id: str, cabeceras: dict
    ) -> MensajeCorreo:
        resp = await http.get(
            f"{BASE_GMAIL}/messages/{msg_id}",
            params={"format": "full"},
            headers=cabeceras,
        )
        resp.raise_for_status()
        return _a_mensaje(resp.json())


class FabricaClienteGmailReal:
    """Construye el `ClienteGmailReal` de UNA integración. Le pasa el `token_ref`
    (no el secreto en claro): el cliente resuelve el refresh contra `AlmacenSecretos`
    al momento de pedir correos. Aísla al poller de cómo se obtienen las credenciales
    (regla de oro #3)."""

    def __init__(
        self,
        *,
        almacen,
        client_id: str,
        client_secret: str,
        cliente: httpx.AsyncClient | None = None,
    ) -> None:
        self._almacen = almacen
        self._client_id = client_id
        self._client_secret = client_secret
        self._cliente = cliente

    def crear(self, integracion: Integracion) -> ClienteGmail:
        return ClienteGmailReal(
            almacen=self._almacen,
            token_ref=integracion.token_ref,
            client_id=self._client_id,
            client_secret=self._client_secret,
            casilla=integracion.casilla,
            cliente=self._cliente,
            # Primer sync: 1 año hacia atrás para traer la correspondencia REAL ya
            # existente del inbox (no solo lo que llegue post-conexión). El tope de
            # `maxResults=50` acota cuántos se ingieren; los siguientes polls son
            # incrementales por historyId, así que esta ventana solo aplica al inicio.
            ventana_inicial_dias=365,
        )


# Aserción de tipos: estas clases satisfacen los Protocols de `gmail.py`.
_: type[ClienteGmail] = ClienteGmailReal
__: type[FabricaClienteGmail] = FabricaClienteGmailReal
