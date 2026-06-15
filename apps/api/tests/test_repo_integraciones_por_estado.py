"""Spec 010 · CA3 · `listar_por_estado(estado)` en el repo de integraciones.

Es la consulta que alimenta la observabilidad del operador: "¿qué integraciones están
en 'reconectar'?". Cruza empresas por diseño (canal de operador / service-role), así que
vive en el repo y se filtra por `estado`. Cubre la versión en memoria (dobles) y la real
de Supabase (PostgREST, transporte mockeado, cero red).
"""
from uuid import UUID, uuid4

import httpx

from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.repositorios.integraciones_supabase import RepositorioIntegracionesSupabase

EMPRESA_A = UUID("0000c0de-0000-4000-8000-000000000001")
EMPRESA_B = UUID("0000c0de-0000-4000-8000-000000000002")
BASE = "https://proyecto.supabase.co"
KEY = "anon-o-service-key"
TOKEN = "jwt-o-service-role"


def _integ(proveedor, empresa_id=EMPRESA_A, estado="conectado", **extra):
    base = dict(
        id=uuid4(),
        empresa_id=empresa_id,
        proveedor=proveedor,
        token_ref=f"secreto://{proveedor}-{empresa_id}",
        estado=estado,
    )
    base.update(extra)
    return Integracion(**base)


# ── En memoria ───────────────────────────────────────────────────────────────


async def test_memoria_lista_solo_las_del_estado_pedido():
    # Mezcla de proveedores/empresas y estados: filtra por 'reconectar'.
    repo = RepositorioIntegracionesEnMemoria(
        [
            _integ("gmail", EMPRESA_A, estado="reconectar"),
            _integ("clickup", EMPRESA_A, estado="conectado"),
            _integ("gmail", EMPRESA_B, estado="conectado"),
            _integ("clickup", EMPRESA_B, estado="reconectar"),
        ]
    )

    reconectar = await repo.listar_por_estado("reconectar")
    conectado = await repo.listar_por_estado("conectado")

    assert {(i.empresa_id, i.proveedor) for i in reconectar} == {
        (EMPRESA_A, "gmail"),
        (EMPRESA_B, "clickup"),
    }
    assert all(i.estado == "reconectar" for i in reconectar)
    assert {(i.empresa_id, i.proveedor) for i in conectado} == {
        (EMPRESA_A, "clickup"),
        (EMPRESA_B, "gmail"),
    }


async def test_memoria_sin_ninguna_en_ese_estado_devuelve_lista_vacia():
    repo = RepositorioIntegracionesEnMemoria(
        [_integ("gmail", EMPRESA_A, estado="conectado")]
    )

    assert await repo.listar_por_estado("reconectar") == []


# ── Supabase (PostgREST, sin red) ────────────────────────────────────────────


def _repo(handler):
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return RepositorioIntegracionesSupabase(BASE, KEY, TOKEN, cliente=cliente)


async def test_supabase_filtra_por_estado_manda_credenciales_y_mapea():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["url"] = str(req.url)
        visto["auth"] = req.headers.get("authorization")
        visto["apikey"] = req.headers.get("apikey")
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(uuid4()),
                    "empresa_id": str(EMPRESA_A),
                    "proveedor": "gmail",
                    "token_ref": "projects/p/secrets/gmail-a",
                    "casilla": "hola@capsulab.cl",
                    "cursor": None,
                    "estado": "reconectar",
                }
            ],
        )

    integs = await _repo(handler).listar_por_estado("reconectar")

    assert visto["auth"] == f"Bearer {TOKEN}"
    assert visto["apikey"] == KEY
    assert "/rest/v1/integraciones" in visto["url"]
    assert "estado=eq.reconectar" in visto["url"]
    assert len(integs) == 1 and isinstance(integs[0], Integracion)
    assert integs[0].estado == "reconectar"


async def test_supabase_sin_filas_devuelve_lista_vacia():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).listar_por_estado("reconectar") == []
