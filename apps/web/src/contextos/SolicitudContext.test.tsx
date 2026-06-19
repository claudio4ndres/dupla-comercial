import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

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

// Importamos los módulos (SolicitudContext aún NO existe — paso rojo del TDD)
import { SolicitudProvider, useSolicitud } from './SolicitudContext'
import { SesionProvider } from './SesionContext'

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
})
