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


class PropuestaResumen(BaseModel):
    """Una propuesta tal como la lista la sección "Propuestas" del front
    (GET /propuestas). Es la cabecera de la propuesta + `asunto`/`remitente` de la
    solicitud ligada (propuesta→conversación→solicitud), sin sus componentes/tareas.

    `empresa_id` es interno (emula la RLS / sirve de aislamiento en el doble); la
    vista que ve el front NUNCA lo incluye (CA5): el endpoint mapea a un esquema plano.
    """

    id: UUID
    empresa_id: UUID
    solicitud_id: UUID
    total: float = 0
    estado: str = "borrador"
    asunto: str = ""
    remitente: str = ""


class RepositorioPropuestas(Protocol):
    async def obtener_por_solicitud(
        self, solicitud_id: UUID, empresa_id: UUID
    ) -> Propuesta | None: ...

    async def listar(self, empresa_id: UUID) -> list[PropuestaResumen]: ...


class RepositorioPropuestasEnMemoria:
    """Doble en memoria para tests. Emula el aislamiento por empresa de la RLS:
    sólo entrega la propuesta si pertenece a la empresa consultada."""

    def __init__(
        self,
        propuestas: list[Propuesta] | list[PropuestaResumen] | None = None,
    ):
        # `obtener_por_solicitud` indexa las `Propuesta` completas por (empresa, solicitud);
        # `listar` devuelve los `PropuestaResumen` (acepta cualquiera de los dos en el alta,
        # así los tests inyectan resúmenes con asunto/remitente o propuestas completas).
        self._por_clave: dict[tuple[UUID, UUID], Propuesta] = {}
        self._resumenes: list[PropuestaResumen] = []
        for p in propuestas or []:
            if isinstance(p, Propuesta):
                self._por_clave[(p.empresa_id, p.solicitud_id)] = p
                self._resumenes.append(
                    PropuestaResumen(
                        id=p.id,
                        empresa_id=p.empresa_id,
                        solicitud_id=p.solicitud_id,
                        total=p.total,
                        estado=p.estado,
                    )
                )
            else:
                self._resumenes.append(p)

    async def obtener_por_solicitud(
        self, solicitud_id: UUID, empresa_id: UUID
    ) -> Propuesta | None:
        return self._por_clave.get((empresa_id, solicitud_id))

    async def listar(self, empresa_id: UUID) -> list[PropuestaResumen]:
        # Sólo las de la empresa consultada (emula la RLS).
        return [r for r in self._resumenes if r.empresa_id == empresa_id]
