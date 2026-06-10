import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'

// Mockeamos el cliente de Supabase (misma forma que App.test.tsx). Con `isolate:false`
// los módulos se comparten entre archivos: si aquí espiáramos el cliente REAL mientras
// App.test.tsx mockea el módulo, el mock se filtra y rompe los tests. Mockeando aquí
// también, cada archivo controla su propio doble de forma determinista.
vi.mock('../supabase/cliente', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      signInWithPassword: vi.fn(),
      signOut: vi.fn(),
      onAuthStateChange: vi.fn(),
    },
  },
}))

import { supabase } from '../supabase/cliente'
import { Login } from './Login'

const signIn = supabase.auth.signInWithPassword as ReturnType<typeof vi.fn>

describe('Login', () => {
  beforeEach(() => {
    signIn.mockReset()
  })

  it('muestra los campos de correo y contraseña', () => {
    render(<Login onEntrar={() => {}} />)
    expect(screen.getByLabelText(/correo/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/contraseña/i)).toBeInTheDocument()
  })

  it('el botón Entrar está deshabilitado hasta completar ambos campos', async () => {
    const user = userEvent.setup()
    render(<Login onEntrar={() => {}} />)
    const boton = screen.getByRole('button', { name: /entrar/i })
    expect(boton).toBeDisabled()
    await user.type(screen.getByLabelText(/correo/i), 'javier@capsulab.cl')
    await user.type(screen.getByLabelText(/contraseña/i), 'secreto123')
    expect(boton).toBeEnabled()
  })

  it('al enviar credenciales válidas, llama a signInWithPassword e invoca onEntrar', async () => {
    signIn.mockResolvedValue({ error: null })
    const user = userEvent.setup()
    const onEntrar = vi.fn()
    render(<Login onEntrar={onEntrar} />)
    await user.type(screen.getByLabelText(/correo/i), 'javier@capsulab.cl')
    await user.type(screen.getByLabelText(/contraseña/i), 'capsulab2024')
    await user.click(screen.getByRole('button', { name: /entrar/i }))
    await waitFor(() => expect(onEntrar).toHaveBeenCalledWith('javier@capsulab.cl'))
    expect(signIn).toHaveBeenCalledWith({ email: 'javier@capsulab.cl', password: 'capsulab2024' })
  })

  it('con credenciales incorrectas, muestra mensaje de error y NO invoca onEntrar', async () => {
    signIn.mockResolvedValue({ error: { message: 'Invalid login credentials' } })
    const user = userEvent.setup()
    const onEntrar = vi.fn()
    render(<Login onEntrar={onEntrar} />)
    await user.type(screen.getByLabelText(/correo/i), 'javier@capsulab.cl')
    await user.type(screen.getByLabelText(/contraseña/i), 'wrongpassword')
    await user.click(screen.getByRole('button', { name: /entrar/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/correo o contraseña incorrectos/i)
    expect(onEntrar).not.toHaveBeenCalled()
  })
})
