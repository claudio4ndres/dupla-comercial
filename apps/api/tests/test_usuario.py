"""Endpoint del usuario actual (GET /usuario, PATCH /usuario/onboarding-visto).

El front lee `onboarding_visto` tras el login para decidir si muestra el slider de
bienvenida (una sola vez por usuario) y lo marca al terminarlo. El usuario sale del
`sub` del JWT; el flag vive en la tabla `usuarios` y se lee/escribe con service role.

Cero red: el resolvedor (acceso a `usuarios`) se mockea; los tokens se firman aquí
con un secreto de prueba (HS256), igual que en test_auth_empresa.
"""
from uuid import UUID

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import obtener_settings
from app.dependencias import obtener_resolvedor_empresa
from app.rutas.usuario import router as router_usuario

SECRETO = "secreto-supabase-de-prueba-muy-largo-para-hs256-0123456789"
USUARIO = "0000a1a1-0000-4000-8000-000000000001"


class _ResolvedorFake:
    """Lee/escribe el flag onboarding_visto en un mapa en memoria (sin red)."""

    def __init__(self, flags: dict[str, bool]):
        self._flags = flags

    async def onboarding_visto_de(self, user_id):
        return self._flags.get(str(user_id), False)

    async def marcar_onboarding_visto(self, user_id):
        self._flags[str(user_id)] = True


@pytest.fixture
def fake():
    return _ResolvedorFake({USUARIO: False})


@pytest.fixture
def cliente(monkeypatch, fake):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRETO)
    obtener_settings.cache_clear()
    app = FastAPI()
    app.include_router(router_usuario)
    app.dependency_overrides[obtener_resolvedor_empresa] = lambda: fake
    return TestClient(app)


def _auth(sub: str = USUARIO) -> dict:
    token = jwt.encode({"sub": sub, "aud": "authenticated"}, SECRETO, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_get_usuario_devuelve_onboarding_visto_false(cliente):
    r = cliente.get("/usuario", headers=_auth())
    assert r.status_code == 200
    assert r.json() == {"onboarding_visto": False}


def test_patch_marca_onboarding_visto_y_persiste(cliente):
    r = cliente.patch("/usuario/onboarding-visto", headers=_auth())
    assert r.status_code == 200
    assert r.json() == {"onboarding_visto": True}
    # Una segunda lectura ya lo refleja (quedó persistido en el resolvedor).
    assert cliente.get("/usuario", headers=_auth()).json() == {"onboarding_visto": True}


def test_get_usuario_sin_token_es_401(cliente):
    assert cliente.get("/usuario").status_code == 401
