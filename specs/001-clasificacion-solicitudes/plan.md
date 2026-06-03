# Plan 001 · Clasificación y resumen de solicitudes

- **Spec:** [spec.md](./spec.md) (estado: aprobada)
- **Decisión clave:** el resumen + tipo se generan **on-demand** cuando el GP abre la
  solicitud, no automáticamente al recibir el correo. Razón: costo (solo se gasta
  Haiku en correos que el humano abre) y mantiene esta spec independiente de la
  ingesta de Gmail (spec aparte).

## 1. Arquitectura
- El front (Vite/React) llama a FastAPI; FastAPI llama a Claude **Haiku 4.5**. La API
  key de Anthropic vive solo en el backend (Regla de oro #3).
- Endpoint nuevo: `POST /solicitudes/{id}/clasificar`
  1. Carga la solicitud (RLS la filtra por la empresa del usuario autenticado).
  2. Si ya tiene `resumen` + `tipo` ≠ `sin_clasificar` → los devuelve (idempotente,
     evita regastar tokens).
  3. Llama a Haiku con system prompt cacheado + cuerpo del correo.
  4. Persiste `resumen` y `tipo` (sugerido) en `solicitudes`. **No** cambia `estado`.
  5. Devuelve `{ resumen, tipo }`.

## 2. Contrato de API
`POST /solicitudes/{id}/clasificar`
- Auth: token de Supabase del usuario. La `empresa_id` se deriva en el backend desde
  el token, **nunca** se confía en el cliente.
- `200` → `{ "resumen": str, "tipo": "tipo_1" | "tipo_2" }`
- `404` → la solicitud no existe **o** es de otra empresa (no se distinguen, por
  privacidad multi-tenant).
- `502` → falló el proveedor LLM.

## 3. Modelo y prompts
- Modelo: `claude-haiku-4-5`.
- Salida **estructurada** vía tool use / JSON: `{ resumen, tipo }`. Validar con
  Pydantic; si `tipo` no es válido → fallback a `sin_clasificar` y que el humano elija.
- Few-shot en el system prompt: sopaipillas/Metro → `tipo_1`; Fórmula 1 → `tipo_2`.
- **Prompt caching** del bloque system (clasificador + few-shot) para abaratar.

## 4. Datos
- **Sin migración nueva.** `solicitudes.resumen` y `solicitudes.tipo` ya existen en
  `0001_esquema_inicial.sql`. `tipo` arranca en `sin_clasificar`; esta feature lo deja
  en `tipo_1`/`tipo_2` como **sugerencia**. La confirmación humana (que cambia
  `estado` a `en_conversacion`) es de otra spec.

## 5. Estrategia de pruebas (TDD)
- **Servicio** (`clasificar_solicitud`) con el SDK de Anthropic **mockeado** (CA5: cero
  llamadas reales, cero tokens). Casos CA2 (`tipo_1`) y CA3 (`tipo_2`).
- **Endpoint** (pytest + `httpx`/`TestClient`): CA1 (resumen no vacío + tipo válido),
  CA4 (`estado` sigue en `nueva`), idempotencia, 502 si el LLM falla.
- **Multi-tenant**: usuario de empresa A → `404` al clasificar solicitud de empresa B.
- **RLS en DB** (SQL contra Supabase local): empresa A no lee solicitud de empresa B.
  Requiere instalar Supabase CLI (se hace al llegar a esa tarea).
- Mock del SDK: fixture que reemplaza el cliente Anthropic por uno falso con payload
  fijo. Determinista y rápido.

## 6. Riesgos / abiertos
- **No-determinismo del LLM** → forzar JSON vía tool use + validación Pydantic con
  fallback seguro.
- **Supabase CLI no instalado** → los tests de RLS quedan marcados y se habilitan en su
  tarea (T5).
- **Auth real (Supabase JWT)** aún no montada → en T3/T4 se simula la `empresa_id` del
  usuario con una dependencia inyectable; la verificación real del JWT es de otra spec.
