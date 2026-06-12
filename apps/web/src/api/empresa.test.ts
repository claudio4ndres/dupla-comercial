import { afterEach, describe, expect, it, vi } from 'vitest'
import { obtenerEmpresa } from './empresa'

/** `Response` mínima (sólo ok/status/json, lo que usa la capa de API). */
function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

describe('api/empresa · obtenerEmpresa', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('lee la empresa del backend (con auth) y la mapea al tipo del front', async () => {
    localStorage.setItem('sb-demo-auth-token', JSON.stringify({ access_token: 'tok123' }))
    const fetchMock = vi.fn().mockResolvedValue(
      respuesta({ id: 'd1', nombre: 'RukkumansLabs', color_marca: '#F04E37', plan: 'operador' }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const e = await obtenerEmpresa()

    expect(e).toEqual({
      nombre: 'RukkumansLabs',
      color: '#F04E37',
      marca: 'R',
      etiqueta: 'Plan operador · BTL',
    })
    const [url, opciones] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/empresa')
    expect((opciones.headers as Record<string, string>).Authorization).toBe('Bearer tok123')
  })

  it('ante error (401 / sin sesión) devuelve null (no rompe el header)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 401)))
    expect(await obtenerEmpresa()).toBeNull()
  })

  it('ante error de red devuelve null (demo offline no se rompe)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('sin red')))
    expect(await obtenerEmpresa()).toBeNull()
  })

  it('si el backend devuelve forma inesperada (sin nombre), devuelve null', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({ no: 'empresa' })))
    expect(await obtenerEmpresa()).toBeNull()
  })
})
