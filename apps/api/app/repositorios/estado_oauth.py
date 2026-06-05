"""Almacén del `state` anti-CSRF del flujo OAuth de Gmail.

El `state` liga el inicio del consentimiento (T7) con su callback (T8): se genera al
iniciar, se guarda ligado a la empresa/sesión y se consume (una sola vez) al volver.
En memoria para los tests; la implementación real (Supabase/Redis con expiración) va
en la fase de cableado.
"""
from typing import Protocol
from uuid import UUID


class AlmacenEstadoOAuth(Protocol):
    async def guardar(self, state: str, empresa_id: UUID) -> None: ...
    async def consumir(self, state: str) -> UUID | None: ...


class AlmacenEstadoOAuthEnMemoria:
    """Guarda `state -> empresa_id`. `consumir` lo devuelve y lo borra: un solo uso,
    para que un mismo `state` no pueda reutilizarse (anti-replay)."""

    def __init__(self) -> None:
        self._por_state: dict[str, UUID] = {}

    async def guardar(self, state: str, empresa_id: UUID) -> None:
        self._por_state[state] = empresa_id

    async def consumir(self, state: str) -> UUID | None:
        return self._por_state.pop(state, None)
