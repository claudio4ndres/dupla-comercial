# Spec 003 · Conversación con Javo (chat real con Claude)

- **Estado:** aprobada
- **Tipo:** backend (el front ya está cableado: `apps/web/src/api/javo.ts` llama al endpoint)
- **Relacionada con:** Tipo 1 cotización / Tipo 2 ideas — es el **corazón conversacional** del producto

## 1. Problema y por qué
La Bandeja ya ingiere correos (002) y el clasificador ya sugiere el tipo (001). Pero
la conversación con **Javo** —donde se aterriza la cotización (Tipo 1) o se proponen
conceptos (Tipo 2)— hoy está **mockeada en el front** (`respuestaFallback`). El front
ya hace `POST /conversaciones/responder`, pero ese endpoint **no existe** en el backend,
así que Javo nunca usa el LLM real. Esta spec crea ese endpoint: convierte el chat de
guion fijo en una conversación real con Claude. Es la pieza que hace que el producto
"piense".

## 2. Usuarios y contexto
El **gestor (Javo)** dentro de la pantalla *Conversación con Javo*, tras elegir el tipo
de una solicitud. Escribe mensajes y recibe respuestas del asistente, que arma
componentes (Tipo 1) o propone ideas (Tipo 2).

## 3. Alcance
**Incluye:**
- `POST /conversaciones/responder` que recibe `{ tipo, mensajes[] }` y devuelve `{ texto }`.
- Servicio puro `responder_javo(tipo, mensajes, cliente)` con **Claude Sonnet** (chat),
  *system prompt* con **prompt caching** y persona/guía según el tipo (regla #4).
- Normalización del historial al formato de Anthropic (empezar en `user`, alternar).
- Resiliencia: si el LLM cae → `502` (el front ya cae a su respuesta offline).
- Cliente Anthropic **inyectable** y **mockeado** en todos los tests (regla #3, cero red).

**No incluye (fuera de alcance):**
- Persistir la conversación en Supabase (hoy es generación sin estado; va en otra spec).
- Búsqueda real en internet (Tipo 2) y consulta real al Drive (componentes/tarifario).
- Autenticación del endpoint: mientras el login siga mock no se exige JWT; antes de
  producción se protege igual que el resto (claim `empresa_id`).

## 4. Criterios de aceptación (de aquí salen los tests)
- **CA1** — Dado un historial que parte con el intro de Javo y un mensaje del usuario,
  Cuando se llama `responder_javo('t1', …)`, Entonces se invoca al modelo **Sonnet** con
  el *system prompt* cacheado y devuelve el texto del bloque de respuesta.
- **CA2** — Dado un historial que **empieza con un mensaje de Javo** (`assistant`),
  Cuando se normaliza, Entonces los mensajes enviados a Anthropic **empiezan en `user`**
  y alternan correctamente (no se rompe la API).
- **CA3** — Dado `tipo='t2'`, Cuando responde, Entonces el *system prompt* incluye la
  guía creativa (proponer conceptos; buscar en internet **solo si lo piden**).
- **CA4** — Dado que el LLM lanza una excepción, Cuando se llama al endpoint, Entonces
  responde `502` (y nunca un 500 crudo); el front cae a su respuesta offline.
- **CA5** — Dado el endpoint `POST /conversaciones/responder` con un historial válido,
  Cuando se llama (cliente Anthropic mockeado), Entonces responde `200` con `{ texto }`.

## 5. Consideraciones multi-tenant
El endpoint **no lee ni escribe** datos de empresa (generación sin estado), por lo que no
hay superficie de cruce de tenants en esta iteración. Cuando se persista la conversación
(spec futura) se scopa por `empresa_id` vía RLS, igual que el resto.

## 6. Aclaraciones pendientes
- Id del modelo Sonnet exacto según el plan de la cuenta (constante `MODELO_CONVERSACION`,
  fácil de ajustar). En vivo, requiere `ANTHROPIC_API_KEY` en el backend (regla #3).
