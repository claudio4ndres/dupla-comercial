"""T2 (Spec 009) · `obtener_cliente_clickup` resuelve el token PER-EMPRESA (CA3/CA4).

EL FIX DEL LEAK: la dependencia deja de usar el `CLICKUP_API_TOKEN` global y resuelve
el token de la integración `clickup` de la empresa del request (token_ref →
`AlmacenSecretos`). Sin integración clickup → `ClienteClickUp("")` (`tiene_token=False`),
y `/clickup/listas` cae a `[]`. El token de A JAMÁS se usa para B.

Cero red, cero ClickUp real: dobles en memoria del repo y del almacén de secretos.
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_almacen_secretos,
    obtener_cliente_clickup,
    obtener_empresa_actual,
    obtener_repositorio_integraciones,
)
from app.main import app
from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.servicios.clickup_real import ClienteClickUp
from app.servicios.secretos import AlmacenSecretosEnMemoria

EMPRESA_A = uuid4()
EMPRESA_B = uuid4()


def teardown_function():
    app.dependency_overrides.clear()


async def _cliente_para(empresa_id, repo, secretos):
    """Llama a la dependencia REAL con dobles (resuelve el cliente como en prod)."""
    return await obtener_cliente_clickup(
        empresa_id=empresa_id, repo=repo, secretos=secretos
    )


async def test_resuelve_el_token_de_la_integracion_clickup_de_la_empresa():
    secretos = AlmacenSecretosEnMemoria()
    token_ref = await secretos.guardar(f"clickup-token-{EMPRESA_A}", "tok-de-A")
    repo = RepositorioIntegracionesEnMemoria(
        [
            Integracion(
                id=uuid4(),
                empresa_id=EMPRESA_A,
                proveedor="clickup",
                token_ref=token_ref,
            )
        ]
    )

    cliente = await _cliente_para(EMPRESA_A, repo, secretos)

    assert isinstance(cliente, ClienteClickUp)
    assert cliente.tiene_token is True
    # El token resuelto es EXACTAMENTE el de A (no el global, no el de otra empresa).
    assert cliente._token == "tok-de-A"


async def test_sin_integracion_clickup_cliente_sin_token():
    # Empresa que nunca conectó clickup (aunque tenga gmail): tiene_token=False.
    secretos = AlmacenSecretosEnMemoria()
    repo = RepositorioIntegracionesEnMemoria(
        [Integracion(id=uuid4(), empresa_id=EMPRESA_A, proveedor="gmail",
                     token_ref="secreto://gmail-A")]
    )

    cliente = await _cliente_para(EMPRESA_A, repo, secretos)

    assert cliente.tiene_token is False


async def test_no_usa_el_token_de_otra_empresa():
    # CA4: A tiene clickup; B no. Resolver para B JAMÁS devuelve el token de A.
    secretos = AlmacenSecretosEnMemoria()
    ref_a = await secretos.guardar(f"clickup-token-{EMPRESA_A}", "tok-de-A")
    repo = RepositorioIntegracionesEnMemoria(
        [Integracion(id=uuid4(), empresa_id=EMPRESA_A, proveedor="clickup",
                     token_ref=ref_a)]
    )

    cliente_b = await _cliente_para(EMPRESA_B, repo, secretos)

    assert cliente_b.tiene_token is False
    assert cliente_b._token != "tok-de-A"


def test_listas_sin_integracion_clickup_devuelve_vacio_end_to_end():
    # CA3 de punta a punta: por la dependencia REAL, una empresa sin clickup obtiene
    # un cliente sin token y `/clickup/listas` responde [] (sin llamar a ClickUp).
    secretos = AlmacenSecretosEnMemoria()
    repo = RepositorioIntegracionesEnMemoria([])  # ninguna integración

    app.dependency_overrides[obtener_repositorio_integraciones] = lambda: repo
    app.dependency_overrides[obtener_almacen_secretos] = lambda: secretos
    app.dependency_overrides[obtener_empresa_actual] = lambda: EMPRESA_A
    http = TestClient(app)

    r = http.get("/clickup/listas")

    assert r.status_code == 200
    assert r.json() == []
