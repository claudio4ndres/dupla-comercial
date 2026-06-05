"""Tests del endpoint GET /integraciones/correo/gmail/callback (T8).

Cierra el flujo OAuth: valida el `state`, canjea el `code` (cliente OAuth MOCKEADO,
cero red — CA6), guarda el refresh token en el `AlmacenSecretos` y persiste la
integración (`estado='conectado'`), redirigiendo 302 al front. La respuesta NUNCA
expone tokens (CA5). `state` inválido → 400 (anti-CSRF).
"""
import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencias import (
    obtener_almacen_estado_oauth,
    obtener_almacen_secretos,
    obtener_cliente_oauth_google,
    obtener_config_oauth_gmail,
    obtener_repositorio_integraciones_servicio,
)
from app.main import app
from app.repositorios.estado_oauth import AlmacenEstadoOAuthEnMemoria
from app.repositorios.integraciones import RepositorioIntegracionesEnMemoria
from app.servicios.oauth_gmail import ConfigOAuthGmail, CredencialesGmail
from app.servicios.secretos import AlmacenSecretosEnMemoria
from tests.dobles import ClienteOAuthGoogleFake

EMPRESA_A = uuid4()


def _cliente_http(estado, oauth, secretos, repo):
    config = ConfigOAuthGmail(
        client_id="cid-de-prueba",
        redirect_uri="https://app.de-prueba/integraciones/correo/gmail/callback",
        url_post_conexion="https://app.de-prueba/bandeja",
    )
    app.dependency_overrides[obtener_config_oauth_gmail] = lambda: config
    app.dependency_overrides[obtener_almacen_estado_oauth] = lambda: estado
    app.dependency_overrides[obtener_cliente_oauth_google] = lambda: oauth
    app.dependency_overrides[obtener_almacen_secretos] = lambda: secretos
    app.dependency_overrides[obtener_repositorio_integraciones_servicio] = lambda: repo
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_callback_persiste_integracion_y_redirige_sin_exponer_tokens():
    # CA5/CA6: con OAuth mockeado, persiste la integración conectada y redirige 302
    # SIN que el refresh token salga por el cuerpo ni los headers.
    estado = AlmacenEstadoOAuthEnMemoria()
    asyncio.run(estado.guardar("state-valido", EMPRESA_A))
    oauth = ClienteOAuthGoogleFake(
        CredencialesGmail(
            refresh_token="refresh-super-secreto", casilla="hola@capsulab.cl"
        )
    )
    secretos = AlmacenSecretosEnMemoria()
    repo = RepositorioIntegracionesEnMemoria([])
    http = _cliente_http(estado, oauth, secretos, repo)

    r = http.get(
        "/integraciones/correo/gmail/callback?code=cod-123&state=state-valido",
        follow_redirects=False,
    )

    assert r.status_code == 302
    # CA5: ni en el cuerpo ni en los headers (incluido Location) viaja el token.
    assert "refresh-super-secreto" not in r.text
    assert "refresh-super-secreto" not in str(r.headers)

    # Persistió la integración conectada para la empresa ligada al state.
    integ = asyncio.run(repo.obtener_por_empresa(EMPRESA_A))
    assert integ is not None
    assert integ.proveedor == "gmail"
    assert integ.estado == "conectado"
    assert integ.casilla == "hola@capsulab.cl"
    # El token_ref es una referencia al secreto, NO el token en claro (CA5).
    assert "refresh-super-secreto" not in integ.token_ref

    # El `code` se canjeó vía el cliente mockeado (cero red, CA6).
    assert oauth.codigos_canjeados == ["cod-123"]
    # Y el refresh quedó guardado en el almacén de secretos bajo ese token_ref.
    assert asyncio.run(secretos.obtener(integ.token_ref)) == "refresh-super-secreto"


def test_callback_con_state_invalido_devuelve_400_y_no_persiste():
    # Anti-CSRF: un `state` desconocido se rechaza con 400 antes de tocar OAuth.
    estado = AlmacenEstadoOAuthEnMemoria()  # vacío: ningún state válido
    oauth = ClienteOAuthGoogleFake()
    secretos = AlmacenSecretosEnMemoria()
    repo = RepositorioIntegracionesEnMemoria([])
    http = _cliente_http(estado, oauth, secretos, repo)

    r = http.get(
        "/integraciones/correo/gmail/callback?code=cod-123&state=desconocido",
        follow_redirects=False,
    )

    assert r.status_code == 400
    # No se canjeó nada ni se persistió integración alguna.
    assert oauth.codigos_canjeados == []
    assert asyncio.run(repo.obtener_por_empresa(EMPRESA_A)) is None
