// RutaProtegida — Guard de autenticación para rutas privadas.
// Verifica la sesión del SesionContext y redirige a /login si no hay.
// Se conectará al router cuando se migre main.tsx a RouterProvider.

import { Navigate, Outlet, useLocation } from 'react-router'
import { useSesion } from '../contextos/SesionContext'

/**
 * Componente layout que envuelve las rutas privadas.
 * Tres estados posibles de sesión:
 * - undefined → aún resolviendo → renderiza null (evita flash)
 * - null → sin sesión → redirige a /login guardando la URL destino
 * - Sesion → autenticado → renderiza el contenido hijo (<Outlet />)
 */
export function RutaProtegida() {
  const { sesion } = useSesion()
  const location = useLocation()

  // Aún resolviendo la sesión — no mostrar nada para evitar flash
  if (sesion === undefined) return null

  // Sin sesión — redirigir a /login preservando la URL de destino
  if (sesion === null) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // Con sesión — renderizar la ruta hija
  return <Outlet />
}
