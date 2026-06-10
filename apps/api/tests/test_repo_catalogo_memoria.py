"""005 · `RepositorioCatalogoEnMemoria` (doble para tests).

Emula el aislamiento por empresa de la RLS (filtra por `empresa_id`) y la búsqueda
por texto en `nombre`/`detalle`. Es la base sobre la que se prueban el servicio de
Javo y el endpoint sin tocar Supabase.
"""
from uuid import uuid4

from app.repositorios.catalogo import ItemCatalogo, RepositorioCatalogoEnMemoria

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def _item(empresa_id=EMPRESA_A, **kwargs):
    base = dict(
        id=uuid4(),
        empresa_id=empresa_id,
        tipo="componente",
        nombre="Promotoras uniformadas",
        detalle="6h/día · 3 tiendas",
        valor_unitario=240000,
    )
    base.update(kwargs)
    return ItemCatalogo(**base)


async def test_buscar_filtra_por_empresa():
    # CA5 (a nivel de doble): la empresa A no ve el catálogo de la B.
    repo = RepositorioCatalogoEnMemoria(
        [
            _item(empresa_id=EMPRESA_A, nombre="Promotoras"),
            _item(empresa_id=EMPRESA_B, nombre="Promotoras"),
        ]
    )

    res = await repo.buscar("promotoras", EMPRESA_A)

    assert len(res) == 1
    assert res[0].empresa_id == EMPRESA_A


async def test_buscar_por_texto_en_nombre_o_detalle():
    repo = RepositorioCatalogoEnMemoria(
        [
            _item(nombre="Promotoras uniformadas", detalle="3 tiendas"),
            _item(nombre="Catering", detalle="coffee break para el equipo"),
        ]
    )

    por_nombre = await repo.buscar("promotoras", EMPRESA_A)
    por_detalle = await repo.buscar("coffee", EMPRESA_A)

    assert [i.nombre for i in por_nombre] == ["Promotoras uniformadas"]
    assert [i.nombre for i in por_detalle] == ["Catering"]


async def test_buscar_respeta_tipo():
    repo = RepositorioCatalogoEnMemoria(
        [
            _item(tipo="componente", nombre="Promotoras"),
            _item(tipo="caso", nombre="Activación F1 Red Bull", valor_unitario=None),
        ]
    )

    casos = await repo.buscar("", EMPRESA_A, tipo="caso")

    assert [i.nombre for i in casos] == ["Activación F1 Red Bull"]


async def test_buscar_respeta_limite():
    repo = RepositorioCatalogoEnMemoria(
        [_item(nombre=f"Componente {n}") for n in range(10)]
    )

    res = await repo.buscar("componente", EMPRESA_A, limite=3)

    assert len(res) == 3


async def test_recursos_devuelve_origenes_distintos_de_la_empresa():
    # El panel "Recursos · Drive" lista los origenes (recursos del Drive) del catálogo
    # de la empresa: distintos, ordenados, sin nulos, y SOLO de su empresa (RLS).
    repo = RepositorioCatalogoEnMemoria(
        [
            _item(empresa_id=EMPRESA_A, origen="Tarifario.xlsx"),
            _item(empresa_id=EMPRESA_A, origen="Tarifario.xlsx"),  # duplicado
            _item(empresa_id=EMPRESA_A, origen="PRODUCCIÓN 3D"),
            _item(empresa_id=EMPRESA_A, origen=None),  # sin origen → se ignora
            _item(empresa_id=EMPRESA_B, origen="Otra empresa.xlsx"),  # de otra empresa
        ]
    )

    recs = await repo.recursos(EMPRESA_A)

    assert recs == ["PRODUCCIÓN 3D", "Tarifario.xlsx"]
