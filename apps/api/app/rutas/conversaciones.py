"""Rutas de conversación con Javo (003 + 005).

`POST /conversaciones/responder` es el corazón conversacional: recibe el tipo y el
historial, y devuelve la respuesta de Javo (texto + componentes propuestos + fuentes)
generada con Sonnet en un loop de tool-use.

**Requiere auth (005):** Javo consulta el **catálogo del Drive de la empresa** con la
RLS, así que la empresa se resuelve del **JWT** del usuario (`obtener_empresa_actual`).
Sin token → 401. Si el LLM cae → 502 (el front cae a su respuesta offline).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.dependencias import (
    obtener_cliente_anthropic,
    obtener_empresa_actual,
    obtener_proveedor_busqueda,
    obtener_repositorio_catalogo,
)
from app.esquemas import EntradaConversacion, RespuestaConversacion
from app.servicios.javo import responder_javo

router = APIRouter(prefix="/conversaciones", tags=["conversaciones"])


@router.post("/responder", response_model=RespuestaConversacion)
async def responder(
    entrada: EntradaConversacion,
    cliente=Depends(obtener_cliente_anthropic),
    repo_catalogo=Depends(obtener_repositorio_catalogo),
    proveedor=Depends(obtener_proveedor_busqueda),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> RespuestaConversacion:
    try:
        return await responder_javo(
            entrada.tipo,
            entrada.mensajes,
            cliente,
            repo_catalogo=repo_catalogo,
            proveedor_busqueda=proveedor,
            empresa_id=empresa_id,
        )
    except Exception as exc:
        # El LLM/herramientas son servicios externos: si caen, es un 502 (no un 500
        # crudo); el front ya cae a su respuesta offline al ver el error.
        raise HTTPException(
            status_code=502, detail="El servicio de conversación no está disponible"
        ) from exc
