"""Spec 015 · Cache en proceso del access token OAuth de Google.

Gmail y Drive canjean el refresh token por un access token efímero en CADA
operación: cada tool-call de Javo al Drive y cada pase del poller paga un
round-trip a Google. El access token dura ~1 hora: se cachea por `token_ref`
con TTL `expires_in - 60s` (margen para no usar un token a punto de vencer).

Best-effort por proceso: con varias instancias cada una tiene su cache (canjear
de más no rompe nada). Los fallos de auth NO se cachean (el cliente lanza antes
de llegar a `guardar`). Reloj inyectable para tests sin espera real.
"""
import time

_MARGEN_SEGUNDOS = 60.0


class CacheTokenAcceso:
    """Cache `token_ref → (access_token, expira_en)` con reloj inyectable."""

    def __init__(self, *, reloj=time.monotonic):
        self._reloj = reloj
        self._por_ref: dict[str, tuple[str, float]] = {}

    def obtener(self, token_ref: str) -> str | None:
        entrada = self._por_ref.get(token_ref)
        if entrada is None:
            return None
        token, expira_en = entrada
        if self._reloj() >= expira_en:
            self._por_ref.pop(token_ref, None)
            return None
        return token

    def guardar(self, token_ref: str, token: str, *, expires_in: float) -> None:
        vida = max(float(expires_in) - _MARGEN_SEGUNDOS, 0.0)
        self._por_ref[token_ref] = (token, self._reloj() + vida)
