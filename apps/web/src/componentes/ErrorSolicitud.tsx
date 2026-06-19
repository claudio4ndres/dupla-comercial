// ErrorSolicitud — Página de error para rutas de solicitud (/bandeja/:id y sub-rutas).
// Distingue entre 404 (solicitud no encontrada) y errores de red.
// Se conectará al router como errorElement de las rutas /bandeja/:id/*.

import { useRouteError, Link } from 'react-router'

/**
 * Componente de error para las rutas de solicitud.
 * Se renderiza automáticamente cuando el loader de la ruta lanza un error.
 */
export function ErrorSolicitud() {
  const error = useRouteError()
  const es404 = error instanceof Response && error.status === 404

  return (
    <section className="screen">
      <div className="wrap">
        <p className="empty" style={{ marginTop: 40 }}>
          {es404 ? 'Solicitud no encontrada.' : 'Error al cargar la solicitud.'}
        </p>
        <Link to="/bandeja" className="btn primary" style={{ marginTop: '1rem', display: 'inline-block' }}>
          Volver a la bandeja
        </Link>
      </div>
    </section>
  )
}
