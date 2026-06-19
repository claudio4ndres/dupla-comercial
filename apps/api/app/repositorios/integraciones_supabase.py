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

from app.repositorios.cliente_postgrest import ClientePostgREST
from app.repositorios.integraciones import Integracion


class RepositorioIntegracionesSupabase(ClientePostgREST):
    """Repositorio `RepositorioIntegraciones` respaldado por PostgREST de Supabase."""

    def __init__(
        self,
        base_url: str,
        key: str,
        token: str,
        *,
        cliente: httpx.AsyncClient | None = None,
    ):
        # `key` puede ser anon_key o service_role_key; `token` puede ser JWT o service role.
        super().__init__(base_url, key, token, cliente=cliente)

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

    async def listar_por_estado(self, estado: str) -> list[Integracion]:
        """CA3 (Spec 010): integraciones en un `estado` dado (p.ej. 'reconectar'),
        para la observabilidad del operador. Lo usa el endpoint interno con la service
        role (cruza empresas a propósito); el `response_model` del endpoint descarta el
        `token_ref`, así la señal nunca expone tokens (regla de oro #3)."""
        resp = await self._peticion(
            "GET",
            f"/integraciones?estado=eq.{estado}&select=*",
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

    async def marcar_estado(
        self, empresa_id: UUID, estado: str, proveedor: str
    ) -> None:
        """Marca el estado de la integración de UN proveedor (gmail/clickup) de la
        empresa. Filtra por `empresa_id` Y `proveedor`: un fallo de gmail JAMÁS arrastra
        a la fila clickup (ni viceversa) — el bug colateral que dejaba ClickUp atascado
        en 'reconectar' por un error de Gmail (#5)."""
        resp = await self._peticion(
            "PATCH",
            f"/integraciones?empresa_id=eq.{empresa_id}&proveedor=eq.{proveedor}",
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
