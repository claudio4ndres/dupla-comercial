"""Proveedores de dependencias de FastAPI.

En los tests se sobrescriben con dobles (`app.dependency_overrides`). El cableado
real con Supabase aún se hará en tareas de integración aparte (con su propio
test); por eso esos proveedores siguen como `NotImplementedError`. El cliente
Anthropic real ya está cableado (T7a): se construye con la key de `Settings`.
"""
from functools import lru_cache
from uuid import UUID

import jwt
from anthropic import AsyncAnthropic
from fastapi import Header, HTTPException, status

from app.config import obtener_settings
from app.repositorios.estado_oauth import AlmacenEstadoOAuthEnMemoria
from app.repositorios.integraciones_supabase import RepositorioIntegracionesSupabase
from app.repositorios.solicitudes_supabase import RepositorioSolicitudesSupabase
from app.servicios.gmail_real import FabricaClienteGmailReal
from app.servicios.oauth_gmail import ConfigOAuthGmail
from app.servicios.oauth_gmail_real import ClienteOAuthGoogleReal
from app.servicios.secretos import AlmacenSecretosSecretManager


def _jwt_del_header(authorization: str | None) -> str:
    """Extrae el JWT del header `Authorization: Bearer ...` o lanza 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de autenticación",
        )
    return authorization.split(" ", 1)[1].strip()


def obtener_repositorio_solicitudes(
    authorization: str | None = Header(default=None),
) -> RepositorioSolicitudesSupabase:
    """Repositorio real de solicitudes (T7c), construido POR REQUEST con el JWT
    del usuario para que la RLS filtre por su empresa. En los tests se sobrescribe
    con uno en memoria vía `app.dependency_overrides`."""
    settings = obtener_settings()
    return RepositorioSolicitudesSupabase(
        settings.supabase_url,
        settings.supabase_anon_key,
        _jwt_del_header(authorization),
    )


def obtener_repositorio_integraciones(
    authorization: str | None = Header(default=None),
) -> RepositorioIntegracionesSupabase:
    """Repo de integraciones para ENDPOINTS DE USUARIO (estado/desconectar): se
    construye POR REQUEST con el JWT del usuario (apikey = anon) para que la RLS
    filtre por su empresa (regla de oro #2). En tests se sobrescribe en memoria."""
    settings = obtener_settings()
    return RepositorioIntegracionesSupabase(
        settings.supabase_url,
        settings.supabase_anon_key,
        _jwt_del_header(authorization),
    )


def obtener_repositorio_integraciones_servicio() -> RepositorioIntegracionesSupabase:
    """Repo de integraciones para el POLLER y el CALLBACK OAuth, que NO traen JWT (el
    poller lo dispara Cloud Scheduler; el callback es un redirect del navegador). Corre
    con la service role key como apikey y bearer: salta la RLS, así que el llamador fija
    `empresa_id` explícito en cada fila (jamás se infiere → no cruza tenants, TR3)."""
    settings = obtener_settings()
    return RepositorioIntegracionesSupabase(
        settings.supabase_url,
        settings.supabase_service_role_key,
        settings.supabase_service_role_key,
    )


def obtener_repositorio_solicitudes_servicio() -> RepositorioSolicitudesSupabase:
    """Repo de solicitudes para el POLLER (sin JWT): service role como apikey y bearer.
    El poller fija `empresa_id` explícito por cada correo que ingiere (TR3)."""
    settings = obtener_settings()
    return RepositorioSolicitudesSupabase(
        settings.supabase_url,
        settings.supabase_service_role_key,
        settings.supabase_service_role_key,
    )


@lru_cache
def obtener_almacen_estado_oauth() -> AlmacenEstadoOAuthEnMemoria:
    """Almacén del `state` anti-CSRF del OAuth. Singleton de proceso (`lru_cache`) para
    que el `state` creado en `iniciar` siga vivo cuando vuelve el `callback`. En memoria
    alcanza para un proceso; si se escala a varias instancias, migrar a Supabase/Redis
    (no cambia el contrato). En tests se sobrescribe."""
    return AlmacenEstadoOAuthEnMemoria()


def obtener_config_oauth_gmail() -> ConfigOAuthGmail:
    """Config del cliente OAuth de Google (client_id/redirect_uri NO son secretos del
    usuario). `url_post_conexion` es a dónde vuelve el navegador tras conectar."""
    settings = obtener_settings()
    return ConfigOAuthGmail(
        client_id=settings.google_client_id,
        redirect_uri=settings.google_redirect_uri,
        url_post_conexion=settings.frontend_url,
    )


def obtener_cliente_oauth_google() -> ClienteOAuthGoogleReal:
    """Cliente real del canje del `code` por credenciales (TR3)."""
    settings = obtener_settings()
    return ClienteOAuthGoogleReal(
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_redirect_uri,
    )


@lru_cache
def obtener_almacen_secretos() -> AlmacenSecretosSecretManager:
    """Almacén real de secretos sobre Secret Manager (TR2). Singleton (`lru_cache`)
    para reusar el cliente de GCP entre requests; se construye sin red (el cliente de
    GCP es perezoso). En tests se sobrescribe con uno en memoria."""
    return AlmacenSecretosSecretManager(obtener_settings().gcp_project_id)


def obtener_fabrica_cliente_gmail() -> FabricaClienteGmailReal:
    """Fábrica real (token_ref → cliente Gmail, TR1). Comparte el almacén de secretos
    singleton para resolver el refresh de cada casilla (regla de oro #3)."""
    settings = obtener_settings()
    return FabricaClienteGmailReal(
        almacen=obtener_almacen_secretos(),
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def obtener_secreto_poller() -> str:
    """Secreto compartido que protege el endpoint interno del poller (T12). Cloud
    Scheduler lo manda en `X-Poller-Token`. En tests se inyecta uno de prueba."""
    return obtener_settings().poller_token


@lru_cache
def obtener_cliente_anthropic() -> AsyncAnthropic:
    """Cliente Anthropic real, cableado con la API key de `Settings` (T7a).

    No hace red al construirse. Se cachea para reutilizar el mismo cliente entre
    requests. En los tests/clasificación se sigue inyectando un doble vía
    `app.dependency_overrides`, así que nunca se gastan tokens reales (CA5)."""
    return AsyncAnthropic(api_key=obtener_settings().anthropic_api_key)


def obtener_empresa_actual(
    authorization: str | None = Header(default=None),
) -> UUID:
    """Auth real (T7b): saca `empresa_id` del JWT de Supabase del usuario.

    Verifica la firma HS256 con el secreto del proyecto (`SUPABASE_JWT_SECRET`).
    El `empresa_id` viaja como claim del token (configurado en Supabase con un
    *custom access token hook*). Cualquier fallo → `401` (no se filtra detalle).
    La RLS de Postgres es la barrera final multi-tenant; esto solo identifica al
    usuario para construir su repositorio con su JWT."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de autenticación",
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = jwt.decode(
            token,
            obtener_settings().supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        )
    empresa_id = claims.get("empresa_id")
    if not empresa_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no trae empresa_id",
        )
    try:
        return UUID(str(empresa_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="empresa_id inválido en el token",
        )
