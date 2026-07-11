// Soporte de la suite E2E `ui` (spec 018): red MOCKEADA con page.route().
//
// La app corre de verdad (Vite + React + supabase-js), pero toda la red sale
// interceptada: Supabase auth (/auth/v1/**) y el backend (/api/**) responden
// fixtures deterministas en español, espejo del seed de Capsulab y de los dobles
// del backend. Cero Docker, cero claves, cero LLM: corre en cualquier CI.

import { expect, type Page, type Route } from '@playwright/test'

export const CORREO_E2E = 'javier@capsulab.cl'

// ── Fixtures (espejo del seed Capsulab) ───────────────────────────────────────

export const SOLICITUDES = [
  {
    id: 'e2e00001-0000-4000-8000-000000000001',
    remitente: 'Zona Espiga',
    correo_origen: 'contacto@zonaespiga.cl',
    asunto: 'Cotización sampling de sopaipillas afuera del Metro',
    cuerpo: 'Hola Javo, queremos cotizar un sampling de sopaipillas afuera del Metro.',
    resumen: 'Sampling de sopaipillas afuera del Metro.',
    tipo: 'tipo_1',
    estado: 'nueva',
    recibido_en: '2026-06-09T09:42:00+00:00',
  },
  {
    id: 'e2e00002-0000-4000-8000-000000000002',
    remitente: 'Fórmula 1 LATAM',
    correo_origen: 'marketing@f1latam.com',
    asunto: 'Necesitamos ideas — activación Fórmula 1',
    cuerpo: 'Hola Javo, necesitamos ideas de alto impacto para la Fórmula 1.',
    resumen: 'Ideas de activación para la Fórmula 1.',
    tipo: 'tipo_2',
    estado: 'nueva',
    recibido_en: '2026-06-08T15:10:00+00:00',
  },
  {
    id: 'e2e00003-0000-4000-8000-000000000003',
    remitente: 'Netflix · Narnia',
    correo_origen: 'activaciones@partner.netflix.com',
    asunto: 'Activación estreno Narnia en cines (Octubre)',
    cuerpo: 'Hola Javo, pensamos algo para el estreno de Narnia.',
    resumen: null,
    tipo: 'sin_clasificar',
    estado: 'nueva',
    recibido_en: '2026-06-07T11:00:00+00:00',
  },
]

export const SOLICITUD_T1 = SOLICITUDES[0]
export const SOLICITUD_T2 = SOLICITUDES[1]

// Componentes que "propone Javo": costo = cantidad × días × valor.
// 6×3×35.000 = 630.000 · 1×3×180.000 = 540.000 → total 1.170.000, venta $1.950.000.
const COMPONENTES_JAVO = [
  {
    nombre: 'Promotoras uniformadas',
    detalle: 'Uniformadas BTL · 3 tiendas',
    cantidad: 6,
    dias: 3,
    valor_unitario: 35000,
    proveedor: 'Staff Eventos',
    origen: 'Tarifario BTL 2026.xlsx',
  },
  {
    nombre: 'Catering sopaipillas',
    detalle: 'Producto e insumos',
    cantidad: 1,
    dias: 3,
    valor_unitario: 180000,
    proveedor: null,
    origen: 'Tarifario BTL 2026.xlsx',
  },
]

const TAREAS_JAVO = [
  { nombre: 'Reclutar promotoras', area: 'RRHH', plazo: '3 días', responsable: null },
  { nombre: 'Comprar insumos', area: 'Compras', plazo: '1 semana', responsable: null },
]

const FUENTES_JAVO = [
  { titulo: 'Tarifario BTL 2026.xlsx', referencia: 'Drive: Tarifario BTL 2026.xlsx' },
]

const RESPUESTA_JAVO = {
  texto:
    'Te propongo el escenario recomendado: 6 promotoras por 3 días más catering. ' +
    'Total estimado $1.950.000 con el tarifario del Drive. ¿Genero la propuesta?',
  componentes: COMPONENTES_JAVO,
  tareas: TAREAS_JAVO,
  fuentes: FUENTES_JAVO,
}

const RESPUESTA_JAVO_T2 = {
  texto:
    'Encontré referencias afuera: te recomiendo el simulador de pit-stop con sampling. ' +
    '¿La aterrizamos y la cotizamos?',
  componentes: [],
  tareas: [],
  fuentes: [{ titulo: 'Caso F1 Fanzone', referencia: 'https://ejemplo.cl/f1-fanzone' }],
}

// Propuesta persistida (forma de GET/POST /solicitudes/{id}/propuesta).
const PROPUESTA = {
  id: 'e2e-prop-0001',
  total: 1950000,
  estado: 'borrador',
  componentes: COMPONENTES_JAVO,
  tareas: TAREAS_JAVO.map((t) => ({
    nombre: t.nombre,
    grupo: t.area,
    responsable: t.responsable,
    vencimiento: t.plazo,
  })),
}

// ── Estado mutable del "backend" mockeado (por página) ───────────────────────

export interface EstadoMock {
  onboardingVisto: boolean
  estadoCorreo: { proveedor: string | null; estado: string | null; casilla: string | null }
  estadoClickup: { proveedor: string | null; estado: string | null }
  /** Hilo persistido por solicitud (rehidratación del chat en deep-link/refresh). */
  historial: Record<string, { rol: string; contenido: string }[]>
  /** Borrador de cotización por solicitud. */
  cotizacion: Record<string, { componentes: unknown[]; tareas: unknown[]; fuentes: unknown[] }>
  /** Hay propuesta persistida por solicitud. */
  propuestas: Record<string, typeof PROPUESTA>
}

export function estadoInicial(): EstadoMock {
  return {
    onboardingVisto: true,
    estadoCorreo: { proveedor: 'gmail', estado: 'conectado', casilla: CORREO_E2E },
    estadoClickup: { proveedor: 'clickup', estado: 'conectado' },
    historial: {},
    cotizacion: {},
    propuestas: {},
  }
}

// ── Mock de Supabase Auth (GoTrue) ────────────────────────────────────────────

const SESION_GOTRUE = {
  access_token: 'jwt-e2e-access-token',
  token_type: 'bearer',
  expires_in: 3600 * 24,
  expires_at: Math.floor(Date.now() / 1000) + 3600 * 24,
  refresh_token: 'jwt-e2e-refresh-token',
  user: {
    id: 'e2e0user-0000-4000-8000-000000000001',
    aud: 'authenticated',
    role: 'authenticated',
    email: CORREO_E2E,
    app_metadata: { provider: 'email' },
    user_metadata: {},
    created_at: '2026-01-01T00:00:00Z',
  },
}

/**
 * Intercepta la auth de Supabase. Con `credencialesInvalidas` el login devuelve
 * 400 (lo que GoTrue responde ante contraseña mala) para probar el error de la UI.
 */
export async function mockSupabaseAuth(
  page: Page,
  { credencialesInvalidas = false }: { credencialesInvalidas?: boolean } = {},
) {
  await page.route('**/auth/v1/token**', async (route) => {
    if (credencialesInvalidas) {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'invalid_grant', error_description: 'Invalid login credentials' }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(SESION_GOTRUE),
    })
  })
  await page.route('**/auth/v1/logout**', (route) => route.fulfill({ status: 204, body: '' }))
  await page.route('**/auth/v1/user**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(SESION_GOTRUE.user) }),
  )
}

// ── Mock del backend (/api/**) ───────────────────────────────────────────────

function json(route: Route, cuerpo: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(cuerpo) })
}

export interface OpcionesMockApi {
  estado?: EstadoMock
  /** Devuelve true si manejó la ruta (para simular fallos puntuales por test). */
  intercepta?: (ruta: string, metodo: string, route: Route) => Promise<boolean> | boolean
}

/**
 * Backend mockeado completo. `estado` es mutable (los POST/PATCH lo cambian) y
 * `intercepta` permite que un test simule un fallo puntual (502/abort) antes de
 * caer al comportamiento feliz por defecto.
 */
export async function mockApi(page: Page, opciones: OpcionesMockApi = {}): Promise<EstadoMock> {
  const estado = opciones.estado ?? estadoInicial()

  // OJO: el matcher es por PATH RAÍZ `/api/...` (el backend detrás del proxy de
  // Vite). Un glob `**/api/**` también atraparía los MÓDULOS del front
  // (`/src/api/*.ts`) y rompería la carga de la app.
  await page.route(
    (url) => url.pathname.startsWith('/api/'),
    async (route) => {
    const url = new URL(route.request().url())
    const ruta = url.pathname.replace(/^\/api/, '')
    const metodo = route.request().method()

    if (opciones.intercepta && (await opciones.intercepta(ruta, metodo, route))) return

    // ── Sesión / empresa / usuario ────────────────────────────────────────
    if (ruta === '/empresa') {
      return json(route, { id: 'e2e-empresa', nombre: 'Capsulab', color_marca: '#F04E37', plan: 'Piloto' })
    }
    if (ruta === '/usuario' && metodo === 'GET') {
      return json(route, { onboarding_visto: estado.onboardingVisto })
    }
    if (ruta === '/usuario/onboarding-visto') {
      estado.onboardingVisto = true
      return json(route, { onboarding_visto: true })
    }

    // ── Conectores ────────────────────────────────────────────────────────
    if (ruta === '/integraciones/correo' && metodo === 'GET') return json(route, estado.estadoCorreo)
    if (ruta === '/integraciones/correo' && metodo === 'DELETE') {
      estado.estadoCorreo = { proveedor: null, estado: null, casilla: null }
      return route.fulfill({ status: 204, body: '' })
    }
    if (ruta === '/integraciones/correo/gmail/iniciar') {
      return json(route, { url: 'https://accounts.google.com/o/oauth2/e2e-falso' })
    }
    if (ruta === '/clickup/estado') return json(route, estado.estadoClickup)
    if (ruta === '/clickup/verificar') {
      return json(route, { estado: 'conectado', mensaje: 'Conexión verificada: 2 listas visibles.' })
    }
    if (ruta === '/clickup/listas') {
      return json(route, [
        { id: 'lista-1', nombre: 'Operaciones', espacio: 'Capsulab' },
        { id: 'lista-2', nombre: 'Comercial', espacio: 'Capsulab' },
      ])
    }

    // ── Bandeja / catálogo / equipo ───────────────────────────────────────
    if (ruta === '/solicitudes') return json(route, SOLICITUDES)
    if (ruta === '/catalogo/recursos') {
      return json(route, ['Tarifario BTL 2026.xlsx', 'Caso Fuchs cerros.pptx'])
    }
    if (ruta === '/miembros') {
      return json(route, [
        { id: 'm1', nombre: 'Isabel Rojas', rol: 'RRHH' },
        { id: 'm2', nombre: 'Pedro Soto', rol: 'Compras' },
      ])
    }
    if (ruta === '/tareas') return json(route, [])
    if (ruta === '/propuestas') {
      return json(
        route,
        Object.entries(estado.propuestas).map(([solicitudId, p]) => ({
          id: p.id,
          solicitud_id: solicitudId,
          total: p.total,
          estado: p.estado,
          asunto: SOLICITUDES.find((s) => s.id === solicitudId)?.asunto ?? '',
          remitente: SOLICITUDES.find((s) => s.id === solicitudId)?.remitente ?? '',
        })),
      )
    }

    // ── Conversación con Javo ─────────────────────────────────────────────
    let m = ruta.match(/^\/conversaciones\/([^/]+)\/iniciar$/)
    if (m) {
      const saludo = { rol: 'javo', contenido: '¡Hola! 👋 Revisé el correo. Partamos por el brief: ¿cuántos días dura la activación?' }
      estado.historial[m[1]] = [saludo]
      return json(route, { texto: saludo.contenido })
    }
    m = ruta.match(/^\/conversaciones\/([^/]+)\/sugerencias$/)
    if (m) {
      return json(route, { chips: ['Dame 2 opciones de presupuesto', 'Sugiere un complemento', 'Genera la propuesta'] })
    }
    m = ruta.match(/^\/conversaciones\/([^/]+)\/cotizacion$/)
    if (m) {
      return json(route, estado.cotizacion[m[1]] ?? { componentes: [], tareas: [], fuentes: [] })
    }
    m = ruta.match(/^\/conversaciones\/([^/]+)$/)
    if (m && metodo === 'GET') return json(route, estado.historial[m[1]] ?? [])
    if (ruta === '/conversaciones/responder') {
      const cuerpo = route.request().postDataJSON() as { solicitud_id: string; tipo: string; mensajes: { rol: string; contenido: string }[] }
      const respuesta = cuerpo.tipo === 't2' ? RESPUESTA_JAVO_T2 : RESPUESTA_JAVO
      // Persistencia (como el backend real): hilo + borrador de cotización.
      estado.historial[cuerpo.solicitud_id] = [
        ...(estado.historial[cuerpo.solicitud_id] ?? []),
        ...cuerpo.mensajes.slice(-1),
        { rol: 'javo', contenido: respuesta.texto },
      ]
      estado.cotizacion[cuerpo.solicitud_id] = {
        componentes: respuesta.componentes,
        tareas: respuesta.tareas,
        fuentes: respuesta.fuentes,
      }
      return json(route, respuesta)
    }

    // ── Propuesta + exports + ClickUp ─────────────────────────────────────
    m = ruta.match(/^\/solicitudes\/([^/]+)\/propuesta$/)
    if (m && metodo === 'POST') {
      estado.propuestas[m[1]] = PROPUESTA
      return json(route, PROPUESTA, 201)
    }
    if (m && metodo === 'GET') {
      const p = estado.propuestas[m[1]]
      return p ? json(route, p) : json(route, { detail: 'La solicitud no tiene propuesta' }, 404)
    }
    m = ruta.match(/^\/solicitudes\/([^/]+)\/cotizacion\.xlsx$/)
    if (m) {
      return route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        body: Buffer.from('PK-e2e-xlsx'),
      })
    }
    m = ruta.match(/^\/solicitudes\/([^/]+)\/propuesta\.pptx$/)
    if (m) {
      return route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        body: Buffer.from('PK-e2e-pptx'),
      })
    }
    m = ruta.match(/^\/solicitudes\/([^/]+)\/tareas\/clickup$/)
    if (m) return json(route, { creadas: 2, lista_id: 'lista-1' })

    // Ruta no contemplada: fallar FUERTE para que el test lo delate.
    return json(route, { detail: `mock sin handler para ${metodo} ${ruta}` }, 500)
  },
  )

  return estado
}

// ── Helpers de flujo ──────────────────────────────────────────────────────────

/** Prepara mocks + login por la UI real y espera el landing (Configuración). */
export async function iniciarSesion(page: Page, opciones: OpcionesMockApi = {}): Promise<EstadoMock> {
  await mockSupabaseAuth(page)
  const estado = await mockApi(page, opciones)
  await page.goto('/')
  await page.getByTestId('login-email').fill(CORREO_E2E)
  await page.getByTestId('login-password').fill('clave-e2e')
  await page.getByTestId('login-submit').click()
  await expect(page.getByRole('heading', { name: 'Prepara tu espacio' })).toBeVisible()
  return estado
}

/** Del landing a la bandeja (espera las tarjetas de solicitudes). */
export async function irABandeja(page: Page) {
  await page.getByTestId('ir-a-bandeja').click()
  await expect(page).toHaveURL(/\/bandeja$/)
  await expect(page.getByTestId('solicitud-card').first()).toBeVisible()
}
