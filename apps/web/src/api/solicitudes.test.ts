import { afterEach, describe, expect, it, vi } from 'vitest'
import { obtenerSolicitudes } from './solicitudes'

function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

/** Forma mínima de una fila tal como la expone GET /solicitudes. */
function fila(extra: Record<string, unknown> = {}) {
  return {
    id: 's1',
    remitente: 'Zona Espiga',
    correo_origen: 'hola@zonaespiga.cl',
    asunto: 'Cotización sopaipillas',
    cuerpo: 'Hola Javo',
    resumen: null,
    tipo: 'tipo_1',
    estado: 'nueva',
    recibido_en: null,
    ...extra,
  }
}

describe('api/solicitudes · obtenerSolicitudes', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('mapea recibido_en (ISO) a un `tiempo` legible para la bandeja', async () => {
    const iso = '2026-06-09T12:30:00+00:00'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta([fila({ recibido_en: iso })])))

    const [s] = await obtenerSolicitudes()

    // Mismo formato corto día+mes que pinta la tarjeta (es-CL).
    const esperado = new Date(iso).toLocaleDateString('es-CL', {
      day: '2-digit',
      month: 'short',
    })
    expect(s.tiempo).toBe(esperado)
    expect(s.tiempo).not.toBe('')
  })

  it('sin recibido_en deja `tiempo` en blanco (no rompe la tarjeta)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta([fila({ recibido_en: null })])))

    const [s] = await obtenerSolicitudes()

    expect(s.tiempo).toBe('')
  })

  it('ante error (ej. 500) devuelve lista vacía', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 500)))
    expect(await obtenerSolicitudes()).toEqual([])
  })
})
