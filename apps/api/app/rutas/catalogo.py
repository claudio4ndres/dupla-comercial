"""Rutas del catálogo del Drive de la empresa.

`GET /catalogo/recursos` alimenta el panel "Recursos · Drive" del chat: lista los
recursos del Drive (origenes del catálogo) de la empresa del usuario. Sólo los de su
empresa (aislamiento multi-tenant por RLS; la empresa sale del JWT).
"""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencias import obtener_empresa_actual, obtener_repositorio_catalogo

router = APIRouter(prefix="/catalogo", tags=["catalogo"])


@router.get("/recursos", response_model=list[str])
async def listar_recursos(
    repo=Depends(obtener_repositorio_catalogo),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> list[str]:
    return await repo.recursos(empresa_id)
