import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Mockeamos el cliente de ClickUp: la pantalla lo llama al montar para saber si
// la empresa ya conectó su gestor de tareas. Cada test ajusta qué devuelve.
vi.mock('../api/clickup', () => ({
  listarListasClickUp: vi.fn(),
}))

import { Configuracion } from './Configuracion'
import { listarListasClickUp } from '../api/clickup'
import { ESTADO_DESCONECTADO, type EstadoCorreo } from '../api/integraciones'

const mockListas = listarListasClickUp as ReturnType<typeof vi.fn>
const noop = () => {}

/** Estado de correo "conectado" a la casilla del piloto (Capsulab). */
const CORREO_CONECTADO: EstadoCorreo = {
  proveedor: 'gmail',
  estado: 'conectado',
  casilla: 'javier@capsulab.cl',
}

describe('Configuracion (onboarding de conectores)', () => {
  beforeEach(() => {
    // Por defecto: sin listas (gestor de tareas aún sin conectar).
    mockListas.mockResolvedValue([])
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('muestra el encabezado del onboarding y las tarjetas de conector', async () => {
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    // Encabezado: "prepara tu espacio".
    expect(screen.getByText(/prepara tu espacio/i)).toBeInTheDocument()
    // Una tarjeta por conector: el título exacto de Correo·Gmail, ClickUp y Jira.
    expect(screen.getByText('Correo · Gmail')).toBeInTheDocument()
    expect(screen.getByText('Gestor de tareas · ClickUp')).toBeInTheDocument()
    expect(screen.getByText('Gestor de tareas · Jira')).toBeInTheDocument()
    // El efecto de montaje consulta ClickUp (evita "act" warnings al desmontar).
    await waitFor(() => expect(mockListas).toHaveBeenCalled())
  })

  it('con el correo conectado, muestra la casilla y un botón para cambiar', () => {
    render(
      <Configuracion
        estadoCorreo={CORREO_CONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    expect(screen.getByText(/javier@capsulab\.cl/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cambiar/i })).toBeInTheDocument()
  })

  it('sin correo conectado, ofrece conectar Gmail y dispara onConectar("gmail")', async () => {
    const user = userEvent.setup()
    const onConectar = vi.fn()
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={onConectar}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    await user.click(screen.getByRole('button', { name: /conectar gmail/i }))
    expect(onConectar).toHaveBeenCalledWith('gmail')
  })

  it('con listas de ClickUp, muestra "Conectado" y cuántas listas hay', async () => {
    mockListas.mockResolvedValue([
      { id: '1', nombre: 'Producción', espacio: 'Capsulab' },
      { id: '2', nombre: 'Compras', espacio: 'Capsulab' },
    ])
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    // Al montar consulta las listas reales del backend.
    await waitFor(() => expect(mockListas).toHaveBeenCalled())
    // "Conectado" aparece (badge de estado + detalle); basta con que exista.
    await waitFor(() => expect(screen.getAllByText(/Conectado/i).length).toBeGreaterThan(0))
    // Refleja cuántas listas tiene la empresa (texto único del detalle).
    expect(screen.getByText(/2 listas/i)).toBeInTheDocument()
  })

  it('sin listas de ClickUp, muestra "Conecta ClickUp" con la nota de OAuth próximamente', async () => {
    mockListas.mockResolvedValue([])
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    await waitFor(() => expect(mockListas).toHaveBeenCalled())
    expect(await screen.findByText(/Conecta ClickUp/i)).toBeInTheDocument()
    // La nota específica del conector OAuth de ClickUp (distinta del badge de Jira).
    expect(screen.getByText(/conector OAuth próximamente/i)).toBeInTheDocument()
  })

  it('la tarjeta de Jira está deshabilitada con un badge "Próximamente"', async () => {
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    // El badge "Próximamente" aparece (al menos una vez: Jira siempre, ClickUp si vacío).
    expect(screen.getAllByText(/próximamente/i).length).toBeGreaterThan(0)
    // Jira no ofrece ningún botón de conexión (tarjeta no clickable).
    expect(screen.queryByRole('button', { name: /conectar jira/i })).not.toBeInTheDocument()
    await waitFor(() => expect(mockListas).toHaveBeenCalled())
  })

  it('el botón "Continuar a la bandeja" navega a la bandeja (onIrA("inbox"))', async () => {
    const user = userEvent.setup()
    const onIrA = vi.fn()
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={onIrA}
      />,
    )
    await user.click(screen.getByRole('button', { name: /continuar a la bandeja/i }))
    expect(onIrA).toHaveBeenCalledWith('inbox')
  })
})
