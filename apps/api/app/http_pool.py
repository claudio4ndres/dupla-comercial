"""Singleton de httpx.AsyncClient compartido con connection pooling.

Reutiliza conexiones TCP a Supabase (PostgREST) para evitar el overhead de DNS +
TLS handshake en cada request. Se crea al importar y se cierra en el lifespan de
la app (main.py). En tests se inyecta otro cliente vía `app.dependency_overrides`,
así que este no interfiere.

Si el paquete `h2` está instalado, se activa HTTP/2 (mayor eficiencia con
multiplexing). Si no, funciona con HTTP/1.1 (keep-alive igualmente reutiliza
conexiones).
"""
import httpx

# Límites razonables: hasta 100 conexiones totales, 20 keep-alive simultáneas.
_limites = httpx.Limits(max_connections=100, max_keepalive_connections=20)

# Intentar activar HTTP/2 si h2 está disponible.
try:
    import h2  # noqa: F401
    _http2 = True
except ImportError:
    _http2 = False

# Singleton de proceso: se reutiliza en todos los requests.
cliente_http_compartido: httpx.AsyncClient = httpx.AsyncClient(
    http2=_http2,
    limits=_limites,
    timeout=httpx.Timeout(30.0),
)


async def cerrar_cliente_http() -> None:
    """Cierra el cliente compartido al shutdown de la app (lifespan)."""
    await cliente_http_compartido.aclose()
