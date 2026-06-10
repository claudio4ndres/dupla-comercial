"""005 · Proveedor de búsqueda en internet (Tipo 2).

Para la demo usamos un proveedor **curado** (determinista, offline-safe) que NO llama
a una API real: devuelve referencias con sus **fuentes** (CA6/CA11). En los tests del
servicio de Javo se inyecta un doble; aquí verificamos el contrato del proveedor.
"""
from app.servicios.busqueda_internet import ProveedorBusquedaCurado


async def test_curado_devuelve_resultados_con_fuentes():
    prov = ProveedorBusquedaCurado()

    res = await prov.buscar("activación fórmula 1")

    assert len(res) >= 1
    # Cada resultado trae una fuente citable (título + referencia/URL).
    assert all(r.titulo and r.referencia for r in res)


async def test_curado_respeta_limite():
    prov = ProveedorBusquedaCurado()

    res = await prov.buscar("ideas de alto impacto", limite=2)

    assert len(res) <= 2


async def test_curado_es_determinista():
    prov = ProveedorBusquedaCurado()

    a = await prov.buscar("sampling metro")
    b = await prov.buscar("sampling metro")

    assert [r.referencia for r in a] == [r.referencia for r in b]
