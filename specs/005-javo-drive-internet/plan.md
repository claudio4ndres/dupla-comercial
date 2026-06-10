# Plan técnico · Spec 005 · Javo agente (Drive + internet)

- **Estado:** borrador
- **Spec:** `specs/005-javo-drive-internet/spec.md`

> Resuelve el CÓMO. El QUÉ/POR QUÉ está en la spec. Regla de oro #3: el LLM se
> llama **solo desde el backend**.

## 1. Arquitectura (capas que toca)

**Full-stack.** Javo pasa de "una sola llamada a Sonnet" (spec 003) a un **agente con
herramientas** (manual tool-use loop) ejecutado en el backend.

```
Front (Chat)
  └─ POST /conversaciones/responder  (ahora con JWT → empresa)
        └─ servicio responder_javo  (loop de tool-use con Sonnet)
              ├─ tool buscar_en_drive    → RepositorioCatalogo (Supabase + RLS)
              ├─ tool buscar_en_internet → ProveedorBusqueda (gateado, con fuentes)
              └─ tool proponer_componentes → captura estructurada (no persiste)
        ⇐ { texto, componentes?, fuentes? }
  └─ pinta texto + panel lateral (componentes con origen) + fuentes
```

- **Backend (FastAPI):** el corazón. El cliente Anthropic actual **ya soporta tools**
  (pasa `tools`/`tool_choice` y expone `stop_reason` + bloques `tool_use`), así que **no
  se modifica**; el loop vive en el servicio `javo.py`.
- **Datos (Supabase):** **nueva tabla `catalogo`** (en español, con `empresa_id` + RLS)
  que representa, de forma **compacta**, los precios/recursos del Drive. Para la demo se
  **siembra** desde los archivos reales del Drive de Capsulab.
- **Front (Vite/React):** la respuesta de Javo se enriquece (componentes + fuentes); el
  panel lateral del chat muestra los componentes propuestos (con su origen) y las fuentes.

## 2. Contratos de API

### `POST /conversaciones/responder` (se extiende; ahora **requiere auth**)
Antes era sin estado y sin auth (spec 003 §3). Ahora Javo consulta el **catálogo de la
empresa** vía RLS, así que necesita el **JWT** (la empresa se resuelve del token, nunca
del front). El puente `VITE_DEV_JWT` ya lo envía.

**Request** (igual que hoy + nada nuevo obligatorio):
```json
{ "tipo": "t1" | "t2",
  "mensajes": [ { "rol": "usuario"|"javo"|"sistema", "contenido": "..." } ],
  "solicitud_id": "uuid-opcional" }
```

**Response** (extendida):
```json
{
  "texto": "respuesta de Javo",
  "componentes": [
    { "nombre": "Promotoras", "detalle": "...", "cantidad": 6,
      "valor_unitario": 240000, "origen": "Tarifario_promotores_2026.xlsx" }
  ],
  "fuentes": [
    { "titulo": "Modelo Cotización", "referencia": "drive: Modelo Cotización.xlsx" },
    { "titulo": "Caso F1 Red Bull", "referencia": "https://…" }
  ]
}
```
- `componentes` y `fuentes` son **opcionales** (solo cuando Javo propuso/citó algo).
- `componentes` **no se persisten** aquí (CA10): es lo que el GP confirmará y, al "Generar
  propuesta", tomará la spec 004.

**Errores:** `401` sin token · `502` si el LLM o una herramienta externa falla (el front
ya cae a su respuesta offline) · loop **acotado** (máx. iteraciones) para no colgarse.

### Herramientas que recibe Sonnet (definidas en el backend)
| Herramienta | Input | Qué hace el backend | Disponible |
|---|---|---|---|
| `buscar_en_drive` | `{ consulta, tipo? }` | Busca en `catalogo` de la empresa (RLS); devuelve **extractos** (filas), no archivos | Siempre |
| `buscar_en_internet` | `{ consulta }` | Llama al `ProveedorBusqueda`; devuelve resultados **con fuentes** | **Solo Tipo 2 y solo si el GP lo pidió**; tope ~3–5 usos |
| `proponer_componentes` | `{ componentes: [...] }` | **Captura** la cotización propuesta (no persiste) → va en `componentes` de la respuesta | Tipo 1 |

## 3. Datos (migración nueva + RLS)

**Nueva migración `supabase/migrations/0003_catalogo.sql`** (todo en español):

```sql
create table catalogo (
  id             uuid primary key default gen_random_uuid(),
  empresa_id     uuid not null references empresas(id) on delete cascade,
  tipo           text not null check (tipo in ('componente','caso')),
  nombre         text not null,
  detalle        text,
  unidad         text,                 -- 'jornada' | 'día' | 'unidad' (componentes)
  valor_unitario numeric(12,2),        -- nullable (los 'caso' no tienen precio)
  proveedor      text,
  origen         text,                 -- recurso del Drive de donde salió
  creado_en      timestamptz not null default now()
);

alter table catalogo enable row level security;
create policy cat_empresa on catalogo
  for all using (empresa_id = empresa_actual())
  with check (empresa_id = empresa_actual());
create index idx_catalogo_empresa on catalogo(empresa_id);
```
- **Búsqueda:** empezar con `ILIKE` sobre `nombre`/`detalle` (PostgREST `or=(...)`); si
  crece, migrar a `pg_trgm`/`tsvector` (no cambia el contrato).
- **Seed:** extender `supabase/seed.sql` con filas de `catalogo` para Capsulab,
  **pre-extraídas del Drive real** (Modelo Cotización, Presupuesto, PROVEEDORES, PRODUCTOS
  LAB → `componente`; casos como F1 → `caso`). Se poblará en `/implementar` leyendo los
  archivos reales.

**Repositorios (patrón ya usado en el proyecto):**
- `repositorios/catalogo.py`: `Protocol RepositorioCatalogo.buscar(consulta, empresa_id, tipo?, limite)` + doble **en memoria** (emula RLS por empresa).
- `repositorios/catalogo_supabase.py`: PostgREST con **JWT del usuario** (RLS), httpx inyectable.
- `dependencias.py`: `obtener_repositorio_catalogo` (por request, con el JWT).

## 4. Modelo LLM y caching

- **Conversar → Sonnet** (`claude-sonnet-4-6`, regla #4). Hoy el código tiene
  `claude-sonnet-4-5`; el plan **actualiza** `MODELO_CONVERSACION` a `claude-sonnet-4-6`.
  (Clasificar/resumir sigue en Haiku, otra spec.)
- **Prompt caching:** `system` = persona + guía del tipo, con `cache_control: ephemeral`
  (ya existe). Las **definiciones de tools** se renderizan antes del `system` y quedan
  cacheadas: mantenerlas **deterministas** (orden fijo) para no romper la caché.
- **Loop de tool-use (manual):** `create` → si `stop_reason == "tool_use"`: ejecutar cada
  bloque, anexar `assistant`(tool_use) + `user`(tool_result), repetir; si `end_turn`:
  extraer texto + `componentes`/`fuentes` capturados. **Tope de iteraciones** y **tope de
  usos de internet** para acotar costo (~$0,02–0,03 por búsqueda, ya estimado).
- **Gating de internet:** el backend ofrece `buscar_en_internet` **solo** en Tipo 2 y
  **solo** si el último turno del GP lo pide (detección de intención); además, contador con
  tope por llamada.

## 5. Estrategia de pruebas (TDD)

Todo con dobles: **Anthropic, Drive/catálogo e internet NUNCA se llaman de verdad** (CA4).

| Capa | Test | Mockea |
|---|---|---|
| Repo catálogo Supabase | `test_repo_catalogo_supabase.py`: manda JWT, pega a `/rest/v1/catalogo`, filtra `ILIKE`, mapea filas; sin filas → `[]` | transporte httpx |
| Repo catálogo memoria | filtra por empresa + texto (emula RLS) | — |
| Servicio `responder_javo` | `test_javo_agente.py`: **CA1** (usa valor real del Drive), **CA2** (no inventa si no hay match), **CA3** (internet solo si se pide), **CA10** (captura `proponer_componentes`), **CA11** (tope de búsquedas), **CA6** (fuentes en la respuesta), loop acotado | cliente Anthropic (scripted tool_use→end_turn) + repo catálogo + proveedor internet |
| Endpoint | `test_endpoint_conversacion.py`: 200 con `texto`+`componentes`+`fuentes`; **401** sin token; **502** si el LLM cae | repo + cliente + empresa (overrides) |
| RLS | `supabase/tests/rls_catalogo.test.sql` (pgTAP): empresa A no ve catálogo de B (**CA5**) | — (DB local) |
| Front | `api/javo.test.ts` (parsea `texto`/`componentes`/`fuentes`); `App.test.tsx`: panel muestra componentes reales con origen; pedir "busca en internet" muestra fuentes; **sin** pedirlo, no busca (**CA3/CA7**) | `fetch` |

Ciclo por tarea: 🔴 test que falla → 🟢 mínimo código → ♻️ refactor → commit en español.

## 6. Riesgos y decisiones abiertas

- **Proveedor de internet.** `ProveedorBusqueda` es **pluggable**. Default para la demo:
  un proveedor **curado/stub** (devuelve referencias realistas con fuentes) → gating, tope
  y fuentes son **reales** sin depender de una API de búsqueda. Producción: Anthropic
  `web_search` (trae citaciones) o una API externa. *(Decisión de implementación, no bloquea.)*
- **`proponer_componentes` como tercer tool.** Es la forma limpia de que Javo entregue
  componentes **estructurados** sin perder el texto del chat (y sin persistir, CA10).
  Alternativa futura: `output_config.format`. Se mantiene el tool por claridad.
- **Tope de internet "por conversación".** El endpoint es sin estado; por ahora el tope es
  **por llamada** (más el gating). Un tope por conversación real requeriría estado/contador
  persistido (se evalúa después).
- **Gating por intención** (heurística sobre el último turno) puede fallar en bordes; es
  aceptable para el MVP y mejorable con una señal explícita desde el front.
- **Cambio de modelo a `claude-sonnet-4-6`** invalida la caché previa (esperado) y alinea
  con la regla #4.
- **Auth en `/conversaciones/responder`.** Pasa de "sin auth" (003) a requerir JWT (por el
  Drive multi-tenant). El puente dev ya lo cubre; documentar el cambio.
- **Tamaño de extractos (CA8).** El repo limita columnas/filas devueltas para no inflar el
  contexto (costo) ni volcar archivos enteros.
