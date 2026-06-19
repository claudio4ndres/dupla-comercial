// NotFound — Página 404 para rutas no definidas.
// Muestra un mensaje amigable con enlace de vuelta a /bandeja.
// Se conectará al router cuando se migre main.tsx a RouterProvider.

import { Link } from 'react-router'

/**
 * Pantalla de error 404 — URL no encontrada.
 * Se usa como catch-all (`path: '*'`) en el árbol del router.
 */
export function NotFound() {
  return (
    <section className="screen">
      <div className="wrap">
        <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Página no encontrada</h1>
        <p style={{ marginBottom: '1.5rem' }}>
          La URL no corresponde a ninguna pantalla de Dupla Comercial.
        </p>
        <Link to="/bandeja" className="btn primary">
          Volver a la bandeja
        </Link>
      </div>
    </section>
  )
}
