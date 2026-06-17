import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Mockeamos el cliente de ClickUp: la pantalla lo llama al montar para saber si
// la empresa ya conectó su gestor de tareas (estado per-empresa) y para iniciar /
// desconectar el OAuth. Cada test ajusta qué devuelve.
vi.mock('../api/clickup', () => ({
  obtenerEstadoClickup: vi.fn(),
  iniciarConexionClickup: vi.fn(),
  desconectarClickup: vi.fn(),
  ESTADO_CLICKUP_DESCONECTADO: { proveedor: null, estado: null },
}))

import { Configuracion } from './Configuracion'
import {
  desconectarClickup,
  iniciarConexionClickup,
  obtenerEstadoClickup,
} from '../api/clickup'
import { ESTADO_DESCONECTADO, type EstadoCorreo } from '../api/integraciones'

const mockEstadoClickup = obtenerEstadoClickup as ReturnType<typeof vi.fn>
const mockIniciarClickup = iniciarConexionClickup as ReturnType<typeof vi.fn>
const mockDesconectarClickup = desconectarClickup as ReturnType<typeof vi.fn>
const noop = () => {}

/** Estado de correo "conectado" a la casilla del piloto (Capsulab). */
const CORREO_CONECTADO: EstadoCorreo = {
  proveedor: 'gmail',
  estado: 'conectado',
  casilla: 'javier@capsulab.cl',
}

describe('Configuracion (onboarding de conectores)', () => {
  beforeEach(() => {
    // Por defecto: ClickUp sin conectar (gestor de tareas aún sin autorizar).
    mockEstadoClickup.mockResolvedValue({ proveedor: null, estado: null })
    mockIniciarClickup.mockResolvedValue('https://app.clickup.com/api?state=abc')
    mockDesconectarClickup.mockResolvedValue(undefined)
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
    // El efecto de montaje consulta el estado de ClickUp (evita "act" warnings).
    await waitFor(() => expect(mockEstadoClickup).toHaveBeenCalled())
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

  it('mientras App resuelve el estado del correo, muestra "Comprobando…" (NO "Sin conectar")', async () => {
    // Bug: al volver al onboarding, Gmail parpadeaba "Sin conectar" aunque estaba
    // conectado, porque App aún no había resuelto el estado real. Con cargandoCorreo
    // la tarjeta debe quedar en "Comprobando…" en vez de afirmar la desconexión.
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        cargandoCorreo
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    const badge = screen.getByTestId('conector-gmail')
    expect(badge).toHaveTextContent(/comprobando/i)
    // Lo crítico: NO debe afirmar "Sin conectar" mientras carga (eso era el flash).
    expect(badge).not.toHaveTextContent(/sin conectar/i)
    // Tampoco ofrece "Conectar Gmail" todavía (no sabemos si hace falta).
    expect(screen.queryByRole('button', { name: /conectar gmail/i })).not.toBeInTheDocument()
    await waitFor(() => expect(mockEstadoClickup).toHaveBeenCalled())
  })

  it('ya resuelto y desconectado, muestra "Sin conectar" (cargandoCorreo=false)', async () => {
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        cargandoCorreo={false}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    expect(screen.getByTestId('conector-gmail')).toHaveTextContent(/sin conectar/i)
    expect(screen.getByRole('button', { name: /conectar gmail/i })).toBeInTheDocument()
    await waitFor(() => expect(mockEstadoClickup).toHaveBeenCalled())
  })

  it('conectado tiene prioridad sobre cargandoCorreo (no muestra "Comprobando…")', () => {
    // Si ya sabemos que está conectado, una recarga de fondo no debe degradar la UI.
    render(
      <Configuracion
        estadoCorreo={CORREO_CONECTADO}
        cargandoCorreo
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    expect(screen.getByTestId('conector-gmail')).toHaveTextContent(/conectado/i)
    expect(screen.getByText(/javier@capsulab\.cl/i)).toBeInTheDocument()
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

  it('con ClickUp conectado (estado per-empresa), muestra "Conectado" y un botón para cambiar', async () => {
    mockEstadoClickup.mockResolvedValue({ proveedor: 'clickup', estado: 'conectado' })
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    // Al montar consulta el estado real del conector de la empresa.
    await waitFor(() => expect(mockEstadoClickup).toHaveBeenCalled())
    // "Conectado" aparece (badge de estado + detalle); basta con que exista.
    await waitFor(() => expect(screen.getAllByText(/Conectado/i).length).toBeGreaterThan(0))
    // Ofrece "Cambiar" (desconectar), espejo de Gmail.
    expect(screen.getByRole('button', { name: /cambiar clickup/i })).toBeInTheDocument()
    // Ya no aparece la vieja nota de "OAuth próximamente" (el flujo es real ahora).
    expect(screen.queryByText(/conector OAuth próximamente/i)).not.toBeInTheDocument()
  })

  it('con ClickUp en "reconectar" (token revocado/401), muestra "Reconectar" (CA6)', async () => {
    mockEstadoClickup.mockResolvedValue({ proveedor: 'clickup', estado: 'reconectar' })
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    await waitFor(() => expect(mockEstadoClickup).toHaveBeenCalled())
    // "Reconectar" aparece (badge de estado + botón); basta con que exista.
    await waitFor(() => expect(screen.getAllByText(/Reconectar/i).length).toBeGreaterThan(0))
    // Permite reconectar (vuelve a disparar el OAuth).
    expect(screen.getByRole('button', { name: /reconectar clickup/i })).toBeInTheDocument()
  })

  it('sin ClickUp conectado, muestra "Sin conectar" y ofrece conectar (sin nota vieja de OAuth)', async () => {
    mockEstadoClickup.mockResolvedValue({ proveedor: null, estado: null })
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    await waitFor(() => expect(mockEstadoClickup).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: /conectar clickup/i })).toBeInTheDocument()
    // El conector ya no dice "próximamente": es un flujo OAuth real.
    expect(screen.queryByText(/conector OAuth próximamente/i)).not.toBeInTheDocument()
  })

  it('"Conectar ClickUp" inicia el OAuth y navega a la URL del backend', async () => {
    const user = userEvent.setup()
    const onNavegar = vi.fn()
    mockEstadoClickup.mockResolvedValue({ proveedor: null, estado: null })
    mockIniciarClickup.mockResolvedValue('https://app.clickup.com/api?state=xyz')
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
        onNavegar={onNavegar}
      />,
    )
    await waitFor(() => expect(mockEstadoClickup).toHaveBeenCalled())
    await user.click(screen.getByRole('button', { name: /conectar clickup/i }))
    expect(mockIniciarClickup).toHaveBeenCalled()
    // Navega a la URL EXACTA del backend (no inventada por el front).
    await waitFor(() =>
      expect(onNavegar).toHaveBeenCalledWith('https://app.clickup.com/api?state=xyz'),
    )
  })

  it('"Cambiar" desconecta ClickUp y la tarjeta vuelve a "Sin conectar"', async () => {
    const user = userEvent.setup()
    mockEstadoClickup.mockResolvedValue({ proveedor: 'clickup', estado: 'conectado' })
    render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    await waitFor(() => expect(mockEstadoClickup).toHaveBeenCalled())
    await user.click(await screen.findByRole('button', { name: /cambiar clickup/i }))
    expect(mockDesconectarClickup).toHaveBeenCalled()
    // Tras desconectar, vuelve a ofrecer "Conectar ClickUp".
    expect(await screen.findByRole('button', { name: /conectar clickup/i })).toBeInTheDocument()
  })

  it('el token de ClickUp jamás aparece en la tarjeta (CA5)', async () => {
    mockEstadoClickup.mockResolvedValue({ proveedor: 'clickup', estado: 'conectado' })
    const { container } = render(
      <Configuracion
        estadoCorreo={ESTADO_DESCONECTADO}
        onConectar={noop}
        onDesconectar={noop}
        onIrA={noop}
      />,
    )
    await waitFor(() => expect(mockEstadoClickup).toHaveBeenCalled())
    await waitFor(() => expect(screen.getAllByText(/Conectado/i).length).toBeGreaterThan(0))
    // El estado per-empresa no trae token; nada parecido a un token se pinta.
    expect(container.textContent ?? '').not.toMatch(/token/i)
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
    await waitFor(() => expect(mockEstadoClickup).toHaveBeenCalled())
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
