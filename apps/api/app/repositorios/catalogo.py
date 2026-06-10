"""Repositorio del catálogo de la empresa (los recursos del Drive para Javo).

`buscar_en_drive` (spec 005) consulta este catálogo: `componente` (con precio, para
cotizar) y `caso` (trabajos anteriores, para inspirar ideas). La implementación real
contra Supabase (que respeta la RLS con el JWT del usuario) vive en
`catalogo_supabase.py`; aquí va la interfaz + un doble en memoria para tests.
"""
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel


class ItemCatalogo(BaseModel):
    """Una fila del catálogo (tabla `catalogo`)."""

    id: UUID
    empresa_id: UUID
    tipo: str = "componente"  # 'componente' | 'caso'
    nombre: str
    detalle: str | None = None
    unidad: str | None = None
    valor_unitario: float | None = None
    proveedor: str | None = None
    origen: str | None = None


class RepositorioCatalogo(Protocol):
    async def buscar(
        self,
        consulta: str,
        empresa_id: UUID,
        *,
        tipo: str | None = None,
        limite: int = 8,
    ) -> list[ItemCatalogo]: ...

    async def recursos(self, empresa_id: UUID) -> list[str]: ...


class RepositorioCatalogoEnMemoria:
    """Doble en memoria para tests. Emula el aislamiento por empresa de la RLS y la
    búsqueda por texto en `nombre`/`detalle`."""

    def __init__(self, items: list[ItemCatalogo] | None = None):
        self._items = list(items or [])

    async def buscar(
        self,
        consulta: str,
        empresa_id: UUID,
        *,
        tipo: str | None = None,
        limite: int = 8,
    ) -> list[ItemCatalogo]:
        q = (consulta or "").strip().lower()
        encontrados: list[ItemCatalogo] = []
        for item in self._items:
            if item.empresa_id != empresa_id:  # barrera multi-tenant (emula RLS)
                continue
            if tipo is not None and item.tipo != tipo:
                continue
            texto = f"{item.nombre} {item.detalle or ''}".lower()
            if q and q not in texto:
                continue
            encontrados.append(item)
        return encontrados[:limite]

    async def recursos(self, empresa_id: UUID) -> list[str]:
        vistos: list[str] = []
        for item in self._items:
            if item.empresa_id == empresa_id and item.origen and item.origen not in vistos:
                vistos.append(item.origen)
        return sorted(vistos)
