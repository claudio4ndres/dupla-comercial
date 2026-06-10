import { afterEach, describe, expect, it, vi } from 'vitest'
import { listarPropuestas, obtenerPropuesta } from './propuestas'

/** `Response` mínima (sólo ok/status/json, lo que usa la capa de API). */
function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

const PROPUESTA_BACKEND = {
  id: 'p-212',
  total: 5190000,
  estado: 'borrador',
  componentes: [
    {
      nombre: 'Promotoras uniformadas',
      detalle: '6h/día · 3 tiendas',
      proveedor: 'Staff BTL',
      cantidad: 6,
      dias: 4,
      valor_unitario: 240000,
    },
  ],
  tareas: [{ nombre: 'Reclutar 6 promotoras', grupo: 'RRHH', responsable: 'Coordinación', vencimiento: '3 días' }],
}

describe('api/propuestas · obtenerPropuesta (004)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('mapea componentes y tareas del backend a los tipos del front', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuesta(PROPUESTA_BACKEND))
    vi.stubGlobal('fetch', fetchMock)

    const prop = await obtenerPropuesta('sol-1')

    expect(prop).not.toBeNull()
    // valor_unitario → valor (la UI calcula subtotal con valor × cantidad).
    expect(prop!.componentes[0]).toEqual({
      nombre: 'Promotoras uniformadas',
      detalle: '6h/día · 3 tiendas',
      proveedor: 'Staff BTL',
      cantidad: 6,
      dias: 4,
      valor: 240000,
    })
    // grupo → área, vencimiento → plazo.
    expect(prop!.tareas[0]).toEqual({
      nombre: 'Reclutar 6 promotoras',
      area: 'RRHH',
      responsable: 'Coordinación',
      plazo: '3 días',
    })
    // Pega al endpoint correcto, con cabeceras de auth.
    expect(String(fetchMock.mock.calls[0][0])).toContain('/solicitudes/sol-1/propuesta')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/propuesta'),
      expect.objectContaining({ headers: expect.anything() }),
    )
  })

  it('ante 404 (solicitud sin propuesta) devuelve null para usar el fallback', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 404)))
    expect(await obtenerPropuesta('sin-propuesta')).toBeNull()
  })

  it('ante error de red devuelve null (demo offline no se rompe)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('sin red')))
    expect(await obtenerPropuesta('x')).toBeNull()
  })
})

const LISTA_BACKEND = [
  {
    id: 'p-212',
    solicitud_id: 's-212',
    total: 5190000,
    estado: 'borrador',
    asunto: 'Cotización activación 212 VIP Black',
    remitente: 'Carolina Herrera · 212',
  },
  {
    id: 'p-metro',
    solicitud_id: 's-metro',
    total: 890000,
    estado: 'enviada',
    asunto: 'Sampling de sopaipillas afuera del Metro',
    remitente: 'Zona Espiga',
  },
]

describe('api/propuestas · listarPropuestas', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('lee la lista de propuestas y la mapea a PropuestaResumen (solicitud_id → solicitudId)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuesta(LISTA_BACKEND))
    vi.stubGlobal('fetch', fetchMock)

    const props = await listarPropuestas()

    expect(props).toEqual([
      {
        id: 'p-212',
        solicitudId: 's-212',
        total: 5190000,
        estado: 'borrador',
        asunto: 'Cotización activación 212 VIP Black',
        remitente: 'Carolina Herrera · 212',
      },
      {
        id: 'p-metro',
        solicitudId: 's-metro',
        total: 890000,
        estado: 'enviada',
        asunto: 'Sampling de sopaipillas afuera del Metro',
        remitente: 'Zona Espiga',
      },
    ])
    // Pega al endpoint correcto, con cabeceras de auth.
    expect(String(fetchMock.mock.calls[0][0])).toContain('/propuestas')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/propuestas'),
      expect.objectContaining({ headers: expect.anything() }),
    )
  })

  it('ante error (ej. 401 / sin sesión) devuelve lista vacía', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 401)))
    expect(await listarPropuestas()).toEqual([])
  })

  it('ante error de red devuelve lista vacía (demo offline no se rompe)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('sin red')))
    expect(await listarPropuestas()).toEqual([])
  })
})
