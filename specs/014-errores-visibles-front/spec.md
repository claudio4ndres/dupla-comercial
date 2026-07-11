# Spec 014 · Errores visibles en el front (Javo y exports)

- **Estado:** aprobada
- **Tipo:** frontend
- **Relacionada con:** conversación con Javo / exportaciones de la propuesta

## 1. Problema y por qué

Cuando el backend cae, el front lo **disfraza**: `api/javo.ts` responde con un
texto pregrabado (Javo "contesta" con el backend muerto) y los exports devuelven
`false` sin ningún aviso. El usuario cree que todo funciona, pierde su turno de
conversación y no sabe por qué no se descargó su Excel. Un fallo debe verse y
poder reintentarse.

## 2. Usuarios y contexto

El gestor en el Chat (turno de Javo fallido) y en la Propuesta (export fallido).

## 3. Alcance

**Incluye:**
- `conversarConJavoOError`: propaga el fallo (patrón `...OError` existente);
  se elimina la respuesta pregrabada (`respuestaFallback`).
- Chat: aviso "Javo no está disponible…" + botón **Reintentar** que reenvía el
  último turno sin duplicar el mensaje del usuario.
- Exports: la Propuesta muestra un `BannerError` si la descarga falla.

**No incluye (fuera de alcance):**
- Banner de export en la pantalla Tareas (misma mejora, otra ola).
- Reintentos automáticos del front (el backoff vive en el backend, spec 012).

## 4. Criterios de aceptación (de aquí salen los tests)

- **CA1** — Dado un 502 del backend, Cuando se llama `conversarConJavoOError`,
  Entonces la promesa RECHAZA (no hay texto pregrabado).
- **CA2** — Dado un turno de Javo fallido, Cuando el usuario mira el chat,
  Entonces ve el aviso de no-disponible con botón Reintentar.
- **CA3** — Dado el aviso de fallo, Cuando el usuario pulsa Reintentar, Entonces
  se reenvía el MISMO historial (el mensaje del usuario no se duplica) y, si el
  backend responde, la conversación sigue normal.
- **CA4** — Dado un export que falla, Cuando termina, Entonces la Propuesta
  muestra un `BannerError`; si el export funciona, no hay banner.

## 5. Consideraciones multi-tenant

No cambia datos ni auth; solo presentación de errores.

## 6. Aclaraciones pendientes

- Ninguna.
