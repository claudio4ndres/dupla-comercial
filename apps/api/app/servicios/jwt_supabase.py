"""Verificación del JWT de Supabase (login real).

Supabase (local nuevo y producción) firma los tokens de sesión con **claves
asimétricas (ES256)** y publica la pública en un JWKS (`/auth/v1/.well-known/
jwks.json`). El secreto compartido HS256 queda como legado (lo usa el JWT de
desarrollo). Este verificador soporta ambos:

  - ES256/RS256 → valida contra la clave pública del JWKS.
  - HS256       → valida con el secreto compartido.

El `PyJWKClient` se cachea por URL (el JWKS se baja una vez). En tests se inyecta un
cliente JWK doble: cero red, cero claves reales.
"""
from functools import lru_cache

import jwt
from jwt import PyJWKClient


@lru_cache
def _jwk_client_para(jwks_url: str) -> PyJWKClient:
    """PyJWKClient cacheado por URL: baja el JWPS una vez y reutiliza las claves."""
    return PyJWKClient(jwks_url)


class VerificadorJwtSupabase:
    """Verifica un JWT de Supabase (ES256 vía JWKS, o HS256 con el secreto)."""

    def __init__(self, supabase_url: str, jwt_secret: str, *, jwk_client=None):
        self._jwks_url = supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        self._secret = jwt_secret
        self._jwk_client = jwk_client  # inyectable para tests

    def _cliente_jwk(self):
        return self._jwk_client or _jwk_client_para(self._jwks_url)

    def verificar(self, token: str) -> dict:
        """Devuelve los claims si el token es válido; lanza `jwt.PyJWTError` si no."""
        alg = jwt.get_unverified_header(token).get("alg", "")
        if alg.startswith(("ES", "RS", "PS", "Ed")):
            clave = self._cliente_jwk().get_signing_key_from_jwt(token).key
            return jwt.decode(
                token, clave, algorithms=[alg], options={"verify_aud": False}
            )
        # HS256: secreto compartido (JWT de desarrollo / legado).
        return jwt.decode(
            token, self._secret, algorithms=["HS256"], options={"verify_aud": False}
        )
