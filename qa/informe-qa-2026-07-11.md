# Informe de QA intensivo · Dupla Comercial

- **Fecha:** 2026-07-11
- **Rama:** `claude/code-review-qa-ytkbkw`
- **Alcance:** backend (`apps/api`), frontend (`apps/web`), base de datos (`supabase/`), specs e infraestructura.
- **Método:** ejecución completa de las suites de tests, build y lint; revisión dirigida de código en los flujos críticos (auth multi-tenant, chat con Javo, propuestas/cotizaciones, exports, OAuth, ingesta de correo); verificación de IDs de modelos de Anthropic contra la referencia oficial vigente.

---

## 1. Veredicto ejecutivo

**La funcionalidad central está sana y bien cubierta por tests.** El flujo principal (correo → clasificación → chat con Javo → propuesta → tareas → exports) funciona según lo especificado, el aislamiento multi-tenant por RLS es sólido (11/11 tablas), no hay secretos reales commiteados y el LLM se llama solo desde el backend.

Se encontraron y **corrigieron en esta rama 4 bugs funcionales** (sección 4). Quedan abiertos riesgos de robustez y UX — el mayor: la navegación del frontend no usa rutas reales, por lo que un refresh en el chat o en una propuesta pierde el estado — pero **ninguno bloquea el flujo feliz**.

## 2. Resultados de las suites

| Suite | Resultado | Detalle |
|---|---|---|
| Backend `pytest` | ✅ **363 pasan** (361 previos + 2 nuevos) | Python 3.12, todo mockeado (cero red). 4.7 s |
| Frontend `vitest` | ✅ **164 pasan** en 25 archivos (162 + 2 nuevos) | jsdom, Supabase y fetch mockeados |
| Frontend `tsc -b && vite build` | ✅ compila sin errores | bundle 437 kB (131 kB gzip) |
| Frontend `eslint` | ❌ **9 errores preexistentes** | ver hallazgo M-4 |
| E2E Playwright | ⚠️ no ejecutado | requiere Supabase local + backend + seed (sección 6) |
| pgTAP (RLS real) | ⚠️ no ejecutado | requiere `supabase start` (sección 6) |

## 3. Cumplimiento de las reglas de oro (CLAUDE.md)

| Regla | Estado | Evidencia |
|---|---|---|
| 1. BD 100 % en español | ✅ | 11 tablas, todas en español (`empresas`, `solicitudes`, `catalogo`, `miembros`, …) |
| 2. Multi-tenant por RLS | ✅ | RLS activa en 11/11 tablas; función `empresa_actual()` SECURITY DEFINER (`0001` L110-118); `with check` reforzado en `0008`. Tablas hijas (`mensajes`, `componentes_propuesta`) aisladas vía JOIN al padre. Nota: `empresas`/`usuarios` solo tienen política SELECT — la escritura queda reservada al service role (intencional) |
| 3. LLM solo desde backend | ✅ | El front no tiene claves ni llamadas a Anthropic (la única mención es un comentario que documenta la prohibición, `apps/web/src/api/javo.ts:4`). OAuth y tokens nunca llegan al front |
| 4. Ruteo de modelos + caching | ✅ | `claude-haiku-4-5` para clasificar/chips (`clasificador.py:9`) y `claude-sonnet-4-6` para el chat (`javo.py:27`) — **ambos IDs verificados como vigentes**, igual que el server tool `web_search_20260209` (soportado en Sonnet 4.6). Prompt caching con `cache_control: ephemeral` en el system prompt (`clasificador.py:58-64`, `javo.py:504-510`) y herramientas en orden fijo |
| 5. SDD + TDD | ⚠️ | El código nuevo sigue TDD (suites amplias), pero hay desfase specs↔realidad: 001 "aprobada" con 5 tareas pendientes; 003 y 006 sin `plan.md`; 011 sin `tasks.md`; `packages/shared/` (mencionado en CLAUDE.md) no existe |
| 6. Commits en español | ✅ | Historial consistente |

## 4. Fixes aplicados en esta rama (TDD: rojo → verde)

| Commit | Bug corregido | Severidad |
|---|---|---|
| `8a24fd9` | **`margen` sin validación en exports.** `GET /solicitudes/{id}/cotizacion.xlsx` y `.pptx` aceptaban cualquier float: `margen=1` provocaba división por cero (500 en vista cliente, `#DIV/0!` en el Excel interno) y `margen>1` generaba precios de venta negativos. Ahora se valida `Query(ge=0, lt=1)` → 422 | Alta |
| `c6e21d8` | **Defensa en profundidad multi-tenant.** `obtener` y `guardar_clasificacion` del repo de solicitudes eran los únicos métodos que filtraban solo por `id`, confiando exclusivamente en la RLS. Ahora añaden `empresa_id=eq.` explícito, igual que `listar`/`actualizar_estado`, protegiendo también un eventual uso con service role | Alta |
| `4509856` | **Propuesta fantasma.** `generarPropuesta` navegaba a la pantalla de propuesta aunque el POST fallara: el usuario veía una propuesta en memoria que desaparecía al recargar. Ahora, si el guardado falla, se queda en el chat con un mensaje de sistema para reintentar (`SolicitudContext.tsx`) | Alta |
| `a29e217` | **Clic muerto en Outlook/IMAP.** La bandeja ofrecía 3 proveedores activos pero solo Gmail está cableado (`App.tsx:90` ignoraba el resto en silencio). Ahora Outlook e IMAP van deshabilitados con badge "Próximamente" (mismo patrón que Jira en Configuración) | Media |

Cada fix tiene su test que falló primero (evidencia en `test_endpoint_cotizacion_excel.py`, `test_endpoint_ppt.py`, `test_repo_solicitudes_supabase.py`, `Bandeja.test.tsx`, `SolicitudContext.test.tsx`).

## 5. Hallazgos abiertos

### Severidad Alta

- **A-1 · Navegación sin rutas reales.** `src/router.tsx` define un árbol completo (`/bandeja/:id`, `/bandeja/:id/chat`, …) pero está **muerto**: `main.tsx:13-18` monta un catch-all que siempre renderiza `<App/>` y la navegación es por estado `pantalla`. Consecuencias: refresh en detalle/chat/propuesta pierde el estado, no hay deep-links, y la URL se desincroniza de la pantalla (`useSincronizarRuta.ts:20-23` colapsa `detail`/`chat`/`propuesta` a `/bandeja`). Requiere completar la migración a React Router ya iniciada (commits "Fase 1-3") — refactor grande, fuera del alcance de esta rama.
- **A-2 · Errores silenciados ("demo offline").** Casi todos los clientes de API del front capturan errores y devuelven fallback silencioso. El caso más grave: si el backend cae, `javo.ts:101-104` responde con un **texto fijo pregrabado** — Javo aparenta funcionar con el backend muerto. `exportaciones.ts` devuelve `false` sin avisar al usuario. Recomendación: reservar el fallback para modo demo explícito y propagar errores con banner (patrón `...OError` que ya existe para las listas).

### Severidad Media

- **M-1 · `abrirPropuestaDesdeLista` fabrica una Solicitud falsa.** `BandejaContext.tsx:173-183` crea `solicitudActual` con campos vacíos y `tipo: 't1'` fijo (el backend no expone `tipo` en `GET /propuestas`). Impacto acotado hoy (esa pantalla casi no usa el tipo), pero es una bomba latente si algo aguas abajo confía en `solicitudActual`. Fix correcto: agregar `tipo` a `PropuestaResumen` en el backend.
- **M-2 · `state` OAuth en memoria de proceso.** `AlmacenEstadoOAuthEnMemoria` (`dependencias.py:190-196`) no funciona con múltiples instancias de Cloud Run (ya documentado en el código). Migrar a tabla/Redis antes de escalar horizontalmente.
- **M-3 · JWT sin verificar `aud`** (`jwt_supabase.py:44-47`, `verify_aud: False`). Decisión consciente, pero conviene activar la verificación con la audiencia de Supabase (`authenticated`).
- **M-4 · Lint del front con 9 errores** (la Definition of Done exige lint ok): 4× `set-state-in-effect` en `BandejaContext.tsx`, 3× `only-export-components` en los contextos, 1 variable sin usar en `Tareas.test.tsx`, 1 triple-slash en `vite.config.ts`.
- **M-5 · Sin reintentos/backoff ante 429 de Anthropic.** Una caída del LLM se traduce en 502 (correcto), pero el poller clasifica en paralelo con `Semaphore(5)` (`interno.py:95`) sin manejo específico de rate-limit.
- **M-6 · Fallback confuso de Supabase en el front.** Si faltan `VITE_SUPABASE_URL`/`ANON_KEY`, `supabase/cliente.ts:3-4` degrada a `http://localhost` en vez de fallar fuerte → login que falla sin explicación.

### Severidad Baja

- **B-1** · `requirements.txt:6` declara `anthropic>=0.40` que el código ya no usa (cliente httpx propio); además omite el extra `httpx[http2]` que sí está en `pyproject.toml`.
- **B-2** · Contraseñas demo en claro commiteadas: `capsulab2024` y `clave-dev` en `supabase/seed.sql` y en los e2e (`auth.setup.ts:6`, `flujo.spec.ts:5`). Son de juguete, pero cualquier entorno sembrado con ese seed queda con credenciales públicas.
- **B-3** · `config.py:48`: `drive_folder_id` por defecto apunta a una carpeta real del cliente piloto (dato de cliente en el repo).
- **B-4** · Migración `0010` re-agrega columnas ya creadas por `0004`/`0005` (idempotente con `IF NOT EXISTS`, sin daño).
- **B-5** · `memory/contexto-producto.md` no lista las tablas `catalogo` ni `miembros`.
- **B-6** · `cabecerasAuth()` síncrona escanea `localStorage` por substring `'auth-token'` (`auth.ts:18`) — frágil ante cambios de Supabase; mitigada porque todos los clientes usan la versión async.
- **B-7** · Primer sync de Gmail truncado a 100 correos / 365 días (`gmail_real.py:39`) — se loggea pero no se avisa al usuario.
- **B-8** · Prompt caching: verificar en producción que el prefijo cacheado supere el mínimo cacheable del modelo (Haiku 4.5 exige ~4096 tokens; por debajo, no cachea silenciosamente). Revisar `usage.cache_read_input_tokens` en los logs.

### Verificaciones que salieron limpias

- Fórmula de margen **consistente** entre front y back: `tipos.ts:131` (`round(costo / 0.6)`) ≡ vista cliente del Excel (`round(cant × días × valor / (1 − margen))` con margen 0.40 por defecto).
- La vista cliente del Excel y el PPT **no filtran costos ni margen** (escriben valores calculados, no fórmulas que referencien el costo) — verificado en código y tests.
- Ingesta de correo idempotente (índice único parcial + captura del 409) y clasificación idempotente.
- Endpoints `/interno/*` protegidos por `X-Poller-Token`; callbacks OAuth validan `state` anti-CSRF de un solo uso.
- `response_model` en todos los endpoints: `empresa_id` y `token_ref` nunca viajan al front.
- **Ojo con `app/demo.py` / `app/demo_gmail_real.py`:** anulan la autenticación (empresa fija sin JWT) y agregan CORS permisivo. El entrypoint de producción es `produccion.py` (correcto en el `Dockerfile`); jamás desplegar las apps demo.

## 6. Cobertura no ejecutada en este QA

- **E2E (Playwright):** `cd apps/web && npx playwright test` — requiere `supabase start` + `supabase db reset` (seed) + backend (`uvicorn main:app`) + front (`npm run dev`). Cubre login y navegación; **no** cubre el flujo profundo (chat → propuesta → export), que sería el siguiente e2e a escribir.
- **pgTAP (RLS real):** `supabase test db` con los 7 archivos de `supabase/tests/` — es la verificación extremo-a-extremo de que empresa A no ve datos de empresa B; la suite unitaria solo verifica los query strings.

## 6-bis. Hallazgos resueltos después del QA (specs 012-017, misma rama)

Tras este informe se ejecutaron 6 fases de mejora (SDD+TDD). Estado final de
las suites: **backend 381 ✅ · frontend 180 ✅ · build ✅**.

| Hallazgo | Resolución | Spec |
|---|---|---|
| **A-1** navegación sin rutas reales | ✅ Migración completa a React Router v7: rutas reales (`/bandeja/:id`, `/bandeja/:id/chat`, `/propuestas/:id`), rehidratación en refresh/deep-link, `useSincronizarRuta` eliminado | 016 |
| **A-2** errores silenciados (Javo "canned", exports) | ✅ `conversarConJavoOError` + aviso con Reintentar en el chat; exports con `BannerError` | 014 |
| **M-2** state OAuth en memoria (multi-instancia) | ✅ Tabla `estados_oauth` (migración 0012) con consumo atómico; selección por `ESTADO_OAUTH_BACKEND` | 015 |
| **M-5** sin reintentos ante 429/529 de Anthropic | ✅ Backoff exponencial + jitter con `Retry-After` en `ClienteAnthropicHttpx` | 012 |
| **B-1** dependencia con dato del piloto (`drive_folder_id`) | ✅ Eliminada (código muerto) con su test | 015 |
| Latencia OAuth Gmail/Drive (canje por operación) | ✅ `CacheTokenAcceso` compartido por las fábricas (TTL `expires_in-60s`) | 015 |
| 010-T9 mensaje por proveedor al reconectar | ✅ Tarjetas Gmail/ClickUp con mensajes de la spec 010 + botón "Probar conexión" (auto-heal) | 017 |
| Specs 010 desfasadas | ✅ T3-T8 marcadas (ya estaban implementadas); quedan T1/T2 (🧑 publicar apps OAuth en las consolas de Google/ClickUp — acción humana, la cura de raíz del "reconectar") | — |

Además, **Javo se convirtió en partner comercial** (spec 013): descubrimiento
del brief, opciones valorizadas recomendada + alternativa, upsell con criterio,
cierre explícito, tool `consultar_tarifario` (catálogo RLS con citas) y chips
comerciales. Pendiente su validación humana (013-T7: sesión de chat real).

Siguen abiertos: M-1 (`tipo` fabricado al abrir propuesta desde la lista),
M-3 (`verify_aud`), M-4 (9 errores de lint preexistentes), B-2 (contraseñas
demo en seed) y la dependencia `anthropic` sin uso en requirements.txt.

## 7. Recomendaciones priorizadas (siguientes pasos)

1. Completar la migración a React Router (A-1) — ya hay 3 fases commiteadas de infraestructura.
2. Reemplazar los fallbacks silenciosos por manejo de error visible (A-2), empezando por `javo.ts`.
3. Correr pgTAP + e2e en CI (Cloud Build) para cubrir lo que esta pasada no pudo ejecutar.
4. Limpiar el lint del front (M-4) y la dependencia muerta `anthropic` (B-1).
5. Exponer `tipo` en `GET /propuestas` y eliminar la Solicitud fabricada (M-1).
