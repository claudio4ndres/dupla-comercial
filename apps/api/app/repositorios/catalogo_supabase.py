"""005 · Implementación real del repositorio de catálogo contra Supabase.

Habla con PostgREST (`/rest/v1`) usando el **JWT del usuario**: la RLS de Postgres
filtra por su empresa (regla de oro #2 — la barrera multi-tenant es la RLS, no un
filtro del backend). Se construye **por request** con el token del usuario.

Cero red en los tests: se inyecta un `httpx.AsyncClient` con transporte mockeado.
"""
from uuid import UUID

import httpx

from app.repositorios.catalogo import ItemCatalogo


class RepositorioCatalogoSupabase:
    """Repositorio `RepositorioCatalogo` respaldado por PostgREST de Supabase."""

    def __init__(
        self,
        base_url: str,
        anon_key: str,
        jwt: str,
        *,
        cliente: httpx.AsyncClient | None = None,
    ):
        self._base = base_url.rstrip("/") + "/rest/v1"
        self._anon = anon_key
        self._jwt = jwt
        self._cliente = cliente  # inyectable para tests; en prod se crea por llamada

    def _headers(self) -> dict:
        # `apikey` identifica al proyecto; `Authorization` lleva el JWT del usuario,
        # que es lo que activa la RLS a nombre de SU empresa.
        return {
            "apikey": self._anon,
            "Authorization": f"Bearer {self._jwt}",
            "Content-Type": "application/json",
        }

    async def _peticion(self, metodo: str, ruta: str, **kw) -> httpx.Response:
        url = self._base + ruta
        if self._cliente is not None:
            return await self._cliente.request(metodo, url, **kw)
        async with httpx.AsyncClient() as cliente:
            return await cliente.request(metodo, url, **kw)

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
