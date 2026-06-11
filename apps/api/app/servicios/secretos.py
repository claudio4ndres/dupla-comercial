"""Almacén de secretos (refresh tokens de los usuarios).

La interfaz es inyectable: en producción la implementa Google Secret Manager (TR2),
en tests una versión en memoria. El backend guarda el secreto y persiste sólo un
`token_ref` (referencia) en la tabla `integraciones`; el token en claro NUNCA sale
de aquí hacia el front (CA5).
"""
import json
import logging
from pathlib import Path
from typing import Protocol

_LOG = logging.getLogger(__name__)


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


class AlmacenSecretosArchivo:
    """Almacén de secretos para DESARROLLO LOCAL: persiste `token_ref -> valor` en un
    archivo JSON local (gitignored). Reemplaza a Secret Manager cuando no hay nube,
    sin exigir el paquete `google` ni credenciales de GCP.

    A diferencia del de memoria, SOBREVIVE a reinicios del backend: el refresh token
    queda en disco, así el poller lo reusa tras un restart. El archivo vive sólo en el
    backend (regla de oro #3); jamás sale al front. NO usar en producción (allí va
    `AlmacenSecretosSecretManager`).
    """

    def __init__(self, ruta: str | Path) -> None:
        self._ruta = Path(ruta)

    def _leer(self) -> dict[str, str]:
        if not self._ruta.exists():
            return {}
        try:
            return json.loads(self._ruta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _escribir(self, datos: dict[str, str]) -> None:
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._ruta.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def guardar(self, nombre: str, valor: str) -> str:
        token_ref = f"secreto://{nombre}"
        datos = self._leer()
        datos[token_ref] = valor
        self._escribir(datos)
        return token_ref

    async def obtener(self, token_ref: str) -> str | None:
        # Conveniencia para el poller/uso interno; el front nunca llega hasta aquí.
        return self._leer().get(token_ref)

    async def borrar(self, token_ref: str) -> None:
        datos = self._leer()
        if datos.pop(token_ref, None) is not None:
            self._escribir(datos)


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
            # NotFound = el secreto no existe; InvalidArgument = el token_ref no es una
            # ruta válida de Secret Manager (p. ej. quedó un ref del backend 'archivo'
            # tras migrar a gcp). Ambos significan "no hay token usable" → None, así el
            # cliente Gmail marca 'reconectar' en vez de tumbar el poller con un 500.
            if type(exc).__name__ in ("NotFound", "InvalidArgument"):
                _LOG.warning(
                    "Secret Manager: token_ref inusable (%s); se trata como no conectado.",
                    type(exc).__name__,
                )
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
