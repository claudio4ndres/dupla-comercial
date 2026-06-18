# Documento de Requisitos — Persistir `dias` y `proveedor` en componentes_propuesta

## Introduction

La tabla `componentes_propuesta` en Supabase no tiene las columnas `dias` ni
`proveedor`, aunque el esquema Pydantic (`ComponentePropuesto`) y el frontend
(`Componente`) sí manejan esos campos. Cuando Javo propone un componente con días
de activación o con proveedor del Drive, esa información se pierde al guardar la
propuesta, y la cotización queda incompleta.

---

## Glossary

- **componentes_propuesta**: Tabla SQL que almacena las líneas de la cotización.
  Actualmente tiene `nombre`, `detalle`, `cantidad`, `valor_unitario`.
- **dias**: Número de días de la partida. El costo de línea es `cantidad × dias × valor_unitario`.
- **proveedor**: Nombre del proveedor del catálogo del Drive (ej: "Staff Eventos SpA").
- **origen**: Nombre del archivo del Drive del que se tomó el valor (ej: "Tarifario BTL 2024.xlsx").

---

## Requirements

### Requirement 1: Migración SQL para agregar columnas faltantes

**User Story:** Como desarrollador, quiero que la tabla `componentes_propuesta`
tenga las columnas `dias`, `proveedor` y `origen`, para que la cotización guardada
refleje exactamente lo que Javo propuso.

#### Acceptance Criteria

1. THE Sistema SHALL crear la migración `supabase/migrations/XXXX_agregar_campos_componente.sql`
   que agrega a `componentes_propuesta`:
   - `dias integer not null default 1`
   - `proveedor text`
   - `origen text`
2. THE Sistema SHALL aplicar la migración sin romper datos existentes
   (columnas con `DEFAULT` son retrocompatibles).
3. WHEN se consulta `GET /solicitudes/:id/propuesta`, THE Sistema SHALL incluir
   `dias`, `proveedor` y `origen` en los componentes devueltos.

---

### Requirement 2: Actualizar esquemas Pydantic y lógica de persistencia

**User Story:** Como desarrollador, quiero que el backend persista y lea `dias`,
`proveedor` y `origen` de la base de datos, para que el ciclo completo propuesta →
guardado → lectura sea consistente.

#### Acceptance Criteria

1. THE Sistema SHALL actualizar `ComponentePropuestaSalida` en `esquemas.py` para
   incluir `dias: int = 1`, `proveedor: str | None = None`, `origen: str | None = None`.
2. WHEN el endpoint `POST /solicitudes/:id/propuesta` guarda un componente con
   `dias`, `proveedor` y `origen`, THE Sistema SHALL persistirlos en la base de datos.
3. WHEN el endpoint `GET /solicitudes/:id/propuesta` lee los componentes, THE
   Sistema SHALL devolver `dias`, `proveedor` y `origen` en la respuesta.

---

## Tasks

- [ ] 1. Crear migración SQL
  - Crear `supabase/migrations/XXXX_agregar_campos_componente.sql`
  - Agregar columnas `dias integer not null default 1`, `proveedor text`, `origen text`
  - Ejecutar `supabase db reset` en local para verificar que no rompe el esquema
  - _Requirements: 1.1, 1.2_

- [ ] 2. Actualizar `ComponentePropuestaSalida` en `esquemas.py`
  - Añadir `dias: int = 1`, `proveedor: str | None = None`, `origen: str | None = None`
  - _Requirements: 2.1_

- [ ] 3. Actualizar la lógica de INSERT en el endpoint de propuestas
  - En `rutas/propuestas.py`, asegurarse de que el INSERT incluye `dias`, `proveedor`, `origen`
  - En el SELECT/mapping de lectura, incluir las nuevas columnas
  - _Requirements: 2.2, 2.3_

- [ ] 4. Escribir tests del backend
  - Test: guardar propuesta con `dias=3`, `proveedor="Staff Eventos"` → leerla de vuelta
    y verificar que los valores coinciden
  - Test: guardar sin `proveedor` → devuelve `null` (no falla)
  - _Requirements: 2.2, 2.3_

- [ ] 5. Checkpoint — `pytest -q` en verde
  - Ejecutar la suite de tests del backend y verificar 0 fallos
