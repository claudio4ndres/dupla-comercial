"""T7b · Auth real: `obtener_empresa_actual` desde el JWT de Supabase.

Verifica el JWT (HS256 + secreto del proyecto Supabase) y extrae `empresa_id`
del claim. Cero red: los tokens se firman en el propio test con un secreto de
prueba (nunca se toca Supabase real).
"""
from uuid import UUID

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import obtener_settings
from app.dependencias import obtener_empresa_actual

# Secreto largo como los de Supabase (≥32 bytes para HS256).
SECRETO = "secreto-supabase-de-prueba-muy-largo-para-hs256-0123456789"
EMPRESA = "0000c0de-0000-4000-8000-000000000001"


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRETO)
    obtener_settings.cache_clear()
    app = FastAPI()

    @app.get("/quien-soy")
    def quien_soy(empresa_id: UUID = Depends(obtener_empresa_actual)):
        return {"empresa_id": str(empresa_id)}

    return TestClient(app)


def _token(claims: dict, secreto: str = SECRETO) -> str:
    return jwt.encode(claims, secreto, algorithm="HS256")


def test_jwt_valido_devuelve_empresa_id(cliente):
    token = _token({"empresa_id": EMPRESA, "aud": "authenticated"})
    r = cliente.get("/quien-soy", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["empresa_id"] == EMPRESA


def test_sin_token_es_401(cliente):
    r = cliente.get("/quien-soy")
    assert r.status_code == 401


def test_firma_invalida_es_401(cliente):
    # Token firmado con OTRO secreto → la verificación HS256 debe rechazarlo.
    token = _token(
        {"empresa_id": EMPRESA}, secreto="secreto-de-un-atacante-igual-de-largo-0123456789"
    )
    r = cliente.get("/quien-soy", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_sin_empresa_id_es_401(cliente):
    token = _token({"sub": "usuario-123", "aud": "authenticated"})
    r = cliente.get("/quien-soy", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
