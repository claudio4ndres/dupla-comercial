"""Repositorio de solicitudes: interfaz + implementación en memoria para tests.

La implementación real con Supabase (que respeta la RLS usando el JWT del usuario)
se hará en una tarea de integración aparte, con su propio test.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.servicios.gmail import MensajeCorreo


class Solicitud(BaseModel):
    """Representación de una fila de la tabla `solicitudes`."""

    id: UUID
    empresa_id: UUID
    remitente: str = ""
    correo_origen: str | None = None
    asunto: str = ""
    cuerpo: str
    resumen: str | None = None
    tipo: str = "sin_clasificar"
    estado: str = "nueva"
    gmail_msg_id: str | None = None
    # Fecha/hora de recepción (columna `creado_en timestamptz` de la tabla). El doble
    # en memoria puede dejarla en None; PostgREST la entrega como ISO y pydantic la
    # parsea. El endpoint la expone al front como `recibido_en`.
    creado_en: datetime | None = None


class RepositorioSolicitudes(Protocol):
    async def obtener(
        self, solicitud_id: UUID, empresa_id: UUID
    ) -> Solicitud | None: ...

    async def guardar_clasificacion(
        self, solicitud_id: UUID, empresa_id: UUID, resumen: str, tipo: str
    ) -> Solicitud: ...

    async def crear_desde_correo(
        self,
        empresa_id: UUID,
        mensaje: "MensajeCorreo",
        *,
        resumen: str | None = None,
        tipo: str = "sin_clasificar",
    ) -> bool: ...

    async def listar(self, empresa_id: UUID) -> list[Solicitud]: ...

    async def listar_sin_clasificar(self, empresa_id: UUID) -> list[Solicitud]: ...

    async def actualizar_reproceso(
        self,
        solicitud_id: UUID,
        empresa_id: UUID,
        *,
        cuerpo: str,
        resumen: str | None,
        tipo: str,
        creado_en: datetime | None = None,
    ) -> Solicitud: ...


class RepositorioSolicitudesEnMemoria:
    """Implementación en memoria para tests. Emula el aislamiento por empresa de la
    RLS (filtra por `empresa_id`) y no cambia `estado` al clasificar."""

    def __init__(self, solicitudes: list[Solicitud] | None = None):
        self._por_id: dict[UUID, Solicitud] = {s.id: s for s in (solicitudes or [])}
        # Emula el índice único parcial (empresa_id, gmail_msg_id): las solicitudes
        # ya ingeridas no se vuelven a crear (idempotencia, CA4).
        self._gmail_vistos: set[tuple[UUID, str]] = {
            (s.empresa_id, s.gmail_msg_id)
            for s in (solicitudes or [])
            if s.gmail_msg_id
        }

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

    async def crear_desde_correo(
        self,
        empresa_id: UUID,
        mensaje: "MensajeCorreo",
        *,
        resumen: str | None = None,
        tipo: str = "sin_clasificar",
    ) -> bool:
        """Crea una `solicitud` (`nueva`) a partir de un correo, con el `resumen` y
        `tipo` que entregó el clasificador (si lo hubo; si no, `sin_clasificar`).

        Devuelve True si la creó, False si el mensaje ya estaba ingerido (mismo
        `gmail_msg_id` en la misma empresa): así el poller cuenta solo las nuevas.
        """
        clave = (empresa_id, mensaje.gmail_msg_id)
        if clave in self._gmail_vistos:
            return False
        self._gmail_vistos.add(clave)
        solicitud = Solicitud(
            id=uuid4(),
            empresa_id=empresa_id,
            remitente=mensaje.remitente,
            correo_origen=mensaje.correo_origen,
            asunto=mensaje.asunto,
            cuerpo=mensaje.cuerpo,
            gmail_msg_id=mensaje.gmail_msg_id,
            resumen=resumen,
            tipo=tipo,
            estado="nueva",
            creado_en=mensaje.fecha,  # fecha REAL de recepción (para ordenar)
        )
        self._por_id[solicitud.id] = solicitud
        return True

    async def listar(self, empresa_id: UUID) -> list[Solicitud]:
        """Devuelve las solicitudes de UNA empresa (emula el filtro por RLS).

        Conserva el orden de inserción (las más nuevas al final): el front puede
        reordenar para mostrar; aquí no inventamos un criterio sin timestamp.
        """
        return [s for s in self._por_id.values() if s.empresa_id == empresa_id]

    async def listar_sin_clasificar(self, empresa_id: UUID) -> list[Solicitud]:
        """Las solicitudes de la empresa que quedaron 'sin_clasificar' (p. ej. correos
        ingeridos antes del fix, o un sync donde Haiku falló). El reproceso las re-baja
        y re-clasifica."""
        return [
            s
            for s in self._por_id.values()
            if s.empresa_id == empresa_id and s.tipo == "sin_clasificar"
        ]

    async def actualizar_reproceso(
        self,
        solicitud_id: UUID,
        empresa_id: UUID,
        *,
        cuerpo: str,
        resumen: str | None,
        tipo: str,
        creado_en: datetime | None = None,
    ) -> Solicitud:
        """Actualiza cuerpo + resumen + tipo (y la fecha real `creado_en` si se pasa)
        de una solicitud existente (reproceso), sin tocar su estado. El cuerpo y la
        fecha se actualizan al re-bajar el correo (recupera texto vacío y la fecha real
        de recepción, para ordenar bien la bandeja)."""
        solicitud = await self.obtener(solicitud_id, empresa_id)
        if solicitud is None:
            raise KeyError(solicitud_id)
        cambios = {"cuerpo": cuerpo, "resumen": resumen, "tipo": tipo}
        if creado_en is not None:
            cambios["creado_en"] = creado_en
        actualizada = solicitud.model_copy(update=cambios)
        self._por_id[solicitud_id] = actualizada
        return actualizada
