// Tests RTL para el componente Chat (puramente presentacional).
// Cubre: envío de mensajes, chips, panel de componentes, fuentes, recursos y botón generar propuesta.

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { Chat } from './Chat'
import type { Solicitud, TipoConfirmado, Componente, Fuente, Mensaje } from '../tipos'
import type { RecursoDrive } from '../datosMock'

const noop = () => {}

// --- Fixtures ----------------------------------------------------------------

const SOLICITUD_FIXTURE: Solicitud = {
  id: 'sol-espiga',
  remitente: 'Zona Espiga',
  correo: 'contacto@zonaespiga.cl',
  tiempo: '09:42',
  asunto: 'Cotización sampling sopaipillas — Metro',
  tipo: 't1',
  resumen: 'Sampling de sopaipillas afuera del Metro.',
  puntos: ['Activación de sampling'],
  cuerpo: 'Hola Javo...',
}

const COMPONENTES_FIXTURE: Componente[] = [
  { nombre: 'Promotoras', detalle: 'Uniformadas BTL', cantidad: 6, valor: 35000, dias: 3, origen: 'Tarifario BTL 2024', proveedor: 'Staff Eventos' },
  { nombre: 'Catering', detalle: 'Sopaipillas', cantidad: 1, valor: 180000, dias: 3 },
]
// costoTotal = 630000 + 540000 = 1170000, valorVenta = 1950000

const RECURSOS_FIXTURE: RecursoDrive[] = [
  { icono: '📄', nombre: 'Tarifario BTL 2024.xlsx' },
  { icono: '📊', nombre: 'Costos Catering Q1.xlsx' },
]

const FUENTES_FIXTURE: Fuente[] = [
  { titulo: 'Precios promotoras BTL', referencia: 'staffeventos.cl/tarifas' },
]

const BASE_PROPS = {
  solicitud: SOLICITUD_FIXTURE,
  tipo: 't1' as TipoConfirmado,
  mensajes: [] as Mensaje[],
  componentes: [] as Componente[],
  fuentes: [] as Fuente[],
  recursos: [] as RecursoDrive[],
  enviando: false,
  onEnviar: noop,
  onGenerarPropuesta: noop,
}

// --- Tests -------------------------------------------------------------------

describe('Chat — envío de mensajes', () => {
  it('clic en botón enviar → onEnviar con texto sin 🌐', async () => {
    const user = userEvent.setup()
    const onEnviar = vi.fn()
    render(<Chat {...BASE_PROPS} onEnviar={onEnviar} />)

    const input = screen.getByTestId('javo-input')
    await user.type(input, 'Busca opciones en internet 🌐')
    await user.click(screen.getByTestId('javo-enviar'))

    expect(onEnviar).toHaveBeenCalledWith('Busca opciones en internet')
  })

  it('Enter envía y vacía campo', async () => {
    const user = userEvent.setup()
    const onEnviar = vi.fn()
    render(<Chat {...BASE_PROPS} onEnviar={onEnviar} />)

    const input = screen.getByTestId('javo-input')
    await user.type(input, 'Hola Javo{Enter}')

    expect(onEnviar).toHaveBeenCalledWith('Hola Javo')
    expect(input).toHaveValue('')
  })

  it('Shift+Enter NO envía (inserta salto)', async () => {
    const user = userEvent.setup()
    const onEnviar = vi.fn()
    render(<Chat {...BASE_PROPS} onEnviar={onEnviar} />)

    const input = screen.getByTestId('javo-input')
    await user.type(input, 'Primera línea')
    await user.keyboard('{Shift>}{Enter}{/Shift}')

    expect(onEnviar).not.toHaveBeenCalled()
  })

  it('texto vacío no envía', async () => {
    const user = userEvent.setup()
    const onEnviar = vi.fn()
    render(<Chat {...BASE_PROPS} onEnviar={onEnviar} />)

    await user.click(screen.getByTestId('javo-enviar'))

    expect(onEnviar).not.toHaveBeenCalled()
  })

  it('enviando=true → botón disabled + javo-pensando visible', () => {
    render(<Chat {...BASE_PROPS} enviando={true} />)

    expect(screen.getByTestId('javo-enviar')).toBeDisabled()
    expect(screen.getByTestId('javo-pensando')).toBeInTheDocument()
  })
})

describe('Chat — chips de acción rápida', () => {
  it('clic en chip → onEnviar con texto del chip sin 🌐', async () => {
    const user = userEvent.setup()
    const onEnviar = vi.fn()
    render(<Chat {...BASE_PROPS} tipo="t2" onEnviar={onEnviar} />)

    // El chip t2 "Busca opciones en internet 🌐" debe enviar sin el emoji
    await user.click(screen.getByText('Busca opciones en internet 🌐'))

    expect(onEnviar).toHaveBeenCalledWith('Busca opciones en internet')
  })

  it('chips t1 vs t2 distintos', () => {
    const { unmount } = render(<Chat {...BASE_PROPS} tipo="t1" />)
    expect(screen.getByText('Son 3 días de activación')).toBeInTheDocument()
    expect(screen.getByText('Suma coordinación de producción')).toBeInTheDocument()
    expect(screen.getByText('Genera la propuesta')).toBeInTheDocument()
    unmount()

    render(<Chat {...BASE_PROPS} tipo="t2" />)
    expect(screen.getByText('Busca opciones en internet 🌐')).toBeInTheDocument()
    expect(screen.getByText('Dame 3 ideas de alto impacto')).toBeInTheDocument()
    expect(screen.getByText('Aterriza la idea ganadora')).toBeInTheDocument()
  })
})

describe('Chat — panel lateral de componentes', () => {
  it('componentes=[] → mensaje vacío', () => {
    render(<Chat {...BASE_PROPS} componentes={[]} />)
    expect(screen.getByText(/Conversa con Javo/i)).toBeInTheDocument()
  })

  it('con componentes → nombres visibles + costo total $1.170.000 + valor venta $1.950.000', () => {
    render(<Chat {...BASE_PROPS} componentes={COMPONENTES_FIXTURE} />)

    expect(screen.getByText('Promotoras')).toBeInTheDocument()
    expect(screen.getByText('Catering')).toBeInTheDocument()
    expect(screen.getByText('$1.170.000')).toBeInTheDocument()
    expect(screen.getByText('$1.950.000')).toBeInTheDocument()
  })

  it('componente con origen → origen visible', () => {
    render(<Chat {...BASE_PROPS} componentes={COMPONENTES_FIXTURE} />)
    expect(screen.getByText(/Tarifario BTL 2024/)).toBeInTheDocument()
  })
})

describe('Chat — fuentes y recursos', () => {
  it('fuentes con elementos → panel visible', () => {
    render(<Chat {...BASE_PROPS} fuentes={FUENTES_FIXTURE} />)

    expect(screen.getByText('Fuentes citadas')).toBeInTheDocument()
    expect(screen.getAllByTestId('fuente-citada').length).toBeGreaterThan(0)
  })

  it('fuentes=[] → panel oculto', () => {
    render(<Chat {...BASE_PROPS} fuentes={[]} />)
    expect(screen.queryByText('Fuentes citadas')).not.toBeInTheDocument()
  })

  it('recursos con elementos → recurso-drive visible', () => {
    render(<Chat {...BASE_PROPS} recursos={RECURSOS_FIXTURE} />)
    expect(screen.getAllByTestId('recurso-drive').length).toBe(2)
  })

  it('recursos=[] → mensaje vacío', () => {
    render(<Chat {...BASE_PROPS} recursos={[]} />)
    expect(screen.getByText(/Sin recursos indexados/i)).toBeInTheDocument()
  })
})

describe('Chat — generar propuesta', () => {
  it('clic generar-propuesta → onGenerarPropuesta llamado', async () => {
    const user = userEvent.setup()
    const onGenerarPropuesta = vi.fn()
    render(<Chat {...BASE_PROPS} onGenerarPropuesta={onGenerarPropuesta} />)

    await user.click(screen.getByTestId('generar-propuesta'))

    expect(onGenerarPropuesta).toHaveBeenCalledOnce()
  })
})
