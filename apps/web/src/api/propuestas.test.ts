import { afterEach, describe, expect, it, vi } from 'vitest'
import { obtenerPropuesta } from './propuestas'

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
      detalle: '6h/día × 4 días · 3 tiendas',
      proveedor: 'Staff BTL',
      cantidad: 6,
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
      detalle: '6h/día × 4 días · 3 tiendas',
      proveedor: 'Staff BTL',
      cantidad: 6,
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
