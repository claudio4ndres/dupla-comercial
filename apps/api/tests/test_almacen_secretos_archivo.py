"""Almacén de secretos para DESARROLLO LOCAL sobre archivo JSON (sustituye a GCP
Secret Manager cuando no hay nube). Verifica el contrato `AlmacenSecretos`:

* `guardar` devuelve un `token_ref` y persiste el valor;
* sobrevive a "reiniciar el backend" (otra instancia lee lo guardado en disco) —
  por eso el poller puede reusar el refresh token tras un restart;
* `obtener` de algo inexistente da `None`;
* `borrar` elimina y es idempotente;
* `guardar` dos veces actualiza el valor.

El refresh token vive sólo en el archivo del backend (regla de oro #3): jamás
sale al front. Se usa `tmp_path` para no ensuciar el disco real.
"""
from pathlib import Path

from app.servicios.secretos import AlmacenSecretosArchivo


def _almacen(tmp_path: Path) -> AlmacenSecretosArchivo:
    return AlmacenSecretosArchivo(tmp_path / ".secretos.local.json")


async def test_guardar_devuelve_token_ref_y_persiste(tmp_path):
    almacen = _almacen(tmp_path)

    ref = await almacen.guardar("gmail-refresh-empresa-a", "refresh-secreto")

    assert ref == "secreto://gmail-refresh-empresa-a"
    assert await almacen.obtener(ref) == "refresh-secreto"


async def test_sobrevive_reinicio_otra_instancia_lee_lo_guardado(tmp_path):
    ruta = tmp_path / ".secretos.local.json"

    ref = await AlmacenSecretosArchivo(ruta).guardar("gmail-refresh-a", "tok")
    # Nueva instancia = simula reiniciar el backend: el valor sigue en disco.
    valor = await AlmacenSecretosArchivo(ruta).obtener(ref)

    assert valor == "tok"


async def test_obtener_inexistente_devuelve_none(tmp_path):
    assert await _almacen(tmp_path).obtener("secreto://no-existe") is None


async def test_borrar_elimina_y_es_idempotente(tmp_path):
    almacen = _almacen(tmp_path)
    ref = await almacen.guardar("gmail-refresh-a", "tok")

    await almacen.borrar(ref)
    assert await almacen.obtener(ref) is None

    await almacen.borrar(ref)  # idempotente: borrar de nuevo no revienta


async def test_guardar_dos_veces_actualiza_el_valor(tmp_path):
    almacen = _almacen(tmp_path)

    await almacen.guardar("gmail-refresh-a", "v1")
    ref = await almacen.guardar("gmail-refresh-a", "v2")

    assert await almacen.obtener(ref) == "v2"
