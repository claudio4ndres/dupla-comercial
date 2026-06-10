"""Auth real: `obtener_empresa_actual` desde el JWT de Supabase.

Verifica el JWT (HS256 + secreto del proyecto) y resuelve la empresa por DOS vías:
  1) `empresa_id` en el claim (producción con custom access token hook, o JWT dev).
  2) si no viene el claim (login real SIN hook), por el `sub` contra la tabla
     `usuarios` (resolvedor inyectado, mockeado aquí).

Cero red: los tokens se firman en el propio test con un secreto de prueba y el
resolvedor se mockea (nunca se toca Supabase real).
"""
from uuid import UUID

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import obtener_settings
from app.dependencias import obtener_empresa_actual, obtener_resolvedor_empresa

SECRETO = "secreto-supabase-de-prueba-muy-largo-para-hs256-0123456789"
EMPRESA = "0000c0de-0000-4000-8000-000000000001"
USUARIO = "0000a1a1-0000-4000-8000-000000000001"  # auth.uid (sub del token)


class _ResolvedorFake:
    """Resuelve empresa por usuario desde un mapa en memoria (sin red)."""

    def __init__(self, mapa: dict[str, str]):
        self._mapa = mapa

    async def empresa_de(self, user_id):
        emp = self._mapa.get(str(user_id))
        return UUID(emp) if emp else None


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRETO)
    obtener_settings.cache_clear()
    app = FastAPI()

    @app.get("/quien-soy")
    async def quien_soy(empresa_id: UUID = Depends(obtener_empresa_actual)):
        return {"empresa_id": str(empresa_id)}

    # El resolvedor (login real sin hook) se mockea: el usuario USUARIO → EMPRESA.
    app.dependency_overrides[obtener_resolvedor_empresa] = lambda: _ResolvedorFake(
        {USUARIO: EMPRESA}
    )
    return TestClient(app)


def _token(claims: dict, secreto: str = SECRETO) -> str:
    return jwt.encode(claims, secreto, algorithm="HS256")


def test_jwt_con_empresa_id_en_el_claim(cliente):
    # Producción con hook (o JWT dev): el empresa_id viene en el token.
    token = _token({"empresa_id": EMPRESA, "sub": USUARIO, "aud": "authenticated"})
    r = cliente.get("/quien-soy", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["empresa_id"] == EMPRESA


def test_resuelve_empresa_desde_usuarios_por_el_sub(cliente):
    # Login real SIN hook: el token no trae empresa_id; se resuelve por el `sub`
    # contra la tabla usuarios.
    token = _token({"sub": USUARIO, "aud": "authenticated"})
    r = cliente.get("/quien-soy", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["empresa_id"] == EMPRESA


def test_sub_sin_usuario_es_401(cliente):
    # Token válido pero el usuario no está en `usuarios` → no hay empresa → 401.
    token = _token({"sub": "0000dead-0000-4000-8000-000000000999", "aud": "authenticated"})
    r = cliente.get("/quien-soy", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_sin_token_es_401(cliente):
    assert cliente.get("/quien-soy").status_code == 401


def test_firma_invalida_es_401(cliente):
    # Token firmado con OTRO secreto → la verificación HS256 debe rechazarlo.
    token = _token({"sub": USUARIO}, secreto="secreto-de-un-atacante-igual-de-largo-0123456789")
    r = cliente.get("/quien-soy", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_sin_empresa_ni_sub_es_401(cliente):
    token = _token({"aud": "authenticated"})
    r = cliente.get("/quien-soy", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
