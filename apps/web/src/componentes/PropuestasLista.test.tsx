import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PropuestasLista } from './PropuestasLista'
import type { PropuestaResumen } from '../api/propuestas'

const PROPUESTAS: PropuestaResumen[] = [
  {
    id: 'p-212',
    solicitudId: 's-212',
    total: 5190000,
    estado: 'borrador',
    asunto: 'Cotización activación 212 VIP Black',
    remitente: 'Carolina Herrera · 212',
  },
  {
    id: 'p-metro',
    solicitudId: 's-metro',
    total: 890000,
    estado: 'enviada',
    asunto: 'Sampling de sopaipillas afuera del Metro',
    remitente: 'Zona Espiga',
  },
]

const noop = () => {}

describe('PropuestasLista', () => {
  it('muestra cada propuesta con asunto, remitente, total (CLP) y estado', () => {
    render(<PropuestasLista propuestas={PROPUESTAS} onAbrir={noop} />)

    expect(screen.getByText(/Cotización activación 212 VIP Black/i)).toBeInTheDocument()
    expect(screen.getByText(/Carolina Herrera · 212/i)).toBeInTheDocument()
    // El total se formatea como pesos chilenos.
    expect(screen.getByText('$5.190.000')).toBeInTheDocument()
    // El estado aparece como badge.
    expect(screen.getByText('borrador')).toBeInTheDocument()
    expect(screen.getByText('enviada')).toBeInTheDocument()
  })

  it('al hacer clic en una propuesta, llama onAbrir con su solicitudId', async () => {
    const user = userEvent.setup()
    const onAbrir = vi.fn()
    render(<PropuestasLista propuestas={PROPUESTAS} onAbrir={onAbrir} />)

    await user.click(screen.getByText(/Sampling de sopaipillas afuera del Metro/i))
    expect(onAbrir).toHaveBeenCalledWith('s-metro')
  })

  it('sin propuestas, muestra un estado vacío', () => {
    render(<PropuestasLista propuestas={[]} onAbrir={noop} />)
    expect(screen.getByText(/Aún no hay propuestas/i)).toBeInTheDocument()
  })
})
