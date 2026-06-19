"""Implementación real del repositorio de tareas contra Supabase.

Habla con PostgREST (`/rest/v1`) usando el **JWT del usuario**: la RLS de Postgres
filtra por su empresa (regla de oro #2). Se construye **por request** con el token
del usuario; nunca se reutiliza entre usuarios.

Lista TODAS las tareas de la empresa (la RLS hace el filtro), pidiendo sólo los
campos del contrato; NO se pide `empresa_id` (no debe viajar, CA5).

Cero red en los tests: se inyecta un `httpx.AsyncClient` con transporte mockeado
(calca a `propuestas_supabase.py`).
"""
from uuid import UUID

import httpx

from app.repositorios.cliente_postgrest import ClientePostgREST
from app.repositorios.tareas import TareaResumen

# Sólo los campos del contrato; la RLS ya restringe a la empresa del JWT.
_SELECT = "nombre,grupo,responsable,vencimiento"


class RepositorioTareasSupabase(ClientePostgREST):
    """Repositorio `RepositorioTareas` respaldado por PostgREST de Supabase."""

    async def listar(self, empresa_id: UUID) -> list[TareaResumen]:
        # La RLS ya restringe a la empresa del JWT (regla #2): basta con pedir las tareas.
        resp = await self._peticion(
            "GET",
            f"/tareas?select={_SELECT}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        filas = resp.json()
        return [
            TareaResumen(
                empresa_id=empresa_id,
                nombre=fila["nombre"],
                grupo=fila.get("grupo"),
                responsable=fila.get("responsable"),
                vencimiento=fila.get("vencimiento"),
            )
            for fila in filas
        ]
