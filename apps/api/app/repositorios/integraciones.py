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
    async def listar_por_proveedor(self, proveedor: str) -> list[Integracion]: ...
    async def guardar(self, integracion: Integracion) -> Integracion: ...
    async def actualizar_cursor(
        self, empresa_id: UUID, cursor: str | None
    ) -> None: ...
    async def marcar_estado(self, empresa_id: UUID, estado: str) -> None: ...
    async def eliminar(self, empresa_id: UUID) -> None: ...


class RepositorioIntegracionesEnMemoria:
    """Implementación en memoria. Emula `unique(empresa_id, proveedor)` guardando
    UNA integración por empresa (en el piloto: una casilla por empresa)."""

    def __init__(self, integraciones: list[Integracion] | None = None):
        self._por_empresa: dict[UUID, Integracion] = {
            i.empresa_id: i for i in (integraciones or [])
        }

    async def obtener_por_empresa(self, empresa_id: UUID) -> Integracion | None:
        return self._por_empresa.get(empresa_id)

    async def listar_por_proveedor(self, proveedor: str) -> list[Integracion]:
        return [i for i in self._por_empresa.values() if i.proveedor == proveedor]

    async def guardar(self, integracion: Integracion) -> Integracion:
        # upsert por empresa (el callback de OAuth conecta o reconecta).
        self._por_empresa[integracion.empresa_id] = integracion
        return integracion

    async def actualizar_cursor(self, empresa_id: UUID, cursor: str | None) -> None:
        integ = self._por_empresa.get(empresa_id)
        if integ is not None:
            self._por_empresa[empresa_id] = integ.model_copy(
                update={"cursor": cursor}
            )

    async def marcar_estado(self, empresa_id: UUID, estado: str) -> None:
        integ = self._por_empresa.get(empresa_id)
        if integ is not None:
            self._por_empresa[empresa_id] = integ.model_copy(
                update={"estado": estado}
            )

    async def eliminar(self, empresa_id: UUID) -> None:
        self._por_empresa.pop(empresa_id, None)
