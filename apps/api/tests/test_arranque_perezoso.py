"""Regresión de arranque: montar la app NO debe importar el SDK de Anthropic.

`anthropic` arrastra ~1800 módulos de tipos; su import en frío llegó a tardar
>60 s en algunas máquinas y colgaba CADA arranque del backend (uvicorn), aunque
la demo ni siquiera use el chat de Javo. El cliente real se construye con import
PEREZOSO dentro de `obtener_cliente_anthropic`, así que importar `app.main` (lo
que hace uvicorn al arrancar) debe quedar libre de `anthropic`.

Se corre en un SUBPROCESO limpio para tener un `sys.modules` sin contaminar por
otros tests que sí importan `anthropic` (p. ej. `test_cliente_anthropic`).
"""
import os
import subprocess
import sys

# apps/api (raíz importable donde vive el paquete `app`).
API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_montar_la_app_no_importa_anthropic():
    codigo = (
        "import sys, app.main; "
        "assert 'anthropic' not in sys.modules, "
        "'app.main importó anthropic al arrancar; debe ser perezoso'; "
        "print('OK sin anthropic')"
    )
    res = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=API_DIR,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"stdout={res.stdout!r} stderr={res.stderr!r}"
    assert "OK sin anthropic" in res.stdout
