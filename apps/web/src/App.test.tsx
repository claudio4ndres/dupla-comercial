import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

/** `Response` mínima (sólo ok/status/json, que es lo que usa la capa de API). */
function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

/** Estado de bandeja "sin conectar" que devuelve el backend por defecto. */
const ESTADO_DESCONECTADO = { proveedor: null, estado: null, casilla: null }

/** Inicia sesión en el demo (por ahora cualquier credencial sirve). */
async function entrar(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/correo/i), 'javier@capsulab.cl')
  await user.type(screen.getByLabelText(/contraseña/i), 'secreto123')
  await user.click(screen.getByRole('button', { name: /entrar/i }))
}

describe('App (arnés)', () => {
  beforeEach(() => {
    // Al montar, la bandeja consulta GET /integraciones/correo. Por defecto la
    // dejamos "sin conectar" para que aparezcan los botones de proveedor.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta(ESTADO_DESCONECTADO)))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('arranca pidiendo iniciar sesión', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /entrar/i })).toBeInTheDocument()
  })

  it('tras iniciar sesión, muestra la bandeja de solicitudes', async () => {
    const user = userEvent.setup()
    render(<App />)
    await entrar(user)
    expect(screen.getByRole('heading', { name: /Bandeja de solicitudes/i })).toBeInTheDocument()
  })

  it('muestra la empresa activa (multi-tenant) en la barra lateral', async () => {
    const user = userEvent.setup()
    render(<App />)
    await entrar(user)
    // "Capsulab" aparece en el selector de empresa y en el breadcrumb.
    expect(screen.getAllByText(/Capsulab/i).length).toBeGreaterThan(0)
  })

  it('lista las solicitudes entrantes de la bandeja', async () => {
    const user = userEvent.setup()
    render(<App />)
    await entrar(user)
    expect(screen.getByText(/Zona Espiga/i)).toBeInTheDocument()
    expect(screen.getByText(/Fórmula 1 LATAM/i)).toBeInTheDocument()
    expect(screen.getByText(/Netflix · Narnia/i)).toBeInTheDocument()
  })

  it('en la bandeja, ofrece conectar un proveedor de correo', async () => {
    const user = userEvent.setup()
    render(<App />)
    await entrar(user)
    // Sin proveedor conectado (estado del backend = null): botones de proveedor.
    expect(screen.getByRole('button', { name: /gmail/i })).toBeInTheDocument()
  })

  it('al conectar Gmail, pide la URL de consentimiento al backend y navega a ella (T14)', async () => {
    const user = userEvent.setup()
    const url = 'https://accounts.google.com/o/oauth2/v2/auth?scope=gmail.readonly&state=xyz'
    // El backend responde la URL en /gmail/iniciar; el GET de estado, "sin conectar".
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      if (u.includes('/gmail/iniciar')) return Promise.resolve(respuesta({ url }))
      return Promise.resolve(respuesta(ESTADO_DESCONECTADO))
    })
    vi.stubGlobal('fetch', fetchMock)
    const navegar = vi.fn()

    render(<App onNavegar={navegar} />)
    await entrar(user)
    await user.click(screen.getByRole('button', { name: /gmail/i }))

    // Navega a la URL EXACTA del backend (no se inventa una URL en el cliente).
    await waitFor(() => expect(navegar).toHaveBeenCalledWith(url))
  })
})
