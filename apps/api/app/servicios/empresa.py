"""Resuelve la empresa de un usuario por su `auth.uid` (login real sin hook).

Cuando el JWT de Supabase NO trae `empresa_id` (porque el *custom access token
hook* está desactivado), el backend resuelve la empresa consultando la tabla
`usuarios` por el `sub` del token, usando la **service role** (salta la RLS: aún no
hay contexto de empresa). En producción, si se activa el hook y el claim viene, esta
vía ni se usa.

Cero red en los tests: se inyecta un `httpx.AsyncClient` con transporte mockeado.
"""
from uuid import UUID

import httpx


class ResolvedorEmpresaSupabase:
    """Resuelve `empresa_id` a partir del `auth.uid` del usuario contra PostgREST."""

    def __init__(
        self,
        base_url: str,
        service_role_key: str,
        *,
        cliente: httpx.AsyncClient | None = None,
    ):
        self._base = base_url.rstrip("/") + "/rest/v1"
        self._key = service_role_key
        self._cliente = cliente  # inyectable para tests; en prod se crea por llamada

    async def _peticion(self, metodo: str, ruta: str, **kw) -> httpx.Response:
        url = self._base + ruta
        if self._cliente is not None:
            return await self._cliente.request(metodo, url, **kw)
        async with httpx.AsyncClient() as cliente:
            return await cliente.request(metodo, url, **kw)

    async def empresa_de(self, user_id: UUID) -> UUID | None:
        """Devuelve la `empresa_id` del usuario, o `None` si no existe en `usuarios`."""
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",  # service role: salta la RLS
        }
        resp = await self._peticion(
            "GET",
            f"/usuarios?id=eq.{user_id}&select=empresa_id&limit=1",
            headers=headers,
        )
        resp.raise_for_status()
        filas = resp.json()
        if not filas:
            return None
        return UUID(filas[0]["empresa_id"])
