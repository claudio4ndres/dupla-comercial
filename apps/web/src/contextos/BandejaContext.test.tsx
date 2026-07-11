import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'

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

// ── Mock de fetch global (las cargas de datos disparan fetch al montar) ──────
vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
  ok: true,
  json: () => Promise.resolve([]),
}))

// Importamos los módulos (BandejaContext aún NO existe — paso rojo del TDD)
import { BandejaProvider, useBandeja } from './BandejaContext'
import { SesionProvider } from './SesionContext'
import { SolicitudProvider } from './SolicitudContext'

// ── Componente auxiliar para consumir el hook en los tests ────────────────────
function Consumidor({ onValor }: { onValor: (v: ReturnType<typeof useBandeja>) => void }) {
  const valor = useBandeja()
  onValor(valor)
  return null
}

describe('BandejaContext', () => {
  it('useBandeja() lanzado fuera del provider arroja error descriptivo', () => {
    // Silenciar el error de React al renderizar un componente que lanza
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => {
      render(<Consumidor onValor={() => {}} />)
    }).toThrow('useBandeja debe usarse dentro de BandejaProvider')

    spy.mockRestore()
  })

  it('montado dentro del provider, devuelve las propiedades esperadas', () => {
    let valor: ReturnType<typeof useBandeja> | null = null

    // Los contextos navegan con useNavigate (016): necesitan un router alrededor.
    render(
      <MemoryRouter>
        <SesionProvider>
          <SolicitudProvider>
            <BandejaProvider>
              <Consumidor onValor={(v) => { valor = v }} />
            </BandejaProvider>
          </SolicitudProvider>
        </SesionProvider>
      </MemoryRouter>,
    )

    // Verificar que todas las propiedades del contrato existen
    expect(valor).not.toBeNull()

    // Solicitudes
    expect(valor).toHaveProperty('solicitudes')
    expect(valor).toHaveProperty('cargandoSolicitudes')
    expect(valor).toHaveProperty('errorSolicitudes')
    expect(valor).toHaveProperty('reintentoSolicitudes')
    expect(valor).toHaveProperty('setReintentoSolicitudes')

    // Propuestas
    expect(valor).toHaveProperty('propuestas')
    expect(valor).toHaveProperty('cargandoPropuestas')
    expect(valor).toHaveProperty('errorPropuestas')
    expect(valor).toHaveProperty('reintentoPropuestas')
    expect(valor).toHaveProperty('setReintentoPropuestas')

    // Tareas globales
    expect(valor).toHaveProperty('cargandoTareas')
    expect(valor).toHaveProperty('errorTareas')
    expect(valor).toHaveProperty('reintentoTareas')
    expect(valor).toHaveProperty('setReintentoTareas')

    // Acciones
    expect(valor).toHaveProperty('abrirPropuestaDesdeLista')

    // Verificar tipos básicos de las funciones
    expect(typeof valor!.setReintentoSolicitudes).toBe('function')
    expect(typeof valor!.setReintentoPropuestas).toBe('function')
    expect(typeof valor!.setReintentoTareas).toBe('function')
    expect(typeof valor!.abrirPropuestaDesdeLista).toBe('function')
  })
})
