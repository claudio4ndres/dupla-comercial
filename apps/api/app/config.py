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


@lru_cache
def obtener_settings() -> Settings:
    return Settings()
