# Spec 001 · Clasificación y resumen de solicitudes

- **Estado:** aprobada
- **Tipo:** full-stack (datos + backend + frontend)
- **Relacionada con:** flujo de bandeja → leer correo → clasificar Tipo 1 / Tipo 2

## 1. Problema y por qué
Cuando llega un correo, Javo necesita revisarlo rápido sin perder el criterio
creativo. El sistema debe entregar un **resumen** del correo y una **sugerencia
de tipo** (Tipo 1 cotización concreta / Tipo 2 ideas), pero la decisión final del
tipo la toma el humano. Esto evita perder oportunidades por una interpretación
automática equivocada.

## 2. Usuarios y contexto
Javo (gestor), en la pantalla de la solicitud, justo después de abrir un correo
de la bandeja.

## 3. Alcance
**Incluye:**
- Generar un resumen del correo (4–5 puntos clave) con Claude Haiku 4.5.
- Sugerir el tipo (tipo_1 / tipo_2) con Haiku 4.5.
- Guardar `resumen` y `tipo` (sugerido) en la tabla `solicitudes`.
- Mostrar resumen + botón "Ver correo completo" + sugerencia de tipo en el front.

**No incluye:**
- La conversación con Javo (spec aparte).
- La búsqueda en internet (spec aparte).

## 4. Criterios de aceptación (de aquí salen los tests)
- **CA1** — Dado un correo con cuerpo de texto, Cuando se solicita el resumen,
  Entonces el backend devuelve `resumen` (texto no vacío) y `tipo` ∈
  {tipo_1, tipo_2}.
- **CA2** — Dado un correo concreto de cotización (ej: sopaipillas/Metro), Cuando
  se clasifica, Entonces el tipo sugerido es `tipo_1`.
- **CA3** — Dado un correo que pide ideas (ej: Fórmula 1), Cuando se clasifica,
  Entonces el tipo sugerido es `tipo_2`.
- **CA4** — La decisión final del tipo la confirma el usuario; el sistema solo
  sugiere (el estado de la solicitud no cambia a `en_conversacion` hasta que el
  usuario elige).
- **CA5** — En los tests el SDK de Anthropic está mockeado: no se hacen llamadas
  reales ni se gastan tokens.

## 5. Consideraciones multi-tenant
La solicitud pertenece a una `empresa_id`. El endpoint solo puede resumir/clasificar
solicitudes de la empresa del usuario autenticado. **Test de RLS:** un usuario de la
empresa A recibe 404/forbidden al pedir el resumen de una solicitud de la empresa B.

## 6. Decisiones resueltas
- **Generación on-demand (no automática):** el resumen + tipo se generan cuando el GP
  abre la solicitud (endpoint `POST /solicitudes/{id}/clasificar`), no al recibir el
  correo. Razón: costo (solo se gasta Haiku en correos que el humano efectivamente
  abre) y mantiene esta spec independiente de la ingesta de Gmail (spec aparte).
  Idempotente: si la solicitud ya tiene `resumen` + `tipo`, se reutilizan sin volver
  a llamar al LLM.
