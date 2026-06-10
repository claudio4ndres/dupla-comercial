import { afterEach, describe, expect, it, vi } from 'vitest'
import { listarMiembros } from './miembros'

/** `Response` mínima (sólo ok/status/json, lo que usa la capa de API). */
function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

const ROSTER = [
  { id: 'm1', nombre: 'Gabriela Lillo', rol: 'RRHH' },
  { id: 'm2', nombre: 'Bruno Soto', rol: 'Producción' },
]

describe('api/miembros · listarMiembros', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('lee el roster del backend con auth y lo devuelve', async () => {
    localStorage.setItem('sb-demo-auth-token', JSON.stringify({ access_token: 'tok123' }))
    const fetchMock = vi.fn().mockResolvedValue(respuesta(ROSTER))
    vi.stubGlobal('fetch', fetchMock)

    const r = await listarMiembros()

    expect(r).toEqual(ROSTER)
    const [url, opciones] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/miembros')
    expect((opciones.headers as Record<string, string>).Authorization).toBe('Bearer tok123')
  })

  it('ante error (ej. 401 / sin sesión) devuelve lista vacía', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 401)))
    expect(await listarMiembros()).toEqual([])
  })

  it('ante error de red devuelve lista vacía (demo offline no se rompe)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('sin red')))
    expect(await listarMiembros()).toEqual([])
  })

  it('si el backend devuelve algo inesperado, no rompe (lista vacía)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({ no: 'array' })))
    expect(await listarMiembros()).toEqual([])
  })
})
