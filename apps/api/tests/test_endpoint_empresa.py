"""Test del endpoint GET /empresa: devuelve la empresa REAL (tenant) del usuario
—nombre, color de marca, plan— para que el front pinte el header del tenant correcto
(no el mock hardcodeado). Cero red: el resolvedor de empresa se inyecta con un doble
vía app.dependency_overrides (CA: nada de Supabase real)."""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import obtener_empresa_actual, obtener_resolvedor_empresa
from app.esquemas import EmpresaActual
from app.main import app

EMPRESA = uuid4()


class ResolvedorFake:
    """Doble del resolvedor: `datos_de(empresa_id)` devuelve la empresa (o None)."""

    def __init__(self, datos):
        self._datos = datos

    async def datos_de(self, empresa_id):
        return self._datos


def teardown_function():
    app.dependency_overrides.clear()


def _http(*, empresa_id=EMPRESA, datos=None):
    app.dependency_overrides[obtener_empresa_actual] = lambda: empresa_id
    app.dependency_overrides[obtener_resolvedor_empresa] = lambda: ResolvedorFake(datos)
    return TestClient(app)


def test_empresa_devuelve_el_tenant_del_usuario():
    # El header del front debe mostrar la empresa REAL del usuario, no un mock.
    datos = EmpresaActual(
        id=str(EMPRESA), nombre="RukkumansLabs", color_marca="#F04E37", plan="operador"
    )
    http = _http(datos=datos)

    r = http.get("/empresa")

    assert r.status_code == 200
    assert r.json() == {
        "id": str(EMPRESA),
        "nombre": "RukkumansLabs",
        "color_marca": "#F04E37",
        "plan": "operador",
    }


def test_empresa_inexistente_devuelve_404():
    # Si la empresa resuelta no existe en la tabla, 404 (no inventa datos).
    http = _http(datos=None)

    r = http.get("/empresa")

    assert r.status_code == 404
