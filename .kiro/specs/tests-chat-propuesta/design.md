# Diseño técnico — Cobertura de tests: Chat y Propuesta

## Overview

Este documento describe el diseño técnico de las suites de tests para los componentes
`Chat.tsx` y `Propuesta.tsx` de Dupla Comercial.

Ambos componentes son **puramente presentacionales**: reciben props inmutables y emiten
callbacks. Eso los hace ideales para tests rápidos y deterministas. El diseño cubre:

- Tests de comportamiento de UI (RTL + `@testing-library/user-event`) para todos los
  criterios de aceptación de los requisitos 1–8.
- Tests de propiedades matemáticas (PBT con `@fast-check/vitest`) para las fórmulas
  de dominio `costoLinea` y `valorVenta` (requisito 9).
- Fixtures de datos locales en cada suite (mismo patrón que `Bandeja.test.tsx` y
  `Tareas.test.tsx`).

### Por qué separar los tests de UI de los PBT

Los tests de UI (RTL) verifican que el componente **renderiza** lo que debe. Los PBT
verifican que las **fórmulas puras** son correctas para cualquier entrada del dominio.
Mezclarlos en una sola suite obliga a generar árboles React por cada iteración (caro e
innecesario). La separación mantiene los PBT en milisegundos y los tests de UI legibles.

---

## Architecture

```
apps/web/src/componentes/
├── Chat.tsx                    (existente, sin modificar)
├── Chat.test.tsx               ← nuevo: tests RTL de Chat
├── Propuesta.tsx               (existente, sin modificar)
└── Propuesta.test.tsx          ← nuevo: tests RTL + PBT de Propuesta
                                   (los PBT de formulas van aquí o en
                                    apps/web/src/tipos.test.ts — ver decisión abajo)

apps/web/src/
└── tipos.test.ts               ← nuevo: PBT de costoLinea y valorVenta aislados
```

### Decisión: ¿dónde viven los PBT de fórmulas?

Las funciones `costoLinea` y `valorVenta` viven en `tipos.ts`, no en los componentes.
Sus tests de propiedades se ubican en `apps/web/src/tipos.test.ts` para:

1. **Cohesión**: los tests de una función viven junto al módulo que la define.
2. **Velocidad**: no hay overhead de React/jsdom para funciones puras.
3. **Separación clara**: `Chat.test.tsx` y `Propuesta.test.tsx` pueden importar las
   funciones ya verificadas como si fueran primitivas confiables.

La propiedad de confluencia (Req. 9.4) sí require renderizar ambos componentes, por lo
que reside en `Propuesta.test.tsx` (es la "verdad final" de la tabla).

---

## Components and Interfaces

### Componentes bajo prueba

#### `Chat.tsx`

```typescript
interface Props {
  solicitud: Solicitud
  tipo: TipoConfirmado          // 't1' | 't2'
  mensajes: Mensaje[]
  componentes: Componente[]
  fuentes: Fuente[]
  recursos: RecursoDrive[]
  enviando: boolean
  onEnviar: (texto: string) => void
  onGenerarPropuesta: () => void
}
```

`data-testid` disponibles en el componente (no hay que añadir ninguno):

| testid            | Elemento                                  |
|-------------------|-------------------------------------------|
| `javo-input`      | `<textarea>` del compositor               |
| `javo-enviar`     | `<button>` de enviar                      |
| `javo-pensando`   | Indicador de "typing" (dots)              |
| `javo-mensaje`    | Cada burbuja de mensaje de Javo           |
| `componente-item` | Fila de componente en el panel lateral    |
| `recurso-drive`   | Fila de archivo del Drive                 |
| `fuente-citada`   | Fila de fuente citada                     |
| `generar-propuesta` | Botón "Generar propuesta ▸"             |

#### `Propuesta.tsx`

```typescript
interface Props {
  componentes: Componente[]
  onVolver: () => void
  onArmarTareas: () => void
  onExportarExcel?: (vista: 'interno' | 'cliente') => void
  onExportarPpt?: () => void
}
```

Los botones de la tabla no tienen `data-testid`, por lo que se usan
`getByRole('button', { name: /…/ })` con los textos ya visibles.

### Fórmulas de dominio (en `tipos.ts`)

```typescript
export const MARGEN_VENTA = 0.4
export const costoLinea = (c: Componente): number =>
  c.cantidad * (c.dias ?? 1) * c.valor
export const valorVenta = (costo: number): number =>
  Math.round(costo / (1 - MARGEN_VENTA))
```

---

## Data Models

### Fixtures compartidas

Cada suite define sus propias fixtures locales (no importa de `datosMock.ts`).

#### `SOLICITUD_FIXTURE` (usada en Chat.test.tsx)

```typescript
const SOLICITUD_FIXTURE: Solicitud = {
  id: 'sol-espiga',
  remitente: 'Zona Espiga',
  correo: 'contacto@zonaespiga.cl',
  tiempo: '09:42',
  asunto: 'Cotización sampling sopaipillas — Metro',
  tipo: 't1',
  resumen: 'Sampling de sopaipillas afuera del Metro.',
  puntos: ['Activación de sampling', '5 horas diarias'],
  cuerpo: 'Hola Javo, queremos cotizar un sampling de sopaipillas.',
}
```

#### `MENSAJES_FIXTURE`

```typescript
const MENSAJES_FIXTURE: Mensaje[] = [
  { rol: 'javo', contenido: '¡Hola! Revisé el correo de Zona Espiga.' },
  { rol: 'usuario', contenido: 'Son 3 días de activación.' },
]
```

#### `COMPONENTES_FIXTURE` (usada en Chat.test.tsx y Propuesta.test.tsx)

```typescript
const COMPONENTES_FIXTURE: Componente[] = [
  {
    nombre: 'Promotoras',
    detalle: 'Promotoras uniformadas BTL',
    cantidad: 6,
    valor: 35000,
    dias: 3,
    origen: 'Tarifario BTL 2024',
    proveedor: 'Staff Eventos SpA',
  },
  {
    nombre: 'Catering sopaipillas',
    detalle: 'Sopaipillas artesanales + salsas',
    cantidad: 1,
    valor: 180000,
    dias: 3,
  },
]
// costoLinea(COMPONENTES_FIXTURE[0]) = 6 × 3 × 35000  = 630000
// costoLinea(COMPONENTES_FIXTURE[1]) = 1 × 3 × 180000 = 540000
// costoTotal                         = 630000 + 540000 = 1170000
// valorVenta(1170000)                = Math.round(1170000 / 0.6) = 1950000
```

#### `COMPONENTE_SIN_DIAS_FIXTURE`

```typescript
const COMPONENTE_SIN_DIAS: Componente = {
  nombre: 'Producto prueba',
  detalle: 'Sin días definidos',
  cantidad: 2,
  valor: 50000,
  // dias: undefined — debe comportarse como dias=1
}
// costoLinea = 2 × 1 × 50000 = 100000
```

#### `RECURSOS_FIXTURE`

```typescript
const RECURSOS_FIXTURE: RecursoDrive[] = [
  { icono: '📄', nombre: 'Tarifario BTL 2024.xlsx' },
  { icono: '📊', nombre: 'Costos Catering Q1.xlsx' },
]
```

#### `FUENTES_FIXTURE`

```typescript
const FUENTES_FIXTURE: Fuente[] = [
  { titulo: 'Precios promotoras BTL', referencia: 'staffeventos.cl/tarifas' },
]
```

---

## Correctness Properties

*Una propiedad es una característica o comportamiento que debe mantenerse verdadero
para todas las ejecuciones válidas del sistema — esencialmente, una afirmación formal
sobre lo que el sistema debe hacer. Las propiedades sirven de puente entre
especificaciones legibles por humanos y garantías de corrección verificables
automáticamente.*

Las siguientes propiedades aplican a las fórmulas puras del dominio (`costoLinea`,
`valorVenta`) y a la consistencia de los cálculos entre componentes. Se implementan con
`@fast-check/vitest` corriendo mínimo 100 iteraciones por propiedad.

> **Nota de instalación**: `@fast-check/vitest` no está aún en `package.json`.
> Debe añadirse como devDependency antes de implementar:
> ```
> npm install -D @fast-check/vitest
> ```

---

### Property 1: Multiplicación exacta de costoLinea

*Para cualquier* combinación válida de `cantidad` (1–1.000), `dias` (1–365) y
`valor` (1–10.000.000 CLP), la función `costoLinea` debe devolver exactamente
`cantidad × dias × valor` sin error de redondeo ni desbordamiento.

**Validates: Requirements 9.1**

---

### Property 2: El margen de venta siempre incrementa el precio

*Para cualquier* valor de `costo` entero no negativo (0–100.000.000 CLP),
`valorVenta(costo)` debe ser mayor o igual que `costo`.
Esto garantiza que el margen de venta (40%) nunca produce un precio de venta
inferior al costo de producción.

**Validates: Requirements 9.2**

---

### Property 3: valorVenta produce siempre un número entero

*Para cualquier* valor de `costo` entero no negativo,
`valorVenta(costo)` debe ser un número entero (`Number.isInteger` = `true`),
confirmando que `Math.round` cumple su función en la fórmula.

**Validates: Requirements 9.3**

---

### Property 4: Confluencia Chat–Propuesta en el costo total

*Para cualquier* lista no vacía de componentes válidos, el costo total que renderiza
`Chat` en su panel lateral debe ser textualmente idéntico al que renderiza `Propuesta`
en la fila "Costo total" de su tabla, usando exactamente los mismos datos de entrada.
Esto verifica que el contexto de renderizado (pantalla de chat vs. pantalla de
propuesta) no altera el cálculo.

**Validates: Requirements 9.4**

---

### Property 5: Idempotencia del valor por defecto de dias

*Para cualquier* componente con campos `cantidad` y `valor` válidos,
llamar a `costoLinea` con `dias = undefined` debe producir exactamente el mismo
resultado que llamar con `dias = 1`. Esto confirma que el operador `?? 1` en la
implementación tiene el comportamiento correcto.

**Validates: Requirements 9.5**

---

**Reflection de redundancias**: Las Properties 1 y 5 son complementarias, no
redundantes: la 1 verifica el cálculo con dias explícito, la 5 verifica el default.
Las Properties 2 y 3 cubren invariantes distintos de `valorVenta` (orden y tipo).
La Property 4 es la única que cruza componentes de UI. No hay redundancias que
eliminar.

---

## Error Handling

Los componentes `Chat` y `Propuesta` son puramente presentacionales y no tienen manejo
de errores propio. Los únicos "errores" que deben verificarse son:

| Situación | Comportamiento esperado | Test |
|-----------|------------------------|------|
| `texto` vacío al enviar | `onEnviar` no se llama | Edge case 1.4 |
| `texto` solo espacios al enviar | `onEnviar` no se llama | Edge case 1.4 |
| `componentes = []` | Muestra estado vacío, no falla | Example 3.1 |
| `fuentes = []` | Oculta el panel, no falla | Edge case 4.2 |
| `recursos = []` | Muestra estado vacío, no falla | Edge case 4.4 |
| `Shift+Enter` en textarea | Inserta `\n`, no envía | Example 1.3 |

No se necesita `vi.stubGlobal('fetch', …)` en ninguna de estas suites porque ambos
componentes son 100% presentacionales (sin llamadas a red).

---

## Testing Strategy

### Stack

| Herramienta | Versión actual | Uso |
|-------------|---------------|-----|
| `vitest` | 4.x | Runner principal |
| `@testing-library/react` | 16.x | Render y queries de DOM |
| `@testing-library/user-event` | 14.x | Simulación de interacciones |
| `@testing-library/jest-dom` | 6.x | Matchers (`toBeInTheDocument`, etc.) |
| `@fast-check/vitest` | *pendiente instalar* | PBT de fórmulas puras |
| `jsdom` | 29.x | Entorno DOM para vitest |

### Estructura de archivos

```
apps/web/src/
├── tipos.test.ts                   ← PBT: costoLinea + valorVenta (Properties 1–3, 5)
└── componentes/
    ├── Chat.test.tsx               ← RTL: Req 1, 2, 3, 4, 5
    └── Propuesta.test.tsx          ← RTL: Req 6, 7, 8 + PBT Property 4
```

### Enfoque de tests por ejemplo (RTL)

- **Selectores preferidos** (en orden): `getByTestId`, `getByRole`, `getByText`.
  Nunca por clase CSS.
- **userEvent sobre fireEvent**: `userEvent.setup()` simula eventos reales del browser
  (incluyendo focus, composición, etc.).
- **Fixtures locales**: Cada archivo define sus propias constantes en el encabezado,
  sin importar de `datosMock.ts` (patrón establecido en `Bandeja.test.tsx`).
- **noop**: Callbacks que no se verifican en un test específico se pasan como
  `const noop = () => {}`.
- **vi.fn()**: Callbacks que sí se verifican se crean con `vi.fn()` y se inspeccionan
  con `toHaveBeenCalledWith` / `toHaveBeenCalledOnce`.

### Enfoque PBT con @fast-check/vitest

- **Generadores** usados en las propiedades:

```typescript
// Componente arbitrario
const arb_componente = fc.record({
  nombre:   fc.string({ minLength: 1, maxLength: 50 }),
  detalle:  fc.string({ minLength: 0, maxLength: 100 }),
  cantidad: fc.integer({ min: 1, max: 1000 }),
  valor:    fc.integer({ min: 1, max: 10_000_000 }),
  dias:     fc.option(fc.integer({ min: 1, max: 365 }), { nil: undefined }),
})

// Lista no vacía de componentes
const arb_componentes = fc.array(arb_componente, { minLength: 1, maxLength: 20 })

// Costo arbitrario
const arb_costo = fc.integer({ min: 0, max: 100_000_000 })
```

- **Configuración de iteraciones**: Mínimo 100 por defecto de fast-check. Sin cambio.
- **Tag de referencia en cada test**:
  ```
  // Feature: tests-chat-propuesta, Property N: <texto de la propiedad>
  ```
- **Un test por propiedad**: Cada propiedad del diseño tiene exactamente un test PBT.

### Código propuesto de tests clave

#### Chat.test.tsx — envío con botón (Req. 1.1)

```typescript
it('al hacer clic en enviar, llama a onEnviar con el texto limpio (sin " 🌐")', async () => {
  const user = userEvent.setup()
  const onEnviar = vi.fn()
  render(
    <Chat
      {...BASE_PROPS}
      onEnviar={onEnviar}
    />,
  )
  const input = screen.getByTestId('javo-input')
  await user.type(input, 'Busca opciones en internet 🌐')
  await user.click(screen.getByTestId('javo-enviar'))
  expect(onEnviar).toHaveBeenCalledWith('Busca opciones en internet')
})
```

#### Chat.test.tsx — Enter envía y vacía el campo (Req. 1.2)

```typescript
it('Enter envía el texto y deja el campo vacío', async () => {
  const user = userEvent.setup()
  const onEnviar = vi.fn()
  render(<Chat {...BASE_PROPS} onEnviar={onEnviar} />)
  const input = screen.getByTestId('javo-input')
  await user.type(input, 'Hola Javo')
  await user.keyboard('{Enter}')
  expect(onEnviar).toHaveBeenCalledWith('Hola Javo')
  expect(input).toHaveValue('')
})
```

#### Chat.test.tsx — Shift+Enter NO envía (Req. 1.3)

```typescript
it('Shift+Enter inserta salto de línea sin enviar', async () => {
  const user = userEvent.setup()
  const onEnviar = vi.fn()
  render(<Chat {...BASE_PROPS} onEnviar={onEnviar} />)
  const input = screen.getByTestId('javo-input')
  await user.type(input, 'Primera línea')
  await user.keyboard('{Shift>}{Enter}{/Shift}')
  expect(onEnviar).not.toHaveBeenCalled()
})
```

#### Chat.test.tsx — enviando deshabilita el botón y muestra indicador (Req. 1.5, 1.6)

```typescript
it('cuando enviando=true, el botón está deshabilitado y aparece el indicador de escritura', () => {
  render(<Chat {...BASE_PROPS} enviando={true} />)
  expect(screen.getByTestId('javo-enviar')).toBeDisabled()
  expect(screen.getByTestId('javo-pensando')).toBeInTheDocument()
})
```

#### Chat.test.tsx — chips de tipo t1 y t2 (Req. 2.2)

```typescript
it('muestra los chips de Tipo 1 para solicitud t1', () => {
  render(<Chat {...BASE_PROPS} tipo="t1" />)
  expect(screen.getByText('Son 3 días de activación')).toBeInTheDocument()
  expect(screen.getByText('Suma coordinación de producción')).toBeInTheDocument()
  expect(screen.getByText('Genera la propuesta')).toBeInTheDocument()
})

it('muestra los chips de Tipo 2 para solicitud t2', () => {
  render(<Chat {...BASE_PROPS} tipo="t2" />)
  expect(screen.getByText(/Busca opciones en internet/i)).toBeInTheDocument()
  expect(screen.getByText('Dame 3 ideas de alto impacto')).toBeInTheDocument()
  expect(screen.getByText('Aterriza la idea ganadora')).toBeInTheDocument()
})
```

#### Propuesta.test.tsx — costo total y valor venta (Req. 7.1, 7.2)

```typescript
it('muestra el costo total y el valor venta calculados correctamente', () => {
  render(<Propuesta {...BASE_PROPUESTA_PROPS} componentes={COMPONENTES_FIXTURE} />)
  // costoTotal = 630000 + 540000 = 1170000
  expect(screen.getByText('$1.170.000')).toBeInTheDocument()
  // valorVenta = Math.round(1170000 / 0.6) = 1950000
  expect(screen.getByText('$1.950.000')).toBeInTheDocument()
})
```

#### tipos.test.ts — PBT Property 1: costoLinea es multiplicación exacta

```typescript
// Feature: tests-chat-propuesta, Property 1: Multiplicación exacta de costoLinea
test.prop([
  fc.integer({ min: 1, max: 1000 }),
  fc.integer({ min: 1, max: 365 }),
  fc.integer({ min: 1, max: 10_000_000 }),
])('costoLinea(c) === cantidad × dias × valor para cualquier entrada válida',
  (cantidad, dias, valor) => {
    const c: Componente = { nombre: 'test', detalle: '', cantidad, valor, dias }
    expect(costoLinea(c)).toBe(cantidad * dias * valor)
  },
)
```

#### tipos.test.ts — PBT Property 2: valorVenta siempre es >= costo

```typescript
// Feature: tests-chat-propuesta, Property 2: El margen de venta siempre incrementa el precio
test.prop([fc.integer({ min: 0, max: 100_000_000 })])(
  'valorVenta(costo) >= costo para cualquier costo no negativo',
  (costo) => {
    expect(valorVenta(costo)).toBeGreaterThanOrEqual(costo)
  },
)
```

#### tipos.test.ts — PBT Property 5: idempotencia de dias=undefined

```typescript
// Feature: tests-chat-propuesta, Property 5: Idempotencia del valor por defecto de dias
test.prop([
  fc.integer({ min: 1, max: 1000 }),
  fc.integer({ min: 1, max: 10_000_000 }),
])(
  'costoLinea con dias=undefined produce el mismo resultado que con dias=1',
  (cantidad, valor) => {
    const sinDias: Componente = { nombre: 'x', detalle: '', cantidad, valor }
    const conUnDia: Componente = { nombre: 'x', detalle: '', cantidad, valor, dias: 1 }
    expect(costoLinea(sinDias)).toBe(costoLinea(conUnDia))
  },
)
```

#### Propuesta.test.tsx — PBT Property 4: confluencia Chat–Propuesta

```typescript
// Feature: tests-chat-propuesta, Property 4: Confluencia Chat–Propuesta en el costo total
test.prop([fc.array(arb_componente, { minLength: 1, maxLength: 20 })])(
  'el costo total es el mismo en Chat y en Propuesta para cualquier lista de componentes',
  (componentes) => {
    const { unmount: unmountChat } = render(<Chat {...BASE_CHAT_PROPS} componentes={componentes} />)
    const costoEnChat = screen.getByText(/Costo total/)
      .closest('.comp-row')!
      .querySelector('.val')!.textContent

    unmountChat()

    render(<Propuesta {...BASE_PROPUESTA_PROPS} componentes={componentes} />)
    const costoEnPropuesta = screen.getByText('Costo total')
      .closest('tr')!
      .querySelector('td:last-child')!.textContent

    expect(costoEnChat).toBe(costoEnPropuesta)
  },
)
```

### Cobertura esperada

| Archivo | Suites | Tests RTL | Tests PBT | Requisitos cubiertos |
|---------|--------|-----------|-----------|---------------------|
| `tipos.test.ts` | 1 | 0 | 4 | Req. 9.1, 9.2, 9.3, 9.5 |
| `Chat.test.tsx` | 5 | ~16 | 0 | Req. 1, 2, 3, 4, 5 |
| `Propuesta.test.tsx` | 4 | ~12 | 1 | Req. 6, 7, 8, 9.4 |

### Principios de diseño de los tests

1. **Tests atómicos**: un comportamiento por test. Si falla, el nombre del test dice
   exactamente qué rompió.
2. **Sin implementación en los tests**: los tests solo llaman API pública (props y
   `data-testid`). No acceden a estado interno ni a refs.
3. **Sin red**: `Chat` y `Propuesta` no hacen fetch; no se necesita `vi.stubGlobal`.
4. **Ciclo TDD**: primero el test en rojo, luego el código que lo hace verde. Como los
   componentes ya existen, el primer run de los tests debería ser verde directamente;
   si no, hay una regresión que resolver antes de continuar.
5. **`BASE_PROPS` pattern**: cada suite define un objeto `BASE_PROPS` con valores por
   defecto válidos, y cada test solo sobreescribe lo que varía. Reduce el ruido en los
   assertions y facilita añadir tests nuevos.

```typescript
// Ejemplo de BASE_PROPS en Chat.test.tsx
const BASE_PROPS = {
  solicitud: SOLICITUD_FIXTURE,
  tipo: 't1' as TipoConfirmado,
  mensajes: MENSAJES_FIXTURE,
  componentes: [],
  fuentes: [],
  recursos: [],
  enviando: false,
  onEnviar: noop,
  onGenerarPropuesta: noop,
}
```
