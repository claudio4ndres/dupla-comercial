# Spec 013 · Javo, partner comercial

- **Estado:** aprobada
- **Tipo:** backend
- **Relacionada con:** Tipo 1 cotización / Tipo 2 ideas (conversación con Javo)

## 1. Problema y por qué

Javo hoy cotiza bien, pero se comporta como un ejecutor: espera instrucciones,
entrega una sola configuración y no conduce la venta. Un **partner comercial**
levanta el brief con las preguntas correctas, presenta opciones valorizadas,
sugiere complementos que suben el ticket con criterio y **empuja al cierre**.
Además, para precios estándar da rodeos por el Drive (2 vueltas de loop) cuando
la empresa ya tiene su tarifario sembrado en el catálogo.

## 2. Usuarios y contexto

El gestor de proyecto (GP) en la pantalla de Chat. Sin UI nueva: cambia el
comportamiento de Javo y los chips de sugerencia.

## 3. Alcance

**Incluye:**
- System prompt con 4 conductas comerciales: descubrimiento del brief BTL,
  opciones valorizadas (recomendada + alternativa), upsell con criterio y
  empuje al cierre ("¿Genero la propuesta?").
- Tool nueva `consultar_tarifario`: consulta el catálogo estructurado de la
  empresa (tabla `catalogo`, RLS) SIEMPRE — aunque haya Drive — con citas.
- Chips de sugerencia reorientados a acciones de partner comercial.

**No incluye (fuera de alcance):**
- Cambiar modelos (Sonnet 4.6 chat / Haiku 4.5 chips — regla de oro #4).
- Subir `MAX_ITERACIONES` o `TOPE_INTERNET`.
- Persistir automáticamente la propuesta (sigue confirmando el GP).

## 4. Criterios de aceptación (de aquí salen los tests)

- **CA1** — Dado el set de herramientas, Cuando se arma con o sin internet,
  Entonces `consultar_tarifario` está presente y el ORDEN de la lista es fijo
  (estabilidad del prompt caching).
- **CA2** — Dado que la empresa tiene Drive Y catálogo, Cuando Javo usa
  `consultar_tarifario`, Entonces el resultado sale del catálogo (valor real,
  citado como Fuente) sin pasar por el Drive.
- **CA3** — Dado dos turnos consecutivos del mismo tipo, Cuando se llama al LLM,
  Entonces el bloque `system` y la lista de tools son BYTE-idénticos entre
  llamadas (regresión anti-invalidadores de caché).
- **CA4** — El system prompt contiene las 4 conductas (descubrimiento con máximo
  2 preguntas por turno, opción recomendada + alternativa, upsell justificado,
  cierre con "¿Genero la propuesta?") y conserva "NUNCA inventes un precio".
- **CA5** — Dado que Haiku falla o devuelve menos de 3 líneas, Cuando se piden
  chips, Entonces el fallback ofrece acciones comerciales (opciones de
  presupuesto / upsell / cierre).

## 5. Consideraciones multi-tenant

`consultar_tarifario` consulta `repo_catalogo.buscar(consulta, empresa_id)`:
la RLS y el filtro explícito garantizan que solo ve el catálogo de SU empresa.

## 6. Aclaraciones pendientes

- Ninguna. Validación cualitativa: sesión de chat manual (checklist 🧑 en tasks).
