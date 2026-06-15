"""Repositorio de integraciones (conexión de correo por empresa): interfaz +
implementación en memoria para tests.

La implementación real (Supabase) se hace en una tarea de integración aparte:
- los endpoints de usuario hablan con el JWT del usuario (la RLS filtra),
- el poller usa el `service role` y FIJA `empresa_id` explícito (la RLS no aplica),
  por eso este repositorio recibe siempre la `empresa_id` y nunca la infiere.
"""
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel


class Integracion(BaseModel):
    """Una fila de la tabla `integraciones` (proveedor de correo por empresa)."""

    id: UUID
    empresa_id: UUID
    proveedor: str = "gmail"
    token_ref: str
    casilla: str | None = None
    cursor: str | None = None
    estado: str = "conectado"  # conectado | reconectar


class RepositorioIntegraciones(Protocol):
    async def obtener_por_empresa(self, empresa_id: UUID) -> Integracion | None: ...
    async def obtener_por_empresa_y_proveedor(
        self, empresa_id: UUID, proveedor: str
    ) -> Integracion | None: ...
    async def listar_por_proveedor(self, proveedor: str) -> list[Integracion]: ...
    async def listar_por_estado(self, estado: str) -> list[Integracion]: ...
    async def guardar(self, integracion: Integracion) -> Integracion: ...
    async def actualizar_cursor(
        self, empresa_id: UUID, cursor: str | None
    ) -> None: ...
    async def marcar_estado(
        self, empresa_id: UUID, estado: str, proveedor: str
    ) -> None: ...
    async def eliminar(self, empresa_id: UUID) -> None: ...
    async def eliminar_por_proveedor(
        self, empresa_id: UUID, proveedor: str
    ) -> None: ...


class RepositorioIntegracionesEnMemoria:
    """Implementación en memoria. Emula `unique(empresa_id, proveedor)`: una empresa
    puede tener VARIAS integraciones (p.ej. gmail Y clickup), pero a lo sumo una por
    proveedor. La clave es `(empresa_id, proveedor)`."""

    def __init__(self, integraciones: list[Integracion] | None = None):
        self._por_clave: dict[tuple[UUID, str], Integracion] = {
            (i.empresa_id, i.proveedor): i for i in (integraciones or [])
        }

    async def obtener_por_empresa(self, empresa_id: UUID) -> Integracion | None:
        # Compat: la primera integración de la empresa (el flujo de Gmail asume una
        # sola). Para distinguir gmail/clickup usar `obtener_por_empresa_y_proveedor`.
        for (emp, _proveedor), integ in self._por_clave.items():
            if emp == empresa_id:
                return integ
        return None

    async def obtener_por_empresa_y_proveedor(
        self, empresa_id: UUID, proveedor: str
    ) -> Integracion | None:
        return self._por_clave.get((empresa_id, proveedor))

    async def listar_por_proveedor(self, proveedor: str) -> list[Integracion]:
        return [
            i for i in self._por_clave.values() if i.proveedor == proveedor
        ]

    async def listar_por_estado(self, estado: str) -> list[Integracion]:
        # CA3 (Spec 010): alimenta la observabilidad del operador ("¿quién está en
        # 'reconectar'?"). Cruza empresas y proveedores por diseño (canal de operador).
        return [i for i in self._por_clave.values() if i.estado == estado]

    async def guardar(self, integracion: Integracion) -> Integracion:
        # upsert por (empresa, proveedor): el callback de OAuth conecta o reconecta.
        self._por_clave[(integracion.empresa_id, integracion.proveedor)] = integracion
        return integracion

    async def actualizar_cursor(self, empresa_id: UUID, cursor: str | None) -> None:
        for clave, integ in list(self._por_clave.items()):
            if clave[0] == empresa_id:
                self._por_clave[clave] = integ.model_copy(update={"cursor": cursor})

    async def marcar_estado(
        self, empresa_id: UUID, estado: str, proveedor: str
    ) -> None:
        # Por (empresa, proveedor): marca SÓLO la fila de ese proveedor. Así un fallo
        # de gmail no arrastra a la fila clickup de la misma empresa (#5).
        clave = (empresa_id, proveedor)
        integ = self._por_clave.get(clave)
        if integ is not None:
            self._por_clave[clave] = integ.model_copy(update={"estado": estado})

    async def eliminar(self, empresa_id: UUID) -> None:
        # Borra TODAS las integraciones de la empresa (comportamiento histórico del
        # "desconectar" de Gmail). Para borrar sólo una usar `eliminar_por_proveedor`.
        for clave in [c for c in self._por_clave if c[0] == empresa_id]:
            self._por_clave.pop(clave, None)

    async def eliminar_por_proveedor(
        self, empresa_id: UUID, proveedor: str
    ) -> None:
        self._por_clave.pop((empresa_id, proveedor), None)
