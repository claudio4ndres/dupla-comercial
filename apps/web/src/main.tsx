import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import './index.css'
import App from './App.tsx'
import { SesionProvider } from './contextos/SesionContext'
import { SolicitudProvider } from './contextos/SolicitudContext'
import { BandejaProvider } from './contextos/BandejaContext'

// Router mínimo: todas las rutas renderizan App, que sigue manejando la
// navegación interna por `pantalla` (estado del SesionContext).
// El hook useSincronizarRuta dentro de App mantiene la URL sincronizada.
const router = createBrowserRouter([
  {
    path: '*',
    element: <App />,
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SesionProvider>
      <SolicitudProvider>
        <BandejaProvider>
          <RouterProvider router={router} />
        </BandejaProvider>
      </SolicitudProvider>
    </SesionProvider>
  </StrictMode>,
)
