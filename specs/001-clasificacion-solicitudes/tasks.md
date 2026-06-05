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
- [x] **T5 · RLS en DB (Supabase local).** `supabase start` + test pgTAP en
  `supabase/tests/`: empresa A no lee solicitud de empresa B (CA multi-tenant a nivel
  de datos). Verificado el rojo (sin RLS A ve filas ajenas) y el verde con `supabase
  test db` (4 tests PASS). ✅
- [x] **T6 · Manejo de error del LLM.** Si el SDK lanza excepción → endpoint responde
  `502` (no 500 crudo) y la solicitud queda sin clasificar (reintentar). ✅

## Cableado real (integración) — reemplaza los proveedores `NotImplementedError`

- [x] **T7a · Settings + cliente Anthropic real.** `app/config.py` (`Settings` con
  pydantic-settings) + `obtener_cliente_anthropic` → `AsyncAnthropic`.
  - Test: se construye con la key de settings, **sin llamadas de red**. ✅
- [ ] **T7b · Auth `obtener_empresa_actual` (JWT de Supabase).** Verifica el JWT (HS256
  + secreto) y extrae `empresa_id` del claim.
  - Test: JWT válido → `empresa_id`; sin token / firma inválida → `401`.
- [ ] **T7c · `RepositorioSolicitudesSupabase`.** Habla con PostgREST usando el JWT del
  usuario; la **RLS** filtra (no el backend). Construido por request con el token.
  - Test: integración contra Supabase local (A lee lo suyo, no lee lo de B).

> **Decisión (2026-06):** se adelanta el frontend ANTES del cableado real (T7a/b/c)
> para tener algo visual que mostrarle a Javier. El front se construye con el `fetch`
> al backend **mockeado** (regla de testing del proyecto), así no depende de la API key
> de Anthropic ni del repo Supabase. El cableado real al backend se hace cuando T7 esté
> verde.

## Frontend (apps/web) — pantalla de la solicitud

- [ ] **T8 · Arnés frontend.** Scaffolding `apps/web` (Vite + React + TS + Tailwind v4
  + vitest + @testing-library/react). Test de humo: `render(<App/>)` muestra el título
  de la app. (Prueba que el arnés y vitest corren.)
- [ ] **T9 · Pantalla de la solicitud (datos mock).** Componente `PantallaSolicitud`
  que recibe una solicitud y muestra: asunto + remitente, el **resumen** (lista de
  puntos) y la **sugerencia de tipo** (Tipo 1 / Tipo 2).
  - Tests: pinta el resumen; muestra la sugerencia de tipo con su etiqueta legible.
- [ ] **T10 · "Ver correo completo".** Botón que revela el cuerpo original del correo
  (oculto por defecto). Es el pedido explícito de Javier (ver el correo original).
  - Tests: el cuerpo no se ve al inicio; al hacer clic en "Ver correo completo" aparece.
- [ ] **T11 · Confirmación humana del tipo (CA4).** El sistema solo **sugiere**; el
  usuario **confirma** Tipo 1 / Tipo 2. Botones que disparan un callback con el tipo
  elegido; la sugerencia se distingue visualmente de la confirmación.
  - Tests: clic en "Tipo 1"/"Tipo 2" llama al callback con el valor correcto.
- [ ] **T12 · Cliente API + carga/error (`fetch` mockeado).** Llama
  `POST /solicitudes/{id}/clasificar`; estados loading/ok/error.
  - Tests: `fetch` mock → pinta resumen; `502` → mensaje de error. (Se cablea al
    backend real cuando T7a/b/c estén verdes.)
