"""Rutas de tareas (lista para la sección "Tareas" del front)."""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencias import (
    obtener_empresa_actual,
    obtener_repositorio_tareas,
)
from app.esquemas import TareaListada

router = APIRouter(prefix="/tareas", tags=["tareas"])


@router.get("", response_model=list[TareaListada])
async def listar_tareas(
    repo=Depends(obtener_repositorio_tareas),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> list[TareaListada]:
    """Todas las tareas de la empresa del usuario (aislamiento multi-tenant, RLS).

    Lista vacía si no hay. La vista es plana: nunca viaja `empresa_id` ni referencias
    internas (CA5). El front mapea grupo→área y vencimiento→plazo.
    """
    tareas = await repo.listar(empresa_id)
    return [
        TareaListada(
            nombre=t.nombre,
            grupo=t.grupo,
            responsable=t.responsable,
            vencimiento=t.vencimiento,
        )
        for t in tareas
    ]
