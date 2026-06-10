import { afterEach, describe, expect, it, vi } from 'vitest'
import { obtenerHistorialConversacion } from './conversaciones'

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
