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

from app.esquemas import EmpresaActual


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

    async def datos_de(self, empresa_id: UUID) -> EmpresaActual | None:
        """Datos de la empresa (nombre, color de marca, plan) para el header del front,
        o None si no existe. El `empresa_id` ya viene resuelto del JWT del usuario
        (obtener_empresa_actual), así que leerlo por service role no cruza tenants."""
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",  # service role: salta la RLS
        }
        resp = await self._peticion(
            "GET",
            f"/empresas?id=eq.{empresa_id}&select=id,nombre,color_marca,plan&limit=1",
            headers=headers,
        )
        resp.raise_for_status()
        filas = resp.json()
        if not filas:
            return None
        fila = filas[0]
        return EmpresaActual(
            id=str(fila["id"]),
            nombre=fila["nombre"],
            color_marca=fila["color_marca"],
            plan=fila["plan"],
        )

    async def onboarding_visto_de(self, user_id: UUID) -> bool:
        """Si el usuario ya vio el onboarding de bienvenida (False si no hay fila)."""
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",  # service role: salta la RLS
        }
        resp = await self._peticion(
            "GET",
            f"/usuarios?id=eq.{user_id}&select=onboarding_visto&limit=1",
            headers=headers,
        )
        resp.raise_for_status()
        filas = resp.json()
        return bool(filas[0]["onboarding_visto"]) if filas else False

    async def marcar_onboarding_visto(self, user_id: UUID) -> None:
        """Marca onboarding_visto = true para el usuario (idempotente)."""
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",  # service role: salta la RLS
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        resp = await self._peticion(
            "PATCH",
            f"/usuarios?id=eq.{user_id}",
            headers=headers,
            json={"onboarding_visto": True},
        )
        resp.raise_for_status()
