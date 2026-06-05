import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Bandeja } from './Bandeja'
import { SOLICITUDES } from '../datosMock'

const noop = () => {}

describe('Bandeja', () => {
  it('muestra las solicitudes con su badge de tipo', () => {
    render(
      <Bandeja
        solicitudes={SOLICITUDES}
        onAbrir={noop}
        proveedor="gmail"
        onConectar={noop}
        onDesconectar={noop}
      />,
    )
    expect(screen.getByText(/Zona Espiga/i)).toBeInTheDocument()
    expect(screen.getByText('Tipo 1 · Cotización')).toBeInTheDocument()
    expect(screen.getByText('Tipo 2 · Creativa')).toBeInTheDocument()
    expect(screen.getByText('Sin clasificar')).toBeInTheDocument()
  })

  it('al hacer clic en una solicitud, la abre', async () => {
    const user = userEvent.setup()
    const onAbrir = vi.fn()
    render(
      <Bandeja
        solicitudes={SOLICITUDES}
        onAbrir={onAbrir}
        proveedor="gmail"
        onConectar={noop}
        onDesconectar={noop}
      />,
    )
    await user.click(screen.getByText(/Cotización sampling de sopaipillas afuera del Metro/i))
    expect(onAbrir).toHaveBeenCalledWith(SOLICITUDES[0])
  })

  it('sin proveedor conectado, ofrece botones para conectar el correo', async () => {
    const user = userEvent.setup()
    const onConectar = vi.fn()
    render(
      <Bandeja
        solicitudes={SOLICITUDES}
        onAbrir={noop}
        proveedor={null}
        onConectar={onConectar}
        onDesconectar={noop}
      />,
    )
    await user.click(screen.getByRole('button', { name: /gmail/i }))
    expect(onConectar).toHaveBeenCalledWith('gmail')
  })

  it('con un proveedor conectado, muestra que está escuchando nuevos correos', () => {
    render(
      <Bandeja
        solicitudes={SOLICITUDES}
        onAbrir={noop}
        proveedor="gmail"
        estado="conectado"
        onConectar={noop}
        onDesconectar={noop}
      />,
    )
    expect(screen.getByText(/Escuchando nuevos correos/i)).toBeInTheDocument()
    expect(screen.getByText('Gmail')).toBeInTheDocument()
  })

  it('con la integración caída (estado "reconectar"), muestra el aviso de reconectar (CA7)', async () => {
    const user = userEvent.setup()
    const onConectar = vi.fn()
    render(
      <Bandeja
        solicitudes={SOLICITUDES}
        onAbrir={noop}
        proveedor="gmail"
        estado="reconectar"
        onConectar={onConectar}
        onDesconectar={noop}
      />,
    )
    // No dice "Escuchando": avisa que hay que reconectar.
    expect(screen.queryByText(/Escuchando nuevos correos/i)).not.toBeInTheDocument()
    expect(screen.getByText(/Reconecta tu bandeja/i)).toBeInTheDocument()
    // El botón "Reconectar" re-inicia la conexión del mismo proveedor.
    await user.click(screen.getByRole('button', { name: /reconectar/i }))
    expect(onConectar).toHaveBeenCalledWith('gmail')
  })
})
