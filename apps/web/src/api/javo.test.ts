import { afterEach, describe, expect, it, vi } from 'vitest'
import { conversarConJavoOError } from './javo'

/** `Response` mínima (sólo ok/status/json, lo que usa la capa de API). */
function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

describe('api/javo · conversarConJavoOError (005 + 014)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('mapea texto, componentes (valor_unitario→valor, origen) y fuentes', async () => {
    const backend = {
      texto: 'Las promotoras quedan a $240.000 c/u.',
      componentes: [
        { nombre: 'Promotoras', detalle: '3 tiendas', cantidad: 6, valor_unitario: 240000, origen: 'Tarifario.xlsx' },
      ],
      fuentes: [{ titulo: 'Tarifario', referencia: 'Drive: Tarifario.xlsx' }],
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta(backend)))

    const r = await conversarConJavoOError({
      solicitudId: 's1',
      tipo: 't1',
      mensajes: [{ rol: 'usuario', contenido: 'cotiza promotoras' }],
    })

    expect(r.texto).toBe('Las promotoras quedan a $240.000 c/u.')
    expect(r.componentes[0]).toEqual({
      nombre: 'Promotoras',
      detalle: '3 tiendas',
      cantidad: 6,
      valor: 240000,
      origen: 'Tarifario.xlsx',
    })
    expect(r.fuentes[0]).toEqual({ titulo: 'Tarifario', referencia: 'Drive: Tarifario.xlsx' })
  })

  it('CA1: ante error del backend RECHAZA (ya no hay respuesta pregrabada)', async () => {
    // Bug 014: antes un 502 devolvía un texto canned y Javo "aparentaba" funcionar
    // con el backend caído. Ahora el fallo se propaga para que la UI lo muestre.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 502)))

    await expect(
      conversarConJavoOError({ solicitudId: 's1', tipo: 't1', mensajes: [] }),
    ).rejects.toThrow()
  })

  it('CA1: ante red caída (fetch rechaza) también propaga', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('red caída')))

    await expect(
      conversarConJavoOError({ solicitudId: 's1', tipo: 't1', mensajes: [] }),
    ).rejects.toThrow()
  })
})
