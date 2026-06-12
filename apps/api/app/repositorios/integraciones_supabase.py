"""TR3 · Implementación real del repositorio de integraciones contra Supabase.

Habla con PostgREST (`/rest/v1/integraciones`). El mismo repo sirve dos llamadores
con credenciales distintas (regla de oro #2):

* **endpoints de usuario** → se construye con el **JWT del usuario** (apikey = anon):
  la RLS filtra por su empresa;
* **poller interno** → se construye con la **service role key** (apikey = service
  role, bearer = service role): la RLS no aplica, por eso cada método recibe la
  `empresa_id` y la fija explícita (jamás se infiere del ambiente → no cruza tenants).

Cero red en los tests: se inyecta un `httpx.AsyncClient` con transporte mockeado.
"""
from uuid import UUID

import httpx

from app.repositorios.integraciones import Integracion


class RepositorioIntegracionesSupabase:
    """Repositorio `RepositorioIntegraciones` respaldado por PostgREST de Supabase."""

    def __init__(
        self,
        base_url: str,
        key: str,
        token: str,
        *,
        cliente: httpx.AsyncClient | None = None,
    ):
        self._base = base_url.rstrip("/") + "/rest/v1"
        self._key = key      # apikey del proyecto (anon o service role)
        self._token = token  # bearer: JWT del usuario o service role
        self._cliente = cliente

    def _headers(self, extra: dict | None = None) -> dict:
        cabeceras = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        if extra:
            cabeceras.update(extra)
        return cabeceras

    async def _peticion(self, metodo: str, ruta: str, **kw) -> httpx.Response:
        url = self._base + ruta
        if self._cliente is not None:
            return await self._cliente.request(metodo, url, **kw)
        async with httpx.AsyncClient() as cliente:
            return await cliente.request(metodo, url, **kw)

    @staticmethod
    def _a_integracion(fila: dict) -> Integracion:
        return Integracion(
            id=fila["id"],
            empresa_id=fila["empresa_id"],
            proveedor=fila.get("proveedor", "gmail"),
            token_ref=fila["token_ref"],
            casilla=fila.get("casilla"),
            cursor=fila.get("cursor"),
            estado=fila.get("estado", "conectado"),
        )

    async def obtener_por_empresa(self, empresa_id: UUID) -> Integracion | None:
        resp = await self._peticion(
            "GET",
            f"/integraciones?empresa_id=eq.{empresa_id}&select=*",
            headers=self._headers(),
        )
        resp.raise_for_status()
        filas = resp.json()
        return self._a_integracion(filas[0]) if filas else None

    async def obtener_por_empresa_y_proveedor(
        self, empresa_id: UUID, proveedor: str
    ) -> Integracion | None:
        """Integración de un proveedor concreto de la empresa (gmail/clickup). Una
        empresa puede tener varias; este filtro distingue cuál sin confundirlas."""
        resp = await self._peticion(
            "GET",
            f"/integraciones?empresa_id=eq.{empresa_id}"
            f"&proveedor=eq.{proveedor}&select=*",
            headers=self._headers(),
        )
        resp.raise_for_status()
        filas = resp.json()
        return self._a_integracion(filas[0]) if filas else None

    async def listar_por_proveedor(self, proveedor: str) -> list[Integracion]:
        resp = await self._peticion(
            "GET",
            f"/integraciones?proveedor=eq.{proveedor}&select=*",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return [self._a_integracion(f) for f in resp.json()]

    async def guardar(self, integracion: Integracion) -> Integracion:
        """Upsert por `(empresa_id, proveedor)`: el callback de OAuth conecta o
        reconecta la misma casilla sin duplicar la fila."""
        resp = await self._peticion(
            "POST",
            "/integraciones?on_conflict=empresa_id,proveedor",
            headers=self._headers(
                {"Prefer": "return=representation,resolution=merge-duplicates"}
            ),
            json={
                "empresa_id": str(integracion.empresa_id),
                "proveedor": integracion.proveedor,
                "token_ref": integracion.token_ref,
                "casilla": integracion.casilla,
                "cursor": integracion.cursor,
                "estado": integracion.estado,
            },
        )
        resp.raise_for_status()
        filas = resp.json()
        return self._a_integracion(filas[0]) if filas else integracion

    async def actualizar_cursor(self, empresa_id: UUID, cursor: str | None) -> None:
        resp = await self._peticion(
            "PATCH",
            f"/integraciones?empresa_id=eq.{empresa_id}",
            headers=self._headers(),
            json={"cursor": cursor},
        )
        resp.raise_for_status()

    async def marcar_estado(self, empresa_id: UUID, estado: str) -> None:
        resp = await self._peticion(
            "PATCH",
            f"/integraciones?empresa_id=eq.{empresa_id}",
            headers=self._headers(),
            json={"estado": estado},
        )
        resp.raise_for_status()

    async def eliminar(self, empresa_id: UUID) -> None:
        resp = await self._peticion(
            "DELETE",
            f"/integraciones?empresa_id=eq.{empresa_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()

    async def eliminar_por_proveedor(
        self, empresa_id: UUID, proveedor: str
    ) -> None:
        """Borra SÓLO la integración de ese proveedor de la empresa (p.ej. desconectar
        clickup sin tocar gmail). Idempotente: si no hay fila, PostgREST devuelve 204."""
        resp = await self._peticion(
            "DELETE",
            f"/integraciones?empresa_id=eq.{empresa_id}&proveedor=eq.{proveedor}",
            headers=self._headers(),
        )
        resp.raise_for_status()
