import { afterEach, describe, expect, it, vi } from 'vitest'
import { obtenerRecursosDrive } from './recursos'

function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

describe('api/recursos · obtenerRecursosDrive', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('mapea los origenes del catálogo a recursos con icono según el tipo', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(respuesta(['Tarifario.xlsx', 'PRODUCCIÓN 3D', 'Permisos.pdf'])),
    )

    const recs = await obtenerRecursosDrive()

    expect(recs.map((r) => r.nombre)).toEqual(['Tarifario.xlsx', 'PRODUCCIÓN 3D', 'Permisos.pdf'])
    expect(recs[0].icono).toBe('📊') // .xlsx
    expect(recs[1].icono).toBe('📁') // sin extensión → carpeta
    expect(recs[2].icono).toBe('📄') // .pdf
  })

  it('ante error (ej. 401) devuelve lista vacía', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 401)))
    expect(await obtenerRecursosDrive()).toEqual([])
  })
})
