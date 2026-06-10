"""`RepositorioPropuestasSupabase.listar` contra PostgREST (sin red).

Verifica que el repo manda el JWT del usuario (lo que dispara la RLS que aísla por
empresa), pega al endpoint `/propuestas` EMBEBIENDO la solicitud ligada (vía la
conversación) para traer `asunto` y `remitente`, y mapea cada fila a
`PropuestaResumen`. La prueba real de aislamiento corre contra `supabase start` en
integración, no en esta suite unitaria.
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


async def test_listar_manda_jwt_embebe_solicitud_y_mapea():
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
                    "conversaciones": {
                        "solicitud_id": str(sol_id),
                        "solicitudes": {
                            "asunto": "Sampling sopaipillas",
                            "remitente": "Zona Espiga",
                        },
                    },
                }
            ],
        )

    propuestas = await _repo(handler).listar(EMPRESA)

    # El JWT del usuario en el header es lo que hace que la RLS filtre por SU empresa.
    assert visto["auth"] == f"Bearer {JWT}"
    assert visto["apikey"] == ANON
    assert "/rest/v1/propuestas" in visto["url"]
    # El select embebe la solicitud (asunto/remitente) a través de la conversación.
    assert "solicitudes" in visto["url"]

    assert len(propuestas) == 1
    p = propuestas[0]
    assert p.id == prop_id
    assert p.solicitud_id == sol_id
    assert p.total == 5190000
    assert p.estado == "borrador"
    assert p.asunto == "Sampling sopaipillas"
    assert p.remitente == "Zona Espiga"


async def test_listar_sin_filas_devuelve_lista_vacia():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).listar(EMPRESA) == []


async def test_listar_tolera_solicitud_ausente():
    # Si por algún motivo la solicitud no viene embebida en la conversación, no rompe:
    # asunto/remitente quedan en blanco y la propuesta igual se lista.
    prop_id = uuid4()
    sol_id = uuid4()

    def handler(req):
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(prop_id),
                    "total": 0,
                    "estado": "borrador",
                    "conversaciones": {"solicitud_id": str(sol_id)},
                }
            ],
        )

    propuestas = await _repo(handler).listar(EMPRESA)
    assert len(propuestas) == 1
    assert propuestas[0].solicitud_id == sol_id
    assert propuestas[0].asunto == ""
    assert propuestas[0].remitente == ""
