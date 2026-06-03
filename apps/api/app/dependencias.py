"""Proveedores de dependencias de FastAPI.

En los tests se sobrescriben con dobles (`app.dependency_overrides`). El cableado
real con Supabase y AsyncAnthropic se hará en una tarea de integración aparte (con
su propio test); por eso aquí los proveedores reales aún no están implementados.
"""


def obtener_repositorio_solicitudes():
    raise NotImplementedError(
        "Repositorio real (Supabase) pendiente; en tests se inyecta uno en memoria."
    )


def obtener_cliente_anthropic():
    raise NotImplementedError(
        "Cliente AsyncAnthropic real pendiente; en tests se inyecta un doble."
    )


def obtener_empresa_actual():
    raise NotImplementedError(
        "Auth (JWT de Supabase) pendiente; en tests se inyecta una empresa_id."
    )
