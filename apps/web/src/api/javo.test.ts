import { afterEach, describe, expect, it, vi } from 'vitest'
import { conversarConJavo } from './javo'

/** `Response` mínima (sólo ok/status/json, lo que usa la capa de API). */
function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

describe('api/javo · conversarConJavo (005)', () => {
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

    const r = await conversarConJavo({
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

  it('ante error del backend cae a la respuesta offline (texto fallback, sin componentes/fuentes)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 502)))

    const r = await conversarConJavo({ solicitudId: 's1', tipo: 't1', mensajes: [] })

    expect(r.texto).toBeTruthy() // hay texto (respuesta canned)
    expect(r.componentes).toEqual([])
    expect(r.fuentes).toEqual([])
  })
})
