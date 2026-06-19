"""Clase base para repositorios que hablan con PostgREST de Supabase.

Encapsula la lógica repetida de conexión y autenticación: constructor, _headers y
_peticion. Los repos concretos heredan y solo implementan sus métodos de dominio.
"""
import httpx


class ClientePostgREST:
    """Base para repositorios Supabase. Maneja conexión + auth con PostgREST."""

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
        self._cliente = cliente

    def _headers(self, extra: dict | None = None) -> dict:
        """Cabeceras PostgREST: apikey + Bearer JWT + Content-Type."""
        cabeceras = {
            "apikey": self._anon,
            "Authorization": f"Bearer {self._jwt}",
            "Content-Type": "application/json",
        }
        if extra:
            cabeceras.update(extra)
        return cabeceras

    async def _peticion(self, metodo: str, ruta: str, **kw) -> httpx.Response:
        """Ejecuta una petición HTTP contra PostgREST."""
        url = self._base + ruta
        if self._cliente is not None:
            return await self._cliente.request(metodo, url, **kw)
        async with httpx.AsyncClient() as cliente:
            return await cliente.request(metodo, url, **kw)
