"""T7c · `RepositorioSolicitudesSupabase` contra PostgREST (sin red).

Usa un transporte httpx **mockeado**: verifica que el repo manda el JWT del
usuario (lo que dispara la RLS que aísla por empresa), pega al endpoint correcto
de PostgREST y mapea la respuesta a `Solicitud`. La prueba extremo-a-extremo de
aislamiento real (empresa A no ve lo de B) corre contra `supabase start` en el
entorno de integración, no en esta suite unitaria.
"""
from uuid import UUID, uuid4

import httpx
import pytest

from app.config import obtener_settings
from app.dependencias import obtener_repositorio_solicitudes
from app.repositorios.solicitudes_supabase import RepositorioSolicitudesSupabase
from app.servicios.gmail import MensajeCorreo

BASE = "https://proyecto.supabase.co"
ANON = "anon-key-de-prueba"
JWT = "jwt-del-usuario-empresa-a"
EMPRESA = UUID("0000c0de-0000-4000-8000-000000000001")


def _repo(handler):
    transporte = httpx.MockTransport(handler)
    cliente = httpx.AsyncClient(transport=transporte)
    return RepositorioSolicitudesSupabase(BASE, ANON, JWT, cliente=cliente)


async def test_obtener_manda_jwt_del_usuario_y_mapea_la_fila():
    sol_id = uuid4()
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["auth"] = req.headers.get("authorization")
        visto["apikey"] = req.headers.get("apikey")
        visto["url"] = str(req.url)
        return httpx.Response(
            200,
            json=[{
                "id": str(sol_id),
                "empresa_id": str(EMPRESA),
                "cuerpo": "quiero un sampling",
                "asunto": "Sampling",
                "tipo": "sin_clasificar",
                "estado": "nueva",
            }],
        )

    sol = await _repo(handler).obtener(sol_id, EMPRESA)

    # El JWT del usuario en el header es lo que hace que la RLS filtre por SU empresa.
    assert visto["auth"] == f"Bearer {JWT}"
    assert visto["apikey"] == ANON
    assert "/rest/v1/solicitudes" in visto["url"]
    assert f"id=eq.{sol_id}" in visto["url"]
    assert sol is not None and sol.cuerpo == "quiero un sampling"


async def test_obtener_sin_filas_devuelve_none():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).obtener(uuid4(), EMPRESA) is None


async def test_guardar_clasificacion_hace_patch_y_devuelve_actualizada():
    sol_id = uuid4()
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["method"] = req.method
        visto["url"] = str(req.url)
        visto["body"] = req.content.decode()
        return httpx.Response(
            200,
            json=[{
                "id": str(sol_id),
                "empresa_id": str(EMPRESA),
                "cuerpo": "c",
                "resumen": "un resumen",
                "tipo": "tipo_1",
                "estado": "nueva",
            }],
        )

    sol = await _repo(handler).guardar_clasificacion(
        sol_id, EMPRESA, "un resumen", "tipo_1"
    )

    assert visto["method"] == "PATCH"
    assert f"id=eq.{sol_id}" in visto["url"]
    assert "un resumen" in visto["body"] and "tipo_1" in visto["body"]
    # No cambia el estado al clasificar (regla de la spec 001).
    assert sol.estado == "nueva" and sol.tipo == "tipo_1" and sol.resumen == "un resumen"


async def test_crear_desde_correo_inserta_y_devuelve_true():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        return httpx.Response(201, json=[{"id": str(uuid4())}])

    creada = await _repo(handler).crear_desde_correo(
        EMPRESA,
        MensajeCorreo(
            gmail_msg_id="msg-1",
            remitente="Zona Espiga",
            correo_origen="ventas@zonaespiga.cl",
            asunto="Sampling",
            cuerpo="hola",
        ),
    )
    assert creada is True


async def test_crear_desde_correo_duplicado_devuelve_false():
    # PostgREST con `resolution=ignore-duplicates` responde sin filas en conflicto.
    def handler(req):
        return httpx.Response(200, json=[])

    creada = await _repo(handler).crear_desde_correo(
        EMPRESA,
        MensajeCorreo(
            gmail_msg_id="msg-1",
            remitente="Zona Espiga",
            correo_origen="ventas@zonaespiga.cl",
            asunto="Sampling",
            cuerpo="hola",
        ),
    )
    assert creada is False


async def test_listar_manda_jwt_del_usuario_y_mapea_las_filas():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["auth"] = req.headers.get("authorization")
        visto["url"] = str(req.url)
        return httpx.Response(
            200,
            json=[
                {"id": str(uuid4()), "empresa_id": str(EMPRESA), "cuerpo": "uno",
                 "asunto": "A", "tipo": "sin_clasificar", "estado": "nueva"},
                {"id": str(uuid4()), "empresa_id": str(EMPRESA), "cuerpo": "dos",
                 "asunto": "B", "tipo": "tipo_2", "estado": "nueva"},
            ],
        )

    filas = await _repo(handler).listar(EMPRESA)

    # El JWT del usuario en el header es lo que hace que la RLS filtre por SU empresa.
    assert visto["auth"] == f"Bearer {JWT}"
    assert "/rest/v1/solicitudes" in visto["url"]
    assert [s.asunto for s in filas] == ["A", "B"]


async def test_listar_mapea_creado_en_de_postgrest():
    # La fila de PostgREST trae `creado_en` (timestamptz como ISO); el repo lo
    # surte en `Solicitud.creado_en` para que el endpoint lo exponga al front.
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"id": str(uuid4()), "empresa_id": str(EMPRESA), "cuerpo": "uno",
                 "asunto": "A", "tipo": "sin_clasificar", "estado": "nueva",
                 "creado_en": "2026-06-09T12:30:00+00:00"},
            ],
        )

    filas = await _repo(handler).listar(EMPRESA)

    assert filas[0].creado_en is not None
    assert filas[0].creado_en.isoformat() == "2026-06-09T12:30:00+00:00"


async def test_listar_sin_filas_devuelve_lista_vacia():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).listar(EMPRESA) == []


def test_provider_construye_repo_con_el_jwt_del_usuario(monkeypatch):
    # El pegamento de FastAPI: arma el repo real por request con el JWT del header.
    monkeypatch.setenv("SUPABASE_URL", "https://proyecto.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    obtener_settings.cache_clear()

    repo = obtener_repositorio_solicitudes(authorization="Bearer jwt-abc")

    assert isinstance(repo, RepositorioSolicitudesSupabase)
    assert repo._jwt == "jwt-abc"


def test_provider_sin_token_es_401():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        obtener_repositorio_solicitudes(authorization=None)
    assert exc.value.status_code == 401
