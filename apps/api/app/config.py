"""Configuración del backend vía variables de entorno (pydantic-settings).

Centraliza los secretos/credenciales que la app lee del entorno (o de un `.env`
en desarrollo). NUNCA se hardcodean claves: se inyectan por entorno (regla de
oro #3 — el LLM y sus credenciales viven solo en el backend). `obtener_settings`
cachea la instancia para no releer el entorno en cada request.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno del backend.

    Los nombres de campo mapean a su versión en MAYÚSCULAS:
    `anthropic_api_key` ← `ANTHROPIC_API_KEY`. El default vacío permite levantar
    la app en tests/CI sin secretos (ahí se inyectan dobles); en producción la
    key real llega por entorno o Secret Manager.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    anthropic_api_key: str = ""

    # Secreto JWT del proyecto Supabase (HS256). Verifica los tokens de los
    # usuarios y de él se extrae `empresa_id` (T7b). Settings → Auth → JWT Secret.
    supabase_jwt_secret: str = ""

    # PostgREST del proyecto (T7c). `supabase_url` → API URL; `supabase_anon_key`
    # → clave pública anónima. El repo real pega acá con el JWT del usuario.
    supabase_url: str = ""
    supabase_anon_key: str = ""

    # App OAuth de Google (TR1): client_id/secret de Google Cloud Console
    # (APIs & Services → Credentials). NO son secretos del usuario; con ellos el
    # backend refresca el access token de Gmail de cada casilla y canjea el code
    # del consentimiento. `redirect_uri` es la URL de callback registrada.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    # Carpeta del Google Drive de la empresa de donde se leen los recursos del
    # catálogo (panel "Recursos · Drive"). Default: la carpeta REAL del cliente
    # piloto (Capsulab). Se sobreescribe por empresa/entorno con `DRIVE_FOLDER_ID`.
    drive_folder_id: str = "1sPeaZbXVi4q-eXNkwGTTpaZUgKNuhy1i"

    # Service role key de Supabase (Settings → API). SÓLO backend/poller: salta la
    # RLS, por eso el poller fija `empresa_id` explícito en cada fila (TR3). NUNCA
    # exponer al front.
    supabase_service_role_key: str = ""

    # Proyecto de Google Cloud donde viven los secretos (Secret Manager, TR2).
    gcp_project_id: str = ""

    # Secreto compartido que protege el endpoint interno del poller (T12). Cloud
    # Scheduler lo manda en el header `X-Poller-Token` (en real puede ser OIDC).
    poller_token: str = ""

    # A dónde vuelve el navegador tras conectar el correo (la bandeja del front);
    # se usa como `url_post_conexion` del OAuth.
    frontend_url: str = "/"

    # Backend del almacén de secretos (refresh tokens de Gmail). "gcp" → Google
    # Secret Manager (producción, TR2); "archivo" → archivo JSON local gitignored
    # (desarrollo, sin nube ni paquete `google`). Default seguro hacia prod; el
    # `.env` local define `SECRETOS_BACKEND=archivo`.
    secretos_backend: str = "gcp"

    # Ruta del archivo cuando `secretos_backend="archivo"` (relativa al CWD del
    # backend, que corre desde `apps/api`). Gitignored.
    secretos_ruta_local: str = ".secretos.local.json"


@lru_cache
def obtener_settings() -> Settings:
    return Settings()
