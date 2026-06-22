"""Ruta del usuario actual (GET /usuario, PATCH /usuario/onboarding-visto).

El front la usa tras el login para saber si mostrar el slider de bienvenida (una
sola vez por usuario) y para marcarlo como visto al terminarlo. El usuario sale del
`sub` del JWT (obtener_usuario_actual); el flag `onboarding_visto` vive en `usuarios`.
"""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencias import obtener_resolvedor_empresa, obtener_usuario_actual
from app.esquemas import UsuarioActual

router = APIRouter(prefix="/usuario", tags=["usuario"])


@router.get("", response_model=UsuarioActual)
async def usuario_actual(
    user_id: UUID = Depends(obtener_usuario_actual),
    resolvedor=Depends(obtener_resolvedor_empresa),
) -> UsuarioActual:
    """Datos del usuario autenticado relevantes para el front (hoy: onboarding_visto)."""
    visto = await resolvedor.onboarding_visto_de(user_id)
    return UsuarioActual(onboarding_visto=visto)


@router.patch("/onboarding-visto", response_model=UsuarioActual)
async def marcar_onboarding_visto(
    user_id: UUID = Depends(obtener_usuario_actual),
    resolvedor=Depends(obtener_resolvedor_empresa),
) -> UsuarioActual:
    """Marca el onboarding de bienvenida como visto para el usuario actual."""
    await resolvedor.marcar_onboarding_visto(user_id)
    return UsuarioActual(onboarding_visto=True)
