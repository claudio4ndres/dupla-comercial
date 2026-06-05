"""TR2 · `AlmacenSecretos` real sobre Google Secret Manager, con el cliente de GCP
**mockeado** (cero red, cero credenciales reales).

El doble imita la API del `SecretManagerServiceAsyncClient`: `create_secret`,
`add_secret_version`, `access_secret_version`, `delete_secret`. Verificamos el
round-trip (guardar→obtener), que `guardar` tolera que el secreto ya exista
(agrega una versión nueva), que `obtener` de algo inexistente da `None` y que
`borrar` elimina el secreto. El refresh token NUNCA viaja al front: se persiste
sólo el `token_ref` (la ruta del secreto).
"""
import pytest

from app.servicios.secretos import AlmacenSecretosSecretManager

PROYECTO = "dupla-comercial-pruebas"


class _YaExiste(Exception):
    """Imita `google.api_core.exceptions.AlreadyExists` (detectado por nombre)."""


_YaExiste.__name__ = "AlreadyExists"


class _NoEncontrado(Exception):
    """Imita `google.api_core.exceptions.NotFound` (detectado por nombre)."""


_NoEncontrado.__name__ = "NotFound"


class _Payload:
    def __init__(self, data: bytes):
        self.data = data


class _RespuestaVersion:
    def __init__(self, data: bytes):
        self.payload = _Payload(data)


class FakeSecretManager:
    """Doble del cliente de GCP Secret Manager. Guarda en memoria y registra las
    llamadas para poder afirmarlas."""

    def __init__(self):
        self.secretos: dict[str, list[bytes]] = {}
        self.creados: list[str] = []
        self.borrados: list[str] = []

    @staticmethod
    def _nombre(ruta: str) -> str:
        # de "projects/<p>/secrets/<nombre>[/versions/...]" saca "<nombre>"
        return ruta.split("/secrets/")[1].split("/versions/")[0]

    async def create_secret(self, request):
        nombre = request["secret_id"]
        if nombre in self.secretos:
            raise _YaExiste()
        self.secretos[nombre] = []
        self.creados.append(nombre)

    async def add_secret_version(self, request):
        nombre = self._nombre(request["parent"])
        self.secretos.setdefault(nombre, []).append(request["payload"]["data"])

    async def access_secret_version(self, request):
        nombre = self._nombre(request["name"])
        versiones = self.secretos.get(nombre)
        if not versiones:
            raise _NoEncontrado()
        return _RespuestaVersion(versiones[-1])

    async def delete_secret(self, request):
        nombre = self._nombre(request["name"])
        self.borrados.append(nombre)
        self.secretos.pop(nombre, None)


def _almacen() -> tuple[AlmacenSecretosSecretManager, FakeSecretManager]:
    fake = FakeSecretManager()
    return AlmacenSecretosSecretManager(PROYECTO, cliente=fake), fake


async def test_guardar_crea_secreto_agrega_version_y_devuelve_token_ref():
    almacen, fake = _almacen()

    ref = await almacen.guardar("gmail-empresa-a", "refresh-secreto")

    assert ref == f"projects/{PROYECTO}/secrets/gmail-empresa-a"
    assert "gmail-empresa-a" in fake.creados
    assert fake.secretos["gmail-empresa-a"] == [b"refresh-secreto"]


async def test_guardar_tolera_secreto_existente_y_agrega_otra_version():
    almacen, fake = _almacen()

    await almacen.guardar("gmail-empresa-a", "v1")
    ref = await almacen.guardar("gmail-empresa-a", "v2")  # ya existe → no revienta

    assert ref == f"projects/{PROYECTO}/secrets/gmail-empresa-a"
    assert fake.creados.count("gmail-empresa-a") == 1  # sólo se creó una vez
    assert fake.secretos["gmail-empresa-a"] == [b"v1", b"v2"]


async def test_obtener_round_trip_devuelve_el_valor():
    almacen, _ = _almacen()

    ref = await almacen.guardar("gmail-empresa-a", "refresh-secreto")
    valor = await almacen.obtener(ref)

    assert valor == "refresh-secreto"


async def test_obtener_inexistente_devuelve_none():
    almacen, _ = _almacen()

    valor = await almacen.obtener(f"projects/{PROYECTO}/secrets/no-existe")

    assert valor is None


async def test_borrar_elimina_el_secreto():
    almacen, fake = _almacen()
    ref = await almacen.guardar("gmail-empresa-a", "refresh-secreto")

    await almacen.borrar(ref)

    assert "gmail-empresa-a" in fake.borrados
    assert await almacen.obtener(ref) is None


async def test_borrar_inexistente_no_revienta():
    almacen, _ = _almacen()
    # Borrar algo que no existe es idempotente (NotFound se traga).
    await almacen.borrar(f"projects/{PROYECTO}/secrets/no-existe")


def test_construye_sin_cliente_no_importa_gcp_hasta_usarlo():
    # Construir sin inyectar cliente NO debe tocar la red ni requerir el paquete
    # de GCP (import perezoso): sólo guarda el project id.
    almacen = AlmacenSecretosSecretManager(PROYECTO)
    assert almacen is not None
