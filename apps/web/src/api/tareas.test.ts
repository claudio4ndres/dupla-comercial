import { afterEach, describe, expect, it, vi } from 'vitest'
import { listarTareas } from './tareas'

/** `Response` mínima (sólo ok/status/json, lo que usa la capa de API). */
function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

const LISTA_BACKEND = [
  { nombre: 'Reclutar 6 promotoras', grupo: 'RRHH', responsable: 'Coordinación', vencimiento: '3 días' },
  { nombre: 'Orden de compra de insumos', grupo: null, responsable: null, vencimiento: null },
]

describe('api/tareas · listarTareas', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('lee las tareas del backend y las mapea al tipo Tarea (grupo → área, vencimiento → plazo)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuesta(LISTA_BACKEND))
    vi.stubGlobal('fetch', fetchMock)

    const tareas = await listarTareas()

    expect(tareas).toEqual([
      { nombre: 'Reclutar 6 promotoras', area: 'RRHH', responsable: 'Coordinación', plazo: '3 días' },
      // Los nulos del backend se normalizan a string vacío (como hace `aTarea`).
      { nombre: 'Orden de compra de insumos', area: '', responsable: '', plazo: '' },
    ])
    // Pega al endpoint correcto, con cabeceras de auth.
    expect(String(fetchMock.mock.calls[0][0])).toContain('/tareas')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tareas'),
      expect.objectContaining({ headers: expect.anything() }),
    )
  })

  it('ante error (ej. 401 / sin sesión) devuelve lista vacía', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 401)))
    expect(await listarTareas()).toEqual([])
  })

  it('ante error de red devuelve lista vacía (demo offline no se rompe)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('sin red')))
    expect(await listarTareas()).toEqual([])
  })
})
