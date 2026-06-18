# Implementation Plan: `navegacion-router`

## Overview

Migración incremental de la navegación por estado (`useState<Pantalla>`) a
**React Router v7** con `createBrowserRouter`. Se sigue la estrategia de 7 pasos
del diseño (Paso 0–6); cada paso termina con `npm test` en verde antes de avanzar
al siguiente. Los tests de `App.test.tsx` no deben romperse en ningún paso.

---

## Tasks

- [ ] 1. Paso 0 — Instalar React Router e inicializar el árbol de rutas

  - [ ] 1.1 Instalar `react-router` como dependencia de producción con versión exacta
    - Agregar `react-router` al `apps/web/package.json` con versión exacta (ej. `7.x.x`)
    - Verificar que `npm run build` completa sin errores de tipos ni bundler
    - _Requirements: 1.1, 1.2_

  - [ ] 1.2 Crear `src/router.tsx` con el árbol inicial de rutas (stub)
    - Crear `src/router.tsx` que exporte `router = createBrowserRouter([...])`
    - Incluir todas las rutas del diseño como stubs (`element: <div />`) para que el árbol compile
    - No conectar todavía a `main.tsx`
    - _Requirements: 1.3_

  - [ ] 1.3 Envolver `main.tsx` con `RouterProvider`
    - Reemplazar `<App />` por `<RouterProvider router={router} />` en `main.tsx`
    - `App.tsx` sigue recibiendo `onNavegar` y manteniendo el `useState<Pantalla>` (sin cambios)
    - El servidor de desarrollo responde a `/bandeja` directamente sin 404 (Vite ya tiene SPA fallback)
    - _Requirements: 1.4, 1.5_

  - [ ]* 1.4 Verificar que la suite existente `App.test.tsx` sigue en verde
    - Envolver el render de `<App />` en `App.test.tsx` con `MemoryRouter` como describe la Opción A del diseño
    - Añadir helper `renderApp(initialPath)` a `src/test/utils.tsx`
    - Ejecutar `npm test` y confirmar que todos los tests de `App.test.tsx` pasan
    - _Requirements: 8.1, 8.2, 8.5_

  - [ ] 1.5 Checkpoint — `npm test` en verde tras el Paso 0
    - Asegurar que todos los tests pasan. Consultar con el usuario si hay dudas.

- [ ] 2. Paso 1 — Crear componentes base: `RutaProtegida`, `RedireccionRaiz`, `NotFound`

  - [ ] 2.1 Crear hook `src/hooks/useSesionActual.ts`
    - Extraer la lógica de `getSession` + `onAuthStateChange` de `App.tsx` a un hook reutilizable
    - El hook devuelve `Sesion | null | undefined` (undefined = aún resolviendo)
    - `App.tsx` lo consume internamente (sin cambio de comportamiento externo)
    - _Requirements: 2.1, 2.3_

  - [ ]* 2.2 Escribir property test para `useSesionActual`
    - **Property 1 (parcial): Para cualquier correo, la sesión válida produce objeto `Sesion`**
    - Usar `fc.emailAddress()` para generar correos arbitrarios
    - **Validates: Requirements 2.1, 2.3, 2.4**

  - [ ] 2.3 Crear `src/componentes/RutaProtegida.tsx`
    - Implementar los tres estados: `undefined` → `null`, `null` → `<Navigate to="/login">`, `Sesion` → `<Outlet />`
    - Guardar `location` en `state.from` al redirigir (para post-login redirect)
    - Incluir `Sidebar`, `Topbar` y área de contenido con `<Outlet />` (layout completo)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 2.4 Escribir property tests para `RutaProtegida` (Property 1 completa)
    - **Property 1: RutaProtegida respeta los tres estados de sesión**
    - Test con `fc.emailAddress()` — sesión válida renderiza `<Outlet>`, no redirige
    - Test ejemplo: sesión `undefined` → `null` (sin flash)
    - Test ejemplo: sesión `null` → redirect a `/login` con `state.from`
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

  - [ ] 2.5 Crear `src/componentes/RedireccionRaiz.tsx`
    - Con sesión → `<Navigate to="/bandeja" replace />`
    - Sin sesión → `<Navigate to="/login" replace />`
    - Mientras resuelve → `null`
    - _Requirements: 3.1, 3.2_

  - [ ]* 2.6 Escribir tests unitarios para `RedireccionRaiz`
    - Test: sesión activa → redirige a `/bandeja`
    - Test: sin sesión → redirige a `/login`
    - Test: resolviendo → renderiza null (sin flash)
    - _Requirements: 3.1, 3.2_

  - [ ] 2.7 Crear `src/componentes/NotFound.tsx`
    - Renderiza mensaje "Página no encontrada" con `<Link to="/bandeja">`
    - _Requirements: 3.5_

  - [ ] 2.8 Crear `src/componentes/ErrorSolicitud.tsx` y `src/componentes/ErrorPropuesta.tsx`
    - `ErrorSolicitud`: usa `useRouteError()`, distingue 404 vs error de red, enlace a `/bandeja`
    - `ErrorPropuesta`: misma lógica, enlace a `/propuestas`
    - _Requirements: 4.4, 5.4_

  - [ ]* 2.9 Escribir tests unitarios para `NotFound`, `ErrorSolicitud` y `ErrorPropuesta`
    - Test: `NotFound` muestra enlace a `/bandeja`
    - Test: `ErrorSolicitud` con `status 404` muestra "Solicitud no encontrada"
    - Test: `ErrorPropuesta` con `status 404` muestra "Propuesta no encontrada"
    - _Requirements: 3.5, 4.4, 5.4_

  - [ ] 2.10 Conectar los nuevos componentes en `src/router.tsx`
    - Reemplazar stubs: conectar `RutaProtegida`, `RedireccionRaiz`, `NotFound`
    - Las pantallas hijas siguen como stubs por ahora
    - _Requirements: 1.3_

  - [ ] 2.11 Checkpoint — `npm test` en verde tras el Paso 1
    - Asegurar que todos los tests pasan. Consultar con el usuario si hay dudas.

- [ ] 3. Paso 2 — Migrar `/bandeja` (pantalla `inbox`)

  - [ ] 3.1 Conectar `Bandeja` en `router.tsx` como ruta `/bandeja`
    - Reemplazar el stub de `/bandeja` por el componente real `<Bandeja>`
    - Las props de carga/error que antes venían de `App.tsx` pasan a ser responsabilidad
      de la ruta: `Bandeja` consulta `obtenerSolicitudesOError` internamente (o via contexto)
    - En este paso se puede mantener la lógica en `App` y pasarla via contexto, sin aún borrar `useState`
    - _Requirements: 4.1_

  - [ ] 3.2 Reemplazar `irA('inbox')` / `irA('detail')` por `useNavigate`
    - En `Configuracion.tsx`: `onIrA('inbox')` → `useNavigate('/bandeja')`
    - En `Bandeja.tsx`: `onAbrir(s)` guarda la solicitud en contexto y llama `navigate('/bandeja/' + s.id)`
    - `App.tsx` aún puede tener el `useState<Pantalla>` pero ya no lo usa para `inbox`
    - _Requirements: 4.1, 4.2_

  - [ ]* 3.3 Escribir tests de navegación para `/bandeja`
    - Test: clic en "Continuar a la bandeja" → URL cambia a `/bandeja`
    - Test: clic en una solicitud → URL cambia a `/bandeja/:id`
    - Usar `MemoryRouter` con `createMemoryRouter` + `RouterProvider` en el render de test
    - _Requirements: 4.1, 4.2_

  - [ ] 3.4 Checkpoint — `npm test` en verde tras migrar `/bandeja`
    - Asegurar que todos los tests pasan. Consultar con el usuario si hay dudas.

- [ ] 4. Paso 3 — Migrar `/bandeja/:id` con loader de solicitud

  - [ ] 4.1 Crear loader `cargarSolicitud` en `src/router.tsx`
    - `async function cargarSolicitud({ params })` → fetch al backend con `params.id`
    - Si el `id` no existe → `throw new Response('No encontrada', { status: 404 })`
    - _Requirements: 4.3, 4.4, 7.1_

  - [ ] 4.2 Conectar `DetalleSolicitud` en la ruta `/bandeja/:id`
    - El componente consume `useLoaderData()` para obtener la solicitud
    - `DetalleSolicitud` deja de recibir `solicitud` como prop de `App` (ahora viene del loader)
    - Mantener compatibilidad de prop para tests existentes de `DetalleSolicitud.test.tsx`
    - `errorElement`: `<ErrorSolicitud />`
    - _Requirements: 4.3, 4.4_

  - [ ]* 4.3 Escribir property test para loader de `/bandeja/:id` (Property 3)
    - **Property 3: Carga directa de solicitud por id**
    - Usar `fc.uuid()` para ids arbitrarios; mockear `obtenerSolicitudPorId` según exista o no
    - Test: id válido → loader devuelve la solicitud
    - Test: id inexistente → loader lanza `Response` con status 404 → renderiza `ErrorSolicitud`
    - **Validates: Requirements 4.3, 4.4, 7.1**

  - [ ] 4.4 Agregar indicador de carga global en `RutaProtegida`
    - Usar `useNavigation().state === 'loading'` para mostrar `<CargandoLista>` sobre el contenido
    - _Requirements: 7.2_

  - [ ] 4.5 Checkpoint — `npm test` en verde tras migrar `/bandeja/:id`
    - Asegurar que todos los tests pasan. Consultar con el usuario si hay dudas.

- [ ] 5. Paso 4 — Migrar sub-rutas de solicitud y rutas del menú

  - [ ] 5.1 Crear loaders `cargarSolicitudSiNecesario` y `cargarPropuesta`
    - `cargarSolicitudSiNecesario`: si hay `SolicitudContext` con el mismo id → retorna `null`; si no → llama `cargarSolicitud`
    - `cargarPropuesta`: fetch al backend de `/solicitudes/:id/propuesta`; si 404 → lanza `Response`
    - _Requirements: 5.3, 5.4, 7.1, 7.4_

  - [ ] 5.2 Conectar `Chat` en `/bandeja/:id/chat` con `cargarSolicitudSiNecesario`
    - El componente consume `useLoaderData()` si no hay contexto, o el contexto si existe
    - `errorElement`: `<ErrorSolicitud />`
    - _Requirements: 4.5, 7.1, 7.3, 7.4_

  - [ ] 5.3 Conectar `Propuesta` en `/bandeja/:id/propuesta` con `cargarSolicitudSiNecesario`
    - `errorElement`: `<ErrorSolicitud />`
    - _Requirements: 4.6_

  - [ ] 5.4 Conectar `PropuestasLista` en `/propuestas` y `Propuesta` en `/propuestas/:id`
    - `/propuestas/:id` usa loader `cargarPropuesta`
    - `errorElement` de `/propuestas/:id`: `<ErrorPropuesta />`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ] 5.5 Conectar `Tareas` en `/tareas` y `Configuracion` en `/configuracion`
    - Adaptar `Configuracion.tsx`: `onIrA('inbox')` → `useNavigate('/bandeja')`
    - _Requirements: 5.5, 5.6_

  - [ ]* 5.6 Escribir property test para loader de `/propuestas/:id` (Property 6)
    - **Property 6: Carga directa de propuesta por id**
    - Usar `fc.uuid()` para ids arbitrarios
    - Test: id válido → loader devuelve la propuesta → `Propuesta` la renderiza
    - Test: id inexistente → loader lanza 404 → renderiza `ErrorPropuesta`
    - **Validates: Requirements 5.3, 5.4**

  - [ ]* 5.7 Escribir property test para post-login redirect (Property 2)
    - **Property 2: Preservación de URL de destino en redirect a login**
    - Usar `fc.constantFrom('/bandeja/abc', '/propuestas/xyz', '/tareas', '/configuracion')` para rutas
    - Test: sin sesión accede a ruta protegida → `location.state.from.pathname` es la ruta original
    - **Validates: Requirements 2.5, 9.2, 9.3**

  - [ ] 5.8 Checkpoint — `npm test` en verde tras migrar todas las rutas
    - Asegurar que todos los tests pasan. Consultar con el usuario si hay dudas.

- [ ] 6. Paso 5 — Migrar `Sidebar` y `Topbar` a `NavLink`/`useLocation`; eliminar `useState<Pantalla>`

  - [ ] 6.1 Refactorizar `Sidebar.tsx`: reemplazar `onClick → onIrA` por `<NavLink>`
    - Crear mapa `RUTA_DE: Record<string, string>` con las rutas de cada ítem
    - `className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}`
    - Eliminar props `pantalla` y `onIrA` de la interfaz de `Sidebar`
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [ ]* 6.2 Escribir property tests para `Sidebar` (Property 4)
    - **Property 4: NavLink del Sidebar refleja la ruta activa**
    - Usar `fc.constantFrom('/bandeja', '/propuestas', '/tareas', '/configuracion')` para rutas
    - Test: para cada ruta activa, el `NavLink` correspondiente tiene clase `active` y los demás no
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [ ] 6.3 Refactorizar `Topbar.tsx`: reemplazar prop `pantalla` por `useLocation`
    - Crear función `nombreDesdePath(pathname: string): string` que mapea rutas a nombres
    - Eliminar prop `pantalla` e import del tipo `Pantalla`
    - Mantener props `empresa`, `onAbrirMenu`, `onCerrarSesion` sin cambios
    - _Requirements: 6.4_

  - [ ]* 6.4 Escribir tests unitarios para `Topbar` con rutas
    - Test: `pathname = '/bandeja'` → muestra "Bandeja de solicitudes"
    - Test: `pathname = '/bandeja/abc'` → muestra "Solicitud"
    - Test: `pathname = '/configuracion'` → muestra "Configuración · conectores"
    - _Requirements: 6.4_

  - [ ] 6.5 Adaptar `Login.tsx` para post-login redirect
    - Importar `useNavigate` y `useLocation`
    - Leer `location.state.from?.pathname` y navegar ahí tras el login exitoso
    - Mantener prop `onEntrar` con la misma firma para compatibilidad de tests
    - Si no hay `state.from`, navegar a `/configuracion` por defecto
    - _Requirements: 3.3, 9.2_

  - [ ]* 6.6 Escribir property test para `Login` con sesión activa (Property 5)
    - **Property 5: Login con sesión activa redirige a /bandeja**
    - Usar `fc.emailAddress()` para sesiones válidas arbitrarias
    - Test: ruta `/login` renderizada con sesión activa → redirige a `/bandeja`
    - **Validates: Requirements 3.4**

  - [ ] 6.7 Eliminar `useState<Pantalla>` de `App.tsx`
    - Eliminar `pantalla`, `setPantalla`, `irA` y el switch de pantallas
    - Eliminar `onIrA` del Sidebar y Topbar en el render de `App`
    - `App.tsx` queda como punto de entrada con `RouterProvider` (o como layout si se usa Opción A)
    - Marcar el tipo `Pantalla` en `tipos.ts` con comentario `@deprecated`
    - _Requirements: 10.5_

  - [ ]* 6.8 Verificar compatibilidad completa de `App.test.tsx` tras eliminar estado
    - Ejecutar la suite completa de `App.test.tsx` y confirmar 0 fallos
    - Ajustar el helper `renderApp` si es necesario tras el refactor de `App.tsx`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ] 6.9 Checkpoint — `npm test` en verde tras el Paso 5 completo
    - Asegurar que todos los tests pasan. Consultar con el usuario si hay dudas.

- [ ] 7. Paso 6 — Configurar SPA fallback en producción (`produccion.py`)

  - [ ] 7.1 Agregar ruta catch-all en `apps/api/app/produccion.py`
    - Agregar `@raiz.get("/{full_path:path}")` que devuelve `FileResponse(SPA_INDEX)`
    - Colocar DESPUÉS del mount `/api` y del mount `/` de `StaticFiles`
    - Comentar el orden de evaluación en el código
    - _Requirements: 9.4_

  - [ ]* 7.2 Escribir test de integración para el SPA fallback
    - Usar el cliente de prueba de FastAPI (`TestClient`)
    - Test: `GET /bandeja/abc123` → responde 200 con contenido HTML (index.html)
    - Test: `GET /api/solicitudes` → NO es capturado por el catch-all (responde desde la API)
    - _Requirements: 9.4_

  - [ ] 7.3 Verificar `vite.config.ts` — confirmar que no requiere cambios para el fallback de dev
    - Comprobar que el proxy `/api` solo captura rutas de API (ya es correcto)
    - Agregar comentario en `vite.config.ts` que documente que Vite sirve `index.html` por defecto para rutas SPA
    - _Requirements: 1.5_

  - [ ] 7.4 Eliminar tipo `Pantalla` de `tipos.ts`
    - Una vez que ningún componente importe `Pantalla`, eliminar la definición del tipo
    - Eliminar `NOMBRE_PANTALLA` de `Topbar.tsx` si ya no se usa
    - _Requirements: 10.5_

  - [ ] 7.5 Checkpoint final — `npm test` en verde y `npm run build` sin errores
    - Ejecutar `npm test` (todos los tests) y `npm run build` (TypeScript + Vite)
    - Confirmar que no hay errores de tipos ni de bundler. Consultar con el usuario si hay dudas.

---

## Notes

- Las tareas marcadas con `*` son opcionales y se pueden omitir para un MVP más rápido
- Cada checkpoint valida que los tests existentes NO se rompieron antes de avanzar
- El orden de los pasos es estricto: cada paso construye sobre el anterior
- Los property tests usan `fast-check` (instalar como `devDependency` con versión exacta al inicio del Paso 1)
- La Opción A del diseño (envolver `App` con `MemoryRouter` en tests) minimiza cambios en `App.test.tsx`
- `App.test.tsx` navega entre pantallas con clics en botones/links; esos tests siguen funcionando porque `NavLink`/`useNavigate` respetan el `MemoryRouter` de contexto

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3"] },
    { "id": 3, "tasks": ["1.4", "2.1"] },
    { "id": 4, "tasks": ["2.2", "2.3"] },
    { "id": 5, "tasks": ["2.4", "2.5", "2.7", "2.8"] },
    { "id": 6, "tasks": ["2.6", "2.9", "2.10"] },
    { "id": 7, "tasks": ["3.1"] },
    { "id": 8, "tasks": ["3.2"] },
    { "id": 9, "tasks": ["3.3", "4.1"] },
    { "id": 10, "tasks": ["4.2"] },
    { "id": 11, "tasks": ["4.3", "4.4"] },
    { "id": 12, "tasks": ["5.1"] },
    { "id": 13, "tasks": ["5.2", "5.3", "5.4", "5.5"] },
    { "id": 14, "tasks": ["5.6", "5.7", "6.1"] },
    { "id": 15, "tasks": ["6.2", "6.3"] },
    { "id": 16, "tasks": ["6.4", "6.5"] },
    { "id": 17, "tasks": ["6.6", "6.7"] },
    { "id": 18, "tasks": ["6.8", "7.1"] },
    { "id": 19, "tasks": ["7.2", "7.3", "7.4"] }
  ]
}
```
