"""Rutas de conversación con Javo (003).

`POST /conversaciones/responder` es el corazón conversacional: recibe el tipo y el
historial, y devuelve el texto de Javo generado con Sonnet. Es **sin estado**: no
lee ni escribe datos de empresa (por eso no exige auth mientras el login siga mock,
spec 003 · §3). Si el LLM cae → 502 y el front cae a su respuesta offline.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.dependencias import obtener_cliente_anthropic
from app.esquemas import EntradaConversacion, RespuestaConversacion
from app.servicios.javo import responder_javo

router = APIRouter(prefix="/conversaciones", tags=["conversaciones"])


@router.post("/responder", response_model=RespuestaConversacion)
async def responder(
    entrada: EntradaConversacion,
    cliente=Depends(obtener_cliente_anthropic),
) -> RespuestaConversacion:
    try:
        texto = await responder_javo(entrada.tipo, entrada.mensajes, cliente)
    except Exception as exc:
        # El LLM es un servicio externo: si cae, es un 502 (no un 500 crudo); el
        # front ya cae a su respuesta offline al ver el error.
        raise HTTPException(
            status_code=502, detail="El servicio de conversación no está disponible"
        ) from exc
    return RespuestaConversacion(texto=texto)
