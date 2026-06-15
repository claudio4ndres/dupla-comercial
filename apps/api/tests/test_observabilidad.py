"""Tests del módulo de observabilidad (Spec 010 · CA5).

`avisar_reconectar(empresa_id, proveedor, motivo)` emite una señal estructurada para
el operador cuando una integración cae a 'reconectar'. Decisión #3 del Gerente TI: por
ahora es un LOG ESTRUCTURADO (nivel warning), sin canal externo.

Invariantes que fijan estos tests:
* el log incluye empresa_id + proveedor + motivo (para que el operador identifique la
  integración caída);
* el log NUNCA incluye un token (regla de oro #3);
* es best-effort: si el logging revienta, la función NO propaga (no debe tumbar la
  ingesta/poller que la llaman).
"""
import logging
from uuid import uuid4

from app.servicios.observabilidad import avisar_reconectar

EMPRESA = uuid4()


def test_avisar_reconectar_emite_warning_con_empresa_proveedor_y_motivo(caplog):
    with caplog.at_level(logging.WARNING):
        avisar_reconectar(EMPRESA, "gmail", "auth_invalida")

    # Hubo al menos un registro de nivel WARNING.
    advertencias = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert advertencias, "se esperaba un log de nivel warning"
    texto = " ".join(r.getMessage() for r in advertencias)
    assert str(EMPRESA) in texto
    assert "gmail" in texto
    assert "auth_invalida" in texto


def test_avisar_reconectar_no_filtra_token_alguno(caplog):
    # Aunque el motivo no debería traer secretos, comprobamos que la señal jamás
    # incluye nada que parezca un token/refresh (regla de oro #3, CA5).
    with caplog.at_level(logging.WARNING):
        avisar_reconectar(EMPRESA, "gmail", "auth_invalida")

    texto = " ".join(r.getMessage() for r in caplog.records).lower()
    assert "token" not in texto
    assert "refresh" not in texto
    assert "bearer" not in texto
    assert "secreto://" not in texto


def test_avisar_reconectar_es_best_effort_si_el_logger_falla(monkeypatch):
    # Si emitir la señal revienta (p.ej. un handler roto), la función NO debe propagar:
    # la alerta es defensa, jamás puede tumbar la ingesta/poller.
    import app.servicios.observabilidad as obs

    class _LoggerRoto:
        def warning(self, *args, **kwargs):
            raise RuntimeError("handler de logging caído")

    monkeypatch.setattr(obs, "_LOG", _LoggerRoto())

    # No debe lanzar.
    avisar_reconectar(EMPRESA, "gmail", "auth_invalida")
