// RedireccionRaiz — Redirige "/" a la landing de la app (spec 016).
// Vive bajo RutaProtegida, así que aquí SIEMPRE hay sesión: el landing
// post-login es Configuración (onboarding de conectores), igual que antes
// de la migración al router.

import { Navigate } from 'react-router'

/** Componente para la ruta raíz `/`: manda al usuario a su landing. */
export function RedireccionRaiz() {
  return <Navigate to="/configuracion" replace />
}
