// Tests RTL para el componente Propuesta (puramente presentacional).
// Cubre: tabla de componentes, totales, margen, y botones de exportación/acción.

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { Propuesta } from './Propuesta'
import type { Componente } from '../tipos'

const noop = () => {}

// --- Fixtures ----------------------------------------------------------------

const COMPONENTES_FIXTURE: Componente[] = [
  { nombre: 'Promotoras', detalle: 'Uniformadas BTL', cantidad: 6, valor: 35000, dias: 3, origen: 'Tarifario BTL 2024', proveedor: 'Staff Eventos' },
  { nombre: 'Catering', detalle: 'Sopaipillas', cantidad: 1, valor: 180000, dias: 3 },
]
// costoLinea[0] = 6 × 3 × 35000  = 630000
// costoLinea[1] = 1 × 3 × 180000 = 540000
// costoTotal = 1170000, valorVenta = Math.round(1170000 / 0.6) = 1950000

const BASE_PROPS = {
  componentes: COMPONENTES_FIXTURE,
  onVolver: noop,
  onArmarTareas: noop,
  onExportarExcel: noop,
  onExportarPpt: noop,
}

// --- Tests -------------------------------------------------------------------

describe('Propuesta — tabla de componentes', () => {
  it('fila por componente con nombre visible', () => {
    render(<Propuesta {...BASE_PROPS} />)
    expect(screen.getByText('Promotoras')).toBeInTheDocument()
    expect(screen.getByText('Catering')).toBeInTheDocument()
  })

  it('dias definido → muestra el valor', () => {
    render(<Propuesta {...BASE_PROPS} />)
    // Ambos componentes tienen dias=3
    const celdas3 = screen.getAllByText('3')
    expect(celdas3.length).toBeGreaterThan(0)
  })

  it('dias undefined → muestra 1', () => {
    const sinDias: Componente[] = [
      { nombre: 'Item sin días', detalle: 'Test', cantidad: 2, valor: 50000 },
    ]
    render(<Propuesta {...BASE_PROPS} componentes={sinDias} />)
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('costo de fila calculado correctamente ($630.000)', () => {
    render(<Propuesta {...BASE_PROPS} />)
    expect(screen.getByText('$630.000')).toBeInTheDocument()
  })

  it('proveedor visible cuando existe', () => {
    render(<Propuesta {...BASE_PROPS} />)
    expect(screen.getByText(/Staff Eventos/)).toBeInTheDocument()
  })

  it('proveedor ausente cuando no existe', () => {
    const sinProveedor: Componente[] = [
      { nombre: 'Sin proveedor', detalle: 'Test', cantidad: 1, valor: 100000, dias: 1 },
    ]
    render(<Propuesta {...BASE_PROPS} componentes={sinProveedor} />)
    // No debe haber badge de proveedor (🏷️)
    expect(screen.queryByText(/🏷️/)).not.toBeInTheDocument()
  })
})

describe('Propuesta — totales', () => {
  it('costo total $1.170.000', () => {
    render(<Propuesta {...BASE_PROPS} />)
    expect(screen.getByText('$1.170.000')).toBeInTheDocument()
  })

  it('valor venta $1.950.000', () => {
    render(<Propuesta {...BASE_PROPS} />)
    expect(screen.getByText('$1.950.000')).toBeInTheDocument()
  })

  it('muestra margen 40%', () => {
    render(<Propuesta {...BASE_PROPS} />)
    expect(screen.getByText(/40%/)).toBeInTheDocument()
  })
})

describe('Propuesta — botones de acción', () => {
  it('clic "Armar tareas ▸" → onArmarTareas', async () => {
    const user = userEvent.setup()
    const onArmarTareas = vi.fn()
    render(<Propuesta {...BASE_PROPS} onArmarTareas={onArmarTareas} />)

    await user.click(screen.getByRole('button', { name: /Armar tareas/i }))

    expect(onArmarTareas).toHaveBeenCalledOnce()
  })

  it('clic "⤓ Excel interno" → onExportarExcel("interno")', async () => {
    const user = userEvent.setup()
    const onExportarExcel = vi.fn()
    render(<Propuesta {...BASE_PROPS} onExportarExcel={onExportarExcel} />)

    await user.click(screen.getByRole('button', { name: /Excel interno/i }))

    expect(onExportarExcel).toHaveBeenCalledWith('interno')
  })

  it('clic "⤓ Excel cliente" → onExportarExcel("cliente")', async () => {
    const user = userEvent.setup()
    const onExportarExcel = vi.fn()
    render(<Propuesta {...BASE_PROPS} onExportarExcel={onExportarExcel} />)

    await user.click(screen.getByRole('button', { name: /Excel cliente/i }))

    expect(onExportarExcel).toHaveBeenCalledWith('cliente')
  })

  it('clic "⤓ PPT" → onExportarPpt', async () => {
    const user = userEvent.setup()
    const onExportarPpt = vi.fn()
    render(<Propuesta {...BASE_PROPS} onExportarPpt={onExportarPpt} />)

    await user.click(screen.getByRole('button', { name: /PPT/i }))

    expect(onExportarPpt).toHaveBeenCalledOnce()
  })
})
