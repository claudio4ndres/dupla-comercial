// RedireccionRaiz — Redirige "/" según el estado de sesión.
// Con sesión → /bandeja | Sin sesión → /login | Resolviendo → null
// Se conectará al router cuando se migre main.tsx a RouterProvider.

import { Navigate } from 'react-router'
import { useSesion } from '../contextos/SesionContext'

/**
 * Componente para la ruta raíz `/`.
 * Redirige al usuario al lugar correcto según su sesión.
 */
export function RedireccionRaiz() {
  const { sesion } = useSesion()

  // Aún resolviendo — sin flash
  if (sesion === undefined) return null

  // Con sesión → bandeja; sin sesión → login
  return <Navigate to={sesion ? '/bandeja' : '/login'} replace />
}
