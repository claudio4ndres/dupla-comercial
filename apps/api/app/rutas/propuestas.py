"""Rutas de propuestas (lista para la sección "Propuestas" del front)."""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencias import (
    obtener_empresa_actual,
    obtener_repositorio_propuestas,
)
from app.esquemas import PropuestaListada

router = APIRouter(prefix="/propuestas", tags=["propuestas"])


@router.get("", response_model=list[PropuestaListada])
async def listar_propuestas(
    repo=Depends(obtener_repositorio_propuestas),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> list[PropuestaListada]:
    """Todas las propuestas de la empresa del usuario (aislamiento multi-tenant, RLS).

    Cada item trae la cabecera de la propuesta + `asunto`/`remitente` de la solicitud
    ligada (propuesta→conversación→solicitud). Lista vacía si no hay. La vista es plana:
    nunca viaja `empresa_id` ni referencias internas (CA5).
    """
    propuestas = await repo.listar(empresa_id)
    return [
        PropuestaListada(
            id=str(p.id),
            solicitud_id=str(p.solicitud_id),
            total=p.total,
            estado=p.estado,
            asunto=p.asunto,
            remitente=p.remitente,
        )
        for p in propuestas
    ]
