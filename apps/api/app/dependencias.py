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
from app.repositorios.solicitudes_supabase import RepositorioSolicitudesSupabase


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


def obtener_repositorio_integraciones():
    raise NotImplementedError(
        "Repositorio real (Supabase) pendiente; en tests se inyecta uno en memoria."
    )


def obtener_almacen_estado_oauth():
    raise NotImplementedError(
        "Almacén real (Supabase/Redis) pendiente; en tests se inyecta uno en memoria."
    )


def obtener_config_oauth_gmail():
    raise NotImplementedError(
        "Config OAuth real (Secret Manager) pendiente; en tests se inyecta una dummy."
    )


def obtener_cliente_oauth_google():
    raise NotImplementedError(
        "Cliente OAuth real (Google) pendiente; en tests se inyecta un doble."
    )


def obtener_almacen_secretos():
    raise NotImplementedError(
        "Almacén real (Secret Manager) pendiente; en tests se inyecta uno en memoria."
    )


def obtener_fabrica_cliente_gmail():
    raise NotImplementedError(
        "Fábrica real (token→cliente Gmail) pendiente; en tests se inyecta un doble."
    )


def obtener_secreto_poller():
    raise NotImplementedError(
        "Secreto del poller real (Scheduler/OIDC) pendiente; en tests se inyecta uno."
    )


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
