"""TR3 · `RepositorioIntegracionesSupabase` contra PostgREST (sin red).

Transporte httpx **mockeado**: verifica que el repo manda la `apikey` + el bearer
(JWT del usuario en los endpoints; service role en el poller), pega al endpoint
correcto de PostgREST y mapea la fila a `Integracion`. La prueba e2e de aislamiento
(empresa A no ve lo de B) corre contra `supabase start` en el entorno de integración.
"""
from uuid import UUID, uuid4

import httpx

from app.repositorios.integraciones import Integracion
from app.repositorios.integraciones_supabase import RepositorioIntegracionesSupabase

BASE = "https://proyecto.supabase.co"
KEY = "anon-o-service-key"
TOKEN = "jwt-o-service-role"
EMPRESA = UUID("0000c0de-0000-4000-8000-000000000001")


def _repo(handler):
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return RepositorioIntegracionesSupabase(BASE, KEY, TOKEN, cliente=cliente)


def _fila(empresa_id=EMPRESA, **extra):
    base = {
        "id": str(uuid4()),
        "empresa_id": str(empresa_id),
        "proveedor": "gmail",
        "token_ref": "projects/p/secrets/gmail-a",
        "casilla": "hola@capsulab.cl",
        "cursor": "123",
        "estado": "conectado",
    }
    base.update(extra)
    return base


async def test_obtener_por_empresa_manda_credenciales_filtra_y_mapea():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["auth"] = req.headers.get("authorization")
        visto["apikey"] = req.headers.get("apikey")
        visto["url"] = str(req.url)
        return httpx.Response(200, json=[_fila()])

    integ = await _repo(handler).obtener_por_empresa(EMPRESA)

    assert visto["auth"] == f"Bearer {TOKEN}"
    assert visto["apikey"] == KEY
    assert "/rest/v1/integraciones" in visto["url"]
    assert f"empresa_id=eq.{EMPRESA}" in visto["url"]
    assert isinstance(integ, Integracion) and integ.casilla == "hola@capsulab.cl"


async def test_obtener_por_empresa_sin_filas_devuelve_none():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).obtener_por_empresa(uuid4()) is None


async def test_listar_por_proveedor_filtra_y_mapea_lista():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["url"] = str(req.url)
        return httpx.Response(
            200, json=[_fila(empresa_id=uuid4()), _fila(empresa_id=uuid4())]
        )

    integs = await _repo(handler).listar_por_proveedor("gmail")

    assert "proveedor=eq.gmail" in visto["url"]
    assert len(integs) == 2 and all(isinstance(i, Integracion) for i in integs)


async def test_guardar_hace_upsert_por_empresa_y_proveedor():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["method"] = req.method
        visto["url"] = str(req.url)
        visto["prefer"] = req.headers.get("prefer", "")
        return httpx.Response(201, json=[_fila()])

    integ = Integracion(
        id=uuid4(), empresa_id=EMPRESA, token_ref="projects/p/secrets/gmail-a",
        casilla="hola@capsulab.cl", cursor=None, estado="conectado",
    )
    guardada = await _repo(handler).guardar(integ)

    assert visto["method"] == "POST"
    assert "on_conflict=empresa_id,proveedor" in visto["url"]
    assert "merge-duplicates" in visto["prefer"]
    assert isinstance(guardada, Integracion) and guardada.empresa_id == EMPRESA


async def test_actualizar_cursor_hace_patch_por_empresa():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["method"] = req.method
        visto["url"] = str(req.url)
        visto["body"] = req.content.decode()
        return httpx.Response(204)

    await _repo(handler).actualizar_cursor(EMPRESA, "cursor-nuevo")

    assert visto["method"] == "PATCH"
    assert f"empresa_id=eq.{EMPRESA}" in visto["url"]
    assert "cursor-nuevo" in visto["body"]


async def test_marcar_estado_hace_patch_con_el_estado_filtrando_por_proveedor():
    # #5 · marcar_estado es POR (empresa, proveedor): el PATCH filtra por AMBOS, así
    # un fallo de gmail NO arrastra a la fila clickup de la misma empresa.
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["method"] = req.method
        visto["url"] = str(req.url)
        visto["body"] = req.content.decode()
        return httpx.Response(204)

    await _repo(handler).marcar_estado(EMPRESA, "reconectar", "gmail")

    assert visto["method"] == "PATCH"
    assert f"empresa_id=eq.{EMPRESA}" in visto["url"]
    assert "proveedor=eq.gmail" in visto["url"]  # SÓLO la fila gmail
    assert "reconectar" in visto["body"]


async def test_eliminar_hace_delete_por_empresa():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["method"] = req.method
        visto["url"] = str(req.url)
        return httpx.Response(204)

    await _repo(handler).eliminar(EMPRESA)

    assert visto["method"] == "DELETE"
    assert f"empresa_id=eq.{EMPRESA}" in visto["url"]
