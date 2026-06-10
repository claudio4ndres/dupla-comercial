"""Rutas de miembros (roster del equipo para el selector "Asignado a", 0006)."""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencias import (
    obtener_empresa_actual,
    obtener_repositorio_miembros,
)
from app.esquemas import MiembroListado

router = APIRouter(prefix="/miembros", tags=["miembros"])


@router.get("", response_model=list[MiembroListado])
async def listar_miembros(
    repo=Depends(obtener_repositorio_miembros),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> list[MiembroListado]:
    """Roster de la empresa del usuario (aislamiento multi-tenant, RLS).

    Lista vacía si no hay. La vista es plana: nunca viaja `empresa_id` ni referencias
    internas (CA5). El front lo usa para el selector "Asignado a" de cada tarea.
    """
    miembros = await repo.listar(empresa_id)
    return [
        MiembroListado(id=str(m.id), nombre=m.nombre, rol=m.rol) for m in miembros
    ]
