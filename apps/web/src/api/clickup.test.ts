import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  desconectarClickup,
  enviarTareasAClickUp,
  ESTADO_CLICKUP_DESCONECTADO,
  iniciarConexionClickup,
  listarListasClickUp,
  obtenerEstadoClickup,
} from './clickup'

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

  it('manda el mapa de asignados en el cuerpo JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuesta({ creadas: 2 }))
    vi.stubGlobal('fetch', fetchMock)

    const asignados = { 'Reclutar 6 promotoras': 'Gabriela Lillo' }
    await enviarTareasAClickUp('sol-7', 'L99', asignados)

    const [, opciones] = fetchMock.mock.calls[0]
    expect(opciones.method).toBe('POST')
    // El body es JSON con la clave `asignados` (nombre_de_tarea → persona).
    expect((opciones.headers as Record<string, string>)['Content-Type']).toContain('application/json')
    expect(JSON.parse(opciones.body as string)).toEqual({ asignados })
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

describe('api/clickup · obtenerEstadoClickup', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('con integración conectada devuelve {proveedor, estado} y manda auth', async () => {
    localStorage.setItem('sb-demo-auth-token', JSON.stringify({ access_token: 'tok123' }))
    const fetchMock = vi
      .fn()
      .mockResolvedValue(respuesta({ proveedor: 'clickup', estado: 'conectado' }))
    vi.stubGlobal('fetch', fetchMock)

    const r = await obtenerEstadoClickup()

    expect(r).toEqual({ proveedor: 'clickup', estado: 'conectado' })
    const [url, opciones] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/clickup/estado')
    expect((opciones.headers as Record<string, string>).Authorization).toBe('Bearer tok123')
  })

  it('sin integración (todo null) entrega "Sin conectar"', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({ proveedor: null, estado: null })))
    expect(await obtenerEstadoClickup()).toEqual(ESTADO_CLICKUP_DESCONECTADO)
  })

  it('con token inválido el backend marca "reconectar" (CA6)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(respuesta({ proveedor: 'clickup', estado: 'reconectar' })),
    )
    expect(await obtenerEstadoClickup()).toEqual({ proveedor: 'clickup', estado: 'reconectar' })
  })

  it('ante error (502) cae a "desconectado" sin romper la UI', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 502)))
    expect(await obtenerEstadoClickup()).toEqual(ESTADO_CLICKUP_DESCONECTADO)
  })

  it('ante fetch rechazado cae a "desconectado"', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('red caída')))
    expect(await obtenerEstadoClickup()).toEqual(ESTADO_CLICKUP_DESCONECTADO)
  })

  it('el token JAMÁS aparece: aunque el backend filtrara uno, no se expone (CA5)', async () => {
    // Defensa: el response_model del backend ya omite el token; el cliente solo
    // mapea proveedor/estado, así que un token colado nunca llega a la app.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respuesta({ proveedor: 'clickup', estado: 'conectado', token: 'secreto-no-debe-salir' }),
      ),
    )
    const r = await obtenerEstadoClickup()
    expect(r).toEqual({ proveedor: 'clickup', estado: 'conectado' })
    expect(JSON.stringify(r)).not.toContain('secreto-no-debe-salir')
  })
})

describe('api/clickup · iniciarConexionClickup', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('pide la URL de consentimiento al backend (POST con auth) y la devuelve', async () => {
    localStorage.setItem('sb-demo-auth-token', JSON.stringify({ access_token: 'tok123' }))
    const fetchMock = vi
      .fn()
      .mockResolvedValue(respuesta({ url: 'https://app.clickup.com/api?state=abc' }))
    vi.stubGlobal('fetch', fetchMock)

    const url = await iniciarConexionClickup()

    expect(url).toBe('https://app.clickup.com/api?state=abc')
    const [endpoint, opciones] = fetchMock.mock.calls[0]
    expect(String(endpoint)).toContain('/clickup/iniciar')
    expect(opciones.method).toBe('POST')
    expect((opciones.headers as Record<string, string>).Authorization).toBe('Bearer tok123')
  })

  it('ante error propaga (no se navega a una URL inventada)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta({}, false, 500)))
    await expect(iniciarConexionClickup()).rejects.toThrow()
  })
})

describe('api/clickup · desconectarClickup', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('hace DELETE /clickup con auth', async () => {
    localStorage.setItem('sb-demo-auth-token', JSON.stringify({ access_token: 'tok123' }))
    const fetchMock = vi.fn().mockResolvedValue(respuesta(null, true, 204))
    vi.stubGlobal('fetch', fetchMock)

    await desconectarClickup()

    const [url, opciones] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/clickup$/)
    expect(opciones.method).toBe('DELETE')
    expect((opciones.headers as Record<string, string>).Authorization).toBe('Bearer tok123')
  })

  it('ante fetch rechazado no propaga (no rompe la UI al cambiar)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('red caída')))
    await expect(desconectarClickup()).resolves.toBeUndefined()
  })
})
