"""Repositorio de miembros del equipo (roster para el selector "Asignado a", 0006).

Cada empresa tiene su roster de personas con un `rol` por área (RRHH, Producción,
Diseño…). La pantalla de Tareas los ofrece en un selector por tarea; el asignado
elegido viaja a la descripción de la tarea de ClickUp. La implementación real contra
Supabase (que respeta la RLS con el JWT del usuario) vive en `miembros_supabase.py`;
aquí va la interfaz + un doble en memoria para tests.
"""
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel


class Miembro(BaseModel):
    """Una persona del roster de la empresa (tabla `miembros`).

    `empresa_id` es interno (emula la RLS / sirve de aislamiento en el doble); la
    vista que ve el front NUNCA lo incluye (CA5): el endpoint mapea a un esquema plano.
    """

    id: UUID | None = None
    empresa_id: UUID
    nombre: str
    rol: str


class RepositorioMiembros(Protocol):
    async def listar(self, empresa_id: UUID) -> list[Miembro]: ...


class RepositorioMiembrosEnMemoria:
    """Doble en memoria para tests. Emula el aislamiento por empresa de la RLS:
    sólo entrega los miembros que pertenecen a la empresa consultada."""

    def __init__(self, miembros: list[Miembro] | None = None):
        self._miembros: list[Miembro] = list(miembros or [])

    async def listar(self, empresa_id: UUID) -> list[Miembro]:
        return [m for m in self._miembros if m.empresa_id == empresa_id]
