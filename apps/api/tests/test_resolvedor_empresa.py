"""Login real (sin hook): `ResolvedorEmpresaSupabase` contra PostgREST (sin red).

Cuando el JWT de Supabase NO trae `empresa_id` (el hook custom access token está
desactivado), el backend resuelve la empresa del usuario por su `auth.uid` (el `sub`)
consultando la tabla `usuarios` con la **service role** (salta RLS: aún no hay
contexto de empresa). Transporte httpx mockeado: cero red.
"""
from uuid import uuid4

import httpx

from app.servicios.empresa import ResolvedorEmpresaSupabase

BASE = "https://proyecto.supabase.co"
SERVICE = "service-role-key-de-prueba"


def _resolvedor(handler):
    transporte = httpx.MockTransport(handler)
    cliente = httpx.AsyncClient(transport=transporte)
    return ResolvedorEmpresaSupabase(BASE, SERVICE, cliente=cliente)


async def test_resuelve_empresa_por_usuario_con_service_role():
    user_id = uuid4()
    empresa_id = uuid4()
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["auth"] = req.headers.get("authorization")
        visto["apikey"] = req.headers.get("apikey")
        visto["url"] = str(req.url)
        return httpx.Response(200, json=[{"empresa_id": str(empresa_id)}])

    emp = await _resolvedor(handler).empresa_de(user_id)

    assert emp == empresa_id
    # Service role como apikey y bearer: salta la RLS (necesitamos la empresa ANTES
    # de tener contexto de empresa).
    assert visto["auth"] == f"Bearer {SERVICE}"
    assert visto["apikey"] == SERVICE
    assert "/rest/v1/usuarios" in visto["url"]
    assert f"id=eq.{user_id}" in visto["url"]


async def test_usuario_inexistente_devuelve_none():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _resolvedor(handler).empresa_de(uuid4()) is None
