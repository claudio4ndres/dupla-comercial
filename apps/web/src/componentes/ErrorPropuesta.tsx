// ErrorPropuesta — Página de error para rutas de propuesta (/propuestas/:id).
// Distingue entre 404 (propuesta no encontrada) y errores de red.
// Se conectará al router como errorElement de la ruta /propuestas/:id.

import { useRouteError, Link } from 'react-router'

/**
 * Componente de error para las rutas de propuesta.
 * Se renderiza automáticamente cuando el loader de la ruta lanza un error.
 */
export function ErrorPropuesta() {
  const error = useRouteError()
  const es404 = error instanceof Response && error.status === 404

  return (
    <section className="screen">
      <div className="wrap">
        <p className="empty" style={{ marginTop: 40 }}>
          {es404 ? 'Propuesta no encontrada.' : 'Error al cargar la propuesta.'}
        </p>
        <Link to="/propuestas" className="btn primary" style={{ marginTop: '1rem', display: 'inline-block' }}>
          Volver a propuestas
        </Link>
      </div>
    </section>
  )
}
