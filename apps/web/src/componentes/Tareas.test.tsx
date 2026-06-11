import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Tareas } from './Tareas'
import type { Tarea } from '../tipos'

const noop = () => {}

const TAREAS: Tarea[] = [
  { nombre: 'Reclutar 6 promotoras', area: 'RRHH', responsable: 'Coordinación', plazo: '3 días' },
  { nombre: 'Comprar insumos', area: 'Compras', responsable: 'Producción', plazo: '1 semana' },
]

const LISTAS = [
  { id: 'L1', nombre: 'Backlog', espacio: 'Marketing' },
  { id: 'L2', nombre: 'Sampling', espacio: 'Marketing' },
]

// Roster de la empresa para el selector "Asignado a" (0006). Hay un miembro por cada
// área de TAREAS (RRHH, Compras) más otro, para verificar la pre-selección por rol.
const ROSTER = [
  { id: 'm1', nombre: 'Gabriela Lillo', rol: 'RRHH' },
  { id: 'm2', nombre: 'Diego Rojas', rol: 'Compras' },
  { id: 'm3', nombre: 'Carla Díaz', rol: 'Diseño' },
]

/** `Response` mínima (sólo ok/status/json). */
function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

/** Mock de fetch ruteado por URL: roster + listas de ClickUp + envío de tareas. */
function fetchMockClickUp(opts: { listas?: unknown; creadas?: unknown; miembros?: unknown } = {}) {
  const { listas = LISTAS, creadas = { creadas: 2 }, miembros = ROSTER } = opts
  return vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
    const u = String(input)
    // `/miembros` debe ir ANTES que `/tareas/clickup`: ninguna comparte substring, pero
    // así queda explícito que el roster es su propia ruta.
    if (u.includes('/miembros')) return Promise.resolve(respuesta(miembros))
    if (u.includes('/clickup/listas')) return Promise.resolve(respuesta(listas))
    if (u.includes('/tareas/clickup')) return Promise.resolve(respuesta(creadas))
    return Promise.resolve(respuesta({}, false, 404))
  })
}

/** El selector de lista de ClickUp (distinto de los selectores "Asignado a"). */
function selectorLista() {
  return screen.getByRole('combobox', { name: /Lista de ClickUp/i })
}

describe('Tareas · conector ClickUp', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('muestra las tareas generadas', () => {
    vi.stubGlobal('fetch', fetchMockClickUp())
    render(<Tareas tareas={TAREAS} onVolver={noop} solicitudId="sol-1" />)
    expect(screen.getByText(/Reclutar 6 promotoras/i)).toBeInTheDocument()
    expect(screen.getByText(/Comprar insumos/i)).toBeInTheDocument()
  })

  it('puebla el selector con las listas reales de ClickUp', async () => {
    vi.stubGlobal('fetch', fetchMockClickUp())
    render(<Tareas tareas={TAREAS} onVolver={noop} solicitudId="sol-1" />)
    // Las opciones aparecen de forma asíncrona (tras listarListasClickUp()).
    expect(await screen.findByRole('option', { name: /Backlog/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Sampling/i })).toBeInTheDocument()
  })

  it('al enviar usa la lista elegida y muestra "N tareas creadas"', async () => {
    const fetchMock = fetchMockClickUp({ creadas: { creadas: 2 } })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<Tareas tareas={TAREAS} onVolver={noop} solicitudId="sol-1" />)

    // Elegir la segunda lista en el selector (espera a que se pueble).
    await screen.findByRole('option', { name: /Sampling/i })
    await user.selectOptions(selectorLista(), 'L2')
    await user.click(screen.getByRole('button', { name: /Enviar a ClickUp/i }))

    // Pegó al endpoint con la lista elegida.
    await waitFor(() => {
      const llamada = fetchMock.mock.calls.find((c) => String(c[0]).includes('/tareas/clickup'))
      expect(llamada).toBeTruthy()
      expect(String(llamada![0])).toContain('/solicitudes/sol-1/tareas/clickup')
      expect(String(llamada![0])).toContain('lista_id=L2')
    })
    // Muestra el resultado al usuario.
    expect(await screen.findByText(/2 tareas creadas/i)).toBeInTheDocument()
  })

  it('recuerda la lista elegida en localStorage', async () => {
    vi.stubGlobal('fetch', fetchMockClickUp())
    const user = userEvent.setup()
    render(<Tareas tareas={TAREAS} onVolver={noop} solicitudId="sol-1" />)

    await screen.findByRole('option', { name: /Sampling/i })
    await user.selectOptions(selectorLista(), 'L2')

    await waitFor(() => {
      expect(Object.values(localStorage).some((v) => v === 'L2')).toBe(true)
    })
  })

  it('sin listas (sin token) muestra el aviso y deshabilita el envío', async () => {
    vi.stubGlobal('fetch', fetchMockClickUp({ listas: [] }))
    render(<Tareas tareas={TAREAS} onVolver={noop} solicitudId="sol-1" />)

    expect(await screen.findByText(/Conecta ClickUp/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Enviar a ClickUp/i })).toBeDisabled()
  })

  it('si el envío falla, muestra un mensaje de error', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      if (u.includes('/clickup/listas')) return Promise.resolve(respuesta(LISTAS))
      if (u.includes('/tareas/clickup')) return Promise.resolve(respuesta({}, false, 502))
      return Promise.resolve(respuesta({}, false, 404))
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<Tareas tareas={TAREAS} onVolver={noop} solicitudId="sol-1" />)

    await screen.findByRole('option', { name: /Backlog/i })
    await user.click(screen.getByRole('button', { name: /Enviar a ClickUp/i }))

    expect(await screen.findByText(/no se pudo|error/i)).toBeInTheDocument()
  })

  it('muestra un selector "Asignado a" por tarea, pre-seleccionado por rol', async () => {
    vi.stubGlobal('fetch', fetchMockClickUp())
    render(<Tareas tareas={TAREAS} onVolver={noop} solicitudId="sol-1" />)
    const selRRHH = await screen.findByRole('combobox', {
      name: /Asignado a · Reclutar 6 promotoras/i,
    })
    expect((selRRHH as HTMLSelectElement).value).toBe('Gabriela Lillo') // rol RRHH calza
    const selCompras = screen.getByRole('combobox', { name: /Asignado a · Comprar insumos/i })
    expect((selCompras as HTMLSelectElement).value).toBe('Diego Rojas') // rol Compras calza
  })

  it('manda el asignado elegido en el cuerpo al enviar a ClickUp', async () => {
    const fetchMock = fetchMockClickUp()
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<Tareas tareas={TAREAS} onVolver={noop} solicitudId="sol-1" />)
    // Espera a que cargue el roster (aparecen los selectores "Asignado a").
    await screen.findByRole('combobox', { name: /Asignado a · Reclutar 6 promotoras/i })
    await user.click(screen.getByRole('button', { name: /Enviar a ClickUp/i }))
    await waitFor(() => {
      const llamada = fetchMock.mock.calls.find((c) => String(c[0]).includes('/tareas/clickup'))
      expect(llamada).toBeTruthy()
      const body = JSON.parse((llamada![1] as RequestInit).body as string)
      expect(body.asignados['Reclutar 6 promotoras']).toBe('Gabriela Lillo')
    })
  })
})
