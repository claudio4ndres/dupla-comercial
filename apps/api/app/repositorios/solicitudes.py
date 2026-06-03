"""Repositorio de solicitudes: interfaz + implementación en memoria para tests.

La implementación real con Supabase (que respeta la RLS usando el JWT del usuario)
se hará en una tarea de integración aparte, con su propio test.
"""
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel


class Solicitud(BaseModel):
    """Representación de una fila de la tabla `solicitudes`."""

    id: UUID
    empresa_id: UUID
    remitente: str = ""
    asunto: str = ""
    cuerpo: str
    resumen: str | None = None
    tipo: str = "sin_clasificar"
    estado: str = "nueva"


class RepositorioSolicitudes(Protocol):
    async def obtener(
        self, solicitud_id: UUID, empresa_id: UUID
    ) -> Solicitud | None: ...

    async def guardar_clasificacion(
        self, solicitud_id: UUID, empresa_id: UUID, resumen: str, tipo: str
    ) -> Solicitud: ...


class RepositorioSolicitudesEnMemoria:
    """Implementación en memoria para tests. Emula el aislamiento por empresa de la
    RLS (filtra por `empresa_id`) y no cambia `estado` al clasificar."""

    def __init__(self, solicitudes: list[Solicitud] | None = None):
        self._por_id: dict[UUID, Solicitud] = {s.id: s for s in (solicitudes or [])}

    def por_id(self, solicitud_id: UUID) -> Solicitud | None:
        return self._por_id.get(solicitud_id)

    async def obtener(self, solicitud_id: UUID, empresa_id: UUID) -> Solicitud | None:
        solicitud = self._por_id.get(solicitud_id)
        if solicitud is None or solicitud.empresa_id != empresa_id:
            return None
        return solicitud

    async def guardar_clasificacion(
        self, solicitud_id: UUID, empresa_id: UUID, resumen: str, tipo: str
    ) -> Solicitud:
        solicitud = await self.obtener(solicitud_id, empresa_id)
        if solicitud is None:
            raise KeyError(solicitud_id)
        actualizada = solicitud.model_copy(update={"resumen": resumen, "tipo": tipo})
        self._por_id[solicitud_id] = actualizada
        return actualizada
