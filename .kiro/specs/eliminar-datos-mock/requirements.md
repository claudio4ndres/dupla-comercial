# Documento de Requisitos — Eliminar datosMock del Sidebar

## Introduction

El archivo `datosMock.ts` exporta `EMPRESAS`, que alimenta el `Sidebar` con datos
hardcodeados. En un sistema multi-tenant real, la lista de empresas accesibles para
un usuario debe venir del backend, no estar fija en el código del frontend.

El objetivo es eliminar `EMPRESAS` del mock como fuente de verdad para el selector
de empresa, reemplazándolo por una llamada real al backend, y reducir `datosMock.ts`
a las constantes auxiliares que aún no tienen endpoint propio (`PROVEEDORES_CORREO`,
`RecursoDrive`).

---

## Glossary

- **datosMock.ts**: Archivo de datos estáticos del frontend. Contenía fixtures de
  demo; hoy solo queda `EMPRESAS`, `PROVEEDORES_CORREO` y el tipo `RecursoDrive`.
- **EMPRESAS**: Array con un solo elemento (`Capsulab`) que se pasa al `Sidebar`
  como lista de tenants disponibles para el usuario.
- **Multi-tenant**: Arquitectura donde una misma instancia sirve a múltiples
  empresas aisladas. La empresa activa del usuario viene de su sesión en Supabase
  (`GET /empresa`).
- **GET /empresa**: Endpoint ya existente en el backend. Devuelve los datos de la
  empresa del usuario autenticado (nombre, color, plan). NO devuelve la lista de
  todas las empresas.
- **Sidebar**: Componente que muestra el selector de empresa y la navegación.
  Actualmente recibe `empresas: Empresa[]` como prop.

---

## Requirements

### Requirement 1: Empresa activa desde el backend

**User Story:** Como desarrollador, quiero que el objeto `Empresa` mostrado en
el Sidebar venga del backend (`GET /empresa`) y no del mock, para que el nombre y
color de marca sean siempre los datos reales del tenant del usuario.

#### Acceptance Criteria

1. WHEN el usuario inicia sesión, THE Sistema SHALL llamar a `obtenerEmpresa()` y
   poblar la empresa activa con la respuesta real del backend.
2. THE Sistema SHALL eliminar la dependencia del `Sidebar` de `EMPRESAS` del mock.
3. IF `obtenerEmpresa()` falla o aún no ha resuelto, THE Sistema SHALL mostrar un
   valor por defecto neutro (nombre: `''`, color de marca: `'#cccccc'`) hasta que
   llegue la respuesta.

---

### Requirement 2: Selector de empresa en el Sidebar

**User Story:** Como desarrollador, quiero simplificar el Sidebar para reflejar
que en el piloto solo hay una empresa por usuario, sin necesidad de un selector.

#### Acceptance Criteria

1. THE Sistema SHALL adaptar `Sidebar` para mostrar la empresa activa sin necesidad
   de iterar un array `empresas: Empresa[]`.
2. IF en el futuro se requiere soportar múltiples empresas por usuario, THE diseño
   SHALL documentar el punto de extensión (agregar `GET /empresas` en el backend y
   actualizar `Sidebar`).
3. THE Sistema SHALL mantener el nombre y color de marca del Sidebar sincronizados
   con los datos reales de `SesionContext` (o `App.tsx` hasta que exista el contexto).

---

### Requirement 3: Limpieza de datosMock.ts

**User Story:** Como desarrollador, quiero que `datosMock.ts` no contenga
datos de negocio activos (empresas), para que quede claro que el archivo solo
tiene constantes auxiliares de UI.

#### Acceptance Criteria

1. THE Sistema SHALL eliminar `EMPRESAS` de `datosMock.ts`.
2. THE Sistema SHALL mantener `PROVEEDORES_CORREO` y el tipo `RecursoDrive` en
   `datosMock.ts` hasta que tengan sus propios endpoints en el backend.
3. THE Sistema SHALL agregar un comentario en `datosMock.ts` indicando que
   `PROVEEDORES_CORREO` es el único dato pendiente de migrar al backend.
4. THE Sistema SHALL eliminar cualquier import de `EMPRESAS` en los archivos del
   frontend (principalmente `App.tsx`).

---

## Tasks

- [ ] 1. Eliminar `EMPRESAS` de `datosMock.ts` y su import en `App.tsx`
  - Borrar la constante `EMPRESAS` de `datosMock.ts`
  - Borrar el import `{ EMPRESAS }` en `App.tsx`
  - Añadir comentario en `datosMock.ts` indicando los datos pendientes de migrar
  - _Requirements: 3.1, 3.3, 3.4_

- [ ] 2. Adaptar `Sidebar` para recibir `empresa: Empresa` en vez de `empresas: Empresa[]`
  - Cambiar la prop `empresas: Empresa[]` por `empresa: Empresa` en la interfaz de `Sidebar`
  - Actualizar el render en `App.tsx` para pasar `empresa` (ya existe en el estado)
  - Eliminar la prop `onCambiarEmpresa` si el piloto no requiere cambio de tenant desde la UI
  - _Requirements: 2.1, 2.2_

- [ ] 3. Verificar que `obtenerEmpresa()` se llama al iniciar sesión
  - Confirmar que el efecto `useEffect([sesion])` en `App.tsx` (o `SesionContext`) ya llama
    `obtenerEmpresa()` y actualiza `empresa` con la respuesta
  - Si no existe, agregarlo
  - _Requirements: 1.1_

- [ ] 4. Checkpoint — `npm test` en verde
  - Ejecutar la suite completa y verificar 0 fallos
  - Ajustar cualquier test de `App.test.tsx` o `Sidebar` que espere `empresas: Empresa[]`
