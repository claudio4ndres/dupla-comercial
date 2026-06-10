"""Tests del doble en memoria `RepositorioMiembrosEnMemoria` (0006).

El roster de miembros alimenta el selector "Asignado a" de la pantalla de Tareas.
El doble en memoria emula el aislamiento por empresa de la RLS: sólo entrega los
miembros de la empresa consultada. La implementación real (PostgREST con el JWT del
usuario) vive en `miembros_supabase.py` y se prueba aparte (sin red).
"""
from uuid import uuid4

from app.repositorios.miembros import Miembro, RepositorioMiembrosEnMemoria

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def _miembro(empresa_id=EMPRESA_A, **kwargs):
    base = dict(empresa_id=empresa_id, nombre="Gabriela Lillo", rol="RRHH")
    base.update(kwargs)
    return Miembro(**base)


async def test_listar_devuelve_los_miembros_de_la_empresa():
    m1 = _miembro(nombre="Gabriela Lillo", rol="RRHH")
    m2 = _miembro(nombre="Bruno Soto", rol="Producción")
    repo = RepositorioMiembrosEnMemoria([m1, m2])

    miembros = await repo.listar(EMPRESA_A)

    assert len(miembros) == 2
    assert {m.nombre for m in miembros} == {"Gabriela Lillo", "Bruno Soto"}
    g = next(m for m in miembros if m.nombre == "Gabriela Lillo")
    assert g.rol == "RRHH"


async def test_listar_sin_miembros_devuelve_lista_vacia():
    repo = RepositorioMiembrosEnMemoria([])
    assert await repo.listar(EMPRESA_A) == []


async def test_listar_solo_devuelve_miembros_de_la_empresa_actual():
    # Aislamiento multi-tenant: la empresa A no ve los miembros de la B.
    m_a = _miembro(empresa_id=EMPRESA_A, nombre="De A")
    m_b = _miembro(empresa_id=EMPRESA_B, nombre="De B")
    repo = RepositorioMiembrosEnMemoria([m_a, m_b])

    miembros = await repo.listar(EMPRESA_A)

    assert len(miembros) == 1
    assert miembros[0].nombre == "De A"
