"""Repositorio de tareas (las que bajan de una propuesta hacia el equipo / ClickUp):
interfaz + doble en memoria para tests.

La sección "Tareas" del front lista TODAS las tareas de la empresa del usuario. Aquí
se modela el resumen plano que necesita esa lista (`nombre`, `grupo`, `responsable`,
`vencimiento`). La implementación real contra Supabase (que respeta la RLS con el JWT
del usuario) vive en `tareas_supabase.py`.
"""
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel


class TareaResumen(BaseModel):
    """Una tarea tal como la lista la sección "Tareas" del front (GET /tareas).

    `empresa_id` es interno (emula la RLS / sirve de aislamiento en el doble); la
    vista que ve el front NUNCA lo incluye (CA5): el endpoint mapea a un esquema plano.
    """

    empresa_id: UUID
    nombre: str
    grupo: str | None = None
    responsable: str | None = None
    vencimiento: str | None = None


class RepositorioTareas(Protocol):
    async def listar(self, empresa_id: UUID) -> list[TareaResumen]: ...


class RepositorioTareasEnMemoria:
    """Doble en memoria para tests. Emula el aislamiento por empresa de la RLS:
    sólo entrega las tareas que pertenecen a la empresa consultada."""

    def __init__(self, tareas: list[TareaResumen] | None = None):
        self._tareas: list[TareaResumen] = list(tareas or [])

    async def listar(self, empresa_id: UUID) -> list[TareaResumen]:
        return [t for t in self._tareas if t.empresa_id == empresa_id]
