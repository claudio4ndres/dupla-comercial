"""Cliente REAL de Google Drive (sólo lectura) + refresh OAuth.

Calca a `gmail_real.py::ClienteGmailReal`: habla con la API REST de Drive vía `httpx`
y refresca el access token a partir del refresh token de la empresa (que vive en
`AlmacenSecretos`, regla de oro #3 — los secretos sólo en el backend). El refresh y
el listado comparten el mismo flujo OAuth que Gmail (mismo `URL_TOKEN_GOOGLE`), porque
el consentimiento pide AMBOS scopes a la vez (`gmail.readonly` + `drive.readonly`).

Se usa para alimentar el panel "Recursos · Drive": lista los archivos de la carpeta
de la empresa. `httpx` es inyectable para tests (cero red, igual que el cliente Gmail).

Si el refresh del token falla (revocado/expirado) o no hay secreto, lanza
`ErrorAutenticacionGmail` (reutilizado: es el error de auth de Google de este backend)
para que el llamador caiga al comportamiento previo sin caerse.
"""
from dataclasses import dataclass

import httpx

from app.repositorios.integraciones import Integracion
from app.servicios.gmail import ErrorAutenticacionGmail
from app.servicios.gmail_real import URL_TOKEN_GOOGLE

BASE_DRIVE = "https://www.googleapis.com/drive/v3"

# Tipos MIME de Google que SÍ se pueden exportar a texto (para que Javo los LEA).
_MIME_GOOGLE_DOC = "application/vnd.google-apps.document"
_MIME_GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
# A qué formato de texto exporta cada tipo Google (Docs→texto plano, Sheets→CSV).
_EXPORT_TEXTO = {
    _MIME_GOOGLE_DOC: "text/plain",
    _MIME_GOOGLE_SHEET: "text/csv",
}


@dataclass
class ArchivoDrive:
    """Un archivo (o carpeta) del Drive, tal como lo devuelve `files.list`."""

    id: str
    nombre: str
    tipo_mime: str


def _a_archivo(datos: dict) -> ArchivoDrive:
    """Mapea una entrada de `files(id,name,mimeType)` a nuestro `ArchivoDrive`."""
    return ArchivoDrive(
        id=datos.get("id", ""),
        nombre=datos.get("name", ""),
        tipo_mime=datos.get("mimeType", ""),
    )


class ClienteDriveReal:
    """Lista los archivos de UNA carpeta del Drive de la empresa. Resuelve el refresh
    token de forma perezosa (en `listar_archivos`, que es async) igual que el cliente
    Gmail, para que la fábrica pueda ser síncrona."""

    def __init__(
        self,
        *,
        almacen,
        token_ref: str,
        client_id: str,
        client_secret: str,
        cliente: httpx.AsyncClient | None = None,
    ) -> None:
        self._almacen = almacen
        self._token_ref = token_ref
        self._client_id = client_id
        self._client_secret = client_secret
        self._cliente = cliente

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

    async def listar_archivos(self, folder_id: str) -> list[ArchivoDrive]:
        """Lista los archivos NO en papelera de la carpeta `folder_id`.

        Pide sólo `id,name,mimeType` (lo justo para el panel/catálogo). Devuelve los
        archivos en el orden que entrega la Drive API.
        """
        http = self._http()
        try:
            token = await self._access_token(http)
            resp = await http.get(
                f"{BASE_DRIVE}/files",
                params={
                    "q": f"'{folder_id}' in parents and trashed=false",
                    "fields": "files(id,name,mimeType)",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return [_a_archivo(f) for f in resp.json().get("files", []) or []]
        finally:
            if self._cliente is None:
                await http.aclose()

    async def listar_carpetas(self) -> list[ArchivoDrive]:
        """Lista las CARPETAS (no archivos) del Drive del usuario. Es un DIAGNÓSTICO:

        * si responde, el token de la empresa TIENE acceso a Drive (el scope
          `drive.readonly` está concedido y el refresh es válido);
        * los IDs devueltos sirven para configurar la carpeta por empresa
          (`drive_folder_id`), sin tener que adivinarlos a mano.

        Filtra por `mimeType='application/vnd.google-apps.folder'` (sólo carpetas) y
        excluye la papelera. Mismo refresh OAuth y manejo de `http`/`finally` que
        `listar_archivos` (el access token efímero sale del refresh de la empresa,
        regla de oro #3).
        """
        http = self._http()
        try:
            token = await self._access_token(http)
            resp = await http.get(
                f"{BASE_DRIVE}/files",
                params={
                    "q": (
                        "mimeType='application/vnd.google-apps.folder' "
                        "and trashed=false"
                    ),
                    "fields": "files(id,name,mimeType)",
                    "pageSize": 100,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return [_a_archivo(f) for f in resp.json().get("files", []) or []]
        finally:
            if self._cliente is None:
                await http.aclose()

    async def buscar_archivos(self, consulta: str) -> list[ArchivoDrive]:
        """Busca en TODO el Drive del usuario (todas las carpetas) por NOMBRE Y
        CONTENIDO: `name contains` (título) o `fullText contains` (texto indexado del
        documento), excluyendo la papelera. Es la búsqueda en vivo que usa Javo para
        encontrar el tarifario/doc que necesita cotizar.

        Escapa las comillas simples de la consulta (Drive las usa como delimitador de
        cadena en `q`: sin escapar, una comilla rompería la query). Mismo refresh OAuth
        y manejo de `http`/`finally` que `listar_archivos`.
        """
        c = consulta.replace("'", "\\'")
        http = self._http()
        try:
            token = await self._access_token(http)
            resp = await http.get(
                f"{BASE_DRIVE}/files",
                params={
                    "q": (
                        f"(name contains '{c}' or fullText contains '{c}') "
                        "and trashed=false"
                    ),
                    "fields": "files(id,name,mimeType)",
                    "pageSize": 30,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return [_a_archivo(f) for f in resp.json().get("files", []) or []]
        finally:
            if self._cliente is None:
                await http.aclose()

    async def leer_documento(self, file_id: str, tipo_mime: str) -> str:
        """Devuelve el CONTENIDO del archivo como TEXTO para que Javo lo lea.

        * Google Docs → `export?mimeType=text/plain`.
        * Google Sheets → `export?mimeType=text/csv`.
        * Otros (xlsx/pdf/imágenes/…) → no se exportan a texto: devuelve un aviso corto
          (NO revienta, ni siquiera toca la red), para que Javo siga conversando y pida
          el dato si lo necesita.

        Mismo refresh OAuth y manejo de `http`/`finally` que `listar_archivos`.
        """
        formato = _EXPORT_TEXTO.get(tipo_mime)
        if formato is None:
            return f"[no exportable a texto: {tipo_mime}]"
        http = self._http()
        try:
            token = await self._access_token(http)
            resp = await http.get(
                f"{BASE_DRIVE}/files/{file_id}/export",
                params={"mimeType": formato},
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.text
        finally:
            if self._cliente is None:
                await http.aclose()


class FabricaClienteDriveReal:
    """Construye el `ClienteDriveReal` de UNA integración. Le pasa el `token_ref`
    (no el secreto en claro): el cliente resuelve el refresh contra `AlmacenSecretos`
    al momento de listar. Calca a `FabricaClienteGmailReal` (mismo refresh token de la
    empresa, porque el consentimiento cubre Gmail y Drive a la vez)."""

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

    def crear(self, integracion: Integracion) -> ClienteDriveReal:
        return ClienteDriveReal(
            almacen=self._almacen,
            token_ref=integracion.token_ref,
            client_id=self._client_id,
            client_secret=self._client_secret,
            cliente=self._cliente,
        )
