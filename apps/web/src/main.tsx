import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import './index.css'
import { crearRutas } from './router'

// Router real (spec 016): el árbol de rutas vive en router.tsx y los providers
// de contexto se montan DENTRO del router (componente Raiz), porque los
// contextos navegan con useNavigate y derivan la pantalla de useLocation.
const router = createBrowserRouter(crearRutas())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
