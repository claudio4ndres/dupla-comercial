"""`RepositorioMiembrosSupabase.listar` contra PostgREST (sin red).

Verifica que el repo manda el JWT del usuario (lo que dispara la RLS que aísla por
empresa), pega al endpoint `/miembros` pidiendo sólo los campos del contrato, y mapea
cada fila a `Miembro`. La RLS de Postgres ya filtra por empresa: el repo no manda
`empresa_id` en el query (no debe viajar, CA5). La prueba real de aislamiento corre
contra `supabase start` en integración, no en esta suite unitaria.
"""
from uuid import UUID

import httpx

from app.repositorios.miembros_supabase import RepositorioMiembrosSupabase

BASE = "https://proyecto.supabase.co"
ANON = "anon-key-de-prueba"
JWT = "jwt-del-usuario-empresa-a"
EMPRESA = UUID("0000c0de-0000-4000-8000-000000000001")


def _repo(handler):
    transporte = httpx.MockTransport(handler)
    cliente = httpx.AsyncClient(transport=transporte)
    return RepositorioMiembrosSupabase(BASE, ANON, JWT, cliente=cliente)


async def test_listar_manda_jwt_pide_campos_y_mapea():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["auth"] = req.headers.get("authorization")
        visto["apikey"] = req.headers.get("apikey")
        visto["url"] = str(req.url)
        return httpx.Response(
            200,
            json=[
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "nombre": "Gabriela Lillo",
                    "rol": "RRHH",
                }
            ],
        )

    miembros = await _repo(handler).listar(EMPRESA)

    # El JWT del usuario en el header es lo que hace que la RLS filtre por SU empresa.
    assert visto["auth"] == f"Bearer {JWT}"
    assert visto["apikey"] == ANON
    assert "/rest/v1/miembros" in visto["url"]
    # Pide exactamente los campos del contrato (no `empresa_id`, CA5).
    assert "nombre" in visto["url"]
    assert "rol" in visto["url"]
    assert "empresa_id" not in visto["url"]

    assert len(miembros) == 1
    m = miembros[0]
    assert m.nombre == "Gabriela Lillo"
    assert m.rol == "RRHH"


async def test_listar_sin_filas_devuelve_lista_vacia():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).listar(EMPRESA) == []
