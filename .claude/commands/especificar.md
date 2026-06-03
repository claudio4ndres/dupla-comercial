---
description: Crea la especificación (QUÉ y POR QUÉ) de una feature en specs/NNN-nombre/spec.md
argument-hint: <descripción de la feature>
---

Vas a crear la **especificación** de una feature siguiendo el flujo SDD de Dupla
Comercial. Lee primero `CLAUDE.md` y `memory/contexto-producto.md` para tener el
contexto del producto.

Feature solicitada: **$ARGUMENTS**

Pasos:
1. Determina el siguiente número correlativo `NNN` mirando las carpetas de `specs/`
   (la mayor + 1, con 3 dígitos). Define un slug corto en español
   (ej. `002-conversacion-javo`).
2. Crea `specs/NNN-slug/spec.md` copiando la estructura de `specs/PLANTILLA/spec.md`.
3. Rellena SOLO el **QUÉ** y el **POR QUÉ**. Nada de cómo técnico (eso va en
   `/planificar`). En concreto:
   - Problema y por qué (necesidad real del gestor/Javo).
   - Usuarios y contexto (¿en qué pantalla / momento del flujo?).
   - Alcance: qué incluye y qué NO (deja fuera lo que sea otra spec).
   - Criterios de aceptación en formato **Dado / Cuando / Entonces**, verificables
     (de aquí saldrán los tests). Incluye siempre un CA que exija mockear el SDK de
     Anthropic y las APIs externas en los tests.
   - Consideraciones multi-tenant: qué debe garantizar la RLS (empresa A nunca ve
     datos de empresa B).
4. Marca con `[NECESITA ACLARACIÓN: …]` toda duda abierta. NO la inventes.
5. Estado inicial: `borrador`. Todo en **español**.

Al terminar: muestra la ruta del archivo y la lista de `[NECESITA ACLARACIÓN]`
pendientes, y recuérdame que el siguiente paso es `/planificar NNN` una vez resueltas.

NO escribas código ni plan técnico todavía.
