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

from app.repositorios.cliente_postgrest import ClientePostgREST
from app.repositorios.miembros import Miembro

# Sólo los campos del contrato; la RLS ya restringe a la empresa del JWT.
_SELECT = "id,nombre,rol"


class RepositorioMiembrosSupabase(ClientePostgREST):
    """Repositorio `RepositorioMiembros` respaldado por PostgREST de Supabase."""

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
