"""T13 · `RepositorioConversacionesSupabase` contra PostgREST (sin red).

Usa un transporte httpx **mockeado**: verifica que el repo manda el JWT del usuario
(lo que dispara la RLS que aísla por empresa), pegue a los endpoints correctos de
PostgREST y traduzca el vocabulario del front (`javo`) al de la base (`asistente`) y
el tipo del chat (`t1`/`t2`) al de la tabla (`tipo_1`/`tipo_2`). La prueba real de
aislamiento corre contra `supabase start` (pgTAP), no en esta suite unitaria.
"""
import json
from uuid import UUID, uuid4

import httpx

from app.repositorios.conversaciones_supabase import RepositorioConversacionesSupabase

BASE = "https://proyecto.supabase.co"
ANON = "anon-key-de-prueba"
JWT = "jwt-del-usuario-empresa-a"
EMPRESA = UUID("0000c0de-0000-4000-8000-000000000001")


def _repo(handler):
    transporte = httpx.MockTransport(handler)
    cliente = httpx.AsyncClient(transport=transporte)
    return RepositorioConversacionesSupabase(BASE, ANON, JWT, cliente=cliente)


async def test_obtener_mensajes_manda_jwt_filtra_por_solicitud_y_mapea_rol():
    sol_id = uuid4()
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["auth"] = req.headers.get("authorization")
        visto["apikey"] = req.headers.get("apikey")
        visto["url"] = str(req.url)
        return httpx.Response(
            200,
            json=[
                {
                    "rol": "usuario",
                    "contenido": "Son 3 días",
                    "creado_en": "2026-06-01T10:00:00+00:00",
                },
                {
                    "rol": "asistente",
                    "contenido": "Perfecto, dejo catering.",
                    "creado_en": "2026-06-01T10:00:01+00:00",
                },
            ],
        )

    mensajes = await _repo(handler).obtener_mensajes(sol_id, EMPRESA)

    # El JWT del usuario en el header es lo que hace que la RLS filtre por SU empresa.
    assert visto["auth"] == f"Bearer {JWT}"
    assert visto["apikey"] == ANON
    assert "/rest/v1/mensajes" in visto["url"]
    # Filtra por la conversación de ESA solicitud y ordena cronológicamente.
    assert f"solicitud_id=eq.{sol_id}" in visto["url"]
    assert "order=creado_en" in visto["url"]

    # El `asistente` de la base se mapea al `javo` que entiende el front.
    assert [(m.rol, m.contenido) for m in mensajes] == [
        ("usuario", "Son 3 días"),
        ("javo", "Perfecto, dejo catering."),
    ]


async def test_obtener_mensajes_sin_filas_devuelve_lista_vacia():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).obtener_mensajes(uuid4(), EMPRESA) == []


async def test_guardar_turnos_crea_conversacion_si_no_existe_y_postea_mensajes():
    sol_id = uuid4()
    conv_id = uuid4()
    peticiones: list[tuple[str, str, dict | list | None]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        cuerpo = json.loads(req.content) if req.content else None
        peticiones.append((req.method, str(req.url), cuerpo))

        # 1) GET conversación por (solicitud) → no existe.
        if req.method == "GET" and "/conversaciones" in str(req.url):
            return httpx.Response(200, json=[])
        # 2) POST crea la conversación → devuelve su id.
        if req.method == "POST" and "/conversaciones" in str(req.url):
            return httpx.Response(201, json=[{"id": str(conv_id)}])
        # 3) POST mensajes.
        if req.method == "POST" and "/mensajes" in str(req.url):
            return httpx.Response(201, json=[])
        return httpx.Response(500, json={})

    await _repo(handler).guardar_turnos(
        sol_id,
        EMPRESA,
        "t1",
        [
            {"rol": "usuario", "contenido": "uno"},
            {"rol": "javo", "contenido": "dos"},
        ],
    )

    # Buscó la conversación (GET) antes de crearla (POST).
    assert any(m == "GET" and "/conversaciones" in u for m, u, _ in peticiones)
    post_conv = next(c for m, u, c in peticiones if m == "POST" and "/conversaciones" in u)
    # La conversación se crea con empresa, solicitud y el tipo mapeado a la tabla.
    assert post_conv["solicitud_id"] == str(sol_id)
    assert post_conv["empresa_id"] == str(EMPRESA)
    assert post_conv["tipo"] == "tipo_1"

    post_msg = next(c for m, u, c in peticiones if m == "POST" and "/mensajes" in u)
    filas = post_msg if isinstance(post_msg, list) else [post_msg]
    # Los mensajes se insertan con el conversacion_id creado y el rol mapeado a la base.
    assert all(f["conversacion_id"] == str(conv_id) for f in filas)
    assert [f["rol"] for f in filas] == ["usuario", "asistente"]
    assert [f["contenido"] for f in filas] == ["uno", "dos"]


async def test_guardar_turnos_reusa_conversacion_existente():
    sol_id = uuid4()
    conv_id = uuid4()
    metodos_ruta: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        metodos_ruta.append((req.method, str(req.url)))
        if req.method == "GET" and "/conversaciones" in str(req.url):
            return httpx.Response(200, json=[{"id": str(conv_id)}])
        if req.method == "POST" and "/mensajes" in str(req.url):
            return httpx.Response(201, json=[])
        return httpx.Response(500, json={})

    await _repo(handler).guardar_turnos(
        sol_id, EMPRESA, "t2", [{"rol": "javo", "contenido": "hola"}]
    )

    # NO debe crear una conversación nueva (no hay POST a /conversaciones).
    assert not any(m == "POST" and "/conversaciones" in u for m, u in metodos_ruta)
    assert any(m == "POST" and "/mensajes" in u for m, u in metodos_ruta)


# ── Borrador de la cotización en curso (0009) ────────────────────────────────
async def test_guardar_borrador_patchea_la_columna_de_la_conversacion():
    sol_id = uuid4()
    conv_id = uuid4()
    peticiones: list[tuple[str, str, dict | list | None]] = []
    borrador = {
        "componentes": [{"nombre": "Promotoras", "valor_unitario": 240000}],
        "tareas": [],
        "fuentes": [],
    }

    def handler(req: httpx.Request) -> httpx.Response:
        cuerpo = json.loads(req.content) if req.content else None
        peticiones.append((req.method, str(req.url), cuerpo))
        # Conversación ya existe (find-or-create devuelve su id).
        if req.method == "GET" and "/conversaciones" in str(req.url):
            return httpx.Response(200, json=[{"id": str(conv_id)}])
        # PATCH del borrador sobre esa conversación.
        if req.method == "PATCH" and "/conversaciones" in str(req.url):
            return httpx.Response(200, json=[{"id": str(conv_id)}])
        return httpx.Response(500, json={})

    await _repo(handler).guardar_borrador(sol_id, EMPRESA, "t1", borrador)

    # El borrador se PATCHea en la fila de la conversación (su columna jsonb).
    patch = next(c for m, u, c in peticiones if m == "PATCH" and "/conversaciones" in u)
    assert patch["cotizacion_borrador"] == borrador
    # El PATCH apunta a la conversación creada/encontrada (por id), con el JWT (RLS).
    url_patch = next(u for m, u, _ in peticiones if m == "PATCH" and "/conversaciones" in u)
    assert f"id=eq.{conv_id}" in url_patch


async def test_obtener_borrador_lee_la_columna_filtrando_por_solicitud():
    sol_id = uuid4()
    visto = {}
    borrador = {"componentes": [{"nombre": "Promotoras"}], "tareas": [], "fuentes": []}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["auth"] = req.headers.get("authorization")
        visto["url"] = str(req.url)
        return httpx.Response(200, json=[{"cotizacion_borrador": borrador}])

    resultado = await _repo(handler).obtener_borrador(sol_id, EMPRESA)

    # El JWT del usuario activa la RLS; se filtra por la conversación de ESA solicitud.
    assert visto["auth"] == f"Bearer {JWT}"
    assert "/rest/v1/conversaciones" in visto["url"]
    assert f"solicitud_id=eq.{sol_id}" in visto["url"]
    assert "cotizacion_borrador" in visto["url"]
    assert resultado == borrador


async def test_obtener_borrador_sin_conversacion_devuelve_none():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).obtener_borrador(uuid4(), EMPRESA) is None


async def test_obtener_borrador_con_columna_nula_devuelve_none():
    # La conversación existe pero aún no tiene borrador (columna NULL) → None.
    def handler(req):
        return httpx.Response(200, json=[{"cotizacion_borrador": None}])

    assert await _repo(handler).obtener_borrador(uuid4(), EMPRESA) is None
