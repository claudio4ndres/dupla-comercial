# Implementation Plan: Cobertura de tests — Chat y Propuesta

## Overview

Las suites de tests cubren los componentes `Chat.tsx` y `Propuesta.tsx` (puramente
presentacionales) y las fórmulas puras `costoLinea`/`valorVenta` de `tipos.ts`.

El ciclo es **TDD invertido**: los componentes ya existen, por lo que el primer run
debe ser **verde directamente**; si algún test falla, hay una regresión que corregir
antes de continuar.

Orden de implementación:
1. Instalar `@fast-check/vitest` + agregar script `test:coverage`
2. `tipos.test.ts` — PBT de las fórmulas puras (Properties 1, 2, 3, 5)
3. `Chat.test.tsx` — tests RTL en orden de requisitos (Req. 1–5)
4. `Propuesta.test.tsx` — tests RTL + PBT de confluencia (Req. 6–8, Property 4)

---

## Tasks

- [ ] 1. Preparar entorno de tests
  - [ ] 1.1 Instalar `@fast-check/vitest` como devDependency
    - Ejecutar `npm install -D @fast-check/vitest` en `apps/web`
    - Verificar que aparece en `devDependencies` de `apps/web/package.json`
    - _Requisitos: 9.1, 9.2, 9.3, 9.4, 9.5_
  - [ ] 1.2 Agregar script `test:coverage` al `package.json` del web
    - Añadir `"test:coverage": "vitest run --coverage"` en la sección `scripts`
    - _Requisitos: (soporte operacional — sin requisito funcional directo)_

- [ ] 2. Implementar PBT de fórmulas puras (`tipos.test.ts`)
  - [ ] 2.1 Crear `apps/web/src/tipos.test.ts` con las fixtures de generadores
    - Importar `costoLinea`, `valorVenta` y `Componente` desde `../tipos`
    - Importar `fc` desde `@fast-check/vitest` y `test` del mismo paquete
    - Definir el generador `arb_componente` con `fc.record` (campos: `nombre`,
      `detalle`, `cantidad` 1–1000, `valor` 1–10_000_000, `dias` 1–365 | undefined)
    - Definir el generador `arb_costo` con `fc.integer({ min: 0, max: 100_000_000 })`
    - _Requisitos: 9.1, 9.2, 9.3, 9.5_

  - [ ]* 2.2 Escribir test PBT: Property 1 — multiplicación exacta de `costoLinea`
    - **Property 1: Multiplicación exacta de costoLinea**
    - **Validates: Requisito 9.1**
    - `test.prop([fc.integer({min:1,max:1000}), fc.integer({min:1,max:365}), fc.integer({min:1,max:10_000_000})])`
    - Verificar: `costoLinea({ cantidad, dias, valor }) === cantidad * dias * valor`

  - [ ]* 2.3 Escribir test PBT: Property 2 — margen de venta siempre incrementa el precio
    - **Property 2: El margen de venta siempre incrementa el precio**
    - **Validates: Requisito 9.2**
    - `test.prop([arb_costo])`
    - Verificar: `valorVenta(costo) >= costo`

  - [ ]* 2.4 Escribir test PBT: Property 3 — `valorVenta` produce siempre un número entero
    - **Property 3: valorVenta produce siempre un número entero**
    - **Validates: Requisito 9.3**
    - `test.prop([arb_costo])`
    - Verificar: `Number.isInteger(valorVenta(costo)) === true`

  - [ ]* 2.5 Escribir test PBT: Property 5 — idempotencia del valor por defecto de `dias`
    - **Property 5: Idempotencia del valor por defecto de dias**
    - **Validates: Requisito 9.5**
    - `test.prop([fc.integer({min:1,max:1000}), fc.integer({min:1,max:10_000_000})])`
    - Verificar: `costoLinea({ ..., dias: undefined }) === costoLinea({ ..., dias: 1 })`

- [ ] 3. Checkpoint — Ejecutar `npm run test` en `apps/web` y verificar que todos los tests pasan.
  - Asegurarse de que los 4 tests PBT de `tipos.test.ts` son verdes.
  - Si alguno falla, hay una regresión en `tipos.ts` que corregir antes de continuar.

- [ ] 4. Implementar suite RTL de `Chat.test.tsx`
  - [ ] 4.1 Crear `apps/web/src/componentes/Chat.test.tsx` con fixtures y `BASE_PROPS`
    - Importar `render`, `screen` de `@testing-library/react`
    - Importar `userEvent` de `@testing-library/user-event`
    - Importar `vi`, `describe`, `it`, `expect` de `vitest`
    - Importar `Chat` del componente y los tipos `Solicitud`, `TipoConfirmado`,
      `Componente`, `Fuente`, `Mensaje` de `../tipos`; `RecursoDrive` de `../datosMock`
    - Definir `const noop = () => {}` y las fixtures:
      `SOLICITUD_FIXTURE`, `MENSAJES_FIXTURE`, `COMPONENTES_FIXTURE`,
      `RECURSOS_FIXTURE`, `FUENTES_FIXTURE`
    - Definir `BASE_PROPS` con todos los props del componente usando las fixtures;
      `componentes: []`, `fuentes: []`, `recursos: []`, `enviando: false` por defecto
    - _Requisitos: 1, 2, 3, 4, 5_

  - [ ]* 4.2 Escribir tests del Requisito 1 — envío de mensajes (5 criterios)
    - Test 1.1: clic en botón enviar → `onEnviar` llamado con texto sin ` 🌐`
    - Test 1.2: `Enter` envía el texto y vacía el campo (`toHaveValue('')`)
    - Test 1.3: `Shift+Enter` inserta salto de línea sin llamar a `onEnviar`
    - Test 1.4: texto vacío → `onEnviar` no se llama
    - Test 1.5 + 1.6: `enviando=true` → botón deshabilitado (`toBeDisabled`) y
      `data-testid="javo-pensando"` en el DOM (`toBeInTheDocument`)
    - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 4.3 Escribir tests del Requisito 2 — chips de acción rápida
    - Test 2.1: clic en chip → `onEnviar` llamado con texto del chip sin ` 🌐`
    - Test 2.2a: tipo `t1` muestra chips 'Son 3 días de activación',
      'Suma coordinación de producción', 'Genera la propuesta'
    - Test 2.2b: tipo `t2` muestra chips 'Busca opciones en internet',
      'Dame 3 ideas de alto impacto', 'Aterriza la idea ganadora'
    - _Requisitos: 2.1, 2.2_

  - [ ]* 4.4 Escribir tests del Requisito 3 — panel lateral de componentes
    - Test 3.1: `componentes=[]` → muestra mensaje de estado vacío del panel
    - Test 3.2: con componentes → todos los `data-testid="componente-item"` presentes
    - Test 3.3: con componentes → detalle de cada componente visible en el panel
    - Test 3.4: componente con `origen` definido → nombre del origen visible en la fila
    - Test 3.5: con componentes → costo de cada línea formateado en CLP
      (ej: `$630.000` para `COMPONENTES_FIXTURE[0]`)
    - Test 3.6: con componentes → costo total (`$1.170.000`) en la fila de resumen
    - Test 3.7: con componentes → valor venta (`$1.950.000`) en la fila de valor venta
    - _Requisitos: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 4.5 Escribir tests del Requisito 4 — fuentes citadas y recursos del Drive
    - Test 4.1: `fuentes` con elemento → panel "Fuentes citadas" visible con
      `data-testid="fuente-citada"`, mostrando `titulo` y `referencia`
    - Test 4.2: `fuentes=[]` → panel "Fuentes citadas" ausente del DOM
    - Test 4.3: `recursos` con elementos → `data-testid="recurso-drive"` visibles
    - Test 4.4: `recursos=[]` → mensaje de estado vacío del panel Recursos Drive
    - _Requisitos: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 4.6 Escribir test del Requisito 5 — botón "Generar propuesta"
    - Test 5.1: clic en `data-testid="generar-propuesta"` → `onGenerarPropuesta`
      llamado exactamente una vez (`toHaveBeenCalledOnce`)
    - _Requisitos: 5.1_

- [ ] 5. Checkpoint — Ejecutar `npm run test` en `apps/web`.
  - Todos los tests de `Chat.test.tsx` deben ser verdes.
  - Si alguno falla, identificar la regresión en `Chat.tsx` y corregirla antes
    de continuar. Los tests no se modifican para hacerlos pasar.

- [ ] 6. Implementar suite RTL + PBT de `Propuesta.test.tsx`
  - [ ] 6.1 Crear `apps/web/src/componentes/Propuesta.test.tsx` con fixtures y `BASE_PROPS`
    - Importar `render`, `screen` de `@testing-library/react`
    - Importar `userEvent` de `@testing-library/user-event`
    - Importar `vi`, `describe`, `it`, `expect` de `vitest`
    - Importar `{ test }` de `@fast-check/vitest` y `fc` del mismo paquete
    - Importar `Propuesta` del componente y `Componente` de `../tipos`
    - Importar `Chat` del componente (para la Property 4 de confluencia)
    - Reutilizar las mismas fixtures: `COMPONENTES_FIXTURE` (con los cálculos
      anotados en comentarios), `COMPONENTE_SIN_DIAS`
    - Definir el generador `arb_componente` igual al de `tipos.test.ts` para la PBT
    - Definir `BASE_PROPUESTA_PROPS` con `onVolver: noop`, `onArmarTareas: noop`,
      `onExportarExcel: noop`, `onExportarPpt: noop`
    - _Requisitos: 6, 7, 8, 9.4_

  - [ ]* 6.2 Escribir tests del Requisito 6 — tabla de componentes valorizados
    - Test 6.1: una fila por componente con nombre, detalle, cantidad, días, valor/día y costo
    - Test 6.2: componente con `dias` definido → muestra el valor de `dias` en la columna
    - Test 6.3: componente sin `dias` → muestra `1` en la columna de días
    - Test 6.4: costo de fila = `cantidad × (dias ?? 1) × valor` formateado en CLP
    - Test 6.5: componente con `proveedor` → nombre del proveedor visible en la fila
    - Test 6.6: componente sin `proveedor` → badge de proveedor ausente del DOM
    - _Requisitos: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 6.3 Escribir tests del Requisito 7 — totales
    - Test 7.1: costo total = suma de `costoLinea(c)` para todos los componentes,
      formateado en CLP (`$1.170.000`)
    - Test 7.2: valor venta = `Math.round(costoTotal / 0.6)` formateado en CLP
      (`$1.950.000`)
    - Test 7.3: cabecera de la fila de valor venta muestra `40%`
    - _Requisitos: 7.1, 7.2, 7.3_

  - [ ]* 6.4 Escribir tests del Requisito 8 — botones de exportación y acción
    - Test 8.1: clic en "Armar tareas ▸" → `onArmarTareas` llamado una vez
    - Test 8.2: clic en "⤓ Excel interno" → `onExportarExcel` llamado con `'interno'`
    - Test 8.3: clic en "⤓ Excel cliente" → `onExportarExcel` llamado con `'cliente'`
    - Test 8.4: clic en "⤓ PPT" → `onExportarPpt` llamado exactamente una vez
    - Usar `getByRole('button', { name: /…/ })` para los botones (sin `data-testid`)
    - _Requisitos: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 6.5 Escribir test PBT: Property 4 — confluencia Chat–Propuesta en el costo total
    - **Property 4: Confluencia Chat–Propuesta en el costo total**
    - **Validates: Requisito 9.4**
    - `test.prop([fc.array(arb_componente, { minLength: 1, maxLength: 20 })])`
    - Renderizar `Chat` con esos componentes, capturar el texto del costo total
      desde `data-testid="componente-item"` y la fila de resumen del panel lateral
    - Desmontar Chat, renderizar `Propuesta` con los mismos componentes
    - Verificar que el texto del costo total en la fila "Costo total" de `Propuesta`
      es textualmente idéntico al capturado de `Chat`
    - _Nota: requiere `BASE_CHAT_PROPS` adicional con las props de `Chat`_

- [ ] 7. Checkpoint final — Ejecutar `npm run test` en `apps/web`.
  - Todos los tests de `tipos.test.ts`, `Chat.test.tsx` y `Propuesta.test.tsx`
    deben ser verdes.
  - Si alguno falla, corregir la regresión en el componente o fórmula correspondiente.
  - La suite de tests no se modifica para hacer pasar los tests.

---

## Notes

- Las tareas marcadas con `*` son tests opcionales; sin embargo, en este feature
  **todos son el objetivo principal** — son la feature completa, no tests de soporte.
- El ciclo TDD es invertido: componentes ya existen → primer run verde es lo esperado;
  fallo = regresión que corregir.
- Los selectores siguen el orden preferido del diseño: `getByTestId` → `getByRole` →
  `getByText`. Nunca por clase CSS.
- `@fast-check/vitest` expone `test.prop([...arbitraries])` directamente; no hay que
  envolver con `fc.assert(fc.property(...))`.
- La Property 4 (confluencia) requiere importar tanto `Chat` como `Propuesta` en
  `Propuesta.test.tsx`; esto es intencional.
- Commits en español según las reglas de oro del proyecto.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5"] },
    { "id": 3, "tasks": ["4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "4.4", "4.5", "4.6"] },
    { "id": 5, "tasks": ["6.1"] },
    { "id": 6, "tasks": ["6.2", "6.3", "6.4", "6.5"] }
  ]
}
```
