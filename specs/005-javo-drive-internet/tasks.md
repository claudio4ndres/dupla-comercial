# Tareas · Spec 005 · Javo agente (Drive + internet)

- **Estado:** borrador
- **Spec/Plan:** `spec.md` · `plan.md`

> Orden de dependencias: **datos → proveedor internet → servicio (loop) → endpoint →
> front → seed → cierre**. Cada tarea es un ciclo TDD (🔴 test que falla → 🟢 mínimo
> código → ♻️ refactor → commit en español). El SDK de Anthropic, el Drive/catálogo y la
> búsqueda en internet **se mockean siempre** (CA4); nada real, cero tokens.

## Datos · catálogo (multi-tenant)

- [x] **T1 · Migración `0003_catalogo.sql` + RLS.** *(código + test pgTAP escritos; verificación con `supabase test db` la corres tú)*
  **Test primero:** `supabase/tests/rls_catalogo.test.sql` (pgTAP) — la empresa A **no
  ve** filas de `catalogo` de la empresa B (**CA5**). Requiere Supabase local
  (`supabase test db`; lo corre el usuario).
  **Código:** tabla `catalogo` (en español: `empresa_id`, `tipo`, `nombre`, `detalle`,
  `unidad`, `valor_unitario`, `proveedor`, `origen`, `creado_en`) + `enable row level
  security` + policy `cat_empresa` (`empresa_actual()`) + índice por `empresa_id`.

- [x] **T2 · Repo catálogo en memoria + `Protocol`.**
  **Test primero:** `test_repo_catalogo_memoria.py` — `buscar(consulta, empresa_id)` filtra
  por **empresa** (emula RLS) y por **texto** en `nombre`/`detalle`; respeta `tipo` y
  `limite`.
  **Código:** `repositorios/catalogo.py` con `ItemCatalogo`, `RepositorioCatalogo`
  (Protocol) y `RepositorioCatalogoEnMemoria`.

- [x] **T3 · Repo catálogo Supabase + dependencia.**
  **Test primero:** `test_repo_catalogo_supabase.py` (transporte httpx mockeado) — manda el
  **JWT del usuario**, pega a `/rest/v1/catalogo`, filtra con `ILIKE` (`or=(...)`), mapea a
  `ItemCatalogo`; sin filas → `[]` (**CA5** a nivel de repo).
  **Código:** `repositorios/catalogo_supabase.py` (patrón de `solicitudes_supabase.py`) +
  `obtener_repositorio_catalogo` en `dependencias.py` (por request, con el JWT).

## Proveedor de búsqueda en internet

- [x] **T4 · `ProveedorBusqueda` (Protocol) + proveedor curado/stub + dependencia.**
  **Test primero:** `test_proveedor_busqueda.py` — `buscar(consulta)` devuelve resultados
  **con fuentes** (`titulo` + `referencia`); el doble es inyectable para tests.
  **Código:** `servicios/busqueda_internet.py` (Protocol + stub curado para la demo) +
  `obtener_proveedor_busqueda` en `dependencias.py`. *(Proveedor real = decisión de §6.)*

## Servicio · Javo agente (loop de tool-use)

- [x] **T5 · Esquemas de salida + definición de herramientas.**
  **Test primero:** `test_esquemas_conversacion.py` — `RespuestaConversacion` admite
  `componentes` y `fuentes` opcionales; las **definiciones de tools** son **deterministas**
  (orden fijo, para no romper la caché).
  **Código:** en `esquemas.py`: `ComponentePropuesto` (`nombre, detalle, cantidad,
  valor_unitario, origen`), `Fuente` (`titulo, referencia`), `RespuestaConversacion`
  extendida. Definiciones de las 3 tools en `javo.py`.

- [x] **T6 · Loop de tool-use: `buscar_en_drive` usa datos reales (CA1).**
  **Test primero:** `test_javo_agente.py::test_usa_valor_real_del_drive` — cliente Anthropic
  *scripted* (turno 1: `tool_use buscar_en_drive`; turno 2: `end_turn`); el servicio ejecuta
  el repo catálogo y **el valor del catálogo llega a la respuesta** (no inventado).
  **Código:** `responder_javo` pasa a loop manual: `create` → si `stop_reason=="tool_use"`
  ejecuta y reanexa `tool_result`, repite; si `end_turn` arma la respuesta. Inyecta cliente
  + repo catálogo + proveedor internet + `empresa_id`.

- [x] **T7 · `proponer_componentes` capturado, sin persistir (CA10).**
  **Test primero:** `...::test_captura_componentes_propuestos` — cuando Javo llama
  `proponer_componentes`, el servicio **captura** la lista y la expone en
  `respuesta.componentes`; **no** escribe en `propuestas`/`componentes_propuesta`.

- [x] **T8 · No inventar precios cuando no hay match (CA2).**
  **Test primero:** `...::test_sin_match_no_inventa` — si `buscar_en_drive` devuelve `[]`, el
  `tool_result` indica explícitamente **"sin resultados en el catálogo"** (la semilla para
  que Javo pida el dato o marque estimación, en vez de fabricar un precio).

- [x] **T9 · Gating + tope de internet (CA3, CA11).**
  **Test primero:** `...::test_internet_solo_si_se_pide` — en **Tipo 2 sin** pedirlo,
  `buscar_en_internet` **no** se incluye en `tools`; **pidiéndolo**, sí y se ejecuta. Y
  `...::test_tope_de_busquedas` — más allá de ~3–5 usos, no se hacen más búsquedas.
  **Código:** ofrecer la tool según tipo + intención del último turno; contador con tope.

- [x] **T10 · Fuentes en la respuesta (CA6).**
  **Test primero:** `...::test_respuesta_trae_fuentes` — los usos de `buscar_en_drive`
  (`origen`) y `buscar_en_internet` (`titulo`/`referencia`) acumulan `respuesta.fuentes`.

- [x] **T11 · Loop acotado (robustez/costo).**
  **Test primero:** `...::test_loop_acotado` — si el cliente *siempre* pide `tool_use`, el
  loop corta en un **máximo de iteraciones** (no se cuelga).

## Endpoint

- [x] **T12 · `/conversaciones/responder` con auth + respuesta extendida.**
  **Test primero:** `test_endpoint_conversacion.py` — **200** con `texto`+`componentes`+
  `fuentes`; **401** sin token (auth nueva); **502** si el LLM/herramienta cae. Dobles vía
  `dependency_overrides` (cliente, repo catálogo, proveedor, `empresa_actual`).
  **Código:** la ruta inyecta `obtener_empresa_actual` + repo catálogo + proveedor; pasa
  `empresa_id` al servicio; mapea a `RespuestaConversacion` extendida.

## Front

- [x] **T13 · `api/javo.ts` parsea la respuesta enriquecida.**
  **Test primero:** `api/javo.test.ts` — mapea `componentes` (`valor_unitario→valor`,
  `origen`) y `fuentes`; retro-compatible (si solo viene `texto`, sigue como hoy); error/caída
  → fallback.

- [x] **T14 · `App.tsx`: panel con componentes reales + fuentes (CA3, CA7).**
  **Test primero:** `App.test.tsx` — al conversar (Tipo 1), el **panel lateral** muestra los
  componentes que Javo propuso (con su **origen**); al pedir "busca en internet" aparecen las
  **fuentes**; **sin** pedirlo, no aparecen.
  **Código:** `enviarMensaje` usa `respuesta.componentes`/`fuentes` para poblar el panel y el
  estado "buscando…".

- [x] **T15 · `tipos.ts` + `Chat.tsx`: render de origen y fuentes.**
  **Test primero:** (cubierto por T14 a nivel App) — el componente muestra `origen` y la lista
  de `fuentes` con su enlace/recurso.
  **Código:** tipo `Fuente`, `Componente.origen?`, render en el panel y bajo los mensajes.

## Datos de demo

- [x] **T16 · Sembrar `catalogo` desde el Drive real de Capsulab.**
  **Verificación:** tras `supabase db reset` (usuario), `buscar_en_drive` devuelve **precios
  reales** (Modelo Cotización, Presupuesto, PROVEEDORES, PRODUCTOS LAB → `componente`; casos
  F1 → `caso`). Se extrae leyendo los archivos reales del Drive en `/implementar` (offline-safe:
  queda sembrado, sin OAuth en vivo).

## Cierre

- [x] **T17 · Suites verdes + smoke del camino feliz.**
  **Verificación:** backend y front en verde; `tsc`/lint ok; con el usuario corriendo
  servidores + `db reset`: abrir 212CH → Tipo 1 → Javo **busca en el Drive** → propone
  componentes reales con origen → fuentes visibles; en Tipo 2, "busca en internet" trae
  referencias con fuentes.
