import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DetalleSolicitud } from './DetalleSolicitud'
import type { Solicitud } from '../tipos'

const solicitud: Solicitud = {
  id: 'x',
  remitente: 'Zona Espiga',
  correo: 'contacto@zonaespiga.cl',
  tiempo: '09:42',
  asunto: 'Cotización sampling de sopaipillas',
  tipo: 't1',
  resumen: 'Solicitud concreta de cotización para un sampling de sopaipillas.',
  puntos: ['Activación tipo sampling', '5 horas diarias'],
  cuerpo: 'Hola Javo, queremos cotizar sopaipillas. Quedo atenta.',
}

const noop = () => {}

describe('DetalleSolicitud', () => {
  it('muestra el remitente y el resumen con sus puntos (CA1)', () => {
    render(<DetalleSolicitud solicitud={solicitud} onVolver={noop} onElegirTipo={noop} />)
    expect(screen.getByText(/Zona Espiga/i)).toBeInTheDocument()
    expect(screen.getByText(/Solicitud concreta de cotización/i)).toBeInTheDocument()
    expect(screen.getByText('Activación tipo sampling')).toBeInTheDocument()
    expect(screen.getByText('5 horas diarias')).toBeInTheDocument()
  })

  it('oculta el correo completo hasta que se pide verlo', async () => {
    const user = userEvent.setup()
    render(<DetalleSolicitud solicitud={solicitud} onVolver={noop} onElegirTipo={noop} />)
    expect(screen.queryByText(/Quedo atenta/i)).not.toBeInTheDocument()
    await user.click(screen.getByText(/Ver correo completo/i))
    expect(screen.getByText(/Quedo atenta/i)).toBeInTheDocument()
  })

  it('la clasificación la confirma el humano: Tipo 1 (CA4)', async () => {
    const user = userEvent.setup()
    const onElegir = vi.fn()
    render(<DetalleSolicitud solicitud={solicitud} onVolver={noop} onElegirTipo={onElegir} />)
    await user.click(screen.getByText(/Tipo 1 · Cotización concreta/i))
    expect(onElegir).toHaveBeenCalledWith('t1')
  })

  it('la clasificación la confirma el humano: Tipo 2 (CA4)', async () => {
    const user = userEvent.setup()
    const onElegir = vi.fn()
    render(<DetalleSolicitud solicitud={solicitud} onVolver={noop} onElegirTipo={onElegir} />)
    await user.click(screen.getByText(/Tipo 2 · Ideas \/ propuesta/i))
    expect(onElegir).toHaveBeenCalledWith('t2')
  })
})
