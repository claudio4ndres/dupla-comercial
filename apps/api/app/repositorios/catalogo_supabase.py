"""005 · Implementación real del repositorio de catálogo contra Supabase.

Habla con PostgREST (`/rest/v1`) usando el **JWT del usuario**: la RLS de Postgres
filtra por su empresa (regla de oro #2 — la barrera multi-tenant es la RLS, no un
filtro del backend). Se construye **por request** con el token del usuario.

Cero red en los tests: se inyecta un `httpx.AsyncClient` con transporte mockeado.
"""
from uuid import UUID

import httpx

from app.repositorios.catalogo import ItemCatalogo
from app.repositorios.cliente_postgrest import ClientePostgREST


class RepositorioCatalogoSupabase(ClientePostgREST):
    """Repositorio `RepositorioCatalogo` respaldado por PostgREST de Supabase."""

    async def buscar(
        self,
        consulta: str,
        empresa_id: UUID,
        *,
        tipo: str | None = None,
        limite: int = 8,
    ) -> list[ItemCatalogo]:
        # La RLS ya restringe a la empresa del JWT (regla #2): no filtramos por
        # empresa_id en el backend. Filtramos por texto (ILIKE en nombre/detalle) y
        # por tipo, y acotamos el número de filas (CA8: extractos, no archivos).
        partes = ["select=*", f"limit={limite}"]
        q = (consulta or "").strip()
        if q:
            partes.append(f"or=(nombre.ilike.*{q}*,detalle.ilike.*{q}*)")
        if tipo:
            partes.append(f"tipo=eq.{tipo}")
        resp = await self._peticion(
            "GET", "/catalogo?" + "&".join(partes), headers=self._headers()
        )
        resp.raise_for_status()
        return [ItemCatalogo(**fila) for fila in resp.json()]

    async def recursos(self, empresa_id: UUID) -> list[str]:
        # La RLS filtra por la empresa del JWT (regla #2). Traemos sólo la columna
        # `origen` y deduplicamos los recursos del Drive del catálogo.
        resp = await self._peticion(
            "GET", "/catalogo?select=origen", headers=self._headers()
        )
        resp.raise_for_status()
        return sorted({fila["origen"] for fila in resp.json() if fila.get("origen")})
