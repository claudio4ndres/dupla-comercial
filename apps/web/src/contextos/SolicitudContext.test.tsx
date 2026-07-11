import { act, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Solicitud } from '../tipos'

// ── Mock de Supabase (mismo patrón que SesionContext.test.tsx) ────────────────
vi.mock('../supabase/cliente', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      signInWithPassword: vi.fn(),
      signOut: vi.fn(),
      onAuthStateChange: vi.fn().mockImplementation(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
    },
  },
}))

// ── Mock de fetch global (obtenerRecursosDrive dispara fetch al montar) ──────
vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
  ok: true,
  json: () => Promise.resolve([]),
}))

// ── Mock del cliente de propuestas (para simular fallo del guardado) ─────────
vi.mock('../api/propuestas', () => ({
  guardarPropuesta: vi.fn().mockResolvedValue(null),
  obtenerPropuesta: vi.fn().mockResolvedValue(null),
}))

// ── Mock del cliente de Javo (spec 014: el fallo se propaga, sin canned) ─────
vi.mock('../api/javo', () => ({
  conversarConJavoOError: vi.fn(),
}))
import { conversarConJavoOError } from '../api/javo'

// Importamos los módulos (SolicitudContext aún NO existe — paso rojo del TDD)
import { SolicitudProvider, useSolicitud } from './SolicitudContext'
import { SesionProvider, useSesion } from './SesionContext'

// ── Componente auxiliar para consumir el hook en los tests ────────────────────
function Consumidor({ onValor }: { onValor: (v: ReturnType<typeof useSolicitud>) => void }) {
  const valor = useSolicitud()
  onValor(valor)
  return null
}

describe('SolicitudContext', () => {
  it('useSolicitud() lanzado fuera del provider arroja error descriptivo', () => {
    // Silenciar el error de React al renderizar un componente que lanza
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => {
      render(<Consumidor onValor={() => {}} />)
    }).toThrow('useSolicitud debe usarse dentro de SolicitudProvider')

    spy.mockRestore()
  })

  it('montado dentro del provider, devuelve las propiedades esperadas', () => {
    let valor: ReturnType<typeof useSolicitud> | null = null

    render(
      <SesionProvider>
        <SolicitudProvider>
          <Consumidor onValor={(v) => { valor = v }} />
        </SolicitudProvider>
      </SesionProvider>,
    )

    // Verificar que todas las propiedades del contrato existen
    expect(valor).not.toBeNull()

    // Estado
    expect(valor).toHaveProperty('solicitudActual')
    expect(valor).toHaveProperty('tipo')
    expect(valor).toHaveProperty('mensajes')
    expect(valor).toHaveProperty('componentes')
    expect(valor).toHaveProperty('tareas')
    expect(valor).toHaveProperty('fuentes')
    expect(valor).toHaveProperty('enviando')
    expect(valor).toHaveProperty('recursos')

    // Acciones
    expect(valor).toHaveProperty('abrirSolicitud')
    expect(valor).toHaveProperty('iniciarChat')
    expect(valor).toHaveProperty('enviarMensaje')
    expect(valor).toHaveProperty('generarPropuesta')
    expect(valor).toHaveProperty('setTareas')

    // Verificar tipos básicos de las funciones
    expect(typeof valor!.abrirSolicitud).toBe('function')
    expect(typeof valor!.iniciarChat).toBe('function')
    expect(typeof valor!.enviarMensaje).toBe('function')
    expect(typeof valor!.generarPropuesta).toBe('function')
    expect(typeof valor!.setTareas).toBe('function')
  })

  it('si guardar la propuesta falla, NO navega y avisa en el chat', async () => {
    // Bug QA: antes navegaba a la pantalla propuesta aunque el POST fallara,
    // mostrando una propuesta que "desaparecía" al recargar (no persistida).
    const solicitud: Solicitud = {
      id: 'espiga',
      remitente: 'Zona Espiga',
      correo: 'contacto@zonaespiga.cl',
      tiempo: '09-jun',
      asunto: 'Sampling de sopaipillas',
      tipo: 't1',
      resumen: 'Sampling afuera del Metro.',
      puntos: [],
      cuerpo: 'Hola Javo, queremos cotizar un sampling.',
    }

    let valor: ReturnType<typeof useSolicitud>
    let pantalla = ''
    function Doble({ onValor }: { onValor: (v: ReturnType<typeof useSolicitud>, p: string) => void }) {
      onValor(useSolicitud(), useSesion().pantalla)
      return null
    }

    render(
      <SesionProvider>
        <SolicitudProvider>
          <Doble onValor={(v, p) => { valor = v; pantalla = p }} />
        </SolicitudProvider>
      </SesionProvider>,
    )

    act(() => valor!.abrirSolicitud(solicitud))
    act(() => valor!.setComponentes([
      { nombre: 'Catering', detalle: 'Té + bocados', cantidad: 1, dias: 1, valor: 380000 },
    ]))
    await act(async () => { await valor!.generarPropuesta() })

    // guardarPropuesta (mockeado) devolvió null → nos quedamos donde estábamos…
    expect(pantalla).not.toBe('propuesta')
    // …y el usuario recibe feedback del fallo en el hilo del chat.
    expect(
      valor!.mensajes.some(
        (m) => m.rol === 'sistema' && /no se pudo guardar/i.test(m.contenido),
      ),
    ).toBe(true)
  })

  it('CA2/CA3 (014): si Javo falla marca errorJavo y Reintentar reenvía sin duplicar', async () => {
    const solicitud: Solicitud = {
      id: 'espiga',
      remitente: 'Zona Espiga',
      correo: 'contacto@zonaespiga.cl',
      tiempo: '09-jun',
      asunto: 'Sampling de sopaipillas',
      tipo: 't1',
      resumen: 'Sampling afuera del Metro.',
      puntos: [],
      cuerpo: 'Hola Javo.',
    }

    let valor: ReturnType<typeof useSolicitud>
    function Doble({ onValor }: { onValor: (v: ReturnType<typeof useSolicitud>) => void }) {
      onValor(useSolicitud())
      return null
    }

    render(
      <SesionProvider>
        <SolicitudProvider>
          <Doble onValor={(v) => { valor = v }} />
        </SolicitudProvider>
      </SesionProvider>,
    )

    act(() => valor!.abrirSolicitud(solicitud))

    // 1) El backend cae: el turno falla y queda errorJavo (sin respuesta canned).
    vi.mocked(conversarConJavoOError).mockRejectedValueOnce(new Error('502'))
    await act(async () => { await valor!.enviarMensaje('cotiza promotoras') })

    expect(valor!.errorJavo).toBe(true)
    const turnosUsuario = valor!.mensajes.filter((m) => m.rol === 'usuario').length
    expect(turnosUsuario).toBe(1)

    // 2) Reintentar: reenvía el MISMO historial (no duplica el turno del usuario).
    vi.mocked(conversarConJavoOError).mockResolvedValueOnce({
      texto: 'Listo, promotoras a $240.000.',
      componentes: [],
      tareas: [],
      fuentes: [],
    })
    await act(async () => { await valor!.reintentarMensaje() })

    expect(valor!.errorJavo).toBe(false)
    expect(valor!.mensajes.filter((m) => m.rol === 'usuario').length).toBe(1)
    expect(valor!.mensajes.at(-1)).toEqual({
      rol: 'javo',
      contenido: 'Listo, promotoras a $240.000.',
    })
  })
})
