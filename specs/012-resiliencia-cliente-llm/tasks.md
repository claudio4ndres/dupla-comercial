# Tareas 012 · Resiliencia del cliente LLM

- [x] **T1** — 🔴 Tests de reintentos (CA1-CA5) en `test_cliente_anthropic_httpx.py`
  con `dormir` falso y ajuste del test existente de 500. Verificar que FALLAN.
- [x] **T2** — 🟢 Implementar el bucle de reintentos con backoff en
  `_Mensajes.create` (`cliente_anthropic.py`), parámetros con default y hook
  `dormir` inyectable.
- [x] **T3** — ♻️ Suite completa verde (`pytest -q`), commit en español.
