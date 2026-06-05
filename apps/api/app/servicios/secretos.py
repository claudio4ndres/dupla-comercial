"""Almacén de secretos (refresh tokens de los usuarios).

La interfaz es inyectable: en producción la implementa Google Secret Manager (TR2),
en tests una versión en memoria. El backend guarda el secreto y persiste sólo un
`token_ref` (referencia) en la tabla `integraciones`; el token en claro NUNCA sale
de aquí hacia el front (CA5).
"""
from typing import Protocol


class AlmacenSecretos(Protocol):
    async def guardar(self, nombre: str, valor: str) -> str: ...
    async def borrar(self, token_ref: str) -> None: ...


class AlmacenSecretosEnMemoria:
    """Guarda `token_ref -> valor`. `guardar` devuelve el `token_ref` que se persiste
    en `integraciones` (jamás el valor en claro)."""

    def __init__(self) -> None:
        self._por_ref: dict[str, str] = {}

    async def guardar(self, nombre: str, valor: str) -> str:
        token_ref = f"secreto://{nombre}"
        self._por_ref[token_ref] = valor
        return token_ref

    async def obtener(self, token_ref: str) -> str | None:
        # Conveniencia para tests/uso interno; el front nunca llega hasta aquí.
        return self._por_ref.get(token_ref)

    async def borrar(self, token_ref: str) -> None:
        self._por_ref.pop(token_ref, None)
