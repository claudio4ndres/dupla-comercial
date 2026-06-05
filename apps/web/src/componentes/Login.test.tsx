import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Login } from './Login'

describe('Login', () => {
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

  it('al enviar credenciales válidas, inicia sesión con el correo', async () => {
    const user = userEvent.setup()
    const onEntrar = vi.fn()
    render(<Login onEntrar={onEntrar} />)
    await user.type(screen.getByLabelText(/correo/i), 'javier@capsulab.cl')
    await user.type(screen.getByLabelText(/contraseña/i), 'secreto123')
    await user.click(screen.getByRole('button', { name: /entrar/i }))
    expect(onEntrar).toHaveBeenCalledWith('javier@capsulab.cl')
  })
})
