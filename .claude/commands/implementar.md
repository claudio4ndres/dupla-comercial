---
description: Ejecuta las tareas de una spec en orden, con TDD estricto (rojo→verde→refactor)
argument-hint: <NNN> (número de la spec)
---

Vas a **implementar** la spec **$ARGUMENTS** ejecutando su `tasks.md` en orden, con TDD
estricto. Lee primero `spec.md`, `plan.md` y `tasks.md` de `specs/$ARGUMENTS-*/`.

Para CADA tarea de `tasks.md`, en orden:
1. 🔴 **Rojo:** escribe el test que describe el comportamiento esperado (ligado a su
   CA). Ejecútalo y **verifica que FALLA por la razón correcta**. Muéstrame la salida.
2. 🟢 **Verde:** escribe el **mínimo** código para que pase. Ejecuta los tests: pasan.
3. ♻️ **Refactor:** limpia manteniendo los tests en verde.
4. Marca la tarea `- [x]` en `tasks.md` y propón un **commit pequeño en español** (no
   commitees sin mi confirmación, salvo que te lo haya autorizado antes).

Reglas no negociables (de CLAUDE.md):
- NUNCA código de producción sin un test que falle antes.
- El SDK de Anthropic y las APIs externas (Gmail/Drive/ClickUp) van **mockeados** en
  los tests; no se gastan tokens ni se llaman servicios reales.
- DB y código nuevo en **español**; RLS verificada si toca datos de empresa.
- Sin secretos en el repo ni en el frontend; la API key de Anthropic solo en el back.
- Enruta el modelo por costo (Haiku/Sonnet) y usa prompt caching.

Si una tarea está bloqueada (ej. falta una herramienta), detente y dímelo en vez de
saltarte el TDD. Avanza tarea por tarea; no hagas todo de un golpe sin checkpoints.
