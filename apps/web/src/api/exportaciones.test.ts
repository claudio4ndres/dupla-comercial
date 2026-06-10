import { afterEach, describe, expect, it, vi } from 'vitest'
import { descargarCotizacionExcel } from './exportaciones'

function respuestaBlob(ok = true, status = 200): Response {
  return {
    ok,
    status,
    blob: async () => new Blob(['xlsx'], { type: 'application/octet-stream' }),
  } as Response
}

describe('api/exportaciones · descargarCotizacionExcel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('descarga el .xlsx de la solicitud con auth y dispara la descarga', async () => {
    // Sesión de Supabase en localStorage → cabecerasAuth() arma el Bearer.
    localStorage.setItem('sb-demo-auth-token', JSON.stringify({ access_token: 'tok123' }))
    const fetchMock = vi.fn().mockResolvedValue(respuestaBlob())
    vi.stubGlobal('fetch', fetchMock)
    const createUrl = vi.fn().mockReturnValue('blob:fake')
    const revokeUrl = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: createUrl, revokeObjectURL: revokeUrl })
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})

    const ok = await descargarCotizacionExcel('sol-123')

    expect(ok).toBe(true)
    const [url, opciones] = fetchMock.mock.calls[0]
    expect(url).toContain('/solicitudes/sol-123/cotizacion.xlsx')
    expect((opciones.headers as Record<string, string>).Authorization).toBe('Bearer tok123')
    expect(createUrl).toHaveBeenCalledOnce()
    expect(clickSpy).toHaveBeenCalledOnce()
    expect(revokeUrl).toHaveBeenCalledOnce()
  })

  it('ante error (404) devuelve false y no rompe la UI', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuestaBlob(false, 404)))
    expect(await descargarCotizacionExcel('x')).toBe(false)
  })

  it('ante fetch rechazado devuelve false', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('red caída')))
    expect(await descargarCotizacionExcel('x')).toBe(false)
  })
})
