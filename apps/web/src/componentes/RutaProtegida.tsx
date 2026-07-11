// RutaProtegida — Guard de autenticación para rutas privadas (spec 016).
// Verifica la sesión del SesionContext; sin sesión, muestra el Login EN LA
// MISMA URL (sin redirigir), así el deep-link se conserva y al autenticarse
// el usuario aterriza directo en la pantalla que le compartieron.

import { Outlet } from 'react-router'
import { useSesion } from '../contextos/SesionContext'
import { Login } from './Login'

/**
 * Componente layout que envuelve las rutas privadas.
 * Tres estados posibles de sesión:
 * - undefined → aún resolviendo → renderiza null (evita flash)
 * - null → sin sesión → muestra el Login (la URL destino se conserva)
 * - Sesion → autenticado → renderiza el contenido hijo (<Outlet />)
 */
export function RutaProtegida() {
  const { sesion } = useSesion()

  // Aún resolviendo la sesión — no mostrar nada para evitar flash
  if (sesion === undefined) return null

  // Sin sesión — Login en la misma URL. El submit lo resuelve Supabase: cuando
  // la sesión queda activa, el contexto re-renderiza y entra el <Outlet/>.
  if (sesion === null) return <Login onEntrar={() => {}} />

  // Con sesión — renderizar la ruta hija
  return <Outlet />
}
