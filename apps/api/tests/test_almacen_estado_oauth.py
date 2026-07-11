"""Spec 015 · Almacén del `state` anti-CSRF persistente en Supabase.

Con varias instancias de Cloud Run, el callback OAuth puede aterrizar en una
instancia distinta a la que inició el flujo: el `state` debe vivir en la base
(tabla `estados_oauth`) y consumirse de forma ATÓMICA (DELETE devolviendo la
fila) para que un replay entre instancias falle. Cero red: MockTransport.
"""
import json
from uuid import UUID, uuid4

import httpx

from app.repositorios.estado_oauth import AlmacenEstadoOAuthEnMemoria
from app.repositorios.estado_oauth_supabase import AlmacenEstadoOAuthSupabase

BASE = "https://proyecto.supabase.co"
SERVICE = "service-role-key"
EMPRESA = UUID("0000c0de-0000-4000-8000-000000000001")


def _almacen(handler):
    transporte = httpx.MockTransport(handler)
    cliente = httpx.AsyncClient(transport=transporte)
    return AlmacenEstadoOAuthSupabase(BASE, SERVICE, SERVICE, cliente=cliente)


async def test_guardar_inserta_con_service_role_y_expiracion():
    # CA1: POST a /estados_oauth con apikey/bearer service-role y expira_en.
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["metodo"] = req.method
        visto["url"] = str(req.url)
        visto["apikey"] = req.headers.get("apikey")
        visto["auth"] = req.headers.get("authorization")
        visto["body"] = json.loads(req.content)
        return httpx.Response(201, json=[])

    await _almacen(handler).guardar("state-abc", EMPRESA)

    assert visto["metodo"] == "POST"
    assert "/rest/v1/estados_oauth" in visto["url"]
    assert visto["apikey"] == SERVICE and visto["auth"] == f"Bearer {SERVICE}"
    assert visto["body"]["state"] == "state-abc"
    assert visto["body"]["empresa_id"] == str(EMPRESA)
    assert visto["body"]["expira_en"]  # el state caduca (10 min)


async def test_consumir_es_delete_atomico_y_devuelve_la_empresa():
    # CA2: DELETE con return=representation filtrando por vigencia.
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["metodo"] = req.method
        visto["url"] = str(req.url)
        visto["prefer"] = req.headers.get("prefer")
        return httpx.Response(200, json=[{"state": "state-abc", "empresa_id": str(EMPRESA)}])

    empresa = await _almacen(handler).consumir("state-abc")

    assert visto["metodo"] == "DELETE"
    assert "estados_oauth" in visto["url"]
    assert "state=eq.state-abc" in visto["url"]
    assert "expira_en=gt." in visto["url"]  # un state vencido no se consume
    assert "return=representation" in (visto["prefer"] or "")
    assert empresa == EMPRESA


async def test_consumir_state_inexistente_o_expirado_devuelve_none():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])  # el DELETE no encontró fila vigente

    assert await _almacen(handler).consumir("state-viejo") is None


async def test_memoria_un_solo_uso_anti_replay():
    # CA3: contrato compartido — el mismo state no se consume dos veces.
    almacen = AlmacenEstadoOAuthEnMemoria()
    state = f"state-{uuid4()}"
    await almacen.guardar(state, EMPRESA)

    assert await almacen.consumir(state) == EMPRESA
    assert await almacen.consumir(state) is None
