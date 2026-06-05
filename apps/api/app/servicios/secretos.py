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


class AlmacenSecretosSecretManager:
    """TR2 · Implementación real sobre Google Secret Manager.

    Cada refresh token vive como un *secret* (`projects/<proj>/secrets/<nombre>`)
    con una *version* por cada valor guardado. El `token_ref` que persistimos en
    `integraciones` es la ruta del secreto (jamás el valor en claro — CA5).

    El cliente de GCP se inyecta (en tests, un doble; en prod, el
    `SecretManagerServiceAsyncClient`, importado de forma perezosa para no exigir
    el paquete ni credenciales en CI). Detectamos `AlreadyExists`/`NotFound` por el
    nombre de la clase para no acoplarnos a `google.api_core.exceptions`.
    """

    def __init__(self, project_id: str, *, cliente=None) -> None:
        self._project = project_id
        self._cliente = cliente

    def _gcp(self):
        if self._cliente is None:
            # Import perezoso: sólo se necesita en producción.
            from google.cloud import secretmanager

            self._cliente = secretmanager.SecretManagerServiceAsyncClient()
        return self._cliente

    def _ref(self, nombre: str) -> str:
        return f"projects/{self._project}/secrets/{nombre}"

    async def guardar(self, nombre: str, valor: str) -> str:
        cliente = self._gcp()
        try:
            await cliente.create_secret(
                request={
                    "parent": f"projects/{self._project}",
                    "secret_id": nombre,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
        except Exception as exc:  # noqa: BLE001 — re-lanzamos si no es AlreadyExists
            if type(exc).__name__ != "AlreadyExists":
                raise
        await cliente.add_secret_version(
            request={
                "parent": self._ref(nombre),
                "payload": {"data": valor.encode("utf-8")},
            }
        )
        return self._ref(nombre)

    async def obtener(self, token_ref: str) -> str | None:
        cliente = self._gcp()
        try:
            resp = await cliente.access_secret_version(
                request={"name": f"{token_ref}/versions/latest"}
            )
        except Exception as exc:  # noqa: BLE001
            if type(exc).__name__ == "NotFound":
                return None
            raise
        return resp.payload.data.decode("utf-8")

    async def borrar(self, token_ref: str) -> None:
        cliente = self._gcp()
        try:
            await cliente.delete_secret(request={"name": token_ref})
        except Exception as exc:  # noqa: BLE001 — idempotente si ya no está
            if type(exc).__name__ != "NotFound":
                raise
