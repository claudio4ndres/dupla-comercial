"""Cableado real de los providers de FastAPI (composition root).

Estos providers se sobrescriben en todos los tests/endpoints y en la demo; acá
verificamos el PEGAMENTO real: que construyan la implementación correcta con las
credenciales de `Settings`, y que el split usuario/servicio respete la regla de
oro #2 (la RLS es la barrera multi-tenant):

* endpoints de usuario   → repo con el JWT del usuario (apikey = anon): la RLS
  filtra por su empresa;
* poller y callback OAuth → repo con la service role key (sin JWT): salta la RLS y
  fija `empresa_id` explícito. Ni el poller (lo dispara Cloud Scheduler) ni el
  callback (es un redirect del navegador) traen JWT, por eso este camino dedicado.

Cero red: sólo se inspecciona cómo quedó construido cada objeto (los clientes de
GCP/httpx se crean de forma perezosa, así que construir no toca la red).
"""
import pytest

from app.config import obtener_settings
from app.dependencias import (
    obtener_almacen_estado_oauth,
    obtener_almacen_secretos,
    obtener_cliente_oauth_google,
    obtener_config_oauth_gmail,
    obtener_fabrica_cliente_gmail,
    obtener_repositorio_integraciones,
    obtener_repositorio_integraciones_servicio,
    obtener_repositorio_solicitudes_servicio,
    obtener_secreto_poller,
)
from app.repositorios.estado_oauth import AlmacenEstadoOAuthEnMemoria
from app.repositorios.integraciones_supabase import RepositorioIntegracionesSupabase
from app.repositorios.solicitudes_supabase import RepositorioSolicitudesSupabase
from app.servicios.gmail_real import FabricaClienteGmailReal
from app.servicios.oauth_gmail import ConfigOAuthGmail
from app.servicios.oauth_gmail_real import ClienteOAuthGoogleReal
from app.servicios.secretos import (
    AlmacenSecretosArchivo,
    AlmacenSecretosSecretManager,
)


@pytest.fixture(autouse=True)
def _entorno(monkeypatch):
    """Inyecta credenciales de prueba por entorno y limpia las cachés (settings y los
    singletons `lru_cache`) para que cada test vea su propio entorno aislado."""
    monkeypatch.setenv("SUPABASE_URL", "https://proyecto.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-publica")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-secreta")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://api/callback")
    monkeypatch.setenv("FRONTEND_URL", "https://front/bandeja")
    monkeypatch.setenv("GCP_PROJECT_ID", "proyecto-gcp")
    monkeypatch.setenv("POLLER_TOKEN", "token-del-poller")
    # Fijamos el backend de secretos por entorno para AISLAR estos tests del `.env`
    # local (que en desarrollo trae `SECRETOS_BACKEND=archivo`). Por defecto en
    # producción es "gcp" → Secret Manager; cada test elige su rama explícitamente.
    monkeypatch.setenv("SECRETOS_BACKEND", "gcp")
    obtener_settings.cache_clear()
    obtener_almacen_secretos.cache_clear()
    obtener_almacen_estado_oauth.cache_clear()
    yield
    obtener_settings.cache_clear()
    obtener_almacen_secretos.cache_clear()
    obtener_almacen_estado_oauth.cache_clear()


def test_integraciones_usuario_usa_el_jwt_del_header():
    # Endpoint de usuario: apikey = anon pública; bearer = JWT del usuario (la RLS
    # filtra por su empresa, regla de oro #2).
    repo = obtener_repositorio_integraciones(authorization="Bearer jwt-del-usuario")
    assert isinstance(repo, RepositorioIntegracionesSupabase)
    assert repo._anon == "anon-publica"
    assert repo._jwt == "jwt-del-usuario"


def test_integraciones_usuario_sin_token_es_401():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        obtener_repositorio_integraciones(authorization=None)
    assert exc.value.status_code == 401


def test_integraciones_servicio_usa_service_role_sin_jwt():
    # Poller y callback OAuth: service role como apikey Y bearer (salta la RLS).
    repo = obtener_repositorio_integraciones_servicio()
    assert isinstance(repo, RepositorioIntegracionesSupabase)
    assert repo._anon == "service-role-secreta"
    assert repo._jwt == "service-role-secreta"


def test_solicitudes_servicio_usa_service_role_sin_jwt():
    repo = obtener_repositorio_solicitudes_servicio()
    assert isinstance(repo, RepositorioSolicitudesSupabase)
    assert repo._anon == "service-role-secreta"
    assert repo._jwt == "service-role-secreta"


def test_config_oauth_gmail_se_arma_desde_settings():
    config = obtener_config_oauth_gmail()
    assert isinstance(config, ConfigOAuthGmail)
    assert config.client_id == "google-client-id"
    assert config.redirect_uri == "https://api/callback"
    assert config.url_post_conexion == "https://front/bandeja"


def test_cliente_oauth_google_real_se_arma_desde_settings():
    oauth = obtener_cliente_oauth_google()
    assert isinstance(oauth, ClienteOAuthGoogleReal)
    assert oauth._client_id == "google-client-id"
    assert oauth._client_secret == "google-client-secret"
    assert oauth._redirect_uri == "https://api/callback"


def test_almacen_secretos_real_es_singleton():
    a = obtener_almacen_secretos()
    b = obtener_almacen_secretos()
    assert isinstance(a, AlmacenSecretosSecretManager)
    assert a is b  # lru_cache: un solo cliente de GCP por proceso
    assert a._project == "proyecto-gcp"


def test_almacen_secretos_archivo_en_desarrollo_local(monkeypatch):
    # En local (`SECRETOS_BACKEND=archivo`) el provider construye el almacén sobre
    # archivo JSON: no exige el paquete `google` ni credenciales de nube, y persiste
    # el refresh token en disco para que el poller lo reuse tras un reinicio.
    monkeypatch.setenv("SECRETOS_BACKEND", "archivo")
    monkeypatch.setenv("SECRETOS_RUTA_LOCAL", ".secretos.test.json")
    obtener_settings.cache_clear()
    obtener_almacen_secretos.cache_clear()

    almacen = obtener_almacen_secretos()
    assert isinstance(almacen, AlmacenSecretosArchivo)
    assert almacen._ruta.name == ".secretos.test.json"


def test_fabrica_gmail_real_comparte_el_almacen_de_secretos():
    fabrica = obtener_fabrica_cliente_gmail()
    assert isinstance(fabrica, FabricaClienteGmailReal)
    # La fábrica resuelve el refresh contra el MISMO almacén singleton.
    assert fabrica._almacen is obtener_almacen_secretos()
    assert fabrica._client_id == "google-client-id"
    assert fabrica._client_secret == "google-client-secret"


def test_almacen_estado_oauth_es_singleton():
    # Debe sobrevivir entre el `iniciar` y el `callback` (mismo proceso).
    a = obtener_almacen_estado_oauth()
    b = obtener_almacen_estado_oauth()
    assert isinstance(a, AlmacenEstadoOAuthEnMemoria)
    assert a is b


def test_secreto_poller_viene_de_settings():
    assert obtener_secreto_poller() == "token-del-poller"
