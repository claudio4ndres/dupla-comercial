# CLAUDE.md — Memoria del proyecto · Dupla Comercial

> Este archivo es la **memoria principal** que Claude Code lee al iniciar.
> Contiene el contexto del producto, el stack, las reglas de oro y el flujo de
> trabajo **SDD + TDD** que se debe seguir SIEMPRE.

---

## 1. Qué es Dupla Comercial

SaaS **multi-empresa (multi-tenant)** que ayuda a una agencia de marketing/BTL a
resolver las solicitudes que llegan por correo. El asistente conversacional
("Javo", con LLM de Claude) lee el correo, lo clasifica, conversa con el usuario
para dejar la **propuesta resuelta** y genera las **tareas** para el equipo.

- **Cliente piloto:** Capsulab.
- **Objetivo de negocio:** vender el producto a varias agencias; por eso cada
  empresa tiene su **espacio aislado** (datos, conversaciones, integraciones).

### Los dos tipos de solicitud (lógica central)
1. **Tipo 1 — Cotización concreta:** ya se sabe qué hacer (ej: sampling de
   sopaipillas afuera del Metro). Javo define componentes (catering, promotores,
   producto, uniforme, horas, valores) y arma la cotización.
2. **Tipo 2 — Ideas / propuesta creativa:** no hay brief cerrado (ej: campaña
   Fórmula 1). Javo propone conceptos y, **si el usuario lo pide**, busca
   referencias en internet. Luego se aterriza la idea ganadora.

Ambos tipos **siempre conversan con Javo**. La definición de componentes
**se consulta contra el Drive**. El resultado baja a propuesta → tareas (ClickUp).

---

## 2. Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | Vite + React + TypeScript + Tailwind (`apps/web`) |
| Backend | FastAPI (Python async) + SDK de Anthropic (`apps/api`) |
| Datos / Auth / Storage | Supabase (Postgres + RLS + Auth + Storage) |
| IA | Claude API: **Haiku 4.5** (clasificar/resumir) · **Sonnet 4.6** (chat) |
| Integraciones | Gmail API, Google Drive API, ClickUp API (OAuth por empresa) |
| Despliegue | Google Cloud Run (front y back) · Secret Manager para tokens |

---

## 3. Reglas de oro (NO negociables)

1. **Base de datos 100% en español.** Tablas y columnas en español
   (`empresas`, `solicitudes`, `conversaciones`, `creado_en`…). Ver
   `supabase/migrations/`. Nunca mezclar inglés.
2. **Multi-tenant por RLS.** Toda tabla de negocio lleva `empresa_id` y tiene
   políticas Row Level Security que filtran por la empresa del usuario. Jamás
   confiar en filtros hechos solo en el backend.
3. **El LLM se llama SOLO desde el backend.** Nunca exponer la API key de
   Anthropic en el frontend. El front habla con FastAPI; FastAPI habla con Claude.
4. **Enrutar modelos por costo:** Haiku 4.5 para clasificar y resumir; Sonnet 4.6
   para conversar. Usar **prompt caching** del system prompt + contexto del correo.
5. **SDD antes de código. TDD dentro del código.** (Ver sección 5.) No se escribe
   implementación sin spec aprobada ni sin test que falle primero.
6. **Comentarios y mensajes de commit en español.**

---

## 4. Estructura del repo

```
dupla-comercial/
├── CLAUDE.md                      # este archivo (memoria)
├── memory/                        # contexto extendido para Claude
│   └── contexto-producto.md
├── .claude/commands/              # comandos del flujo SDD+TDD
│   ├── especificar.md
│   ├── planificar.md
│   ├── tareas.md
│   └── implementar.md
├── specs/                         # una carpeta por feature
│   ├── PLANTILLA/spec.md
│   └── 001-clasificacion-solicitudes/spec.md
├── supabase/migrations/           # esquema SQL en español + RLS
├── apps/
│   ├── web/                       # Vite + React + TS
│   └── api/                       # FastAPI
└── packages/shared/               # tipos/contratos compartidos
```

---

## 5. Flujo de trabajo: SDD + TDD

### SDD — Desarrollo Guiado por Especificación
Para CADA feature se avanza en 4 pasos, cada uno con su comando:

1. `/especificar <feature>` → crea `specs/NNN-nombre/spec.md`
   (el QUÉ y el POR QUÉ; nada de cómo técnico todavía).
2. `/planificar NNN` → crea `plan.md` (el CÓMO: arquitectura, datos, contratos
   de API, **estrategia de pruebas**).
3. `/tareas NNN` → crea `tasks.md` (lista ordenada y pequeña; cada tarea declara
   su test primero).
4. `/implementar NNN` → ejecuta las tareas en orden, **con TDD**.

**No se salta al código sin spec + plan + tareas.** Si el usuario pide algo,
primero `/especificar`.

### TDD — Desarrollo Guiado por Pruebas
Dentro de `/implementar`, cada tarea sigue el ciclo **rojo → verde → refactor**:

1. 🔴 Escribir un test que describa el comportamiento esperado. **Ejecutarlo y
   verificar que FALLA** por la razón correcta.
2. 🟢 Escribir el mínimo código para que el test pase. Ejecutar: pasa.
3. ♻️ Refactorizar manteniendo los tests en verde.
4. Commit pequeño y descriptivo (en español).

Nunca escribir código de producción sin un test que falle antes.

---

## 6. Herramientas de prueba

- **Backend (FastAPI):** `pytest` + `httpx` para endpoints. Mockear el SDK de
  Anthropic y las APIs externas (Gmail/Drive/ClickUp) — los tests NO llaman
  servicios reales. Pruebas de RLS contra una DB de Supabase local.
- **Frontend (React):** `vitest` + `@testing-library/react`. Mockear `fetch` al
  backend.
- Apuntar a tests rápidos y deterministas. Cobertura útil > cobertura alta.

## 7. Definición de "Terminado" (Definition of Done)
- [ ] Hay spec + plan + tareas en `specs/NNN-…`.
- [ ] Todos los tests de la feature pasan (y existían antes del código).
- [ ] RLS verificada si la feature toca datos de empresa.
- [ ] Sin secretos en el repo ni en el frontend.
- [ ] Lint/format ok. Commit en español.

## 8. Comandos útiles del proyecto
```bash
# backend
cd apps/api && uvicorn main:app --reload
cd apps/api && pytest -q

# frontend
cd apps/web && npm run dev
cd apps/web && npm run test

# base de datos (Supabase local)
supabase start
supabase db reset           # aplica migrations + seed
```
