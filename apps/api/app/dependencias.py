"""Proveedores de dependencias de FastAPI.

En los tests se sobrescriben con dobles (`app.dependency_overrides`). El cableado
real con Supabase y AsyncAnthropic se hará en una tarea de integración aparte (con
su propio test); por eso aquí los proveedores reales aún no están implementados.
"""


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


def obtener_cliente_anthropic():
    raise NotImplementedError(
        "Cliente AsyncAnthropic real pendiente; en tests se inyecta un doble."
    )


def obtener_empresa_actual():
    raise NotImplementedError(
        "Auth (JWT de Supabase) pendiente; en tests se inyecta una empresa_id."
    )
