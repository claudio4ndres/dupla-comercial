---
description: Crea el plan técnico (CÓMO) de una spec en specs/NNN-*/plan.md
argument-hint: <NNN> (número de la spec)
---

Vas a crear el **plan técnico** de la spec **$ARGUMENTS** siguiendo el flujo SDD.

Pasos:
1. Localiza la carpeta `specs/$ARGUMENTS-*/` y lee su `spec.md`. Lee también
   `CLAUDE.md` (stack, reglas de oro) y el esquema en `supabase/migrations/`.
2. Si la spec tiene `[NECESITA ACLARACIÓN]` sin resolver, NO planifiques: pídeme que
   las resuelva primero (o propón una recomendación y espera mi visto bueno).
3. Crea `specs/$ARGUMENTS-*/plan.md` con el **CÓMO**:
   - Arquitectura: qué capas toca (front Vite/React, back FastAPI, datos Supabase).
     Recuerda: el LLM se llama SOLO desde el backend (Regla #3).
   - Contrato(s) de API: rutas, request/response, códigos de error.
   - Datos: ¿hace falta migración nueva en `supabase/migrations/`? Columnas/tablas
     en **español**. ¿Qué políticas RLS aplican?
   - Modelo LLM: Haiku 4.5 (clasificar/resumir) o Sonnet 4.6 (conversar). Indica
     prompt caching del system + contexto.
   - **Estrategia de pruebas (TDD):** qué se testea en cada capa, qué se mockea
     (Anthropic, Gmail/Drive/ClickUp NUNCA se llaman de verdad) y los tests de RLS.
   - Riesgos y decisiones abiertas.
4. Todo en **español**. No escribas código aún.

Al terminar: muestra la ruta y recuérdame que el siguiente paso es `/tareas $ARGUMENTS`.
