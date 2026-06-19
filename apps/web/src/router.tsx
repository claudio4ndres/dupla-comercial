// router.tsx — Árbol de rutas de la aplicación usando React Router v7.
// Define createBrowserRouter con todas las rutas del proyecto.
//
// NOTA: Este archivo aún NO está conectado a main.tsx.
// Se activará cuando la migración esté completa y los tests se adapten.
// Por ahora es infraestructura lista para conectar.
//
// Para activar: en main.tsx reemplazar <App /> por:
//   import { RouterProvider } from 'react-router'
//   import { router } from './router'
//   <RouterProvider router={router} />

import { createBrowserRouter } from 'react-router'
import { RutaProtegida } from './componentes/RutaProtegida'
import { RedireccionRaiz } from './componentes/RedireccionRaiz'
import { NotFound } from './componentes/NotFound'
import { ErrorSolicitud } from './componentes/ErrorSolicitud'
import { ErrorPropuesta } from './componentes/ErrorPropuesta'

// Importaciones lazy de pantallas (se cargan al navegar a la ruta).
// Cuando se conecte el router, estas apuntarán a los componentes reales.
// Por ahora usan imports estáticos — el tree-shaking de Vite los excluirá
// porque nada importa `router` desde main.tsx.
import { Login } from './componentes/Login'
import { Configuracion } from './componentes/Configuracion'
import { Bandeja } from './componentes/Bandeja'
import { DetalleSolicitud } from './componentes/DetalleSolicitud'
import { Chat } from './componentes/Chat'
import { Propuesta } from './componentes/Propuesta'
import { PropuestasLista } from './componentes/PropuestasLista'
import { Tareas } from './componentes/Tareas'

// ── Loaders (stubs por ahora — se implementarán con el backend conectado) ────

// TODO: implementar fetch real al backend cuando se conecte el router
// async function cargarSolicitud({ params }: { params: { id: string } }) {
//   const solicitud = await obtenerSolicitudPorId(params.id)
//   if (!solicitud) throw new Response('No encontrada', { status: 404 })
//   return solicitud
// }

// ── Árbol de rutas ───────────────────────────────────────────────────────────

export const router = createBrowserRouter([
  // Raíz: redirige según sesión
  {
    path: '/',
    element: <RedireccionRaiz />,
  },

  // Login: ruta pública
  {
    path: '/login',
    element: <Login onEntrar={() => {}} />,
  },

  // Rutas protegidas: requieren sesión activa
  {
    element: <RutaProtegida />,
    children: [
      {
        path: '/configuracion',
        element: <Configuracion
          estadoCorreo={{ estado: null, proveedor: null, casilla: null }}
          cargandoCorreo={false}
          onConectar={() => {}}
          onDesconectar={() => {}}
          onIrA={() => {}}
          onNavegar={() => {}}
        />,
      },
      {
        path: '/bandeja',
        element: <Bandeja
          solicitudes={[]}
          onAbrir={() => {}}
          proveedor={null}
          estado={null}
          onConectar={() => {}}
          onDesconectar={() => {}}
          cargando={false}
          error={false}
          onReintentar={() => {}}
        />,
      },
      {
        path: '/bandeja/:id',
        element: <DetalleSolicitud
          solicitud={{ id: '', remitente: '', correo: '', tiempo: '', asunto: '', tipo: 'new', resumen: '', puntos: [], cuerpo: '' }}
          onVolver={() => {}}
          onElegirTipo={() => {}}
        />,
        errorElement: <ErrorSolicitud />,
        // TODO: loader: cargarSolicitud
      },
      {
        path: '/bandeja/:id/chat',
        element: <Chat
          solicitud={{ id: '', remitente: '', correo: '', tiempo: '', asunto: '', tipo: 'new', resumen: '', puntos: [], cuerpo: '' }}
          tipo="t1"
          mensajes={[]}
          componentes={[]}
          fuentes={[]}
          recursos={[]}
          enviando={false}
          onEnviar={() => {}}
          onGenerarPropuesta={() => {}}
        />,
        errorElement: <ErrorSolicitud />,
        // TODO: loader: cargarSolicitudSiNecesario
      },
      {
        path: '/bandeja/:id/propuesta',
        element: <Propuesta
          componentes={[]}
          onVolver={() => {}}
          onArmarTareas={() => {}}
        />,
        errorElement: <ErrorSolicitud />,
        // TODO: loader: cargarSolicitudSiNecesario
      },
      {
        path: '/propuestas',
        element: <PropuestasLista
          propuestas={[]}
          onAbrir={() => {}}
          cargando={false}
          error={false}
          onReintentar={() => {}}
        />,
      },
      {
        path: '/propuestas/:id',
        element: <Propuesta
          componentes={[]}
          onVolver={() => {}}
          onArmarTareas={() => {}}
        />,
        errorElement: <ErrorPropuesta />,
        // TODO: loader: cargarPropuesta
      },
      {
        path: '/tareas',
        element: <Tareas
          tareas={[]}
          onVolver={() => {}}
        />,
      },
    ],
  },

  // Catch-all: 404
  {
    path: '*',
    element: <NotFound />,
  },
])
