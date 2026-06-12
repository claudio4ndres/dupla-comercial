"""Cliente Google Drive real (refresh OAuth + listar archivos de una carpeta) **sin red**.

Calca el patrón de `test_cliente_gmail_real.py`: un transporte httpx **mockeado**
intercepta el endpoint de token de Google y la Drive API (`/drive/v3/files`). Cero
llamadas reales, cero credenciales reales. Verifica lo esencial:

* se construye sin tocar la red;
* refresca el access token con el refresh token (resuelto desde `AlmacenSecretos`);
* `listar_archivos` consulta la carpeta con el `q`/`fields` correctos y parsea
  `files(id,name,mimeType)` a `ArchivoDrive`;
* carpeta vacía → lista vacía;
* si el refresh falla (token revocado/expirado) lanza `ErrorAutenticacionGmail`;
* la fábrica resuelve el refresh desde el almacén y arma un cliente usable.
"""
from uuid import uuid4

import httpx

from app.repositorios.integraciones import Integracion
from app.servicios.drive_real import (
    ArchivoDrive,
    ClienteDriveReal,
    FabricaClienteDriveReal,
)
from app.servicios.gmail import ErrorAutenticacionGmail
from app.servicios.secretos import AlmacenSecretosEnMemoria

CLIENT_ID = "client-id-de-prueba"
CLIENT_SECRET = "client-secret-de-prueba"
REFRESH = "refresh-token-de-prueba"
CARPETA = "carpeta-de-prueba-123"


def _ruteador(registro: list, *, files=None, token_status=200):
    """Handler de `httpx.MockTransport` que despacha por path (token / files)."""

    def handler(req: httpx.Request) -> httpx.Response:
        registro.append(req)
        path = req.url.path
        if path.endswith("/token"):
            if token_status != 200:
                return httpx.Response(token_status, json={"error": "invalid_grant"})
            return httpx.Response(
                200,
                json={
                    "access_token": "ya29.token-fresco",
                    "expires_in": 3599,
                    "token_type": "Bearer",
                },
            )
        if path.endswith("/files"):
            return httpx.Response(200, json={"files": files if files is not None else []})
        return httpx.Response(404, json={"error": "no esperado"})

    return handler


def _cliente_http(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _almacen_con_refresh() -> tuple[AlmacenSecretosEnMemoria, str]:
    almacen = AlmacenSecretosEnMemoria()
    token_ref = await almacen.guardar("gmail:empresa-a", REFRESH)
    return almacen, token_ref


# --- Construcción sin red -----------------------------------------------------

async def test_se_construye_sin_tocar_la_red():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    cliente = ClienteDriveReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(_ruteador(registro)),
    )
    assert hasattr(cliente, "listar_archivos")
    assert registro == []  # construir NO dispara ninguna petición


def test_fabrica_crea_cliente_por_integracion_sin_red():
    registro: list = []
    fabrica = FabricaClienteDriveReal(
        almacen=AlmacenSecretosEnMemoria(),
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(_ruteador(registro)),
    )
    integ = Integracion(id=uuid4(), empresa_id=uuid4(), token_ref="secreto://x",
                        casilla="hola@capsulab.cl", cursor="123")
    cliente = fabrica.crear(integ)
    assert isinstance(cliente, ClienteDriveReal)
    assert registro == []


# --- listar_archivos: refresh OAuth + query + parseo de la respuesta ----------

async def test_listar_archivos_consulta_la_carpeta_y_parsea_la_respuesta():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    files = [
        {"id": "f1", "name": "Tarifario.xlsx",
         "mimeType": "application/vnd.google-apps.spreadsheet"},
        {"id": "f2", "name": "PRODUCCIÓN 3D",
         "mimeType": "application/vnd.google-apps.folder"},
    ]
    handler = _ruteador(registro, files=files)
    cliente = ClienteDriveReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    archivos = await cliente.listar_archivos(CARPETA)

    assert [a.nombre for a in archivos] == ["Tarifario.xlsx", "PRODUCCIÓN 3D"]
    a = archivos[0]
    assert isinstance(a, ArchivoDrive)
    assert a.id == "f1"
    assert a.tipo_mime == "application/vnd.google-apps.spreadsheet"

    # El refresh OAuth ocurrió y el listado usó el access token fresco.
    token_req = next(r for r in registro if r.url.path.endswith("/token"))
    assert REFRESH in token_req.content.decode()
    files_req = next(r for r in registro if r.url.path.endswith("/files"))
    assert files_req.headers["authorization"] == "Bearer ya29.token-fresco"
    # El `q` acota a la carpeta y excluye papelera; `fields` pide id/name/mimeType.
    q = files_req.url.params["q"]
    assert f"'{CARPETA}' in parents" in q
    assert "trashed=false" in q
    assert files_req.url.params["fields"] == "files(id,name,mimeType)"


async def test_listar_archivos_carpeta_vacia_devuelve_lista_vacia():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    cliente = ClienteDriveReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(_ruteador(registro, files=[])),
    )

    archivos = await cliente.listar_archivos(CARPETA)

    assert archivos == []


# --- listar_carpetas: diagnóstico de acceso al Drive (sólo carpetas) ----------

async def test_listar_carpetas_pide_solo_carpetas_y_parsea_la_respuesta():
    # Diagnóstico: si el token responde a este listado, TIENE acceso a Drive; los IDs
    # devueltos sirven para configurar la carpeta por empresa.
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    files = [
        {"id": "carpeta-1", "name": "Capsulab · Operaciones",
         "mimeType": "application/vnd.google-apps.folder"},
        {"id": "carpeta-2", "name": "Tarifarios",
         "mimeType": "application/vnd.google-apps.folder"},
    ]
    handler = _ruteador(registro, files=files)
    cliente = ClienteDriveReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    carpetas = await cliente.listar_carpetas()

    assert [c.nombre for c in carpetas] == ["Capsulab · Operaciones", "Tarifarios"]
    c = carpetas[0]
    assert isinstance(c, ArchivoDrive)
    assert c.id == "carpeta-1"
    assert c.tipo_mime == "application/vnd.google-apps.folder"

    # El refresh OAuth ocurrió y el listado usó el access token fresco.
    token_req = next(r for r in registro if r.url.path.endswith("/token"))
    assert REFRESH in token_req.content.decode()
    files_req = next(r for r in registro if r.url.path.endswith("/files"))
    assert files_req.headers["authorization"] == "Bearer ya29.token-fresco"
    # El `q` filtra SÓLO carpetas (no archivos) y excluye papelera.
    q = files_req.url.params["q"]
    assert "mimeType='application/vnd.google-apps.folder'" in q
    assert "trashed=false" in q


# --- buscar_archivos: busca en TODO el Drive (nombre + contenido) -------------

async def test_buscar_archivos_busca_en_todo_el_drive_por_nombre_y_contenido():
    # Javo busca en vivo en TODO el Drive (sin acotar a una carpeta): por nombre Y por
    # contenido (fullText). Verifica el `q` y el parseo de la respuesta.
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    files = [
        {"id": "doc1", "name": "Tarifario promotores 2026",
         "mimeType": "application/vnd.google-apps.document"},
        {"id": "sht1", "name": "Costos catering",
         "mimeType": "application/vnd.google-apps.spreadsheet"},
    ]
    handler = _ruteador(registro, files=files)
    cliente = ClienteDriveReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    archivos = await cliente.buscar_archivos("tarifario")

    assert [a.nombre for a in archivos] == ["Tarifario promotores 2026", "Costos catering"]
    a = archivos[0]
    assert isinstance(a, ArchivoDrive)
    assert a.id == "doc1"
    assert a.tipo_mime == "application/vnd.google-apps.document"

    # El refresh OAuth ocurrió y el listado usó el access token fresco.
    token_req = next(r for r in registro if r.url.path.endswith("/token"))
    assert REFRESH in token_req.content.decode()
    files_req = next(r for r in registro if r.url.path.endswith("/files"))
    assert files_req.headers["authorization"] == "Bearer ya29.token-fresco"
    # El `q` busca en TODO el Drive: por nombre (name contains) Y contenido (fullText).
    q = files_req.url.params["q"]
    assert "name contains 'tarifario'" in q
    assert "fullText contains 'tarifario'" in q
    assert "trashed=false" in q
    assert files_req.url.params["fields"] == "files(id,name,mimeType)"


async def test_buscar_archivos_escapa_comillas_simples_de_la_consulta():
    # Una consulta con comilla simple no debe romper el `q` de Drive (inyección).
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    cliente = ClienteDriveReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(_ruteador(registro, files=[])),
    )

    await cliente.buscar_archivos("l'oréal")

    files_req = next(r for r in registro if r.url.path.endswith("/files"))
    q = files_req.url.params["q"]
    # La comilla simple va escapada (Drive usa \' dentro de cadenas con comilla simple).
    assert "l\\'oréal" in q


# --- leer_documento: exporta el contenido a texto plano ----------------------

def _ruteador_export(registro: list, *, contenido: str, content_type: str):
    """Handler que ademas del /token responde el /files/{id}/export con texto."""

    def handler(req: httpx.Request) -> httpx.Response:
        registro.append(req)
        path = req.url.path
        if path.endswith("/token"):
            return httpx.Response(
                200,
                json={"access_token": "ya29.token-fresco", "expires_in": 3599,
                      "token_type": "Bearer"},
            )
        if path.endswith("/export"):
            return httpx.Response(
                200, text=contenido, headers={"content-type": content_type}
            )
        return httpx.Response(404, json={"error": "no esperado"})

    return handler


async def test_leer_documento_google_doc_exporta_texto_plano():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    handler = _ruteador_export(
        registro, contenido="Promotora día: 120000", content_type="text/plain"
    )
    cliente = ClienteDriveReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    texto = await cliente.leer_documento(
        "doc1", "application/vnd.google-apps.document"
    )

    assert texto == "Promotora día: 120000"
    export_req = next(r for r in registro if r.url.path.endswith("/export"))
    assert export_req.headers["authorization"] == "Bearer ya29.token-fresco"
    assert "/files/doc1/export" in export_req.url.path
    assert export_req.url.params["mimeType"] == "text/plain"


async def test_leer_documento_google_sheet_exporta_csv():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    handler = _ruteador_export(
        registro, contenido="item,valor\npromotora,120000", content_type="text/csv"
    )
    cliente = ClienteDriveReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    texto = await cliente.leer_documento(
        "sht1", "application/vnd.google-apps.spreadsheet"
    )

    assert "promotora,120000" in texto
    export_req = next(r for r in registro if r.url.path.endswith("/export"))
    assert export_req.url.params["mimeType"] == "text/csv"


async def test_leer_documento_no_exportable_devuelve_aviso_sin_reventar():
    # Un xlsx/pdf binario no se exporta a texto: devuelve un aviso corto, NO revienta
    # (ni siquiera toca la red, porque no hay export aplicable).
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    cliente = ClienteDriveReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(_ruteador_export(registro, contenido="", content_type="x")),
    )

    texto = await cliente.leer_documento("pdf1", "application/pdf")

    assert "no exportable" in texto.lower()
    assert "application/pdf" in texto


# --- Resiliencia del token: refresh inválido → ErrorAutenticacionGmail --------

async def test_refresh_invalido_lanza_error_de_autenticacion():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    handler = _ruteador(registro, token_status=400)
    cliente = ClienteDriveReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    try:
        await cliente.listar_archivos(CARPETA)
        assert False, "debía lanzar ErrorAutenticacionGmail"
    except ErrorAutenticacionGmail:
        pass
    # No siguió a la Drive API tras fallar el refresh.
    assert not any(r.url.path.endswith("/files") for r in registro)


async def test_sin_refresh_en_el_almacen_lanza_error_de_autenticacion():
    registro: list = []
    almacen = AlmacenSecretosEnMemoria()  # vacío: no hay refresh guardado
    cliente = ClienteDriveReal(
        almacen=almacen, token_ref="secreto://no-existe",
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(_ruteador(registro)),
    )

    try:
        await cliente.listar_archivos(CARPETA)
        assert False, "debía lanzar ErrorAutenticacionGmail"
    except ErrorAutenticacionGmail:
        pass
    assert registro == []  # ni siquiera intentó el refresh sin secreto


# --- La fábrica resuelve el refresh desde el almacén y arma un cliente usable --

async def test_fabrica_resuelve_refresh_desde_almacen_y_lista():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    files = [{"id": "f1", "name": "Brief.pdf", "mimeType": "application/pdf"}]
    handler = _ruteador(registro, files=files)
    fabrica = FabricaClienteDriveReal(
        almacen=almacen, client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )
    integ = Integracion(id=uuid4(), empresa_id=uuid4(), token_ref=token_ref,
                        casilla="hola@capsulab.cl", cursor="500")

    archivos = await fabrica.crear(integ).listar_archivos(CARPETA)

    assert [a.nombre for a in archivos] == ["Brief.pdf"]
    token_req = next(r for r in registro if r.url.path.endswith("/token"))
    assert REFRESH in token_req.content.decode()  # leyó el refresh del almacén
