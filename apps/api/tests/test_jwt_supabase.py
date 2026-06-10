"""Login real · `VerificadorJwtSupabase`.

Supabase (local y prod nuevo) firma los JWT de sesión con claves **asimétricas
(ES256)** y publica la pública en un JWKS. El verificador valida ES256 contra el
JWKS y HS256 con el secreto compartido (JWT dev/legacy). Cero red: el cliente JWK
se inyecta; las claves se generan en el test.
"""
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.servicios.jwt_supabase import VerificadorJwtSupabase

SECRETO = "secreto-supabase-de-prueba-muy-largo-para-hs256-0123456789"
URL = "http://127.0.0.1:54321"


class _JwkClientFake:
    """Doble de PyJWKClient: devuelve siempre la clave pública dada (sin red)."""

    def __init__(self, public_key):
        self._key = public_key

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=self._key)


def _verificador(jwk_client=None):
    return VerificadorJwtSupabase(URL, SECRETO, jwk_client=jwk_client)


def test_verifica_hs256_con_el_secreto():
    token = jwt.encode({"sub": "a1", "aud": "authenticated"}, SECRETO, algorithm="HS256")
    claims = _verificador().verificar(token)
    assert claims["sub"] == "a1"


def test_hs256_secreto_incorrecto_lanza():
    token = jwt.encode(
        {"sub": "a1"}, "otro-secreto-largo-de-atacante-0123456789-abcd", algorithm="HS256"
    )
    with pytest.raises(jwt.PyJWTError):
        _verificador().verificar(token)


def test_verifica_es256_via_jwks():
    priv = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode({"sub": "a1", "aud": "authenticated"}, priv, algorithm="ES256")

    claims = _verificador(jwk_client=_JwkClientFake(priv.public_key())).verificar(token)

    assert claims["sub"] == "a1"


def test_es256_firmado_con_otra_clave_lanza():
    priv = ec.generate_private_key(ec.SECP256R1())
    otra = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode({"sub": "a1"}, priv, algorithm="ES256")

    with pytest.raises(jwt.PyJWTError):
        _verificador(jwk_client=_JwkClientFake(otra.public_key())).verificar(token)
