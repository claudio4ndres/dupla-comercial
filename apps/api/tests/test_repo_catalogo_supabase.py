"""005 · `RepositorioCatalogoSupabase` contra PostgREST (sin red).

Transporte httpx **mockeado**: verifica que el repo manda el **JWT del usuario** (lo
que dispara la RLS que aísla por empresa, CA5), pega a `/rest/v1/catalogo` filtrando
por texto (`ILIKE`) y por `tipo`, y mapea la respuesta a `ItemCatalogo`.
"""
from uuid import UUID, uuid4

import httpx
import pytest

from app.config import obtener_settings
from app.dependencias import obtener_repositorio_catalogo
from app.repositorios.catalogo_supabase import RepositorioCatalogoSupabase

BASE = "https://proyecto.supabase.co"
ANON = "anon-key-de-prueba"
JWT = "jwt-del-usuario-empresa-a"
EMPRESA = UUID("0000c0de-0000-4000-8000-000000000001")


def _repo(handler):
    transporte = httpx.MockTransport(handler)
    cliente = httpx.AsyncClient(transport=transporte)
    return RepositorioCatalogoSupabase(BASE, ANON, JWT, cliente=cliente)


async def test_buscar_manda_jwt_filtra_ilike_y_mapea():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["auth"] = req.headers.get("authorization")
        visto["apikey"] = req.headers.get("apikey")
        visto["url"] = str(req.url)
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(uuid4()),
                    "empresa_id": str(EMPRESA),
                    "tipo": "componente",
                    "nombre": "Promotoras uniformadas",
                    "detalle": "6h/día · 3 tiendas",
                    "valor_unitario": 240000,
                    "origen": "Tarifario_promotores_2026.xlsx",
                }
            ],
        )

    items = await _repo(handler).buscar("promotoras", EMPRESA)

    # El JWT del usuario en el header es lo que hace que la RLS filtre por SU empresa.
    assert visto["auth"] == f"Bearer {JWT}"
    assert visto["apikey"] == ANON
    url = visto["url"].lower()
    assert "/rest/v1/catalogo" in url
    assert "ilike" in url and "promotoras" in url
    assert len(items) == 1
    assert items[0].nombre == "Promotoras uniformadas"
    assert items[0].valor_unitario == 240000
    assert items[0].origen == "Tarifario_promotores_2026.xlsx"


async def test_buscar_con_tipo_agrega_filtro():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["url"] = str(req.url)
        return httpx.Response(200, json=[])

    await _repo(handler).buscar("", EMPRESA, tipo="caso")
    assert "tipo=eq.caso" in visto["url"]


async def test_buscar_sin_filas_devuelve_lista_vacia():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).buscar("x", EMPRESA) == []


async def test_recursos_dedup_origenes_del_catalogo():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["auth"] = req.headers.get("authorization")
        visto["url"] = str(req.url)
        return httpx.Response(
            200,
            json=[
                {"origen": "Tarifario.xlsx"},
                {"origen": "Tarifario.xlsx"},  # duplicado
                {"origen": "PRODUCCIÓN 3D"},
                {"origen": None},  # nulo → se ignora
            ],
        )

    recs = await _repo(handler).recursos(EMPRESA)

    assert visto["auth"] == f"Bearer {JWT}"  # JWT del usuario → RLS por empresa
    assert "/rest/v1/catalogo" in visto["url"]
    assert recs == ["PRODUCCIÓN 3D", "Tarifario.xlsx"]


def test_provider_construye_repo_con_el_jwt_del_usuario(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proyecto.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    obtener_settings.cache_clear()

    repo = obtener_repositorio_catalogo(authorization="Bearer jwt-abc")

    assert isinstance(repo, RepositorioCatalogoSupabase)
    assert repo._jwt == "jwt-abc"


def test_provider_sin_token_es_401():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        obtener_repositorio_catalogo(authorization=None)
    assert exc.value.status_code == 401
