# Spec 012 · Resiliencia del cliente LLM (reintentos con backoff)

- **Estado:** aprobada
- **Tipo:** backend
- **Relacionada con:** conversación con Javo / clasificación / chips (todo lo que llama a Claude)

## 1. Problema y por qué

Hoy una sola respuesta 429 (rate limit) o 529 (sobrecarga) de la API de Anthropic
tumba la operación completa: el chat de Javo devuelve 502, el clasificador deja la
solicitud `sin_clasificar` y los chips caen al fallback estático. Son errores
**transitorios** que se resuelven reintentando segundos después; hacer que el
usuario reintente a mano (o esperar al reproceso) es mala experiencia y hace ver
al producto como inestable, justo en su función principal.

## 2. Usuarios y contexto

Invisible para el usuario final: beneficia a todo el que conversa con Javo, a la
clasificación automática del poller y a los chips de sugerencias. No hay UI nueva.

## 3. Alcance

**Incluye:**
- Reintentos automáticos con espera exponencial + jitter en `ClienteAnthropicHttpx`
  ante errores transitorios (429, 500, 529, 408 y fallos de red/timeout).
- Respetar el header `Retry-After` cuando la API lo indique.
- Interfaz pública sin cambios: `cliente.messages.create(**payload)`.

**No incluye (fuera de alcance):**
- Reintentos en las APIs de Google/ClickUp (otra spec).
- Colas/reintentos persistentes entre requests.
- Cambiar de modelo ante sobrecarga (fallback de modelo).

## 4. Criterios de aceptación (de aquí salen los tests)

- **CA1** — Dado que la API responde 429 con `Retry-After` y luego 200, Cuando se
  llama `messages.create`, Entonces devuelve la respuesta exitosa y se hicieron
  exactamente 2 peticiones, esperando lo indicado por `Retry-After`.
- **CA2** — Dado que la API responde 529 en todos los intentos, Cuando se agotan
  los reintentos, Entonces se relanza `httpx.HTTPStatusError` (la ruta sigue
  devolviendo 502, contrato intacto).
- **CA3** — Dado que la API responde 400 (error del payload, no transitorio),
  Cuando se llama `messages.create`, Entonces NO se reintenta (1 sola petición).
- **CA4** — Dado un fallo de red (`ConnectError`/timeout) y luego 200, Cuando se
  llama `messages.create`, Entonces reintenta y devuelve la respuesta.
- **CA5** — Las esperas entre intentos crecen exponencialmente (base configurable)
  y en los tests no se duerme de verdad (hook `dormir` inyectable).

## 5. Consideraciones multi-tenant

No toca datos de empresa. El cliente es compartido (la API key es del producto);
el aislamiento por empresa ocurre aguas arriba.

## 6. Aclaraciones pendientes

- Ninguna.
