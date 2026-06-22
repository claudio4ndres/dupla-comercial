import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { OnboardingBienvenida } from './OnboardingBienvenida'

describe('OnboardingBienvenida (slider de bienvenida)', () => {
  it('muestra el primer slide con la bienvenida', () => {
    render(<OnboardingBienvenida onCerrar={vi.fn()} />)
    expect(screen.getByText(/bienvenido a dupla comercial/i)).toBeInTheDocument()
  })

  it('avanza al siguiente slide con "Siguiente"', async () => {
    render(<OnboardingBienvenida onCerrar={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /siguiente/i }))
    expect(screen.getByText(/tu bandeja inteligente/i)).toBeInTheDocument()
  })

  it('en el último slide el botón es "Empezar" y al pulsarlo llama onCerrar', async () => {
    const onCerrar = vi.fn()
    render(<OnboardingBienvenida onCerrar={onCerrar} />)
    for (let i = 0; i < 4; i++) {
      await userEvent.click(screen.getByRole('button', { name: /siguiente/i }))
    }
    await userEvent.click(screen.getByRole('button', { name: /empezar/i }))
    expect(onCerrar).toHaveBeenCalledTimes(1)
  })

  it('"Saltar" llama onCerrar de inmediato', async () => {
    const onCerrar = vi.fn()
    render(<OnboardingBienvenida onCerrar={onCerrar} />)
    await userEvent.click(screen.getByRole('button', { name: /saltar/i }))
    expect(onCerrar).toHaveBeenCalledTimes(1)
  })
})
