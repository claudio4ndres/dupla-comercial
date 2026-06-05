"""Proveedores de dependencias de FastAPI.

En los tests se sobrescriben con dobles (`app.dependency_overrides`). El cableado
real con Supabase aún se hará en tareas de integración aparte (con su propio
test); por eso esos proveedores siguen como `NotImplementedError`. El cliente
Anthropic real ya está cableado (T7a): se construye con la key de `Settings`.
"""
from functools import lru_cache

from anthropic import AsyncAnthropic

from app.config import obtener_settings


def obtener_repositorio_solicitudes():
    raise NotImplementedError(
        "Repositorio real (Supabase) pendiente; en tests se inyecta uno en memoria."
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


def obtener_empresa_actual():
    raise NotImplementedError(
        "Auth (JWT de Supabase) pendiente; en tests se inyecta una empresa_id."
    )
