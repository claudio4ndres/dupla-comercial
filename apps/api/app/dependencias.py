"""Proveedores de dependencias de FastAPI.

En los tests se sobrescriben con dobles (`app.dependency_overrides`). El cableado
real con Supabase aún se hará en tareas de integración aparte (con su propio
test); por eso esos proveedores siguen como `NotImplementedError`. El cliente
Anthropic real ya está cableado (T7a): se construye con la key de `Settings`.
"""
from functools import lru_cache
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from app.config import obtener_settings
from app.repositorios.estado_oauth import AlmacenEstadoOAuthEnMemoria
from app.repositorios.catalogo_supabase import RepositorioCatalogoSupabase
from app.repositorios.conversaciones_supabase import RepositorioConversacionesSupabase
from app.repositorios.integraciones_supabase import RepositorioIntegracionesSupabase
from app.repositorios.propuestas_supabase import RepositorioPropuestasSupabase
from app.repositorios.solicitudes_supabase import RepositorioSolicitudesSupabase
from app.servicios.busqueda_internet import ProveedorBusquedaCurado
from app.servicios.cliente_anthropic import ClienteAnthropicHttpx
from app.servicios.drive_real import FabricaClienteDriveReal
from app.servicios.empresa import ResolvedorEmpresaSupabase
from app.servicios.jwt_supabase import VerificadorJwtSupabase
from app.servicios.gmail_real import FabricaClienteGmailReal
from app.servicios.oauth_gmail import ConfigOAuthGmail
from app.servicios.oauth_gmail_real import ClienteOAuthGoogleReal
from app.servicios.secretos import (
    AlmacenSecretos,
    AlmacenSecretosArchivo,
    AlmacenSecretosSecretManager,
)


def _jwt_del_header(authorization: str | None) -> str:
    """Extrae el JWT del header `Authorization: Bearer ...` o lanza 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de autenticación",
        )
    return authorization.split(" ", 1)[1].strip()


def obtener_repositorio_solicitudes(
    authorization: str | None = Header(default=None),
) -> RepositorioSolicitudesSupabase:
    """Repositorio real de solicitudes (T7c), construido POR REQUEST con el JWT
    del usuario para que la RLS filtre por su empresa. En los tests se sobrescribe
    con uno en memoria vía `app.dependency_overrides`."""
    settings = obtener_settings()
    return RepositorioSolicitudesSupabase(
        settings.supabase_url,
        settings.supabase_anon_key,
        _jwt_del_header(authorization),
    )


def obtener_repositorio_catalogo(
    authorization: str | None = Header(default=None),
) -> RepositorioCatalogoSupabase:
    """Repo real del catálogo (005), construido POR REQUEST con el JWT del usuario
    para que la RLS filtre el catálogo por su empresa. En tests se sobrescribe con
    uno en memoria vía `app.dependency_overrides`."""
    settings = obtener_settings()
    return RepositorioCatalogoSupabase(
        settings.supabase_url,
        settings.supabase_anon_key,
        _jwt_del_header(authorization),
    )


def obtener_repositorio_propuestas(
    authorization: str | None = Header(default=None),
) -> RepositorioPropuestasSupabase:
    """Repo real de propuestas (004), construido POR REQUEST con el JWT del usuario
    para que la RLS filtre la cotización por su empresa. En tests se sobrescribe con
    uno en memoria vía `app.dependency_overrides`."""
    settings = obtener_settings()
    return RepositorioPropuestasSupabase(
        settings.supabase_url,
        settings.supabase_anon_key,
        _jwt_del_header(authorization),
    )


def obtener_repositorio_conversaciones(
    authorization: str | None = Header(default=None),
) -> RepositorioConversacionesSupabase:
    """Repo real de conversaciones (T13), construido POR REQUEST con el JWT del usuario
    para que la RLS filtre el hilo del chat por su empresa. En tests se sobrescribe con
    uno en memoria vía `app.dependency_overrides`."""
    settings = obtener_settings()
    return RepositorioConversacionesSupabase(
        settings.supabase_url,
        settings.supabase_anon_key,
        _jwt_del_header(authorization),
    )


def obtener_repositorio_integraciones(
    authorization: str | None = Header(default=None),
) -> RepositorioIntegracionesSupabase:
    """Repo de integraciones para ENDPOINTS DE USUARIO (estado/desconectar): se
    construye POR REQUEST con el JWT del usuario (apikey = anon) para que la RLS
    filtre por su empresa (regla de oro #2). En tests se sobrescribe en memoria."""
    settings = obtener_settings()
    return RepositorioIntegracionesSupabase(
        settings.supabase_url,
        settings.supabase_anon_key,
        _jwt_del_header(authorization),
    )


def obtener_repositorio_integraciones_servicio() -> RepositorioIntegracionesSupabase:
    """Repo de integraciones para el POLLER y el CALLBACK OAuth, que NO traen JWT (el
    poller lo dispara Cloud Scheduler; el callback es un redirect del navegador). Corre
    con la service role key como apikey y bearer: salta la RLS, así que el llamador fija
    `empresa_id` explícito en cada fila (jamás se infiere → no cruza tenants, TR3)."""
    settings = obtener_settings()
    return RepositorioIntegracionesSupabase(
        settings.supabase_url,
        settings.supabase_service_role_key,
        settings.supabase_service_role_key,
    )


def obtener_repositorio_solicitudes_servicio() -> RepositorioSolicitudesSupabase:
    """Repo de solicitudes para el POLLER (sin JWT): service role como apikey y bearer.
    El poller fija `empresa_id` explícito por cada correo que ingiere (TR3)."""
    settings = obtener_settings()
    return RepositorioSolicitudesSupabase(
        settings.supabase_url,
        settings.supabase_service_role_key,
        settings.supabase_service_role_key,
    )


@lru_cache
def obtener_almacen_estado_oauth() -> AlmacenEstadoOAuthEnMemoria:
    """Almacén del `state` anti-CSRF del OAuth. Singleton de proceso (`lru_cache`) para
    que el `state` creado en `iniciar` siga vivo cuando vuelve el `callback`. En memoria
    alcanza para un proceso; si se escala a varias instancias, migrar a Supabase/Redis
    (no cambia el contrato). En tests se sobrescribe."""
    return AlmacenEstadoOAuthEnMemoria()


def obtener_config_oauth_gmail() -> ConfigOAuthGmail:
    """Config del cliente OAuth de Google (client_id/redirect_uri NO son secretos del
    usuario). `url_post_conexion` es a dónde vuelve el navegador tras conectar."""
    settings = obtener_settings()
    return ConfigOAuthGmail(
        client_id=settings.google_client_id,
        redirect_uri=settings.google_redirect_uri,
        url_post_conexion=settings.frontend_url,
    )


def obtener_cliente_oauth_google() -> ClienteOAuthGoogleReal:
    """Cliente real del canje del `code` por credenciales (TR3)."""
    settings = obtener_settings()
    return ClienteOAuthGoogleReal(
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_redirect_uri,
    )


@lru_cache
def obtener_almacen_secretos() -> AlmacenSecretos:
    """Almacén de secretos (refresh tokens de Gmail), elegido por `SECRETOS_BACKEND`:

    * `"gcp"` (default, producción) → Google Secret Manager (TR2). Singleton
      (`lru_cache`) para reusar el cliente de GCP; se construye sin red (perezoso).
    * `"archivo"` (desarrollo local) → archivo JSON gitignored, sin exigir el
      paquete `google` ni credenciales de nube; durable entre reinicios.

    En tests se sobrescribe con uno en memoria vía `app.dependency_overrides`."""
    settings = obtener_settings()
    if settings.secretos_backend.lower() == "archivo":
        return AlmacenSecretosArchivo(settings.secretos_ruta_local)
    return AlmacenSecretosSecretManager(settings.gcp_project_id)


def obtener_fabrica_cliente_gmail() -> FabricaClienteGmailReal:
    """Fábrica real (token_ref → cliente Gmail, TR1). Comparte el almacén de secretos
    singleton para resolver el refresh de cada casilla (regla de oro #3)."""
    settings = obtener_settings()
    return FabricaClienteGmailReal(
        almacen=obtener_almacen_secretos(),
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def obtener_fabrica_cliente_drive() -> FabricaClienteDriveReal:
    """Fábrica real (token_ref → cliente Drive). Calca a la de Gmail: comparte el
    mismo almacén de secretos singleton y las mismas credenciales OAuth de Google
    (el consentimiento cubre Gmail y Drive a la vez). Alimenta el panel "Recursos ·
    Drive". En tests se sobrescribe con un doble vía `app.dependency_overrides`."""
    settings = obtener_settings()
    return FabricaClienteDriveReal(
        almacen=obtener_almacen_secretos(),
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def obtener_secreto_poller() -> str:
    """Secreto compartido que protege el endpoint interno del poller (T12). Cloud
    Scheduler lo manda en `X-Poller-Token`. En tests se inyecta uno de prueba."""
    return obtener_settings().poller_token


@lru_cache
def obtener_cliente_anthropic() -> ClienteAnthropicHttpx:
    """Cliente Anthropic real sobre **httpx**, cableado con la API key de `Settings`.

    No hace red al construirse. Se cachea para reutilizar el mismo cliente entre
    requests. En los tests/clasificación se sigue inyectando un doble vía
    `app.dependency_overrides`, así que nunca se gastan tokens reales (CA5).

    Antes se usaba el SDK `anthropic`, pero su import en frío arrastraba ~1800
    módulos y tardaba minutos en esta máquina, frenando CADA arranque del backend y
    el primer llamado a Javo. `ClienteAnthropicHttpx` habla directo con la Messages
    API por httpx (ya usado en el proyecto): import instantáneo, misma interfaz
    `.messages.create` que consumen el clasificador y Javo."""
    return ClienteAnthropicHttpx(api_key=obtener_settings().anthropic_api_key)


def obtener_proveedor_busqueda() -> ProveedorBusquedaCurado:
    """Proveedor de búsqueda en internet para Tipo 2 (005). Para la demo: curado y
    offline-safe. En tests se sobrescribe con un doble vía `app.dependency_overrides`
    (CA4: nunca se llama una API real)."""
    return ProveedorBusquedaCurado()


def obtener_resolvedor_empresa() -> ResolvedorEmpresaSupabase:
    """Resolvedor de la empresa de un usuario por su `auth.uid` (login real sin el
    *custom access token hook*). Usa la service role para leer `usuarios` saltando la
    RLS. En tests se sobrescribe con un doble vía `app.dependency_overrides`."""
    settings = obtener_settings()
    return ResolvedorEmpresaSupabase(
        settings.supabase_url, settings.supabase_service_role_key
    )


def obtener_verificador_jwt() -> VerificadorJwtSupabase:
    """Verificador del JWT de Supabase: ES256 (vía JWKS) o HS256 (secreto / JWT dev).
    En tests se sobrescribe con un doble vía `app.dependency_overrides`."""
    settings = obtener_settings()
    return VerificadorJwtSupabase(settings.supabase_url, settings.supabase_jwt_secret)


async def obtener_empresa_actual(
    authorization: str | None = Header(default=None),
    verificador=Depends(obtener_verificador_jwt),
    resolvedor=Depends(obtener_resolvedor_empresa),
) -> UUID:
    """Auth real: identifica la empresa del usuario a partir del JWT de Supabase.

    Verifica la firma HS256 con `SUPABASE_JWT_SECRET` y resuelve la empresa por dos
    vías, en orden:
      1) `empresa_id` en el claim (producción con *custom access token hook*, o el
         JWT de desarrollo);
      2) si no viene el claim (login real SIN hook), por el `sub` (auth.uid) contra la
         tabla `usuarios`.
    Cualquier fallo → `401` (no se filtra detalle). La RLS de Postgres sigue siendo la
    barrera final multi-tenant; esto solo identifica al usuario."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de autenticación",
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = verificador.verificar(token)
    except Exception:
        # Firma inválida, token expirado, JWKS inalcanzable, etc. → 401 sin detalle.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        )

    # 1) empresa_id en el claim (hook activo / JWT dev).
    empresa_id = claims.get("empresa_id")
    if empresa_id:
        try:
            return UUID(str(empresa_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="empresa_id inválido en el token",
            )

    # 2) Login real sin hook: resolver por el `sub` contra la tabla usuarios.
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no identifica al usuario",
        )
    try:
        user_id = UUID(str(sub))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="sub inválido en el token"
        )
    empresa = await resolvedor.empresa_de(user_id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario no tiene empresa asignada",
        )
    return empresa
