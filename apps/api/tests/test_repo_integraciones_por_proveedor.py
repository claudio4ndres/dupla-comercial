"""T1 (Spec 009) · `obtener_por_empresa_y_proveedor(empresa_id, proveedor)`.

Una misma empresa puede tener DOS integraciones (gmail Y clickup); el getter por
proveedor las distingue sin confundirlas. Cubre la versión en memoria (dobles de los
tests) y la real de Supabase (PostgREST, transporte mockeado, cero red).
"""
from uuid import UUID, uuid4

import httpx

from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.repositorios.integraciones_supabase import RepositorioIntegracionesSupabase

EMPRESA = UUID("0000c0de-0000-4000-8000-000000000001")
BASE = "https://proyecto.supabase.co"
KEY = "anon-o-service-key"
TOKEN = "jwt-o-service-role"


def _integ(proveedor, empresa_id=EMPRESA, **extra):
    base = dict(
        id=uuid4(),
        empresa_id=empresa_id,
        proveedor=proveedor,
        token_ref=f"secreto://{proveedor}-{empresa_id}",
    )
    base.update(extra)
    return Integracion(**base)


# ── En memoria ───────────────────────────────────────────────────────────────


async def test_memoria_distingue_gmail_y_clickup_de_la_misma_empresa():
    # Una empresa con AMBAS integraciones: el getter por proveedor devuelve la
    # correcta, sin confundir el token de gmail con el de clickup.
    repo = RepositorioIntegracionesEnMemoria(
        [_integ("gmail"), _integ("clickup")]
    )

    gmail = await repo.obtener_por_empresa_y_proveedor(EMPRESA, "gmail")
    clickup = await repo.obtener_por_empresa_y_proveedor(EMPRESA, "clickup")

    assert gmail is not None and gmail.proveedor == "gmail"
    assert clickup is not None and clickup.proveedor == "clickup"
    assert gmail.token_ref != clickup.token_ref


async def test_memoria_sin_esa_integracion_devuelve_none():
    # Empresa con sólo gmail: pedir clickup → None (aún no conectó ese conector).
    repo = RepositorioIntegracionesEnMemoria([_integ("gmail")])

    assert await repo.obtener_por_empresa_y_proveedor(EMPRESA, "clickup") is None


async def test_memoria_no_cruza_empresas():
    # El clickup de OTRA empresa jamás se devuelve para la empresa pedida.
    otra = uuid4()
    repo = RepositorioIntegracionesEnMemoria([_integ("clickup", empresa_id=otra)])

    assert await repo.obtener_por_empresa_y_proveedor(EMPRESA, "clickup") is None


async def test_memoria_marcar_estado_solo_toca_la_fila_de_su_proveedor():
    # #5 · marcar_estado('reconectar', 'gmail') NO debe arrastrar la fila clickup de la
    # MISMA empresa (el bug colateral: un fallo de Gmail dejaba ClickUp 'reconectar').
    repo = RepositorioIntegracionesEnMemoria(
        [_integ("gmail"), _integ("clickup")]
    )

    await repo.marcar_estado(EMPRESA, "reconectar", "gmail")

    gmail = await repo.obtener_por_empresa_y_proveedor(EMPRESA, "gmail")
    clickup = await repo.obtener_por_empresa_y_proveedor(EMPRESA, "clickup")
    assert gmail.estado == "reconectar"  # la fila gmail SÍ cambió
    assert clickup.estado == "conectado"  # la fila clickup quedó intacta


# ── Supabase (PostgREST, sin red) ────────────────────────────────────────────


def _repo(handler):
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return RepositorioIntegracionesSupabase(BASE, KEY, TOKEN, cliente=cliente)


async def test_supabase_filtra_por_empresa_y_proveedor_y_mapea():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["url"] = str(req.url)
        visto["auth"] = req.headers.get("authorization")
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(uuid4()),
                    "empresa_id": str(EMPRESA),
                    "proveedor": "clickup",
                    "token_ref": "projects/p/secrets/clickup-a",
                    "casilla": None,
                    "cursor": None,
                    "estado": "conectado",
                }
            ],
        )

    integ = await _repo(handler).obtener_por_empresa_y_proveedor(EMPRESA, "clickup")

    assert visto["auth"] == f"Bearer {TOKEN}"
    assert "/rest/v1/integraciones" in visto["url"]
    assert f"empresa_id=eq.{EMPRESA}" in visto["url"]
    assert "proveedor=eq.clickup" in visto["url"]
    assert isinstance(integ, Integracion) and integ.proveedor == "clickup"


async def test_supabase_sin_filas_devuelve_none():
    def handler(req):
        return httpx.Response(200, json=[])

    assert (
        await _repo(handler).obtener_por_empresa_y_proveedor(EMPRESA, "clickup")
        is None
    )
