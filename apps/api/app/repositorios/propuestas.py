"""Repositorio de propuestas (la cotización de una solicitud): interfaz + doble
en memoria para tests.

La cotización es la cadena `solicitud → conversacion → propuesta →
componentes_propuesta + tareas`. Aquí se modela la propuesta ya resuelta con sus
componentes valorizados y sus tareas. La implementación real contra Supabase
(que respeta la RLS con el JWT del usuario) vive en `propuestas_supabase.py`.
"""
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel


class ComponentePropuesta(BaseModel):
    """Una línea valorizada de la cotización (tabla `componentes_propuesta`)."""

    nombre: str
    detalle: str | None = None
    proveedor: str | None = None
    cantidad: int = 1
    dias: int = 1
    valor_unitario: float = 0  # tarifa POR DÍA por unidad (T17); costo = cant×días×valor


class TareaPropuesta(BaseModel):
    """Una tarea derivada de la propuesta (tabla `tareas`)."""

    nombre: str
    grupo: str | None = None
    responsable: str | None = None
    vencimiento: str | None = None


class Propuesta(BaseModel):
    """Propuesta resuelta de una solicitud, con sus componentes y tareas.

    `empresa_id`/`solicitud_id` son internos (emulan la RLS / sirven de llave); la
    vista que ve el front NUNCA los incluye (CA5): el endpoint mapea a un esquema
    plano.
    """

    id: UUID
    empresa_id: UUID
    solicitud_id: UUID
    total: float = 0
    estado: str = "borrador"
    componentes: list[ComponentePropuesta] = []
    tareas: list[TareaPropuesta] = []


class RepositorioPropuestas(Protocol):
    async def obtener_por_solicitud(
        self, solicitud_id: UUID, empresa_id: UUID
    ) -> Propuesta | None: ...


class RepositorioPropuestasEnMemoria:
    """Doble en memoria para tests. Emula el aislamiento por empresa de la RLS:
    sólo entrega la propuesta si pertenece a la empresa consultada."""

    def __init__(self, propuestas: list[Propuesta] | None = None):
        self._por_clave: dict[tuple[UUID, UUID], Propuesta] = {
            (p.empresa_id, p.solicitud_id): p for p in (propuestas or [])
        }

    async def obtener_por_solicitud(
        self, solicitud_id: UUID, empresa_id: UUID
    ) -> Propuesta | None:
        return self._por_clave.get((empresa_id, solicitud_id))
