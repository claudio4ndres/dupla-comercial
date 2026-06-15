"""Observabilidad de los conectores OAuth (Spec 010).

Punto ÚNICO y reutilizable para avisar que una integración cayó a 'reconectar'. Lo
llaman los dos sitios que marcan 'reconectar' (la ingesta de correo y el poller
interno), de modo que la señal se emite y se prueba en un solo lugar.

Decisión #3 del Gerente TI: por ahora la "alerta" es un LOG ESTRUCTURADO (nivel
warning) — sin canal externo (correo/Slack). La función deja un punto natural de
extensión para reenviar a un canal final más adelante, sin que esta spec lo cablee.

Reglas de oro aplicadas:
* #3 — la señal identifica la integración por `(empresa_id, proveedor)` y un `motivo`;
  JAMÁS incluye un token (ni refresh ni access).
* best-effort — si emitir la señal falla (handler de logging roto, etc.), NO se propaga:
  una alerta es defensa en profundidad y nunca puede tumbar la ingesta/poller.
"""
import logging
from uuid import UUID

_LOG = logging.getLogger(__name__)


def avisar_reconectar(empresa_id: UUID, proveedor: str, motivo: str) -> None:
    """Emite una señal para el operador de que `(empresa_id, proveedor)` cayó a
    'reconectar' por `motivo` (p.ej. `"auth_invalida"`).

    Best-effort y sin tokens: identifica la integración por empresa+proveedor, nunca
    por su secreto. Si el logging revienta, traga la excepción (no rompe al llamador).
    """
    try:
        _LOG.warning(
            "Conector caído: empresa_id=%s proveedor=%s motivo=%s "
            "→ requiere reconexión (estado 'reconectar').",
            empresa_id,
            proveedor,
            motivo,
        )
    except Exception:  # noqa: BLE001 — la alerta JAMÁS puede tumbar al llamador
        # Si ni siquiera podemos loggear, no hay mucho más que hacer; tragamos para
        # preservar la ingesta/poller (la señal es best-effort, regla del plan).
        pass
