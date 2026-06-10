"""T13 · `RepositorioConversacionesEnMemoria` (doble para tests).

Verifica el contrato del repositorio que persiste el hilo del chat con Javo:
guardar turnos y luego obtenerlos ordenados por `creado_en`, y que el aislamiento
por empresa (que en la base impone la RLS) no cruce tenants.
"""
from uuid import uuid4

from app.repositorios.conversaciones import RepositorioConversacionesEnMemoria

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


async def test_sin_conversacion_obtener_devuelve_lista_vacia():
    repo = RepositorioConversacionesEnMemoria()
    sol = uuid4()

    assert await repo.obtener_mensajes(sol, EMPRESA_A) == []


async def test_guardar_turnos_y_obtenerlos_ordenados():
    repo = RepositorioConversacionesEnMemoria()
    sol = uuid4()

    await repo.guardar_turnos(
        sol,
        EMPRESA_A,
        "t1",
        [
            {"rol": "usuario", "contenido": "Son 3 días de activación"},
            {"rol": "javo", "contenido": "Perfecto, dejo catering + 2 promotores."},
        ],
    )

    mensajes = await repo.obtener_mensajes(sol, EMPRESA_A)
    assert [(m.rol, m.contenido) for m in mensajes] == [
        ("usuario", "Son 3 días de activación"),
        ("javo", "Perfecto, dejo catering + 2 promotores."),
    ]


async def test_guardar_turnos_acumula_en_la_misma_conversacion():
    # Dos llamadas a guardar_turnos sobre la misma (solicitud, empresa) NO crean
    # conversaciones nuevas: agregan mensajes al mismo hilo.
    repo = RepositorioConversacionesEnMemoria()
    sol = uuid4()

    await repo.guardar_turnos(sol, EMPRESA_A, "t1", [{"rol": "usuario", "contenido": "uno"}])
    await repo.guardar_turnos(sol, EMPRESA_A, "t1", [{"rol": "javo", "contenido": "dos"}])

    mensajes = await repo.obtener_mensajes(sol, EMPRESA_A)
    assert [m.contenido for m in mensajes] == ["uno", "dos"]


async def test_aislamiento_por_empresa_no_cruza_tenants():
    # La conversación es de la empresa A; la empresa B no la ve (emula la RLS).
    repo = RepositorioConversacionesEnMemoria()
    sol = uuid4()

    await repo.guardar_turnos(sol, EMPRESA_A, "t1", [{"rol": "usuario", "contenido": "privado"}])

    assert await repo.obtener_mensajes(sol, EMPRESA_B) == []
    assert len(await repo.obtener_mensajes(sol, EMPRESA_A)) == 1
