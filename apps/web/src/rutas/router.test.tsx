// Tests de navegación con React Router v7 (spec 016).
//
// Montan el árbol REAL de rutas (crearRutas) en un createMemoryRouter, con los
// módulos de api y Supabase mockeados (mismo patrón que SolicitudContext.test.tsx):
// aquí se prueba el valor del cambio — deep-links y refresh REHIDRATAN el estado
// desde el backend en vez de perderlo (CA1-CA5 de la spec 016).

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, RouterProvider } from 'react-router'
import type { Solicitud } from '../tipos'

// ── Mock de Supabase (mismo patrón que los tests de contextos) ───────────────
vi.mock('../supabase/cliente', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      signInWithPassword: vi.fn(),
      signOut: vi.fn(),
      onAuthStateChange: vi.fn().mockImplementation(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
    },
  },
}))

// ── Mocks de los módulos de api (los contextos y contenedores los consumen) ──
vi.mock('../api/empresa', () => ({
  obtenerEmpresa: vi.fn().mockResolvedValue({
    nombre: 'Capsulab', color: '#F04E37', marca: 'C', etiqueta: 'piloto',
  }),
}))
vi.mock('../api/usuario', () => ({
  obtenerUsuario: vi.fn().mockResolvedValue({ onboarding_visto: true }),
  marcarOnboardingVisto: vi.fn().mockResolvedValue(undefined),
}))
vi.mock('../api/recursos', () => ({
  obtenerRecursosDrive: vi.fn().mockResolvedValue([]),
}))
vi.mock('../api/integraciones', () => ({
  ESTADO_DESCONECTADO: { proveedor: null, estado: null, casilla: null },
  obtenerEstadoCorreo: vi.fn(),
  iniciarConexionGmail: vi.fn().mockResolvedValue('https://oauth.example'),
  desconectarCorreo: vi.fn().mockResolvedValue(undefined),
}))
vi.mock('../api/solicitudes', () => ({
  obtenerSolicitudes: vi.fn(),
  obtenerSolicitudesOError: vi.fn(),
}))
vi.mock('../api/conversaciones', () => ({
  obtenerSugerencias: vi.fn().mockResolvedValue([]),
  iniciarConversacion: vi.fn().mockResolvedValue({ texto: '¡Hola!' }),
  obtenerHistorialConversacion: vi.fn(),
  obtenerCotizacionEnCurso: vi.fn(),
}))
vi.mock('../api/propuestas', () => ({
  obtenerPropuesta: vi.fn(),
  guardarPropuesta: vi.fn().mockResolvedValue(null),
  listarPropuestasOError: vi.fn().mockResolvedValue([]),
  listarPropuestas: vi.fn().mockResolvedValue([]),
}))
vi.mock('../api/tareas', () => ({
  listarTareasOError: vi.fn().mockResolvedValue([]),
  listarTareas: vi.fn().mockResolvedValue([]),
}))
vi.mock('../api/javo', () => ({
  conversarConJavoOError: vi.fn(),
}))

// Resto de llamadas sueltas (p. ej. estado de ClickUp en Configuración): fetch
// global mockeado para que nada golpee la red.
vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
  ok: true,
  status: 200,
  json: () => Promise.resolve([]),
}))

import { supabase } from '../supabase/cliente'
import { obtenerEstadoCorreo } from '../api/integraciones'
import { obtenerSolicitudes, obtenerSolicitudesOError } from '../api/solicitudes'
import { obtenerCotizacionEnCurso, obtenerHistorialConversacion } from '../api/conversaciones'
import { obtenerPropuesta } from '../api/propuestas'
import { crearRutas } from '../router'

// ── Datos de prueba ──────────────────────────────────────────────────────────

const SOLICITUD: Solicitud = {
  id: 's1',
  remitente: 'Carolina Herrera',
  correo: 'eventos@212.cl',
  tiempo: '09-jun',
  asunto: '212 VIP — activación de fragancia',
  tipo: 't1',
  resumen: 'Activación 212 VIP en retail',
  puntos: [],
  cuerpo: 'Necesitamos cotizar una activación en retail…',
}

const SESION_ACTIVA = {
  data: { session: { user: { email: 'javier@capsulab.cl' } } },
}

const mockAuth = supabase.auth as unknown as {
  getSession: ReturnType<typeof vi.fn>
}

/** Monta el árbol real de rutas en un router de memoria arrancando en `ruta`. */
function renderEnRuta(ruta: string) {
  const router = createMemoryRouter(crearRutas(), { initialEntries: [ruta] })
  render(<RouterProvider router={router} />)
  return router
}

describe('Router (spec 016) — deep-links, navegación y rehidratación', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Por defecto: sesión activa, bandeja desconectada, backend "vacío".
    mockAuth.getSession.mockResolvedValue(SESION_ACTIVA)
    vi.mocked(obtenerEstadoCorreo).mockResolvedValue({
      proveedor: null, estado: null, casilla: null,
    })
    vi.mocked(obtenerSolicitudes).mockResolvedValue([SOLICITUD])
    vi.mocked(obtenerSolicitudesOError).mockResolvedValue([SOLICITUD])
    vi.mocked(obtenerHistorialConversacion).mockResolvedValue([])
    vi.mocked(obtenerCotizacionEnCurso).mockResolvedValue({
      componentes: [], tareas: [], fuentes: [],
    })
    vi.mocked(obtenerPropuesta).mockResolvedValue(null)
  })

  it('CA1: deep-link a /bandeja/:id rehidrata la solicitud y muestra su detalle', async () => {
    renderEnRuta('/bandeja/s1')

    // El detalle se pinta con la solicitud que el contenedor buscó en el backend.
    expect(await screen.findByText('Carolina Herrera')).toBeInTheDocument()
    expect(screen.getByText(/Activación 212 VIP en retail/i)).toBeInTheDocument()
    expect(screen.getByText(/Volver a la bandeja/i)).toBeInTheDocument()
    expect(obtenerSolicitudes).toHaveBeenCalled()
  })

  it('CA1: deep-link a /bandeja/:id con un id inexistente muestra NotFound', async () => {
    renderEnRuta('/bandeja/no-existe')

    expect(await screen.findByText(/Página no encontrada/i)).toBeInTheDocument()
  })

  it('CA2: deep-link a /bandeja/:id/chat repuebla el historial de la conversación', async () => {
    vi.mocked(obtenerHistorialConversacion).mockResolvedValue([
      { rol: 'javo', contenido: '¡Hola! Leí el correo de 212.' },
      { rol: 'usuario', contenido: 'Necesito 6 promotoras uniformadas' },
    ])

    renderEnRuta('/bandeja/s1/chat')

    // Los mensajes persistidos aparecen SIN iniciar una conversación nueva.
    expect(await screen.findByText('¡Hola! Leí el correo de 212.')).toBeInTheDocument()
    expect(screen.getByText('Necesito 6 promotoras uniformadas')).toBeInTheDocument()
    expect(obtenerHistorialConversacion).toHaveBeenCalledWith('s1')
    expect(obtenerCotizacionEnCurso).toHaveBeenCalledWith('s1')
  })

  it('CA3: hacer clic en una solicitud de la bandeja navega a /bandeja/:id', async () => {
    const user = userEvent.setup()
    // Bandeja conectada a Gmail para que cargue las solicitudes.
    vi.mocked(obtenerEstadoCorreo).mockResolvedValue({
      proveedor: 'gmail', estado: 'conectado', casilla: 'javier@capsulab.cl',
    })

    const router = renderEnRuta('/bandeja')

    await user.click(await screen.findByText('Carolina Herrera'))

    // La URL refleja la solicitud abierta (deep-link compartible) y se ve el detalle.
    await waitFor(() => expect(router.state.location.pathname).toBe('/bandeja/s1'))
    expect(await screen.findByText(/Volver a la bandeja/i)).toBeInTheDocument()
  })

  it('CA4: deep-link a /propuestas/:id repuebla los componentes vía obtenerPropuesta', async () => {
    vi.mocked(obtenerPropuesta).mockResolvedValue({
      componentes: [
        { nombre: 'Promotoras uniformadas', detalle: '3 tiendas', cantidad: 6, dias: 3, valor: 240000 },
      ],
      tareas: [],
    })

    renderEnRuta('/propuestas/s1')

    expect(await screen.findByText(/Promotoras uniformadas/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Propuesta resuelta/i })).toBeInTheDocument()
    expect(obtenerPropuesta).toHaveBeenCalledWith('s1')
  })

  it('CA5: sin sesión, una ruta protegida muestra el Login (no la pantalla)', async () => {
    mockAuth.getSession.mockResolvedValue({ data: { session: null } })

    renderEnRuta('/bandeja')

    expect(await screen.findByRole('button', { name: /entrar/i })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /Bandeja de solicitudes/i })).not.toBeInTheDocument()
  })
})
