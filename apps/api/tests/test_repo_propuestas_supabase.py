"""004 · `RepositorioPropuestasSupabase` contra PostgREST (sin red).

Usa un transporte httpx **mockeado**: verifica que el repo manda el JWT del
usuario (lo que dispara la RLS que aísla por empresa), pega al endpoint correcto
de PostgREST filtrando por la solicitud, y mapea la respuesta (con componentes y
tareas embebidos) a `Propuesta`. La prueba real de aislamiento corre contra
`supabase start` en integración, no en esta suite unitaria.
"""
from uuid import UUID, uuid4

import httpx

from app.repositorios.propuestas_supabase import RepositorioPropuestasSupabase

BASE = "https://proyecto.supabase.co"
ANON = "anon-key-de-prueba"
JWT = "jwt-del-usuario-empresa-a"
EMPRESA = UUID("0000c0de-0000-4000-8000-000000000001")


def _repo(handler):
    transporte = httpx.MockTransport(handler)
    cliente = httpx.AsyncClient(transport=transporte)
    return RepositorioPropuestasSupabase(BASE, ANON, JWT, cliente=cliente)


async def test_obtener_por_solicitud_manda_jwt_y_mapea_componentes_y_tareas():
    sol_id = uuid4()
    prop_id = uuid4()
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["auth"] = req.headers.get("authorization")
        visto["apikey"] = req.headers.get("apikey")
        visto["url"] = str(req.url)
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(prop_id),
                    "total": 5190000,
                    "estado": "borrador",
                    "componentes_propuesta": [
                        {
                            "nombre": "Promotoras uniformadas",
                            "detalle": "6h/día × 4 días · 3 tiendas",
                            "cantidad": 6,
                            "valor_unitario": 240000,
                        }
                    ],
                    "tareas": [
                        {
                            "nombre": "Reclutar 6 promotoras",
                            "grupo": "RRHH",
                            "responsable": "Coordinación",
                            "vencimiento": "3 días",
                        }
                    ],
                }
            ],
        )

    prop = await _repo(handler).obtener_por_solicitud(sol_id, EMPRESA)

    # El JWT del usuario en el header es lo que hace que la RLS filtre por SU empresa.
    assert visto["auth"] == f"Bearer {JWT}"
    assert visto["apikey"] == ANON
    assert "/rest/v1/propuestas" in visto["url"]
    # Filtra la propuesta por la conversación de ESA solicitud.
    assert f"solicitud_id=eq.{sol_id}" in visto["url"]

    assert prop is not None
    assert prop.id == prop_id
    assert prop.estado == "borrador"
    assert prop.total == 5190000
    assert len(prop.componentes) == 1
    assert prop.componentes[0].nombre == "Promotoras uniformadas"
    assert prop.componentes[0].valor_unitario == 240000
    assert prop.componentes[0].cantidad == 6
    assert len(prop.tareas) == 1
    assert prop.tareas[0].grupo == "RRHH"
    assert prop.tareas[0].vencimiento == "3 días"


async def test_obtener_por_solicitud_sin_filas_devuelve_none():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).obtener_por_solicitud(uuid4(), EMPRESA) is None


async def test_obtener_por_solicitud_propuesta_sin_hijos_mapea_listas_vacias():
    prop_id = uuid4()

    def handler(req):
        return httpx.Response(
            200,
            json=[{"id": str(prop_id), "total": 0, "estado": "borrador"}],
        )

    prop = await _repo(handler).obtener_por_solicitud(uuid4(), EMPRESA)
    assert prop is not None
    assert prop.componentes == []
    assert prop.tareas == []
