# Documento de Requisitos — Cambiar `vencimiento` de `text` a `date` en tareas

## Introduction

La columna `vencimiento` en la tabla `tareas` es de tipo `text`, lo que almacena
valores como `"3 días"` o `"1 semana"` como texto libre. Esto dificulta filtros por
fecha, ordenamiento cronológico y la integración con calendarios o ClickUp (que
espera fechas ISO 8601).

---

## Glossary

- **vencimiento**: Fecha límite de una tarea. Actualmente se guarda como texto libre
  (ej: `"3 días"`, `"Viernes"`, `"2026-07-01"`). Debe ser una fecha ISO 8601 o `null`.
- **ISO 8601**: Formato de fecha estándar: `YYYY-MM-DD`. Compatible con PostgreSQL
  `date`, Python `datetime.date`, y la API de ClickUp.

---

## Requirements

### Requirement 1: Migración SQL

**User Story:** Como desarrollador, quiero que `tareas.vencimiento` sea de tipo
`date` (o `timestamptz`), para poder filtrar, ordenar y exportar fechas reales.

#### Acceptance Criteria

1. THE Sistema SHALL crear la migración que cambia `vencimiento text` a `vencimiento date`.
2. THE migración SHALL manejar los valores existentes como texto: los que sean fechas
   válidas se convierten, los que no (ej: "3 días") se ponen a `null`.
3. IF un valor de `vencimiento` existente no puede parsearse como fecha, THE migración
   SHALL dejarlo como `null` sin fallar.

---

### Requirement 2: Actualizar esquemas Pydantic y frontend

**User Story:** Como desarrollador, quiero que el backend y el frontend usen
fechas reales (string ISO 8601 o null) en lugar de texto libre para `vencimiento`.

#### Acceptance Criteria

1. THE Sistema SHALL actualizar `TareaPropuesta.plazo` y `TareaListada.vencimiento`
   en `esquemas.py` para documentar que el valor esperado es ISO 8601 o `null`.
2. THE Sistema SHALL actualizar el componente `Tareas.tsx` para mostrar la fecha
   formateada en español (ej: `"1 jul 2026"`) cuando `vencimiento` es una fecha ISO.
3. THE Sistema SHALL mantener compatibilidad con `null` (tarea sin fecha límite).
4. WHEN Javo propone una tarea en el chat, THE Sistema SHALL generar fechas en formato
   ISO 8601 en lugar de texto descriptivo como "3 días".

---

## Tasks

- [ ] 1. Crear migración SQL
  - Crear `supabase/migrations/XXXX_vencimiento_como_fecha.sql`
  - Agregar columna temporal `vencimiento_fecha date`
  - Hacer `UPDATE` convirtiendo los valores válidos: `TRY_CAST` o `CASE WHEN vencimiento ~ '^\d{4}-\d{2}-\d{2}$'`
  - Renombrar `vencimiento` a `vencimiento_texto` (backup) y `vencimiento_fecha` a `vencimiento`
  - Alternativamente: `ALTER COLUMN vencimiento TYPE date USING vencimiento::date` (falla si hay texto libre)
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 2. Actualizar esquemas Pydantic
  - Cambiar tipo de `vencimiento` a `date | None` en `TareaListada` y `TareaPropuestaSalida`
  - Actualizar el prompt del sistema de Javo para que genere fechas ISO en vez de texto descriptivo
  - _Requirements: 2.1, 2.4_

- [ ] 3. Actualizar `Tareas.tsx` para mostrar fechas formateadas
  - Crear función `fmtFecha(iso: string | null): string` que formatea la fecha en español
  - Reemplazar el render de `tarea.plazo` por `fmtFecha(tarea.plazo)`
  - _Requirements: 2.2, 2.3_

- [ ] 4. Tests del backend
  - Test: crear tarea con `vencimiento = '2026-07-01'` → leerla y verificar que devuelve la fecha
  - Test: crear tarea con `vencimiento = null` → devuelve `null`
  - _Requirements: 2.1, 2.3_

- [ ] 5. Checkpoint — `pytest -q` y `npm test` en verde
