"""`RepositorioTareasSupabase.listar` contra PostgREST (sin red).

Verifica que el repo manda el JWT del usuario (lo que dispara la RLS que aísla por
empresa), pega al endpoint `/tareas` pidiendo sólo los campos del contrato, y mapea
cada fila a `TareaResumen`. La RLS de Postgres ya filtra por empresa: el repo no
manda `empresa_id` en el query (no debe viajar, CA5). La prueba real de aislamiento
corre contra `supabase start` en integración, no en esta suite unitaria.
"""
from uuid import UUID

import httpx

from app.repositorios.tareas_supabase import RepositorioTareasSupabase

BASE = "https://proyecto.supabase.co"
ANON = "anon-key-de-prueba"
JWT = "jwt-del-usuario-empresa-a"
EMPRESA = UUID("0000c0de-0000-4000-8000-000000000001")


def _repo(handler):
    transporte = httpx.MockTransport(handler)
    cliente = httpx.AsyncClient(transport=transporte)
    return RepositorioTareasSupabase(BASE, ANON, JWT, cliente=cliente)


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
                    "nombre": "Reclutar 6 promotoras",
                    "grupo": "RRHH",
                    "responsable": "Coordinación",
                    "vencimiento": "3 días",
                }
            ],
        )

    tareas = await _repo(handler).listar(EMPRESA)

    # El JWT del usuario en el header es lo que hace que la RLS filtre por SU empresa.
    assert visto["auth"] == f"Bearer {JWT}"
    assert visto["apikey"] == ANON
    assert "/rest/v1/tareas" in visto["url"]
    # Pide exactamente los campos del contrato (no `empresa_id`, CA5).
    assert "nombre" in visto["url"]
    assert "empresa_id" not in visto["url"]

    assert len(tareas) == 1
    t = tareas[0]
    assert t.nombre == "Reclutar 6 promotoras"
    assert t.grupo == "RRHH"
    assert t.responsable == "Coordinación"
    assert t.vencimiento == "3 días"


async def test_listar_sin_filas_devuelve_lista_vacia():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).listar(EMPRESA) == []


async def test_listar_tolera_campos_opcionales_nulos():
    def handler(req):
        return httpx.Response(
            200,
            json=[{"nombre": "Tarea suelta", "grupo": None,
                   "responsable": None, "vencimiento": None}],
        )

    tareas = await _repo(handler).listar(EMPRESA)
    assert len(tareas) == 1
    assert tareas[0].nombre == "Tarea suelta"
    assert tareas[0].grupo is None
    assert tareas[0].responsable is None
    assert tareas[0].vencimiento is None
