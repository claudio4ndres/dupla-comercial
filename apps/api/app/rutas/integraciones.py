"""Rutas de integraciones de correo (lo que consume la Bandeja del front).

Aquí sólo vive el estado que el usuario puede ver; los tokens viven en el
`AlmacenSecretos` y JAMÁS salen por estos endpoints (CA5). La empresa del usuario
se resuelve por el JWT de Supabase (inyectado); la RLS filtra en la capa real.
"""
import secrets
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.dependencias import (
    obtener_almacen_estado_oauth,
    obtener_almacen_secretos,
    obtener_cliente_oauth_google,
    obtener_config_oauth_gmail,
    obtener_empresa_actual,
    obtener_repositorio_integraciones,
    obtener_repositorio_integraciones_servicio,
)
from app.esquemas import EstadoCorreo, UrlConsentimiento
from app.repositorios.integraciones import Integracion
from app.servicios.oauth_gmail import ConfigOAuthGmail, construir_url_consentimiento

router = APIRouter(prefix="/integraciones", tags=["integraciones"])


@router.get("/correo", response_model=EstadoCorreo)
async def estado_correo(
    repo=Depends(obtener_repositorio_integraciones),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> EstadoCorreo:
    """Devuelve el estado de la conexión de correo de la empresa del usuario.

    Sin integración → todo en null (CA1). Con integración → proveedor/estado/casilla
    (CA2). Nunca incluye tokens (CA5, garantizado por el `response_model`).
    """
    integracion = await repo.obtener_por_empresa(empresa_id)
    if integracion is None:
        return EstadoCorreo()
    return EstadoCorreo(
        proveedor=integracion.proveedor,
        estado=integracion.estado,
        casilla=integracion.casilla,
    )


@router.post("/correo/gmail/iniciar", response_model=UrlConsentimiento)
async def iniciar_gmail(
    config: ConfigOAuthGmail = Depends(obtener_config_oauth_gmail),
    almacen=Depends(obtener_almacen_estado_oauth),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> UrlConsentimiento:
    """Arranca el consentimiento de Gmail: genera un `state` anti-CSRF ligado a la
    empresa, lo registra y devuelve la URL de Google a la que el front redirige.

    No toca Google: sólo construye la URL (scope mínimo `gmail.readonly`). El canje
    ocurre en el callback (T8).
    """
    state = secrets.token_urlsafe(32)
    await almacen.guardar(state, empresa_id)
    return UrlConsentimiento(url=construir_url_consentimiento(config, state))


@router.get("/correo/gmail/callback")
async def callback_gmail(
    code: str,
    state: str,
    config: ConfigOAuthGmail = Depends(obtener_config_oauth_gmail),
    almacen_estado=Depends(obtener_almacen_estado_oauth),
    oauth=Depends(obtener_cliente_oauth_google),
    secretos=Depends(obtener_almacen_secretos),
    repo=Depends(obtener_repositorio_integraciones_servicio),
) -> RedirectResponse:
    """Cierra el consentimiento: valida el `state` (anti-CSRF), canjea el `code`,
    guarda el refresh token como secreto y persiste la integración conectada; luego
    redirige al front. Los tokens nunca salen en la respuesta (CA5).

    La empresa se toma del `state` validado (no del JWT): es el navegador del usuario
    el que vuelve de Google (un redirect, sin header `Authorization`), y el `state` es
    lo que liga ese retorno a su empresa. Por eso el repo es el de SERVICIO (service
    role): no hay JWT que active la RLS, así que escribimos con `empresa_id` explícito.
    """
    empresa_id = await almacen_estado.consumir(state)
    if empresa_id is None:
        raise HTTPException(status_code=400, detail="state inválido o expirado")

    credenciales = await oauth.canjear_codigo(code)
    token_ref = await secretos.guardar(
        f"gmail-refresh-{empresa_id}", credenciales.refresh_token
    )
    await repo.guardar(
        Integracion(
            id=uuid4(),
            empresa_id=empresa_id,
            proveedor="gmail",
            token_ref=token_ref,
            casilla=credenciales.casilla,
            cursor=None,  # el cliente real fija el historyId inicial (TR1)
            estado="conectado",
        )
    )
    return RedirectResponse(url=config.url_post_conexion, status_code=302)


@router.delete("/correo", status_code=204)
async def desconectar_correo(
    repo=Depends(obtener_repositorio_integraciones),
    secretos=Depends(obtener_almacen_secretos),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> None:
    """Desconecta la casilla de la empresa (el botón "Cambiar"): borra el secreto
    (refresh token) y elimina la fila de `integraciones`. Idempotente: si no hay
    integración, responde 204 igual.
    """
    integracion = await repo.obtener_por_empresa(empresa_id)
    if integracion is not None:
        await secretos.borrar(integracion.token_ref)
        await repo.eliminar(empresa_id)
