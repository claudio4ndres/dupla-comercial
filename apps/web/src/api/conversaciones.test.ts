import { afterEach, describe, expect, it, vi } from 'vitest'
import { obtenerCotizacionEnCurso, obtenerHistorialConversacion } from './conversaciones'

function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

describe('api/conversaciones · obtenerHistorialConversacion (T14)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('trae el hilo persistido y lo mapea a Mensaje[]', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      respuesta([
        { rol: 'usuario', contenido: 'Son 3 días de activación' },
        { rol: 'javo', contenido: 'Perfecto, dejo catering + 2 promotores.' },
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    const h = await obtenerHistorialConversacion('sol-1')

    expect(h).toEqual([
      { rol: 'usuario', contenido: 'Son 3 días de activación' },
      { rol: 'javo', contenido: 'Perfecto, dejo catering + 2 promotores.' },
    ])
    expect(String(fetchMock.mock.calls[0][0])).toContain('/conversaciones/sol-1')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/conversaciones/'),
      expect.objectContaining({ headers: expect.anything() }),
    )
  })

  it('ante error (401/red) devuelve [] para que el chat parta de cero', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 401)))
    expect(await obtenerHistorialConversacion('x')).toEqual([])
  })
})

describe('api/conversaciones · obtenerCotizacionEnCurso (0009)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('trae el borrador persistido (componentes/tareas/fuentes) y lo mapea a la UI', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      respuesta({
        componentes: [
          {
            nombre: 'Promotoras uniformadas',
            detalle: '3 tiendas',
            cantidad: 6,
            dias: 3,
            valor_unitario: 240000,
            proveedor: 'Staff BTL',
            origen: 'Tarifario_promotores_2026.xlsx',
          },
        ],
        tareas: [{ nombre: 'Reclutar 6 promotoras', area: 'RRHH', plazo: '3 días', responsable: null }],
        fuentes: [{ titulo: 'Tarifario 2026', referencia: 'Drive: Tarifario 2026' }],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const c = await obtenerCotizacionEnCurso('sol-1')

    expect(c.componentes).toEqual([
      {
        nombre: 'Promotoras uniformadas',
        detalle: '3 tiendas',
        cantidad: 6,
        dias: 3,
        valor: 240000,
        proveedor: 'Staff BTL',
        origen: 'Tarifario_promotores_2026.xlsx',
      },
    ])
    expect(c.tareas).toEqual([{ nombre: 'Reclutar 6 promotoras', area: 'RRHH', plazo: '3 días', responsable: '' }])
    expect(c.fuentes).toEqual([{ titulo: 'Tarifario 2026', referencia: 'Drive: Tarifario 2026' }])
    expect(String(fetchMock.mock.calls[0][0])).toContain('/conversaciones/sol-1/cotizacion')
  })

  it('ante error (401/red) devuelve cotización vacía para que el panel no rompa', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 401)))
    expect(await obtenerCotizacionEnCurso('x')).toEqual({ componentes: [], tareas: [], fuentes: [] })
  })
})
