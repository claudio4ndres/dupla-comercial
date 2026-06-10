import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ESTADO_DESCONECTADO,
  iniciarConexionGmail,
  obtenerEstadoCorreo,
} from './integraciones'

/** Arma una `Response` mínima (sólo lo que usa el cliente: ok/status/json). */
function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

describe('api/integraciones', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  describe('obtenerEstadoCorreo (T13)', () => {
    it('devuelve el estado parseado cuando el backend responde 200', async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValue(
          respuesta({ proveedor: 'gmail', estado: 'conectado', casilla: 'hola@capsulab.cl' }),
        )
      vi.stubGlobal('fetch', fetchMock)

      const estado = await obtenerEstadoCorreo()

      expect(estado).toEqual({
        proveedor: 'gmail',
        estado: 'conectado',
        casilla: 'hola@capsulab.cl',
      })
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/integraciones/correo'),
        expect.objectContaining({ headers: expect.anything() }),
      )
    })

    it('refleja el estado "reconectar" (token caído, CA7)', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          respuesta({ proveedor: 'gmail', estado: 'reconectar', casilla: 'hola@capsulab.cl' }),
        ),
      )

      const estado = await obtenerEstadoCorreo()

      expect(estado.estado).toBe('reconectar')
    })

    it('cae a "sin conectar" si el backend falla (demo offline)', async () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('sin red')))

      const estado = await obtenerEstadoCorreo()

      expect(estado).toEqual(ESTADO_DESCONECTADO)
    })
  })

  describe('iniciarConexionGmail (T14)', () => {
    it('devuelve la URL EXACTA del backend (el cliente no inventa la URL de OAuth)', async () => {
      const url = 'https://accounts.google.com/o/oauth2/v2/auth?scope=gmail.readonly&state=abc'
      const fetchMock = vi.fn().mockResolvedValue(respuesta({ url }))
      vi.stubGlobal('fetch', fetchMock)

      const devuelta = await iniciarConexionGmail()

      expect(devuelta).toBe(url)
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/integraciones/correo/gmail/iniciar'),
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('propaga el error si el backend falla (no navega a una URL inventada)', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 500)))

      await expect(iniciarConexionGmail()).rejects.toThrow()
    })
  })
})
