import { afterEach, describe, expect, it, vi } from 'vitest'
import { enviarTareasAClickUp, listarListasClickUp } from './clickup'

/** `Response` mínima (sólo ok/status/json, lo que usa la capa de API). */
function respuesta(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

describe('api/clickup · listarListasClickUp', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('lista las listas del backend con auth', async () => {
    localStorage.setItem('sb-demo-auth-token', JSON.stringify({ access_token: 'tok123' }))
    const listas = [
      { id: 'L1', nombre: 'Backlog', espacio: 'Marketing' },
      { id: 'L2', nombre: 'Sampling', espacio: 'Marketing' },
    ]
    const fetchMock = vi.fn().mockResolvedValue(respuesta(listas))
    vi.stubGlobal('fetch', fetchMock)

    const r = await listarListasClickUp()

    expect(r).toEqual(listas)
    const [url, opciones] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/clickup/listas')
    expect((opciones.headers as Record<string, string>).Authorization).toBe('Bearer tok123')
  })

  it('sin token (backend devuelve []) entrega lista vacía', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta([])))
    expect(await listarListasClickUp()).toEqual([])
  })

  it('ante error (502) devuelve lista vacía sin romper la UI', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 502)))
    expect(await listarListasClickUp()).toEqual([])
  })

  it('ante fetch rechazado devuelve lista vacía', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('red caída')))
    expect(await listarListasClickUp()).toEqual([])
  })
})

describe('api/clickup · enviarTareasAClickUp', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('postea a la solicitud con la lista elegida y devuelve {creadas}', async () => {
    localStorage.setItem('sb-demo-auth-token', JSON.stringify({ access_token: 'tok123' }))
    const fetchMock = vi.fn().mockResolvedValue(respuesta({ creadas: 3 }))
    vi.stubGlobal('fetch', fetchMock)

    const r = await enviarTareasAClickUp('sol-7', 'L99')

    expect(r).toEqual({ creadas: 3 })
    const [url, opciones] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/solicitudes/sol-7/tareas/clickup')
    expect(String(url)).toContain('lista_id=L99')
    expect(opciones.method).toBe('POST')
    expect((opciones.headers as Record<string, string>).Authorization).toBe('Bearer tok123')
  })

  it('sin lista elegida no agrega lista_id (usa el fallback del backend)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuesta({ creadas: 1 }))
    vi.stubGlobal('fetch', fetchMock)

    await enviarTareasAClickUp('sol-7', '')

    expect(String(fetchMock.mock.calls[0][0])).not.toContain('lista_id=')
  })

  it('ante error (400 sin lista) devuelve null', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 400)))
    expect(await enviarTareasAClickUp('sol-7', 'L1')).toBeNull()
  })

  it('ante fetch rechazado devuelve null', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('red caída')))
    expect(await enviarTareasAClickUp('sol-7', 'L1')).toBeNull()
  })
})
