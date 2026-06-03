# Tareas 001 · Clasificación y resumen

Orden TDD: cada tarea escribe **el test primero (rojo)**, luego el mínimo código
(verde), luego refactor. Tareas pequeñas, commit por tarea (en español).

- [x] **T1 · Arnés backend.** Scaffolding `apps/api` (uv + FastAPI + pytest).
  - Test: `GET /salud` → `200 {"estado": "ok"}`. (Prueba que el arnés corre.) ✅
- [x] **T2 · Servicio de clasificación (mock).** Esquema Pydantic
  `ResultadoClasificacion { resumen, tipo }` + `clasificar_solicitud(cuerpo, cliente)`
  con el SDK de Anthropic **mockeado** (tool use + prompt caching del system).
  - Tests: CA2 (sopaipillas → `tipo_1`), CA3 (F1 → `tipo_2`), CA5 (sin llamadas reales). ✅
- [x] **T3 · Endpoint `POST /solicitudes/{id}/clasificar`.** Carga la solicitud, llama
  al servicio, persiste `resumen` + `tipo`, **no** cambia `estado`. (Repositorio
  abstracto + en memoria; cliente Anthropic inyectado.)
  - Tests: CA1 (resumen no vacío + tipo válido), CA4 (`estado` sigue `nueva`),
    idempotencia (2ª llamada no regasta tokens), 404 si no existe. ✅
- [x] **T4 · Aislamiento multi-tenant (endpoint).** Usuario de empresa A pide clasificar
  solicitud de empresa B → `404`. (Dependencia `obtener_empresa_actual` inyectable; el
  repositorio filtra por `empresa_id` emulando la RLS.) ✅
- [ ] **T5 · RLS en DB (Supabase local).** Instalar Supabase CLI, `supabase start`, test
  SQL: empresa A no lee solicitud de empresa B (CA multi-tenant a nivel de datos).
- [x] **T6 · Manejo de error del LLM.** Si el SDK lanza excepción → endpoint responde
  `502` (no 500 crudo) y la solicitud queda sin clasificar (reintentar). ✅

> El frontend de esta spec (mostrar resumen + botón "Ver correo completo" + sugerencia
> de tipo) se aborda como tareas T7+ una vez verde el backend, o en una spec de UI
> aparte. Backend primero.
