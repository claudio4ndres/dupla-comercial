"""Implementación real del repositorio de miembros contra Supabase (0006).

Habla con PostgREST (`/rest/v1`) usando el **JWT del usuario**: la RLS de Postgres
filtra por su empresa (regla de oro #2). Se construye **por request** con el token
del usuario; nunca se reutiliza entre usuarios.

Lista TODOS los miembros de la empresa (la RLS hace el filtro), pidiendo sólo los
campos del contrato (`id,nombre,rol`); NO se pide `empresa_id` (no debe viajar, CA5).

Cero red en los tests: se inyecta un `httpx.AsyncClient` con transporte mockeado
(calca a `tareas_supabase.py`).
"""
from uuid import UUID

import httpx

from app.repositorios.miembros import Miembro

# Sólo los campos del contrato; la RLS ya restringe a la empresa del JWT.
_SELECT = "id,nombre,rol"


class RepositorioMiembrosSupabase:
    """Repositorio `RepositorioMiembros` respaldado por PostgREST de Supabase."""

    def __init__(
        self,
        base_url: str,
        anon_key: str,
        jwt: str,
        *,
        cliente: httpx.AsyncClient | None = None,
    ):
        self._base = base_url.rstrip("/") + "/rest/v1"
        self._anon = anon_key
        self._jwt = jwt
        self._cliente = cliente  # inyectable para tests; en prod se crea por llamada

    def _headers(self) -> dict:
        # `apikey` identifica al proyecto; `Authorization` lleva el JWT del usuario,
        # que es lo que activa la RLS a nombre de SU empresa.
        return {
            "apikey": self._anon,
            "Authorization": f"Bearer {self._jwt}",
            "Content-Type": "application/json",
        }

    async def _peticion(self, metodo: str, ruta: str, **kw) -> httpx.Response:
        url = self._base + ruta
        if self._cliente is not None:
            return await self._cliente.request(metodo, url, **kw)
        async with httpx.AsyncClient() as cliente:
            return await cliente.request(metodo, url, **kw)

    async def listar(self, empresa_id: UUID) -> list[Miembro]:
        # La RLS ya restringe a la empresa del JWT (regla #2): basta con pedir los
        # miembros. `empresa_id` lo conoce el llamador (sale del JWT) y se rellena aquí
        # para el modelo interno; nunca viaja en el query ni en la respuesta (CA5).
        resp = await self._peticion(
            "GET",
            f"/miembros?select={_SELECT}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        filas = resp.json()
        return [
            Miembro(
                id=fila.get("id"),
                empresa_id=empresa_id,
                nombre=fila["nombre"],
                rol=fila["rol"],
            )
            for fila in filas
        ]
