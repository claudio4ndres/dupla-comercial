# Tareas 013 · Javo, partner comercial

- [x] **T1** — 🔴 Tests CA1-CA4 en `test_javo_agente.py` (orden fijo de tools,
  tarifario con Drive presente, estabilidad system/tools, conductas del prompt).
- [x] **T2** — 🔴 Test CA5 en `tests/test_endpoint_sugerencias.py` (fallback
  comercial + happy path con doble de Haiku).
- [x] **T3** — 🟢 `_CONDUCTA_COMERCIAL` + `_system_para` en `javo.py`.
- [x] **T4** — 🟢 `_tool_consultar_tarifario` (primera, description prescriptiva)
  + ejecutor sobre `_buscar_en_catalogo` (siempre catálogo, aunque haya Drive).
- [x] **T5** — 🟢 Chips comerciales (prompt Haiku + `_chips_fallback`).
- [x] **T6** — ♻️ Suite completa verde, commit en español.
- [ ] **T7** — 🧑 Sesión de chat manual T1: Javo pregunta lo que falta (máx. 2),
  presenta recomendada + alternativa, sugiere upsell, ofrece "¿Genero la propuesta?".
