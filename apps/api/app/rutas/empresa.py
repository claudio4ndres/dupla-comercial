"""Ruta de la empresa actual (GET /empresa).

El front la usa para el header/branding del tenant del usuario —nombre y color de
marca—, reemplazando el mock hardcodeado. La empresa sale de `obtener_empresa_actual`
(el JWT del usuario): nunca se infiere ni se cruza entre tenants.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencias import obtener_empresa_actual, obtener_resolvedor_empresa
from app.esquemas import EmpresaActual

router = APIRouter(prefix="/empresa", tags=["empresa"])


@router.get("", response_model=EmpresaActual)
async def empresa_actual(
    empresa_id: UUID = Depends(obtener_empresa_actual),
    resolvedor=Depends(obtener_resolvedor_empresa),
) -> EmpresaActual:
    """Devuelve la empresa (tenant) del usuario autenticado: id, nombre, color de marca
    y plan. El front la pinta en el header (no más mock). 404 si la empresa no existe."""
    datos = await resolvedor.datos_de(empresa_id)
    if datos is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada"
        )
    return datos
