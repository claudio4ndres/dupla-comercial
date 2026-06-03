---
description: Desglosa una spec en tareas pequeñas, test-primero, en specs/NNN-*/tasks.md
argument-hint: <NNN> (número de la spec)
---

Vas a crear la lista de **tareas** de la spec **$ARGUMENTS**.

Pasos:
1. Lee `specs/$ARGUMENTS-*/spec.md` y `plan.md`. Si falta `plan.md`, pídeme correr
   `/planificar $ARGUMENTS` primero.
2. Crea `specs/$ARGUMENTS-*/tasks.md` con una lista **ordenada y pequeña** de tareas:
   - Cada tarea es un incremento chico, idealmente un ciclo TDD completo.
   - Cada tarea **declara su test primero** (qué comportamiento se verifica, ligado a
     un CA de la spec).
   - Empieza por el arnés/scaffolding si la capa aún no existe.
   - Incluye tareas explícitas de multi-tenant/RLS si la feature toca datos de empresa.
   - Marca dependencias externas (ej. instalar Supabase CLI) como tareas propias.
3. Usa checkboxes `- [ ]` y numeración `T1, T2, …`. Todo en **español**.

Al terminar: muestra la ruta y recuérdame que el siguiente paso es
`/implementar $ARGUMENTS`.
