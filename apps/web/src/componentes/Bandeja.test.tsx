import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Bandeja } from './Bandeja'
import type { Solicitud } from '../tipos'

const noop = () => {}

// Fixture local de la bandeja (antes venía del mock `SOLICITUDES`, ya eliminado):
// cubre los tres tipos de badge (t1/t2/new) que verifica esta suite.
const SOLICITUDES: Solicitud[] = [
  {
    id: 'espiga',
    remitente: 'Zona Espiga',
    correo: 'contacto@zonaespiga.cl',
    tiempo: '09-jun',
    asunto: 'Cotización sampling de sopaipillas afuera del Metro',
    tipo: 't1',
    resumen: 'Sampling de sopaipillas afuera del Metro.',
    puntos: ['Activación de sampling', '5 horas diarias'],
    cuerpo: 'Hola Javo, queremos cotizar un sampling de sopaipillas.',
  },
  {
    id: 'f1',
    remitente: 'Fórmula 1 LATAM',
    correo: 'marketing@f1latam.com',
    tiempo: '08-jun',
    asunto: 'Necesitamos ideas — activación Fórmula 1',
    tipo: 't2',
    resumen: 'Ideas de activación para la Fórmula 1.',
    puntos: ['Sin brief cerrado', 'Alto impacto'],
    cuerpo: 'Hola Javo, necesitamos ideas para la Fórmula 1.',
  },
  {
    id: 'narnia',
    remitente: 'Netflix · Narnia',
    correo: 'activaciones@partner.netflix.com',
    tiempo: '07-jun',
    asunto: 'Activación estreno Narnia en cines (Octubre)',
    tipo: 'new',
    resumen: 'Estreno de Narnia en cines, por clasificar.',
    puntos: ['Estreno en cines', 'Por clasificar'],
    cuerpo: 'Hola Javo, pensamos algo para el estreno de Narnia.',
  },
]

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

  it('Outlook e IMAP aparecen deshabilitados con "Próximamente" (solo Gmail conecta)', () => {
    // App.tsx solo cablea Gmail (`if (p !== 'gmail') return`): los otros botones
    // no deben ofrecer un clic muerto sin feedback (mismo patrón que Jira en
    // Configuración).
    render(
      <Bandeja
        solicitudes={[]}
        onAbrir={noop}
        proveedor={null}
        onConectar={noop}
        onDesconectar={noop}
      />,
    )
    expect(screen.getByRole('button', { name: /gmail/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /outlook/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /otro \(imap\)/i })).toBeDisabled()
    expect(screen.getAllByText(/próximamente/i).length).toBeGreaterThanOrEqual(2)
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

  it('mientras carga (conectada, sin solicitudes aún), muestra "Cargando…" en vez del vacío', () => {
    render(
      <Bandeja
        solicitudes={[]}
        onAbrir={noop}
        proveedor="gmail"
        estado="conectado"
        onConectar={noop}
        onDesconectar={noop}
        cargando
      />,
    )
    expect(screen.getByText(/Cargando solicitudes/i)).toBeInTheDocument()
  })

  it('si la carga falla (conectada), muestra un banner de error con "Reintentar"', async () => {
    const user = userEvent.setup()
    const onReintentar = vi.fn()
    render(
      <Bandeja
        solicitudes={[]}
        onAbrir={noop}
        proveedor="gmail"
        estado="conectado"
        onConectar={noop}
        onDesconectar={noop}
        error
        onReintentar={onReintentar}
      />,
    )
    expect(screen.getByText(/No se pudieron cargar las solicitudes/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /reintentar/i }))
    expect(onReintentar).toHaveBeenCalledOnce()
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
