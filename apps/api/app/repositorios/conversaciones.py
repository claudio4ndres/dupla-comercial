"""Repositorio de la conversación del chat con Javo (T13): interfaz + doble en
memoria para tests.

Persiste el hilo `solicitud → conversacion → mensajes` para que el chat sobreviva
a un refresh de la página (hoy el endpoint `responder` es sin estado). El `rol` de
cada mensaje usa el vocabulario del front (`usuario`/`javo`/`sistema`); el mapeo a
los valores que admite la base (`usuario`/`asistente`/`sistema`) lo hace la
implementación real en `conversaciones_supabase.py`, no este doble.
"""
from datetime import datetime, timedelta, timezone
from itertools import count
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel


class MensajeGuardado(BaseModel):
    """Un mensaje persistido del hilo (tabla `mensajes`).

    `rol` está en el vocabulario del front (`usuario`/`javo`/`sistema`). `creado_en`
    sirve para ordenar el hilo cronológicamente.
    """

    rol: str
    contenido: str
    creado_en: datetime


class RepositorioConversaciones(Protocol):
    async def obtener_mensajes(
        self, solicitud_id: UUID, empresa_id: UUID
    ) -> list[MensajeGuardado]: ...

    async def guardar_turnos(
        self,
        solicitud_id: UUID,
        empresa_id: UUID,
        tipo: str,
        nuevos: list[dict],
    ) -> None: ...

    async def obtener_o_crear_conversacion(
        self, solicitud_id: UUID, empresa_id: UUID, tipo: str
    ) -> UUID: ...


class RepositorioConversacionesEnMemoria:
    """Doble en memoria para tests. Emula el aislamiento por empresa de la RLS:
    sólo entrega/acepta mensajes de la conversación de la empresa consultada."""

    def __init__(self) -> None:
        # clave (empresa_id, solicitud_id) → lista de mensajes en orden de llegada.
        self._por_clave: dict[tuple[UUID, UUID], list[MensajeGuardado]] = {}
        # Secuencia monótona para fijar `creado_en` estrictamente creciente: así dos
        # mensajes guardados en el mismo instante conservan su orden de inserción.
        self._secuencia = count()
        # Id de la conversación por (empresa, solicitud) — find-or-create en memoria.
        self._ids: dict[tuple[UUID, UUID], UUID] = {}

    async def obtener_mensajes(
        self, solicitud_id: UUID, empresa_id: UUID
    ) -> list[MensajeGuardado]:
        mensajes = self._por_clave.get((empresa_id, solicitud_id), [])
        # Orden cronológico estable (emula `order=creado_en` de PostgREST).
        return sorted(mensajes, key=lambda m: m.creado_en)

    async def obtener_o_crear_conversacion(
        self, solicitud_id: UUID, empresa_id: UUID, tipo: str
    ) -> UUID:
        clave = (empresa_id, solicitud_id)
        if clave not in self._ids:
            self._ids[clave] = uuid4()
        return self._ids[clave]

    async def guardar_turnos(
        self,
        solicitud_id: UUID,
        empresa_id: UUID,
        tipo: str,
        nuevos: list[dict],
    ) -> None:
        hilo = self._por_clave.setdefault((empresa_id, solicitud_id), [])
        base = datetime.now(timezone.utc)
        for n in nuevos:
            hilo.append(
                MensajeGuardado(
                    rol=n["rol"],
                    contenido=n["contenido"],
                    # `creado_en` estrictamente creciente vía la secuencia (no por el
                    # reloj de pared), para que el orden de inserción sea determinista.
                    creado_en=n.get("creado_en")
                    or base + timedelta(microseconds=next(self._secuencia)),
                )
            )
