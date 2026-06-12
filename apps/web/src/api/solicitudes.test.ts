import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Mock del cliente de Supabase: aquí solo nos importa `auth.getSession`, que es la
// ruta que AUTO-REFRESCA el access_token. `vi.mock` se hoistea, así que el factory
// no puede referenciar variables del módulo; usamos `vi.fn()` directo y lo ajustamos
// en cada test con `mockResolvedValue`. (vitest corre con `isolate: true`, así que
// este mock NO se filtra a otros archivos de test.)
vi.mock('../supabase/cliente', () => ({
  supabase: { auth: { getSession: vi.fn() } },
}))

import { supabase } from '../supabase/cliente'
import { obtenerSolicitudes } from './solicitudes'

const getSession = supabase.auth.getSession as ReturnType<typeof vi.fn>

function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

/** Forma mínima de una fila tal como la expone GET /solicitudes. */
function fila(extra: Record<string, unknown> = {}) {
  return {
    id: 's1',
    remitente: 'Zona Espiga',
    correo_origen: 'hola@zonaespiga.cl',
    asunto: 'Cotización sopaipillas',
    cuerpo: 'Hola Javo',
    resumen: null,
    tipo: 'tipo_1',
    estado: 'nueva',
    recibido_en: null,
    ...extra,
  }
}

describe('api/solicitudes · obtenerSolicitudes', () => {
  beforeEach(() => {
    // Por defecto, sin sesión activa (los tests de mapeo no dependen del token).
    getSession.mockResolvedValue({ data: { session: null } })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    getSession.mockReset()
    localStorage.clear()
  })

  it('usa la ruta async que refresca el token (getSession) y manda ese Bearer', async () => {
    // Problema #3: el cliente debe resolver el token con `getSession()` —que
    // auto-refresca el access_token vencido— y NO leer el token crudo de
    // localStorage. Aquí `getSession` entrega un token "fresco" y verificamos que
    // (a) se invocó y (b) viaja en la cabecera Authorization de la petición.
    getSession.mockResolvedValue({ data: { session: { access_token: 'tok-fresco' } } })
    const fetchMock = vi.fn().mockResolvedValue(respuesta([]))
    vi.stubGlobal('fetch', fetchMock)

    await obtenerSolicitudes()

    expect(getSession).toHaveBeenCalled()
    const [, opciones] = fetchMock.mock.calls[0]
    expect((opciones.headers as Record<string, string>).Authorization).toBe('Bearer tok-fresco')
  })

  it('mapea recibido_en (ISO) a un `tiempo` legible para la bandeja', async () => {
    const iso = '2026-06-09T12:30:00+00:00'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta([fila({ recibido_en: iso })])))

    const [s] = await obtenerSolicitudes()

    // Mismo formato corto día+mes que pinta la tarjeta (es-CL).
    const esperado = new Date(iso).toLocaleDateString('es-CL', {
      day: '2-digit',
      month: 'short',
    })
    expect(s.tiempo).toBe(esperado)
    expect(s.tiempo).not.toBe('')
  })

  it('sin recibido_en deja `tiempo` en blanco (no rompe la tarjeta)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta([fila({ recibido_en: null })])))

    const [s] = await obtenerSolicitudes()

    expect(s.tiempo).toBe('')
  })

  it('ante error (ej. 500) devuelve lista vacía', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 500)))
    expect(await obtenerSolicitudes()).toEqual([])
  })
})
