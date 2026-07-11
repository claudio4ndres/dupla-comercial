import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'

// ── Mock de Supabase (mismo patrón que App.test.tsx) ─────────────────────────
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

// Importamos el módulo que aún NO existe (paso rojo del TDD)
import { SesionProvider, useSesion } from './SesionContext'

// ── Componente auxiliar para consumir el hook en los tests ────────────────────
function Consumidor({ onValor }: { onValor: (v: ReturnType<typeof useSesion>) => void }) {
  const valor = useSesion()
  onValor(valor)
  return null
}

describe('SesionContext', () => {
  it('useSesion() lanzado fuera del provider arroja error descriptivo', () => {
    // Silenciar el error de React al renderizar un componente que lanza
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => {
      render(<Consumidor onValor={() => {}} />)
    }).toThrow('useSesion debe usarse dentro de SesionProvider')

    spy.mockRestore()
  })

  it('montado dentro del provider, devuelve las propiedades esperadas', () => {
    let valor: ReturnType<typeof useSesion> | null = null

    // El provider navega con useNavigate (016): necesita un router alrededor.
    render(
      <MemoryRouter>
        <SesionProvider>
          <Consumidor onValor={(v) => { valor = v }} />
        </SesionProvider>
      </MemoryRouter>,
    )

    // Verificar que todas las propiedades del contrato existen
    expect(valor).not.toBeNull()
    expect(valor).toHaveProperty('sesion')
    expect(valor).toHaveProperty('empresa')
    expect(valor).toHaveProperty('setEmpresa')
    expect(valor).toHaveProperty('cerrarSesion')
    expect(valor).toHaveProperty('pantalla')
    expect(valor).toHaveProperty('irA')

    // Verificar tipos básicos de las funciones
    expect(typeof valor!.setEmpresa).toBe('function')
    expect(typeof valor!.cerrarSesion).toBe('function')
    expect(typeof valor!.irA).toBe('function')
  })
})
