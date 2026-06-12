"""TR1 · Cliente Gmail real (refresh OAuth + historyId) **sin red**.

Usa un transporte httpx **mockeado** que intercepta el endpoint de token de
Google y la API de Gmail (history/messages/profile): cero llamadas reales, cero
credenciales reales (CA6). Verifica lo esencial de la tarea:

* se construye sin tocar la red (requisito explícito de TR1);
* refresca el access token con el refresh token (resuelto desde `AlmacenSecretos`);
* con `cursor` usa `users.history.list` y avanza el cursor al nuevo `historyId`;
* sin `cursor` cae al fallback `after:` y fija el cursor desde el `historyId` actual;
* si el refresh falla (token revocado/expirado) lanza `ErrorAutenticacionGmail` (CA7).
"""
import base64
from uuid import uuid4

import httpx

from app.repositorios.integraciones import Integracion
from app.servicios.gmail import ErrorAutenticacionGmail, MensajeCorreo
from app.servicios.gmail_real import (
    ClienteGmailReal,
    FabricaClienteGmailReal,
    _a_mensaje,
)
from app.servicios.secretos import AlmacenSecretosEnMemoria

CLIENT_ID = "client-id-de-prueba"
CLIENT_SECRET = "client-secret-de-prueba"
REFRESH = "refresh-token-de-prueba"


def _b64url(texto: str) -> str:
    return base64.urlsafe_b64encode(texto.encode()).decode()


def _mensaje_texto_plano(msg_id: str, de: str, asunto: str, cuerpo: str) -> dict:
    return {
        "id": msg_id,
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": de},
                {"name": "Subject", "value": asunto},
            ],
            "body": {"data": _b64url(cuerpo)},
        },
    }


def _mensaje_multipart(msg_id: str, de: str, asunto: str, cuerpo: str) -> dict:
    return {
        "id": msg_id,
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": de},
                {"name": "Subject", "value": asunto},
            ],
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64url("<p>hola</p>")}},
                {"mimeType": "text/plain", "body": {"data": _b64url(cuerpo)}},
            ],
        },
    }


def _ruteador(registro: list, *, history=None, mensajes=None, lista_ids=None,
              history_id="9999", token_status=200):
    """Devuelve un handler de `httpx.MockTransport` que despacha por path."""
    mensajes = mensajes or {}

    def handler(req: httpx.Request) -> httpx.Response:
        registro.append(req)
        path = req.url.path
        if path.endswith("/token"):
            if token_status != 200:
                return httpx.Response(token_status, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "ya29.token-fresco",
                                             "expires_in": 3599, "token_type": "Bearer"})
        if path.endswith("/history"):
            return httpx.Response(200, json=history or {"historyId": history_id})
        if path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "x@y.cl",
                                             "historyId": history_id})
        if path.endswith("/messages"):  # listado (fallback inicial)
            return httpx.Response(200, json={"messages": lista_ids or []})
        # get de un mensaje: .../messages/<id>
        msg_id = path.rsplit("/", 1)[1]
        return httpx.Response(200, json=mensajes[msg_id])

    return handler


def _cliente_http(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _almacen_con_refresh() -> tuple[AlmacenSecretosEnMemoria, str]:
    almacen = AlmacenSecretosEnMemoria()
    token_ref = await almacen.guardar("gmail:empresa-a", REFRESH)
    return almacen, token_ref


# --- Construcción sin red (requisito explícito de TR1) -----------------------

async def test_se_construye_sin_tocar_la_red():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    cliente = ClienteGmailReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        casilla="hola@capsulab.cl", cliente=_cliente_http(_ruteador(registro)),
    )
    assert hasattr(cliente, "listar_nuevos")
    assert registro == []  # construir NO dispara ninguna petición


def test_fabrica_crea_cliente_por_integracion_sin_red():
    registro: list = []
    fabrica = FabricaClienteGmailReal(
        almacen=AlmacenSecretosEnMemoria(),
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(_ruteador(registro)),
    )
    integ = Integracion(id=uuid4(), empresa_id=uuid4(), token_ref="secreto://x",
                        casilla="hola@capsulab.cl", cursor="123")
    cliente = fabrica.crear(integ)
    assert isinstance(cliente, ClienteGmailReal)
    assert registro == []


# --- Camino con cursor: users.history.list + mapeo + avance del cursor -------

async def test_con_cursor_usa_history_list_y_mapea_los_mensajes():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    history = {
        "history": [
            {"id": "501", "messagesAdded": [{"message": {"id": "msg-a"}}]},
            {"id": "502", "messagesAdded": [{"message": {"id": "msg-b"}}]},
        ],
        "historyId": "777",
    }
    mensajes = {
        "msg-a": _mensaje_texto_plano(
            "msg-a", "Zona Espiga <ventas@zonaespiga.cl>",
            "Sampling de sopaipillas", "quiero un sampling afuera del metro"),
        "msg-b": _mensaje_multipart(
            "msg-b", "Marca F1 <hola@f1.cl>", "Idea para la F1", "necesito ideas"),
    }
    handler = _ruteador(registro, history=history, mensajes=mensajes)
    cliente = ClienteGmailReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    msgs, nuevo_cursor = await cliente.listar_nuevos("500")

    assert nuevo_cursor == "777"  # avanza al historyId de la respuesta
    assert [m.gmail_msg_id for m in msgs] == ["msg-a", "msg-b"]
    a = msgs[0]
    assert isinstance(a, MensajeCorreo)
    assert a.remitente == "Zona Espiga" and a.correo_origen == "ventas@zonaespiga.cl"
    assert a.asunto == "Sampling de sopaipillas"
    assert a.cuerpo == "quiero un sampling afuera del metro"
    assert msgs[1].cuerpo == "necesito ideas"  # extrae el text/plain del multipart

    # El refresh OAuth ocurrió y el history.list usó el access token fresco.
    token_req = next(r for r in registro if r.url.path.endswith("/token"))
    assert REFRESH in token_req.content.decode()
    hist_req = next(r for r in registro if r.url.path.endswith("/history"))
    assert hist_req.headers["authorization"] == "Bearer ya29.token-fresco"
    assert hist_req.url.params["startHistoryId"] == "500"


# --- Robustez (auditoría) ----------------------------------------------------

async def test_history_404_resincroniza_desde_cero_sin_reventar():
    # Auditoría #8: si el historyId caducó, Gmail responde 404. En vez de tumbar el
    # poller con 500, re-sincronizamos desde cero (fallback inicial) y fijamos cursor.
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    mensajes = {"msg-x": _mensaje_texto_plano("msg-x", "A <a@x.cl>", "Hola", "cuerpo")}

    def handler(req: httpx.Request) -> httpx.Response:
        registro.append(req)
        path = req.url.path
        if path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3599,
                                             "token_type": "Bearer"})
        if path.endswith("/history"):
            return httpx.Response(404, json={"error": {"code": 404}})  # historyId viejo
        if path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "x@y.cl", "historyId": "888"})
        if path.endswith("/messages"):
            return httpx.Response(200, json={"messages": [{"id": "msg-x"}]})
        return httpx.Response(200, json=mensajes[path.rsplit("/", 1)[1]])

    cliente = ClienteGmailReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    msgs, nuevo_cursor = await cliente.listar_nuevos("123")  # cursor viejo → 404

    assert [m.gmail_msg_id for m in msgs] == ["msg-x"]  # re-sync trajo los iniciales
    assert nuevo_cursor == "888"  # cursor nuevo desde el profile (no reventó)


async def test_mensaje_borrado_404_se_salta_sin_reventar_el_poll():
    # Si UN correo da 404 al bajarlo (fue BORRADO entre que el history lo listó y
    # ahora), antes el list-comprehension reventaba el poll entero y el cursor jamás
    # avanzaba → el poller quedaba atascado PARA SIEMPRE en ese correo. Ahora se SALTA
    # el borrado, se ingieren los demás y el cursor avanza igual.
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    history = {
        "history": [
            {"id": "501", "messagesAdded": [{"message": {"id": "msg-vivo"}}]},
            {"id": "502", "messagesAdded": [{"message": {"id": "msg-borrado"}}]},
        ],
        "historyId": "777",
    }

    def handler(req: httpx.Request) -> httpx.Response:
        registro.append(req)
        path = req.url.path
        if path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3599,
                                             "token_type": "Bearer"})
        if path.endswith("/history"):
            return httpx.Response(200, json=history)
        msg_id = path.rsplit("/", 1)[1]
        if msg_id == "msg-borrado":
            return httpx.Response(404, json={"error": {"code": 404}})  # correo borrado
        return httpx.Response(
            200,
            json=_mensaje_texto_plano(msg_id, "A <a@x.cl>", "Hola", "vivo"),
        )

    cliente = ClienteGmailReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    msgs, nuevo_cursor = await cliente.listar_nuevos("500")

    # El borrado se saltó; el vivo se ingirió; el cursor avanzó (no se atascó).
    assert [m.gmail_msg_id for m in msgs] == ["msg-vivo"]
    assert nuevo_cursor == "777"


async def test_primer_sync_pagina_con_next_page_token():
    # Auditoría #9: el primer sync PAGINA (antes solo traía la primera página de 50).
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    mensajes = {
        f"m{i}": _mensaje_texto_plano(f"m{i}", "A <a@x.cl>", "s", "c") for i in range(3)
    }

    def handler(req: httpx.Request) -> httpx.Response:
        registro.append(req)
        path = req.url.path
        if path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3599,
                                             "token_type": "Bearer"})
        if path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "x@y.cl", "historyId": "999"})
        if path.endswith("/messages"):
            if "pageToken" in req.url.params:  # página 2: sin nextPageToken → fin
                return httpx.Response(200, json={"messages": [{"id": "m2"}]})
            return httpx.Response(200, json={"messages": [{"id": "m0"}, {"id": "m1"}],
                                             "nextPageToken": "PAG2"})
        return httpx.Response(200, json=mensajes[path.rsplit("/", 1)[1]])

    cliente = ClienteGmailReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    msgs, _ = await cliente.listar_nuevos(None)  # sin cursor → primer sync

    assert [m.gmail_msg_id for m in msgs] == ["m0", "m1", "m2"]  # trajo AMBAS páginas


def test_correo_solo_html_cae_al_html_y_no_queda_vacio():
    # Correos solo-HTML (Uber, newsletters) NO traen text/plain. Antes el cuerpo
    # quedaba vacío → la clasificación fallaba con 400 (mensaje vacío). Ahora cae al
    # text/html limpiado, así Javo sí puede clasificarlo.
    datos = {
        "id": "msg-html",
        "payload": {
            "mimeType": "text/html",
            "headers": [
                {"name": "From", "value": "Uber <no-reply@uber.com>"},
                {"name": "Subject", "value": "Tu viaje del viernes"},
            ],
            "body": {
                "data": _b64url(
                    "<html><head><style>p{color:red}</style></head>"
                    "<body><p>Gracias por tu viaje</p><b>$5.000</b></body></html>"
                )
            },
        },
    }

    m = _a_mensaje(datos)

    assert m.asunto == "Tu viaje del viernes"
    assert m.cuerpo == "Gracias por tu viaje $5.000"  # sin tags, sin <style>, limpio
    assert m.cuerpo.strip() != ""  # ya no es vacío → no más 400


def test_a_mensaje_captura_la_fecha_real_de_recepcion():
    # internalDate de Gmail (epoch en ms) → fecha real del correo, para ordenar la
    # bandeja por recencia en vez de por la hora de ingesta.
    from datetime import datetime, timezone

    datos = {
        "id": "m-fecha",
        "internalDate": "1717200000000",  # epoch en milisegundos
        "payload": {
            "mimeType": "text/plain",
            "headers": [{"name": "Subject", "value": "x"}],
            "body": {"data": _b64url("hola")},
        },
    }

    m = _a_mensaje(datos)

    assert m.fecha == datetime.fromtimestamp(1717200000, tz=timezone.utc)


# --- Camino sin cursor: fallback `after:` + cursor desde el historyId actual --

async def test_sin_cursor_usa_fallback_y_fija_cursor_desde_profile():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    mensajes = {
        "msg-1": _mensaje_texto_plano("msg-1", "A <a@a.cl>", "Hola", "uno"),
    }
    handler = _ruteador(
        registro, mensajes=mensajes,
        lista_ids=[{"id": "msg-1"}], history_id="424242",
    )
    cliente = ClienteGmailReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    msgs, nuevo_cursor = await cliente.listar_nuevos(None)

    assert [m.gmail_msg_id for m in msgs] == ["msg-1"]
    assert nuevo_cursor == "424242"  # baseline tomado del profile
    lista_req = next(r for r in registro if r.url.path.endswith("/messages"))
    assert lista_req.url.params["q"].startswith("after:")
    # Excluye el ruido (promos/redes/foros/novedades) → solo el inbox "Primary".
    assert "-category:promotions" in lista_req.url.params["q"]
    assert "-category:updates" in lista_req.url.params["q"]


# --- Resiliencia del token (CA7): refresh inválido → ErrorAutenticacionGmail --

async def test_refresh_invalido_lanza_error_de_autenticacion():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    handler = _ruteador(registro, token_status=400)
    cliente = ClienteGmailReal(
        almacen=almacen, token_ref=token_ref,
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )

    try:
        await cliente.listar_nuevos("500")
        assert False, "debía lanzar ErrorAutenticacionGmail"
    except ErrorAutenticacionGmail:
        pass
    # No siguió a Gmail tras fallar el refresh.
    assert not any(r.url.path.endswith("/history") for r in registro)


async def test_sin_refresh_en_el_almacen_lanza_error_de_autenticacion():
    registro: list = []
    almacen = AlmacenSecretosEnMemoria()  # vacío: no hay refresh guardado
    cliente = ClienteGmailReal(
        almacen=almacen, token_ref="secreto://no-existe",
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(_ruteador(registro)),
    )

    try:
        await cliente.listar_nuevos("500")
        assert False, "debía lanzar ErrorAutenticacionGmail"
    except ErrorAutenticacionGmail:
        pass
    assert registro == []  # ni siquiera intentó el refresh sin secreto


# --- La fábrica resuelve el refresh desde el almacén y arma un cliente usable --

async def test_fabrica_resuelve_refresh_desde_almacen_y_lista():
    registro: list = []
    almacen, token_ref = await _almacen_con_refresh()
    mensajes = {"msg-a": _mensaje_texto_plano("msg-a", "A <a@a.cl>", "Hi", "hola")}
    history = {"history": [{"id": "1", "messagesAdded": [{"message": {"id": "msg-a"}}]}],
               "historyId": "888"}
    handler = _ruteador(registro, history=history, mensajes=mensajes)
    fabrica = FabricaClienteGmailReal(
        almacen=almacen, client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        cliente=_cliente_http(handler),
    )
    integ = Integracion(id=uuid4(), empresa_id=uuid4(), token_ref=token_ref,
                        casilla="hola@capsulab.cl", cursor="500")

    msgs, nuevo_cursor = await fabrica.crear(integ).listar_nuevos(integ.cursor)

    assert nuevo_cursor == "888" and [m.gmail_msg_id for m in msgs] == ["msg-a"]
    token_req = next(r for r in registro if r.url.path.endswith("/token"))
    assert REFRESH in token_req.content.decode()  # leyó el refresh del almacén
