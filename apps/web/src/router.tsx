// router.tsx — Árbol de rutas de la aplicación con React Router v7 (spec 016).
//
// `crearRutas()` devuelve el árbol para createBrowserRouter (main.tsx) o
// createMemoryRouter (tests). Los providers de contexto se montan en `Raiz`
// (App.tsx), DENTRO del router, porque SesionContext usa useNavigate/useLocation.
//
// El parámetro `onNavegar` (inyectable en tests) es la navegación a URLs
// EXTERNAS (consentimiento OAuth), no la navegación interna del router.

import type { RouteObject } from 'react-router'
import { RutaProtegida } from './componentes/RutaProtegida'
import { RedireccionRaiz } from './componentes/RedireccionRaiz'
import { NotFound } from './componentes/NotFound'
import {
  Layout,
  Raiz,
  RutaBandeja,
  RutaChat,
  RutaConfiguracion,
  RutaDetalle,
  RutaPropuesta,
  RutaPropuestas,
  RutaTareas,
} from './App'

/**
 * Construye el árbol de rutas real de la app.
 * @param onNavegar navegación a URLs externas (OAuth); inyectable para tests.
 */
export function crearRutas(onNavegar?: (url: string) => void): RouteObject[] {
  return [
    {
      element: <Raiz />,
      children: [
        {
          // Guard de sesión: sin sesión muestra el Login CONSERVANDO la URL,
          // así un deep-link sobrevive al paso por el login.
          element: <RutaProtegida />,
          children: [
            { path: '/', element: <RedireccionRaiz /> },
            {
              element: <Layout />,
              children: [
                { path: '/configuracion', element: <RutaConfiguracion onNavegar={onNavegar} /> },
                { path: '/bandeja', element: <RutaBandeja onNavegar={onNavegar} /> },
                { path: '/bandeja/:id', element: <RutaDetalle /> },
                { path: '/bandeja/:id/chat', element: <RutaChat /> },
                { path: '/propuestas', element: <RutaPropuestas /> },
                { path: '/propuestas/:id', element: <RutaPropuesta /> },
                { path: '/tareas', element: <RutaTareas /> },
              ],
            },
          ],
        },
        // Catch-all: URL desconocida → 404.
        { path: '*', element: <NotFound /> },
      ],
    },
  ]
}
