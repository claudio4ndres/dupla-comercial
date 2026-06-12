"""Repositorio de propuestas (la cotización de una solicitud): interfaz + doble
en memoria para tests.

La cotización es la cadena `solicitud → conversacion → propuesta →
componentes_propuesta + tareas`. Aquí se modela la propuesta ya resuelta con sus
componentes valorizados y sus tareas. La implementación real contra Supabase
(que respeta la RLS con el JWT del usuario) vive en `propuestas_supabase.py`.
"""
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel


def _total_de(componentes: "list[ComponentePropuesta]") -> float:
    """Costo total de la cotización: Σ cantidad × días × valor_unitario (T17)."""
    return sum(
        c.cantidad * (c.dias or 1) * (c.valor_unitario or 0) for c in componentes
    )


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

    async def crear(
        self,
        empresa_id: UUID,
        solicitud_id: UUID,
        conversacion_id: UUID,
        componentes: list[ComponentePropuesta],
        tareas: list[TareaPropuesta],
    ) -> Propuesta: ...

    async def actualizar_estado(
        self, propuesta_id: UUID, empresa_id: UUID, nuevo_estado: str
    ) -> Propuesta: ...

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

    async def crear(
        self,
        empresa_id: UUID,
        solicitud_id: UUID,
        conversacion_id: UUID,
        componentes: list[ComponentePropuesta],
        tareas: list[TareaPropuesta],
    ) -> Propuesta:
        # #4 · IDEMPOTENTE: la conversación se reutiliza por (solicitud, tipo), así que
        # re-generar la propuesta NO debe duplicarla. Si ya hay una para esta (empresa,
        # solicitud), se REEMPLAZA en sitio (misma fila lógica + su resumen) en vez de
        # apilar otra. Emula el UNIQUE(conversacion_id) + el reemplazo del repo real.
        clave = (empresa_id, solicitud_id)
        existente = self._por_clave.get(clave)
        propuesta = Propuesta(
            id=existente.id if existente else uuid4(),
            empresa_id=empresa_id,
            solicitud_id=solicitud_id,
            total=_total_de(componentes),
            estado="borrador",
            componentes=componentes,
            tareas=tareas,
        )
        self._por_clave[clave] = propuesta
        resumen = PropuestaResumen(
            id=propuesta.id,
            empresa_id=empresa_id,
            solicitud_id=solicitud_id,
            total=propuesta.total,
            estado=propuesta.estado,
        )
        # Reemplaza el resumen de la misma propuesta si existía; si no, lo agrega.
        self._resumenes = [r for r in self._resumenes if r.id != propuesta.id]
        self._resumenes.append(resumen)
        return propuesta

    async def actualizar_estado(
        self, propuesta_id: UUID, empresa_id: UUID, nuevo_estado: str
    ) -> Propuesta:
        # Sólo mueve propuestas de la empresa consultada (emula la RLS). Actualiza tanto
        # la `Propuesta` completa como su `PropuestaResumen` para que `listar` quede al día.
        for clave, propuesta in self._por_clave.items():
            if propuesta.id == propuesta_id and clave[0] == empresa_id:
                actualizada = propuesta.model_copy(update={"estado": nuevo_estado})
                self._por_clave[clave] = actualizada
                self._resumenes = [
                    r.model_copy(update={"estado": nuevo_estado})
                    if r.id == propuesta_id
                    else r
                    for r in self._resumenes
                ]
                return actualizada
        raise KeyError(propuesta_id)

    async def listar(self, empresa_id: UUID) -> list[PropuestaResumen]:
        # Sólo las de la empresa consultada (emula la RLS).
        return [r for r in self._resumenes if r.empresa_id == empresa_id]
