# Documento de Requisitos — Cobertura de tests: Chat y Propuesta

## Introduction

Este documento especifica los requisitos de la suite de tests unitarios para los
componentes `Chat.tsx` y `Propuesta.tsx` del frontend de Dupla Comercial.

Ambos componentes son **puramente presentacionales** (sin efectos propios ni llamadas
a fetch): reciben props puras y emiten callbacks. Eso los hace ideales para tests
rápidos y deterministas con **vitest + @testing-library/react**.

El objetivo es cerrar el riesgo de regresión en el flujo core de la aplicación
(conversación → propuesta → tareas) antes de que entre el refactor de contextos (ítem 3).

### Alcance

- `apps/web/src/componentes/Chat.test.tsx` (nuevo)
- `apps/web/src/componentes/Propuesta.test.tsx` (nuevo)
- Las fórmulas de dominio (`costoLinea`, `valorVenta`) también se testean directamente
  como funciones puras usando **property-based testing** con `@fast-check/vitest`.
- Los demás componentes (`Bandeja`, `Configuracion`, `Tareas`, etc.) ya tienen
  cobertura; quedan fuera de este ítem.

---

## Glossary

- **Chat**: Componente `Chat.tsx` que muestra la conversación con Javo, el panel lateral
  de componentes/recursos/fuentes y el compositor de mensajes.
- **Propuesta**: Componente `Propuesta.tsx` que muestra la tabla de componentes
  valorizados con totales y los botones de exportación.
- **Componente** (de propuesta): Objeto `{ nombre, detalle, cantidad, valor, dias?, origen?, proveedor? }`
  que representa una partida de la cotización (promotoras, catering, producto, etc.).
- **costoLinea**: Función pura `cantidad × (dias ?? 1) × valor` (definida en `tipos.ts`).
- **valorVenta**: Función pura `Math.round(costo / (1 − MARGEN_VENTA))` con
  `MARGEN_VENTA = 0.4` (definida en `tipos.ts`).
- **MARGEN_VENTA**: Constante `0.4` (40%) que representa el margen de venta estándar.
- **Chip**: Botón de acción rápida en el compositor del Chat (ej: "Genera la propuesta").
- **Fuente**: Objeto `{ titulo, referencia }` que representa una fuente citada por Javo.
- **RecursoDrive**: Archivo del Drive de la empresa indexado en el catálogo.
- **onEnviar**: Callback del Chat que recibe el texto limpio del mensaje a enviar.
- **onGenerarPropuesta**: Callback del Chat que solicita la generación de la propuesta.
- **onArmarTareas**: Callback de Propuesta que solicita la generación de tareas.
- **onExportarExcel**: Callback de Propuesta que recibe `'interno'` o `'cliente'`.
- **onExportarPpt**: Callback de Propuesta que dispara la exportación a PPT.
- **RTL**: `@testing-library/react` — biblioteca de renderizado para tests de UI.
- **PBT**: Property-Based Testing — técnica que genera cientos de entradas aleatorias
  para verificar invariantes matemáticas del dominio.

---

## Requirements

### Requirement 1 — Envío de mensajes desde el compositor (Chat)

**User Story:** Como usuario, quiero escribir un mensaje en el textarea y
enviarlo con el botón o con la tecla Enter, para que Javo reciba el texto limpio
(sin emojis de acción).

#### Acceptance Criteria

1. WHEN el usuario escribe texto en el textarea y hace clic en el botón enviar,
   THE Chat SHALL llamar a `onEnviar` con el texto sin el sufijo ` 🌐`.

2. WHEN el usuario presiona `Enter` (sin `Shift`) estando el foco en el textarea,
   THE Chat SHALL llamar a `onEnviar` con el texto actual del campo y vaciar el campo.

3. WHEN el usuario presiona `Shift+Enter` estando el foco en el textarea,
   THE Chat SHALL insertar un salto de línea en el campo sin llamar a `onEnviar`.

4. WHEN el texto del compositor está vacío,
   THE Chat SHALL ignorar el intento de envío y no llamar a `onEnviar`.

5. WHEN `enviando` es `true`,
   THE Chat SHALL mantener el botón enviar deshabilitado (`disabled`) para que el
   usuario no pueda enviar un mensaje mientras Javo está procesando.

6. WHEN `enviando` es `true`,
   THE Chat SHALL mostrar el indicador de escritura de Javo (`data-testid="javo-pensando"`).

---

### Requirement 2 — Chips de acción rápida (Chat)

**User Story:** Como usuario, quiero clicar un chip de acción para enviar
ese texto a Javo directamente, sin tener que escribirlo.

#### Acceptance Criteria

1. WHEN el usuario hace clic en un chip,
   THE Chat SHALL llamar a `onEnviar` con el texto del chip sin el sufijo ` 🌐`.

2. THE Chat SHALL mostrar los chips correspondientes al tipo confirmado de la
   solicitud (`t1` o `t2`), de acuerdo con la constante `CHIPS` definida en el
   componente.

---

### Requirement 3 — Panel lateral: estado vacío vs. con componentes (Chat)

**User Story:** Como usuario, quiero ver el panel lateral reflejando el
estado actual de los componentes de la cotización a medida que converso con Javo.

#### Acceptance Criteria

1. WHEN `componentes` es un arreglo vacío,
   THE Chat SHALL mostrar el mensaje de estado vacío en el panel de componentes
   (texto que invite a conversar con Javo para armar la cotización).

2. WHEN `componentes` tiene al menos un elemento,
   THE Chat SHALL mostrar el nombre de cada componente (`data-testid="componente-item"`).

3. WHEN `componentes` tiene al menos un elemento,
   THE Chat SHALL mostrar el detalle de cada componente en el panel lateral.

4. WHEN un componente tiene `origen` definido,
   THE Chat SHALL mostrar el nombre del origen del Drive en la fila del componente.

5. WHEN `componentes` tiene al menos un elemento,
   THE Chat SHALL mostrar el costo de cada línea formateado en CLP, calculado como
   `costoLinea(c)` = `cantidad × (dias ?? 1) × valor`.

6. WHEN `componentes` tiene al menos un elemento,
   THE Chat SHALL mostrar el costo total (suma de todos los `costoLinea`) en la fila
   de resumen del panel lateral.

7. WHEN `componentes` tiene al menos un elemento,
   THE Chat SHALL mostrar el valor venta (`Math.round(costoTotal / (1 − 0.4))`)
   formateado en CLP en la fila de valor venta del panel lateral.

---

### Requirement 4 — Fuentes citadas y recursos del Drive (Chat)

**User Story:** Como usuario, quiero ver qué fuentes usó Javo y qué archivos
tiene indexados el Drive, para poder validar la información de la propuesta.

#### Acceptance Criteria

1. WHEN `fuentes` tiene al menos un elemento,
   THE Chat SHALL mostrar el panel "Fuentes citadas" con cada fuente
   (`data-testid="fuente-citada"`) incluyendo su `titulo` y `referencia`.

2. IF `fuentes` es un arreglo vacío,
   THEN THE Chat SHALL ocultar completamente el panel "Fuentes citadas".

3. WHEN `recursos` tiene al menos un elemento,
   THE Chat SHALL mostrar cada archivo del Drive (`data-testid="recurso-drive"`) con
   su nombre e ícono.

4. IF `recursos` es un arreglo vacío,
   THEN THE Chat SHALL mostrar el mensaje de estado vacío del panel Recursos Drive.

---

### Requirement 5 — Botón "Generar propuesta" (Chat)

**User Story:** Como usuario, quiero generar la propuesta formal a partir de
los componentes definidos en la conversación.

#### Acceptance Criteria

1. WHEN el usuario hace clic en el botón "Generar propuesta",
   THE Chat SHALL llamar a `onGenerarPropuesta` exactamente una vez.

---

### Requirement 6 — Tabla de componentes valorizados (Propuesta)

**User Story:** Como usuario, quiero ver todos los componentes de la
cotización en una tabla con sus valores calculados, para revisar la propuesta antes
de exportarla.

#### Acceptance Criteria

1. THE Propuesta SHALL renderizar una fila por cada elemento del arreglo `componentes`,
   mostrando nombre, detalle, cantidad, días, valor por día y costo de línea.

2. WHEN un componente tiene `dias` definido,
   THE Propuesta SHALL mostrar el valor de `dias` en la columna correspondiente.

3. WHEN un componente no tiene `dias` definido (`undefined`),
   THE Propuesta SHALL mostrar `1` en la columna de días (valor por defecto).

4. THE Propuesta SHALL calcular el costo de cada fila como `cantidad × (dias ?? 1) × valor`
   y mostrarlo formateado en CLP.

5. WHEN un componente tiene `proveedor` definido,
   THE Propuesta SHALL mostrar el nombre del proveedor en la fila del componente
   (como badge o texto secundario).

6. IF un componente no tiene `proveedor`,
   THEN THE Propuesta SHALL omitir el badge de proveedor en esa fila.

---

### Requirement 7 — Totales: costo total y valor venta (Propuesta)

**User Story:** Como usuario, quiero ver el costo total y el precio de venta
con margen calculados automáticamente, para conocer el precio final de la propuesta.

#### Acceptance Criteria

1. THE Propuesta SHALL calcular el costo total como la suma de `costoLinea(c)` para
   todos los componentes, y mostrarlo en la fila "Costo total" de la tabla.

2. THE Propuesta SHALL calcular el valor venta como `Math.round(costoTotal / (1 − 0.4))`
   y mostrarlo en la fila "Valor venta" de la tabla.

3. THE Propuesta SHALL mostrar en la cabecera de la fila de valor venta el porcentaje
   de margen aplicado (`40%`).

---

### Requirement 8 — Botones de exportación y acción (Propuesta)

**User Story:** Como usuario, quiero exportar la propuesta a Excel (versión
interna y versión cliente) y a PPT, además de poder iniciar la generación de tareas.

#### Acceptance Criteria

1. WHEN el usuario hace clic en "Armar tareas ▸",
   THE Propuesta SHALL llamar a `onArmarTareas` exactamente una vez.

2. WHEN el usuario hace clic en "⤓ Excel interno",
   THE Propuesta SHALL llamar a `onExportarExcel` con el argumento `'interno'`.

3. WHEN el usuario hace clic en "⤓ Excel cliente",
   THE Propuesta SHALL llamar a `onExportarExcel` con el argumento `'cliente'`.

4. WHEN el usuario hace clic en "⤓ PPT",
   THE Propuesta SHALL llamar a `onExportarPpt` exactamente una vez.

---

### Requirement 9 — Invariantes matemáticas de las fórmulas del dominio (PBT)

**User Story:** Como desarrollador, quiero garantizar que las fórmulas de
cálculo del dominio son correctas para cualquier entrada válida, para prevenir
errores de regresión en los cálculos de cotización.

#### Acceptance Criteria

1. FOR ALL valores enteros positivos de `cantidad`, `dias` y `valor`,
   THE Sistema SHALL calcular `costoLinea` como `cantidad × dias × valor` sin
   desbordamiento ni error de redondeo para valores dentro del rango de uso real
   (cantidad ≤ 1.000, dias ≤ 365, valor ≤ 10.000.000 CLP).

2. FOR ALL valores de `costo` ≥ 0 (número entero),
   THE Sistema SHALL garantizar que `valorVenta(costo) >= costo`, ya que el margen
   de venta siempre incrementa el precio (MARGEN_VENTA = 0.4 > 0).

3. FOR ALL valores de `costo` ≥ 0,
   THE Sistema SHALL garantizar que `valorVenta(costo)` es un número entero
   (resultado de `Math.round`).

4. FOR ALL listas no vacías de componentes,
   THE Sistema SHALL garantizar que el costo total que muestra `Chat` para esos
   componentes es igual al costo total que muestra `Propuesta` para los mismos
   componentes (propiedad de confluencia: el contexto de renderizado no altera el
   cálculo).

5. FOR ALL componentes con `dias = undefined`,
   THE Sistema SHALL garantizar que `costoLinea` produce el mismo resultado que
   para el mismo componente con `dias = 1` (idempotencia del valor por defecto).

---

## Notas de implementación (para el plan/diseño)

- **Patrón de fixture local:** Las suites usarán fixtures definidas localmente
  (como en `Bandeja.test.tsx` y `Tareas.test.tsx`), sin importar datos del mock global.
- **No hay fetch en estos componentes:** `Chat` y `Propuesta` son puramente
  presentacionales. No se necesita `vi.stubGlobal('fetch', …)`.
- **PBT con `@fast-check/vitest`:** Los requisitos del grupo 9 (invariantes
  matemáticas) se implementarán con `fc.property` de fast-check, que generará
  cientos de combinaciones aleatorias de entradas válidas.
- **Selectores recomendados:** Los componentes ya incluyen `data-testid` explícitos
  (`javo-input`, `javo-enviar`, `javo-pensando`, `componente-item`, `recurso-drive`,
  `fuente-citada`, `generar-propuesta`). Los tests deben priorizar estos selectores
  y `getByRole` sobre selectores frágiles por clase CSS.
- **Cobertura mínima esperada:** Todos los criterios de aceptación de este documento
  deben tener al menos un test que falle antes del código (TDD).
