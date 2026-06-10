# Spec 004 · Propuesta / cotización real (backend → front)

## QUÉ y POR QUÉ

Hoy las pantallas **Propuesta** y **Tareas** del front muestran datos **mock**
(`COMPONENTES_T1`/`TAREAS_T1`, las sopaipillas hardcodeadas), aunque el resto del
flujo (bandeja, detalle, chat con Javo) ya es real. Para cerrar la demo como **MVP
presentable** eliminamos ese último mock: la cotización de una solicitud
(componentes valorizados + tareas) se **lee desde la base de datos** vía la API,
con la RLS multi-tenant de siempre.

Alcance MVP: la cotización se **siembra** (como si Javo + Drive ya la hubieran
armado en la conversación); lo que se hace real ahora es el **cableado
backend→front** (endpoint + repo + cliente + render). La *generación* automática de
componentes por el LLM cruzando Drive queda fuera (post-MVP, es lo frágil para un
escenario en vivo).

## CÓMO (plan)

**Contrato API** — `GET /solicitudes/{solicitud_id}/propuesta`:
```json
{
  "id": "<uuid>",
  "total": 5190000,
  "estado": "borrador",
  "componentes": [
    {"nombre": "...", "detalle": "...", "cantidad": 6, "valor_unitario": 240000}
  ],
  "tareas": [
    {"nombre": "...", "grupo": "RRHH", "responsable": "...", "vencimiento": "3 días"}
  ]
}
```
- Multi-tenant por RLS (JWT del usuario; nunca viaja `empresa_id` en la respuesta, CA5).
- Sin propuesta para esa solicitud → **404** (el front cae a su fallback offline).

**Datos** — cadena ya existente en el esquema: `solicitud → conversacion →
propuesta → componentes_propuesta + tareas`. PostgREST con *embedding* y filtro por
la conversación de la solicitud (`conversaciones!inner(solicitud_id)`).

**Mapeo backend→front:**
| DB / API | Front (`tipos.ts`) |
|---|---|
| `componentes_propuesta.valor_unitario` | `Componente.valor` |
| `tareas.grupo` | `Tarea.area` |
| `tareas.vencimiento` | `Tarea.plazo` |

**Capas:**
- `esquemas.py`: `PropuestaDetalle` + componentes/tareas de salida.
- `repositorios/propuestas.py`: modelos `Propuesta/ComponentePropuesta/TareaPropuesta`,
  `Protocol` + doble en memoria (emula RLS por empresa).
- `repositorios/propuestas_supabase.py`: implementación PostgREST (httpx inyectable).
- `dependencias.py`: `obtener_repositorio_propuestas` (por request, con el JWT).
- `rutas/solicitudes.py`: `GET /{solicitud_id}/propuesta`.
- Front `api/propuestas.ts`: `obtenerPropuesta(solicitudId)` → `{componentes, tareas}`
  (mapea a tipos del front; error/404 → `null` → fallback mock).
- Front `App.tsx`: `generarPropuesta` async pide la cotización real; estado `tareas`.
- `supabase/seed.sql`: cotización completa de la 212CH.

## Estrategia de pruebas (TDD)

- **Repo Supabase** (`test_repo_propuestas_supabase.py`): transporte httpx mockeado;
  manda el JWT del usuario, pega a `/rest/v1/propuestas` filtrando por la solicitud,
  mapea componentes/tareas; sin filas → `None`. Cero red.
- **Endpoint** (`test_endpoint_propuesta.py`): `TestClient` + dobles en memoria;
  200 con la forma plana; **404** si no hay propuesta; aislamiento multi-tenant
  (empresa B no ve la propuesta de A); la respuesta **no** trae `empresa_id` (CA5).
- **Front** (`api/propuestas.test.ts`): mapea la respuesta del backend a los tipos
  del front; ante error/404 devuelve `null`. **App**: al generar propuesta, pinta la
  cotización del backend (no el mock).

## Tareas

1. (rojo) Tests backend repo + endpoint. → 2. (verde) esquemas + repos + dependencia + ruta.
3. (rojo) Tests front api + App. → 4. (verde) `api/propuestas.ts` + wiring en `App.tsx`.
5. Seed de la cotización de la 212CH. 6. Suites verdes (back + front).

## Fuera de alcance
Generación de componentes por el LLM (Drive), edición de la propuesta, POST/PUT,
envío real a ClickUp. Login real con Supabase Auth (spec aparte).
