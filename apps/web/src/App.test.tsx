import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// ── Mock de Supabase ─────────────────────────────────────────────────────────
// vi.mock se hoistea: el factory NO puede referenciar variables del módulo.
// Usamos vi.fn() directamente en el factory; los tests ajustan el comportamiento
// con mockResolvedValue / mockReturnValue en beforeEach.
vi.mock('./supabase/cliente', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      signInWithPassword: vi.fn(),
      signOut: vi.fn(),
      onAuthStateChange: vi.fn(),
    },
  },
}))

// El usuario de estos tests ya vio el onboarding → sin slider de bienvenida (no tapa
// el flujo) y sin un fetch extra a /usuario que descuadre el orden de respuestas.
vi.mock('./api/usuario', () => ({
  obtenerUsuario: vi.fn().mockResolvedValue({ onboarding_visto: true }),
  marcarOnboardingVisto: vi.fn().mockResolvedValue(undefined),
}))

import { supabase } from './supabase/cliente'
import App from './App'
import { SesionProvider } from './contextos/SesionContext'
import { SolicitudProvider } from './contextos/SolicitudContext'
import { BandejaProvider } from './contextos/BandejaContext'

/** Helper: renderiza App envuelto en los tres providers (requerido tras la extracción de contextos). */
function renderApp(props?: { onNavegar?: (url: string) => void }) {
  return render(
    <SesionProvider>
      <SolicitudProvider>
        <BandejaProvider>
          <App {...props} />
        </BandejaProvider>
      </SolicitudProvider>
    </SesionProvider>,
  )
}

// Alias tipado para acceder a los mocks sin castings repetitivos.
const mockAuth = supabase.auth as unknown as {
  getSession: ReturnType<typeof vi.fn>
  signInWithPassword: ReturnType<typeof vi.fn>
  signOut: ReturnType<typeof vi.fn>
  onAuthStateChange: ReturnType<typeof vi.fn>
}

// Referencia al callback de onAuthStateChange para dispararlo en los tests.
let authStateCallback: ((event: string, session: unknown) => void) | null = null

/** `Response` mínima (sólo ok/status/json, que es lo que usa la capa de API). */
function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

/** Estado de bandeja "sin conectar" que devuelve el backend por defecto. */
const ESTADO_DESCONECTADO = { proveedor: null, estado: null, casilla: null }

/**
 * Inicia sesión en el demo disparando el flujo real de Supabase (mockeado).
 * Tras el login, el landing es el onboarding de Configuración (no la bandeja);
 * los tests que necesitan la bandeja llaman luego a `irABandeja`.
 */
async function entrar(user: ReturnType<typeof userEvent.setup>) {
  // Esperar que el login aparezca (App arranca con sesion=undefined, renderiza null
  // hasta que getSession resuelve, luego muestra el login).
  await screen.findByLabelText(/correo/i)
  await user.type(screen.getByLabelText(/correo/i), 'javier@capsulab.cl')
  await user.type(screen.getByLabelText(/contraseña/i), 'capsulab2024')
  await user.click(screen.getByRole('button', { name: /entrar/i }))
  // Simula que Supabase notifica la sesión activa tras el sign-in.
  // act() envuelve la actualización de estado para que React la procese.
  await act(async () => {
    authStateCallback?.('SIGNED_IN', { user: { email: 'javier@capsulab.cl' } })
  })
}

/** Inicia sesión y avanza desde el onboarding a la bandeja ("Continuar a la bandeja ▸"). */
async function entrarABandeja(user: ReturnType<typeof userEvent.setup>) {
  await entrar(user)
  await user.click(await screen.findByRole('button', { name: /continuar a la bandeja/i }))
}

describe('App (arnés)', () => {
  beforeEach(() => {
    // Aislamiento: useSincronizarRuta hace pushState (NO es no-op en jsdom), así que
    // la URL se filtra entre tests. Reseteamos a "/" para que cada test arranque en la
    // pantalla por defecto (configuracion) y no herede la ruta del test anterior.
    window.history.replaceState(null, '', '/')
    authStateCallback = null
    mockAuth.getSession.mockResolvedValue({ data: { session: null } })
    mockAuth.signInWithPassword.mockResolvedValue({ error: null })
    mockAuth.signOut.mockResolvedValue({})
    mockAuth.onAuthStateChange.mockImplementation((cb: (event: string, session: unknown) => void) => {
      authStateCallback = cb
      return { data: { subscription: { unsubscribe: vi.fn() } } }
    })
    // Al montar, la bandeja consulta GET /integraciones/correo. Por defecto la
    // dejamos "sin conectar" para que aparezcan los botones de proveedor.
    // También GET /empresa responde con Capsulab (empresa del piloto).
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      if (u.includes('/empresa')) {
        return Promise.resolve(respuesta({ id: 'e1', nombre: 'Capsulab', color_marca: '#F04E37', plan: 'piloto' }))
      }
      return Promise.resolve(respuesta(ESTADO_DESCONECTADO))
    }))
  })

  afterEach(() => {
    // Por si un test que usó timers falsos murió antes de restaurarlos: evita que
    // se filtren al resto de la suite.
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('arranca pidiendo iniciar sesión', async () => {
    renderApp()
    expect(await screen.findByRole('button', { name: /entrar/i })).toBeInTheDocument()
  })

  it('tras iniciar sesión, muestra el onboarding de Configuración (no la bandeja)', async () => {
    const user = userEvent.setup()
    renderApp()
    await entrar(user)
    // El landing post-login es el onboarding: "Prepara tu espacio".
    expect(await screen.findByRole('heading', { name: /Prepara tu espacio/i })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /Bandeja de solicitudes/i })).not.toBeInTheDocument()
  })

  it('desde el onboarding, "Continuar a la bandeja" lleva a la bandeja de solicitudes', async () => {
    const user = userEvent.setup()
    renderApp()
    await entrarABandeja(user)
    expect(screen.getByRole('heading', { name: /Bandeja de solicitudes/i })).toBeInTheDocument()
  })

  it('mantiene la sesión tras recargar (no rebota al login)', async () => {
    const user = userEvent.setup()
    const { unmount } = renderApp()
    await entrarABandeja(user)
    expect(screen.getByRole('heading', { name: /Bandeja de solicitudes/i })).toBeInTheDocument()

    // Simula un refresh: ahora getSession devuelve sesión activa (como haría el
    // cliente real de Supabase que persiste la sesión en localStorage).
    mockAuth.getSession.mockResolvedValue({
      data: { session: { user: { email: 'javier@capsulab.cl' }, access_token: 'tok' } },
    })
    unmount()
    renderApp()
    // Supabase notifica la sesión ya activa al montar.
    await act(async () => {
      authStateCallback?.('SIGNED_IN', { user: { email: 'javier@capsulab.cl' } })
    })

    // Tras recargar se entra directo a la app (landing = onboarding), sin rebotar al login.
    expect(await screen.findByRole('heading', { name: /Prepara tu espacio/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /entrar/i })).not.toBeInTheDocument()
  })

  it('muestra la empresa activa (multi-tenant) en la barra lateral', async () => {
    const user = userEvent.setup()
    renderApp()
    await entrar(user)
    // "Capsulab" aparece en el selector de empresa y en el breadcrumb.
    expect(screen.getAllByText(/Capsulab/i).length).toBeGreaterThan(0)
  })

  it('con la bandeja conectada, lista las solicitudes reales que entrega el backend', async () => {
    const user = userEvent.setup()
    // Contrato actual: la lista ya NO sale de mocks. Si la bandeja está conectada,
    // el front pide GET /solicitudes y pinta lo que devuelve el backend (la
    // empresa real). Mockeamos ambos: estado "conectado" + las solicitudes.
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      if (u.includes('/solicitudes')) {
        return Promise.resolve(
          respuesta([
            {
              id: 's1',
              remitente: 'Carolina Herrera',
              correo_origen: 'eventos@212.cl',
              asunto: '212 VIP — activación de fragancia',
              cuerpo: 'Necesitamos cotizar una activación en retail…',
              resumen: 'Activación 212 VIP en retail',
              tipo: 'tipo_1',
              estado: 'nueva',
            },
            {
              id: 's2',
              remitente: 'Metro de Santiago',
              correo_origen: 'mkt@metro.cl',
              asunto: 'Sampling de sopaipillas',
              cuerpo: 'Queremos un sampling afuera del Metro…',
              resumen: 'Sampling afuera del Metro',
              tipo: 'tipo_1',
              estado: 'nueva',
            },
          ]),
        )
      }
      // GET /integraciones/correo → bandeja conectada a Gmail.
      return Promise.resolve(respuesta({ proveedor: 'gmail', estado: 'conectado', casilla: 'javier@capsulab.cl' }))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp()
    await entrarABandeja(user)

    // Las solicitudes del backend aparecen en la bandeja (llegada asíncrona).
    expect(await screen.findByText(/Carolina Herrera/i)).toBeInTheDocument()
    expect(screen.getByText(/Metro de Santiago/i)).toBeInTheDocument()
  })

  it('con la bandeja conectada, refresca SOLA las solicitudes cada 20s (auto-refresh, sin recargar)', async () => {
    // La gracia del producto: la bandeja se actualiza sola cada 20s para que los
    // correos que el poller va ingiriendo aparezcan sin recargar a mano. Aquí
    // contamos las llamadas a GET /solicitudes y verificamos que tras ~20s sube.
    // Timers falsos ACTIVOS antes del render: así el setInterval(cargar, 20000) que
    // arma el efecto de la bandeja queda bajo control de los timers falsos y podemos
    // "saltar" 20s sin esperar de verdad. `shouldAdvanceTime` deja que el reloj
    // avance también en tiempo real, para que el polling interno de findBy/waitFor
    // (login + onboarding) no se cuelgue. `advanceTimers` ata userEvent al reloj falso.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    let llamadasSolicitudes = 0
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      if (u.includes('/solicitudes')) {
        llamadasSolicitudes += 1
        return Promise.resolve(respuesta([]))
      }
      // GET /integraciones/correo → bandeja conectada a Gmail.
      return Promise.resolve(respuesta({ proveedor: 'gmail', estado: 'conectado', casilla: 'javier@capsulab.cl' }))
    })
    vi.stubGlobal('fetch', fetchMock)

    try {
      renderApp()
      await entrarABandeja(user)

      // 1ª carga al entrar a la bandeja (carga inmediata del efecto).
      await waitFor(() => expect(llamadasSolicitudes).toBeGreaterThanOrEqual(1))
      const tras1raCarga = llamadasSolicitudes

      // Avanza ~20s: el setInterval(cargar, 20000) dispara una nueva carga.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(20000)
      })

      // La bandeja RE-pidió /solicitudes sola (el contador subió), sin recargar.
      expect(llamadasSolicitudes).toBeGreaterThan(tras1raCarga)
    } finally {
      vi.useRealTimers()
    }
  })

  it('con la bandeja en "reconectar", igual muestra las solicitudes ya ingeridas y el banner de reconectar', async () => {
    const user = userEvent.setup()
    // Bug en prod: hay correos ingeridos pero el token de Gmail quedó en
    // 'reconectar'. La bandeja debe SEGUIR mostrando esos correos (el backend ya
    // filtra por empresa con RLS) y, además, avisar que hay que reconectar para
    // los FUTUROS correos. Antes el front vaciaba la lista y la bandeja salía vacía.
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      if (u.includes('/solicitudes')) {
        return Promise.resolve(
          respuesta([
            {
              id: 's1',
              remitente: 'Carolina Herrera',
              correo_origen: 'eventos@212.cl',
              asunto: '212 VIP — activación de fragancia',
              cuerpo: 'Necesitamos cotizar una activación en retail…',
              resumen: 'Activación 212 VIP en retail',
              tipo: 'tipo_1',
              estado: 'nueva',
            },
          ]),
        )
      }
      // GET /integraciones/correo → bandeja con el token caído (reconectar).
      return Promise.resolve(
        respuesta({ proveedor: 'gmail', estado: 'reconectar', casilla: 'javier@capsulab.cl' }),
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp()
    await entrarABandeja(user)

    // Los correos ya ingeridos SIGUEN visibles aunque el estado sea 'reconectar'.
    expect(await screen.findByText(/Carolina Herrera/i)).toBeInTheDocument()
    // Y el banner de reconectar sigue arriba (avisa para los próximos correos).
    expect(screen.getByText(/Reconecta tu bandeja/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Reconectar/i })).toBeInTheDocument()
  })

  it('si la carga de la bandeja falla, muestra un banner de error y "Reintentar" recarga', async () => {
    const user = userEvent.setup()
    // Bandeja conectada, pero el 1er GET /solicitudes falla (backend caído).
    // El front NO debe mostrar un vacío mudo: muestra un banner con "Reintentar".
    // Al reintentar, el 2º GET ya responde y aparecen las solicitudes.
    let intentos = 0
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      if (u.includes('/solicitudes')) {
        intentos += 1
        if (intentos === 1) return Promise.resolve(respuesta(null, false, 500))
        return Promise.resolve(
          respuesta([
            {
              id: 's1',
              remitente: 'Carolina Herrera',
              correo_origen: 'eventos@212.cl',
              asunto: '212 VIP — activación de fragancia',
              cuerpo: 'Necesitamos cotizar…',
              resumen: 'Activación 212 VIP en retail',
              tipo: 'tipo_1',
              estado: 'nueva',
            },
          ]),
        )
      }
      return Promise.resolve(respuesta({ proveedor: 'gmail', estado: 'conectado', casilla: 'javier@capsulab.cl' }))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp()
    await entrarABandeja(user)

    // El fallo se ve como banner, no como vacío silencioso.
    expect(await screen.findByText(/No se pudieron cargar las solicitudes/i)).toBeInTheDocument()

    // Reintentar dispara una nueva carga, que ahora trae las solicitudes.
    await user.click(screen.getByRole('button', { name: /reintentar/i }))
    expect(await screen.findByText(/Carolina Herrera/i)).toBeInTheDocument()
    expect(screen.queryByText(/No se pudieron cargar las solicitudes/i)).not.toBeInTheDocument()
  })

  it('en la bandeja, ofrece conectar un proveedor de correo', async () => {
    const user = userEvent.setup()
    renderApp()
    await entrarABandeja(user)
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

    renderApp({ onNavegar: navegar })
    await entrarABandeja(user)
    await user.click(screen.getByRole('button', { name: /gmail/i }))

    // Navega a la URL EXACTA del backend (no se inventa una URL en el cliente).
    await waitFor(() => expect(navegar).toHaveBeenCalledWith(url))
  })

  it('al generar la propuesta, muestra la cotización REAL del backend (no el mock)', async () => {
    const user = userEvent.setup()
    // Bandeja conectada + una solicitud (212CH) + su propuesta real en el backend.
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      if (u.includes('/propuesta')) {
        return Promise.resolve(
          respuesta({
            id: 'p-212',
            total: 5190000,
            estado: 'borrador',
            componentes: [
              { nombre: 'Promotoras uniformadas', detalle: '3 tiendas', cantidad: 6, valor_unitario: 240000 },
            ],
            tareas: [
              { nombre: 'Reclutar 6 promotoras', grupo: 'RRHH', responsable: 'Coordinación', vencimiento: '3 días' },
            ],
          }),
        )
      }
      if (u.includes('/solicitudes')) {
        return Promise.resolve(
          respuesta([
            {
              id: 's-212',
              remitente: 'Carolina Herrera · 212',
              correo_origen: 'marketing@carolinaherrera.cl',
              asunto: 'Cotización activación 212 VIP Black',
              cuerpo: 'Necesitamos cotizar una activación de sampling…',
              resumen: 'Activación de sampling para 212 VIP Black en 3 tiendas.',
              tipo: 'tipo_1',
              estado: 'nueva',
            },
          ]),
        )
      }
      // Estado de la bandeja: conectada a Gmail.
      return Promise.resolve(respuesta({ proveedor: 'gmail', estado: 'conectado', casilla: 'javier@capsulab.cl' }))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp()
    await entrarABandeja(user)

    // Abre la 212CH desde la bandeja → elige Tipo 1 → entra al chat.
    await user.click(await screen.findByText(/Carolina Herrera/i))
    await user.click(screen.getByText(/Tipo 1 · Cotización concreta/i))
    // Genera la propuesta: el front pide la cotización real al backend.
    await user.click(screen.getByRole('button', { name: /Generar propuesta/i }))

    // La tabla muestra el componente del backend, NO el mock de sopaipillas.
    expect(await screen.findByText(/Promotoras uniformadas/i)).toBeInTheDocument()
    expect(screen.queryByText(/Catering sopaipillas/i)).not.toBeInTheDocument()
  })

  it('desde el menú "Propuestas", lista las propuestas reales y abre el detalle al hacer clic', async () => {
    const user = userEvent.setup()
    // El backend entrega la lista (GET /propuestas) y, al abrir una, su detalle
    // (GET /solicitudes/{id}/propuesta). No hay mock de sopaipillas de por medio.
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      if (u.includes('/solicitudes/s-212/propuesta')) {
        return Promise.resolve(
          respuesta({
            id: 'p-212',
            total: 5190000,
            estado: 'borrador',
            componentes: [
              { nombre: 'Promotoras uniformadas', detalle: '3 tiendas', cantidad: 6, valor_unitario: 240000 },
            ],
            tareas: [],
          }),
        )
      }
      if (u.includes('/propuestas')) {
        return Promise.resolve(
          respuesta([
            {
              id: 'p-212',
              solicitud_id: 's-212',
              total: 5190000,
              estado: 'borrador',
              asunto: 'Cotización activación 212 VIP Black',
              remitente: 'Carolina Herrera · 212',
            },
          ]),
        )
      }
      return Promise.resolve(respuesta(ESTADO_DESCONECTADO))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp()
    await entrar(user)

    // Navega a la lista de propuestas desde el menú lateral.
    await user.click(screen.getByText('Propuestas'))
    // La fila real del backend aparece (asunto del correo).
    expect(await screen.findByText(/Cotización activación 212 VIP Black/i)).toBeInTheDocument()

    // Al hacer clic en la fila, abre el detalle: la cotización real del backend.
    await user.click(screen.getByText(/Cotización activación 212 VIP Black/i))
    expect(await screen.findByText(/Promotoras uniformadas/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Propuesta resuelta/i })).toBeInTheDocument()
  })

  it('desde el menú "Tareas", lista las tareas reales del backend (no el mock)', async () => {
    const user = userEvent.setup()
    // El backend entrega la lista global de tareas (GET /tareas).
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      if (u.includes('/tareas')) {
        return Promise.resolve(
          respuesta([
            { nombre: 'Reclutar 6 promotoras', grupo: 'RRHH', responsable: 'Coordinación', vencimiento: '3 días' },
          ]),
        )
      }
      return Promise.resolve(respuesta(ESTADO_DESCONECTADO))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp()
    await entrar(user)

    await user.click(screen.getByText('Tareas'))
    // La tarea real del backend aparece; el mock de sopaipillas ya no existe.
    expect(await screen.findByText(/Reclutar 6 promotoras/i)).toBeInTheDocument()
    expect(screen.queryByText(/contratar catering de sopaipillas/i)).not.toBeInTheDocument()
  })

  it('en el chat, Javo propone componentes reales del Drive (con origen) y cita fuentes', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      if (u.includes('/conversaciones/responder')) {
        // Javo respondió usando el catálogo del Drive: trae componentes (con origen) y fuentes.
        return Promise.resolve(
          respuesta({
            texto: 'Las promotoras quedan a $240.000 c/u.',
            componentes: [
              {
                nombre: 'Promotoras uniformadas',
                detalle: '3 tiendas',
                cantidad: 6,
                valor_unitario: 240000,
                origen: 'Tarifario_promotores_2026.xlsx',
              },
            ],
            fuentes: [{ titulo: 'Caso Red Bull F1', referencia: 'https://ejemplo.cl/f1' }],
          }),
        )
      }
      if (u.includes('/solicitudes')) {
        return Promise.resolve(
          respuesta([
            {
              id: 's-212',
              remitente: 'Carolina Herrera · 212',
              correo_origen: 'marketing@carolinaherrera.cl',
              asunto: 'Cotización activación 212 VIP Black',
              cuerpo: 'Necesitamos cotizar promotoras…',
              resumen: 'Activación de sampling 212 VIP Black.',
              tipo: 'tipo_1',
              estado: 'nueva',
            },
          ]),
        )
      }
      return Promise.resolve(respuesta({ proveedor: 'gmail', estado: 'conectado', casilla: 'javier@capsulab.cl' }))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp()
    await entrarABandeja(user)
    await user.click(await screen.findByText(/Carolina Herrera/i))
    await user.click(screen.getByText(/Tipo 1 · Cotización concreta/i))
    // Envía un mensaje (chip) → Javo responde consultando el Drive.
    await user.click(screen.getByText('Son 3 días de activación'))

    // El panel del chat muestra el componente REAL, su origen del Drive y la fuente citada.
    expect(await screen.findByText(/Promotoras uniformadas/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Tarifario_promotores_2026/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Caso Red Bull F1/i)).toBeInTheDocument()
  })

  it('al rehidratar la conversación, REPUEBLA el panel con la cotización en curso persistida (0009)', async () => {
    const user = userEvent.setup()
    // El backend ya tiene un borrador de cotización para esta solicitud (componentes que
    // Javo armó en una sesión anterior). NO hay propuesta confirmada (GET /propuesta 404).
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const u = String(input)
      // El hilo de texto se rehidrata (mensajes previos).
      if (u.includes('/conversaciones/s-212/cotizacion')) {
        return Promise.resolve(
          respuesta({
            componentes: [
              {
                nombre: 'Promotoras uniformadas',
                detalle: '3 tiendas',
                cantidad: 6,
                dias: 3,
                valor_unitario: 240000,
                origen: 'Tarifario_promotores_2026.xlsx',
              },
            ],
            tareas: [{ nombre: 'Reclutar 6 promotoras', area: 'RRHH', plazo: '3 días', responsable: null }],
            fuentes: [{ titulo: 'Caso Red Bull F1', referencia: 'https://ejemplo.cl/f1' }],
          }),
        )
      }
      if (u.endsWith('/conversaciones/s-212')) {
        return Promise.resolve(
          respuesta([
            { rol: 'javo', contenido: '¡Hola! Leí el correo.' },
            { rol: 'usuario', contenido: 'Son 3 días de activación' },
            { rol: 'javo', contenido: 'Listo, dejo 6 promotoras.' },
          ]),
        )
      }
      // No hay propuesta confirmada todavía → 404 (la cotización vive solo en el borrador).
      if (u.includes('/propuesta')) {
        return Promise.resolve(respuesta({}, false, 404))
      }
      if (u.includes('/solicitudes')) {
        return Promise.resolve(
          respuesta([
            {
              id: 's-212',
              remitente: 'Carolina Herrera · 212',
              correo_origen: 'marketing@carolinaherrera.cl',
              asunto: 'Cotización activación 212 VIP Black',
              cuerpo: 'Necesitamos cotizar promotoras…',
              resumen: 'Activación de sampling 212 VIP Black.',
              tipo: 'tipo_1',
              estado: 'nueva',
            },
          ]),
        )
      }
      return Promise.resolve(respuesta({ proveedor: 'gmail', estado: 'conectado', casilla: 'javier@capsulab.cl' }))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp()
    await entrarABandeja(user)
    await user.click(await screen.findByText(/Carolina Herrera/i))
    // Entra al chat: SIN enviar ningún mensaje, el panel ya trae la cotización persistida.
    await user.click(screen.getByText(/Tipo 1 · Cotización concreta/i))

    // El panel "Componentes" se repobló desde el borrador (no quedó vacío ni pidió conversar).
    expect(await screen.findByText(/Promotoras uniformadas/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Tarifario_promotores_2026/i).length).toBeGreaterThan(0)
    // Las fuentes citadas también se rehidratan.
    expect(screen.getByText(/Caso Red Bull F1/i)).toBeInTheDocument()
  })
})
