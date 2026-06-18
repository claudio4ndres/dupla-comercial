# Requirements Document

## Introduction

El frontend de Dupla Comercial navega hoy mediante un `useState<Pantalla>` en
`App.tsx`. Ese enfoque cubre siete pantallas (`configuracion`, `inbox`, `detail`,
`chat`, `propuestas`, `propuesta`, `tareas`) pero no produce URLs reales en el
navegador: no se puede compartir un enlace directo a una pantalla, el botón
"atrás" del navegador no funciona y el switch de pantallas en `App.tsx` crecerá
indefinidamente conforme se agreguen nuevas vistas.

Esta feature migra la navegación a un **router real con historial de navegador**,
asignando a cada pantalla su propia URL semántica y manteniendo las reglas de oro
del proyecto:

- Toda pantalla (excepto `/login`) requiere sesión activa de Supabase.
- Las pantallas de detalle, chat y propuesta de solicitud dependen de una
  `solicitudActual` en estado (la URL contiene el `id`, pero el objeto completo
  puede no estar disponible sin la carga previa).
- Los tests existentes en `App.test.tsx` deben seguir pasando sin reescritura mayor.
- Comentarios y commits en español.

### Elección de librería

Se recomienda **React Router v7** (modo framework-less / SPA) por las siguientes
razones:

| Criterio | React Router v7 | TanStack Router |
|---|---|---|
| Tipado de rutas y params | Suficiente con TypeScript estándar; `useParams` tipado genéricamente | Tipado al 100 % inferido del árbol de rutas |
| Compatibilidad Vite 8 + React 19 | ✅ Official, primera clase | ✅ Compatible, plugin separado |
| Tamaño bundle | ~26 kB minzip | ~14 kB minzip |
| Facilidad de migración desde estado | Alta: `<Routes>` + `<Route>` es declarativo, se añade sobre el código existente | Media: requiere definir el árbol de rutas con tipos antes de renderizar |
| Popularidad / mantenimiento | Altísima (Remix team, millones de instalaciones semanales) | Alta y creciente, comunidad más pequeña |
| Curva de aprendizaje | Baja (ya conocido por la mayoría del ecosistema React) | Media (paradigma diferente) |

**TanStack Router** es una excelente opción cuando el tipado end-to-end de
parámetros de ruta es crítico desde el inicio del proyecto. Para Dupla Comercial,
en esta etapa, el beneficio marginal no justifica la complejidad de migración
adicional. React Router v7 se instala en modo SPA con `createBrowserRouter` y se
puede incrementalizar ruta a ruta.

Si el proyecto adopta SSR en el futuro (Cloud Run + React Server Components),
React Router v7 en modo framework es la evolución natural sin cambiar de librería.

---

## Glossary

- **Router**: Librería que mapea URLs del navegador a componentes React y gestiona
  el historial de navegación (botón "atrás" / "adelante").
- **Ruta**: Par URL-patrón ↔ componente React. Ejemplo: `/bandeja/:id` ↔
  `DetalleSolicitud`.
- **Parámetro de ruta**: Segmento variable en la URL marcado con `:`. Ejemplo:
  el `:id` de `/bandeja/:id` corresponde al `id` de la solicitud.
- **React Router v7**: Versión actual de la librería de enrutamiento oficial del
  ecosistema React, mantenida por el equipo de Remix. Se usa en modo SPA con
  `createBrowserRouter`.
- **createBrowserRouter**: Función de React Router v7 que crea el router usando
  la History API del navegador (URLs limpias sin `#`).
- **Guard de autenticación**: Componente o lógica que redirige al usuario a
  `/login` si no hay sesión activa, protegiendo las rutas privadas.
- **Ruta protegida**: Ruta que solo puede acceder un usuario con sesión activa de
  Supabase.
- **Ruta pública**: Ruta accesible sin sesión (`/login`).
- **SolicitudActual**: Estado en memoria que contiene el objeto `Solicitud`
  completo seleccionado por el usuario. La URL lleva el `id` pero el objeto se
  carga desde el backend al navegar directamente a la ruta de detalle.
- **Pantalla**: Nombre interno del tipo `Pantalla` en `tipos.ts`. Tras la
  migración, este tipo se elimina o reemplaza por las rutas del router.
- **Historial de navegador**: Mecanismo del navegador (History API) que gestiona
  la pila de URLs visitadas y habilita el botón "atrás"/"adelante".
- **Acceso directo (deep link)**: Capacidad de llegar a una pantalla concreta
  escribiendo su URL directamente en el navegador.
- **Bandeja**: Pantalla que lista las solicitudes recibidas (equivalente a
  `'inbox'`).
- **DetalleSolicitud**: Pantalla con el detalle de una solicitud individual.
- **Chat**: Pantalla de conversación con Javo para una solicitud.
- **Propuesta**: Pantalla con la cotización generada por Javo para una solicitud.
- **PropuestasLista**: Pantalla con el listado global de propuestas del menú.
- **Configuracion**: Pantalla de onboarding post-login para conectar integraciones.
- **Tareas**: Pantalla con el listado de tareas.
- **TanStack Router**: Alternativa evaluada; tipado end-to-end superior, pero
  mayor complejidad de migración. Descartada para esta fase.
- **Supabase Auth**: Servicio de autenticación usado por el proyecto. La sesión
  activa se verifica mediante `supabase.auth.getSession()`.

---

## Mapeo de pantallas a rutas

| Pantalla actual (`Pantalla`) | Ruta nueva | Notas |
|---|---|---|
| — (raíz) | `/` | Redirige a `/bandeja` si hay sesión, a `/login` si no |
| `'configuracion'` | `/configuracion` | Ruta protegida; landing post-login |
| `'inbox'` | `/bandeja` | Ruta protegida |
| `'detail'` | `/bandeja/:id` | Ruta protegida; carga `SolicitudActual` por `id` |
| `'chat'` | `/bandeja/:id/chat` | Ruta protegida; requiere `SolicitudActual` cargado |
| `'propuesta'` (desde chat) | `/bandeja/:id/propuesta` | Ruta protegida; requiere `SolicitudActual` |
| `'propuestas'` | `/propuestas` | Ruta protegida |
| `'propuesta'` (desde lista) | `/propuestas/:id` | Ruta protegida; carga propuesta por `id` |
| `'tareas'` | `/tareas` | Ruta protegida |
| Login | `/login` | Ruta pública |

---

## Requirements

### Requirement 1: Instalación y configuración de React Router v7

**User Story:** Como desarrollador, quiero instalar React Router v7 en modo SPA,
para poder definir rutas con URLs reales usando `createBrowserRouter`.

#### Acceptance Criteria

1. THE Sistema SHALL agregar `react-router` (v7) como dependencia de producción en
   `apps/web/package.json` con versión exacta fijada.
2. WHEN el comando `npm run build` se ejecuta tras la instalación, THE Sistema SHALL
   completar la compilación sin errores de tipos ni de bundler.
3. THE Sistema SHALL configurar `createBrowserRouter` en un archivo dedicado
   `src/router.tsx`, separado de `main.tsx` y `App.tsx`, para mantener la
   definición del árbol de rutas en un único lugar.
4. THE Sistema SHALL envolver el árbol de `App` con `<RouterProvider router={router}>`
   en `main.tsx`, reemplazando el render actual de `<App />` directo.
5. WHEN el servidor de desarrollo se inicia con `npm run dev`, THE Sistema SHALL
   servir correctamente cualquier ruta definida (recargando `/bandeja` directamente,
   por ejemplo) sin devolver 404.

---

### Requirement 2: Guard de autenticación

**User Story:** Como desarrollador, quiero un componente `RutaProtegida` que
redirija a `/login` cuando no hay sesión activa, para que ninguna pantalla privada
sea accesible sin autenticación.

#### Acceptance Criteria

1. THE Sistema SHALL crear un componente `RutaProtegida` que envuelva las rutas
   privadas y verifique la sesión de Supabase antes de renderizar el contenido.
2. WHEN `sesion` es `null` (sin sesión), THE `RutaProtegida` SHALL redirigir al
   usuario a `/login` usando el mecanismo de redirección del router (sin recargar
   la página).
3. WHILE `sesion` es `undefined` (estado inicial, aún resolviéndose), THE
   `RutaProtegida` SHALL renderizar `null` para evitar un flash de contenido o de
   redirección prematura al login.
4. WHEN `sesion` tiene un valor válido, THE `RutaProtegida` SHALL renderizar el
   contenido de la ruta hija sin restricción.
5. WHEN el usuario accede directamente a una URL protegida sin sesión (deep link),
   THE `RutaProtegida` SHALL redirigir a `/login` y, tras el login exitoso, THE
   Sistema SHALL redirigir de vuelta a la URL original solicitada.
6. THE Sistema SHALL mantener la lógica de guardias en `RutaProtegida` y NO SHALL
   duplicar comprobaciones de sesión en componentes de pantalla individuales.

---

### Requirement 3: Ruta raíz y redirecciones

**User Story:** Como usuario, quiero que al acceder a `/` se me lleve
automáticamente al lugar correcto según mi sesión, para no tener que recordar la
URL exacta de cada pantalla.

#### Acceptance Criteria

1. WHEN un usuario con sesión activa accede a `/`, THE Sistema SHALL redirigirlo
   a `/bandeja`.
2. WHEN un usuario sin sesión accede a `/`, THE Sistema SHALL redirigirlo a
   `/login`.
3. WHEN el usuario completa el login exitosamente, THE Sistema SHALL redirigirlo a
   `/configuracion` (landing post-login / onboarding) si es la primera vez, o a
   `/bandeja` si ya completó la configuración.
4. WHEN el usuario accede a `/login` con sesión activa (ya estaba autenticado), THE
   Sistema SHALL redirigirlo a `/bandeja` para evitar mostrar el login innecesariamente.
5. IF el usuario accede a una URL inexistente (ruta no definida), THEN THE Sistema
   SHALL mostrar una pantalla de error 404 con enlace de vuelta a `/bandeja`.

---

### Requirement 4: Rutas de la Bandeja y sus sub-pantallas

**User Story:** Como usuario, quiero que cada pantalla del flujo de una solicitud
(bandeja → detalle → chat → propuesta) tenga su propia URL, para poder regresar a
cualquiera de ellas con el botón "atrás" del navegador.

#### Acceptance Criteria

1. WHEN el usuario navega a `/bandeja`, THE Sistema SHALL renderizar el componente
   `Bandeja` con la lista de solicitudes.
2. WHEN el usuario hace clic en una solicitud, THE Sistema SHALL navegar a
   `/bandeja/:id` usando `useNavigate` del router (en lugar de `setSolicitudActual`
   + `setPantalla`).
3. WHEN el usuario carga directamente la URL `/bandeja/:id`, THE Sistema SHALL
   obtener la solicitud con ese `id` desde el backend y renderizar `DetalleSolicitud`
   con los datos correctos.
4. IF el `id` de `/bandeja/:id` no corresponde a ninguna solicitud existente, THEN
   THE Sistema SHALL mostrar un mensaje de error indicando que la solicitud no fue
   encontrada, con un enlace de vuelta a `/bandeja`.
5. WHEN el usuario navega a `/bandeja/:id/chat`, THE Sistema SHALL renderizar el
   componente `Chat` para la solicitud indicada por `:id`.
6. WHEN el usuario navega a `/bandeja/:id/propuesta`, THE Sistema SHALL renderizar
   el componente `Propuesta` para la solicitud indicada por `:id`.
7. WHEN el usuario pulsa el botón "atrás" del navegador dentro del flujo
   `/bandeja/:id/chat → /bandeja/:id → /bandeja`, THE Sistema SHALL retroceder
   correctamente a la pantalla anterior usando el historial del navegador.

---

### Requirement 5: Rutas de Propuestas y Tareas

**User Story:** Como usuario, quiero que las pantallas de lista de propuestas,
detalle de propuesta y tareas tengan sus propias URLs, para acceder directamente
desde el menú o desde un enlace externo.

#### Acceptance Criteria

1. WHEN el usuario navega a `/propuestas`, THE Sistema SHALL renderizar el componente
   `PropuestasLista` con la lista global de propuestas.
2. WHEN el usuario hace clic en una fila de propuesta, THE Sistema SHALL navegar a
   `/propuestas/:id` y renderizar el detalle de esa propuesta.
3. WHEN el usuario carga directamente `/propuestas/:id`, THE Sistema SHALL obtener
   la propuesta con ese `id` desde el backend y renderizar `Propuesta` con los datos
   correctos.
4. IF el `id` de `/propuestas/:id` no corresponde a ninguna propuesta, THEN THE
   Sistema SHALL mostrar un mensaje de error con un enlace de vuelta a `/propuestas`.
5. WHEN el usuario navega a `/tareas`, THE Sistema SHALL renderizar el componente
   `Tareas` con la lista global de tareas.
6. WHEN el usuario navega a `/configuracion`, THE Sistema SHALL renderizar el
   componente `Configuracion` (onboarding de integraciones).

---

### Requirement 6: Navegación desde Sidebar y Topbar

**User Story:** Como usuario, quiero que los elementos del menú lateral y la barra
superior usen enlaces del router en lugar de callbacks, para que el historial del
navegador se actualice correctamente al navegar entre secciones.

#### Acceptance Criteria

1. THE Sistema SHALL reemplazar los `onClick` de navegación en `Sidebar` por
   componentes `<Link>` o `<NavLink>` de React Router, apuntando a las URLs
   correspondientes.
2. WHEN el usuario hace clic en un ítem del `Sidebar` (Bandeja, Propuestas, Tareas,
   Configuración), THE Sistema SHALL actualizar la URL del navegador a la ruta
   correspondiente.
3. WHEN la URL activa coincide con la ruta de un ítem del `Sidebar`, THE `NavLink`
   SHALL aplicar la clase activa para resaltar visualmente el ítem seleccionado,
   manteniendo el mismo estilo visual que hoy.
4. THE Sistema SHALL mantener la prop `onCerrarSesion` en `Topbar` sin cambios, ya
   que el cierre de sesión no es una navegación de ruta.
5. THE Sistema SHALL eliminar la prop `onIrA` de `Sidebar` y `Topbar` una vez que
   toda la navegación pase por el router, para simplificar las interfaces de esos
   componentes.

---

### Requirement 7: Preservación del estado de SolicitudActual en navegación directa

**User Story:** Como usuario, quiero que si accedo directamente a `/bandeja/:id/chat`
(por ejemplo, desde un enlace compartido), la app cargue la solicitud necesaria y
muestre el chat correctamente, sin quedar en un estado vacío.

#### Acceptance Criteria

1. WHEN el usuario accede directamente a `/bandeja/:id/chat` sin `solicitudActual`
   en estado, THE Sistema SHALL cargar la solicitud con ese `id` desde el backend
   antes de renderizar `Chat`.
2. WHILE la solicitud se está cargando en un acceso directo, THE Sistema SHALL
   mostrar un indicador de carga en lugar del componente vacío o un error.
3. IF la solicitud no puede cargarse (error de red o id inválido), THEN THE Sistema
   SHALL redirigir al usuario a `/bandeja/:id` con un mensaje de error, o a
   `/bandeja` si el `id` tampoco es válido.
4. WHEN el usuario navega a `/bandeja/:id/chat` desde el flujo normal (clic en
   DetalleSolicitud → elige tipo), THE Sistema SHALL pasar directamente al chat sin
   recargar la solicitud desde el backend (ya está en estado).
5. THE Sistema SHALL mantener el estado de `SolicitudActual` en un contexto React
   compartido (compatible con `SolicitudContext` del Requirement 3 de la spec
   `refactor-app-contextos`) para que sea accesible tanto por la navegación interna
   como por la carga directa.

---

### Requirement 8: Compatibilidad con tests existentes

**User Story:** Como desarrollador, quiero que los tests actuales de `App.test.tsx`
sigan pasando tras la migración al router, para garantizar que no se rompe ningún
comportamiento observable.

#### Acceptance Criteria

1. WHEN la suite completa de `App.test.tsx` se ejecuta con `npm run test` tras la
   migración, THE Sistema SHALL completarla sin fallos ni errores.
2. THE Sistema SHALL envolver el componente `App` (o su equivalente en el nuevo
   árbol) con un `MemoryRouter` o un router de prueba en el entorno de test, para
   que los tests no dependan de la History API real del navegador.
3. THE Sistema SHALL mantener la prop `onNavegar` en el punto de entrada testeable
   con la misma firma que hoy (`(url: string) => void`), ya que varios tests la
   inyectan para interceptar navegaciones OAuth.
4. IF un test existente navega entre pantallas mediante clics en botones o links,
   THEN THE Sistema SHALL seguir respondiendo a esos eventos con la misma transición
   de pantalla que antes, aunque internamente use el router en lugar del estado.
5. THE Sistema SHALL NO requerir mocks adicionales de React Router en los tests
   actuales: el wrapper de router de prueba debe ser transparente para los tests
   existentes.

---

### Requirement 9: Acceso directo (deep link) sin pérdida de sesión

**User Story:** Como usuario, quiero poder escribir directamente la URL
`/bandeja/abc123` en el navegador y llegar a esa pantalla tras autenticarme, para
poder compartir enlaces directos a solicitudes concretas.

#### Acceptance Criteria

1. WHEN un usuario no autenticado intenta acceder a `/bandeja/:id`, THE Sistema
   SHALL redirigirlo a `/login` preservando la URL de destino como parámetro.
2. WHEN el usuario completa el login exitosamente tras ser redirigido desde una
   URL protegida, THE Sistema SHALL redirigirlo de vuelta a la URL original
   (`/bandeja/:id`) en lugar de al landing por defecto.
3. THE Sistema SHALL transmitir la URL de destino al proceso de login mediante el
   state del router (`location.state`) o un query param `?redirigir=/bandeja/:id`,
   de forma que Login pueda redirigir de vuelta al completar la autenticación.
4. WHEN el servidor de producción (Cloud Run) recibe una petición a cualquier ruta
   definida (p. ej. `/bandeja/abc123`), THE Sistema SHALL servir el mismo
   `index.html` de la SPA para que el router del cliente tome el control, sin
   devolver 404.

---

### Requirement 10: Historial de navegación funcional

**User Story:** Como usuario, quiero que el botón "atrás" del navegador me lleve
a la pantalla anterior dentro de la app, para poder explorar el flujo de una
solicitud con los controles nativos del navegador.

#### Acceptance Criteria

1. WHEN el usuario navega de `/bandeja` a `/bandeja/:id` y pulsa "atrás", THE
   Sistema SHALL mostrar `/bandeja` con la lista de solicitudes en el estado en que
   estaba antes de entrar al detalle.
2. WHEN el usuario navega a través del flujo completo `/bandeja → /bandeja/:id →
   /bandeja/:id/chat → /bandeja/:id/propuesta` y pulsa "atrás" cuatro veces, THE
   Sistema SHALL retroceder paso a paso por ese historial.
3. THE Sistema SHALL usar `useNavigate` de React Router para las navegaciones
   programáticas (ej. "Generar propuesta" que navega a la propuesta), de forma que
   esas transiciones también queden en el historial del navegador.
4. WHEN el usuario usa el botón "adelante" del navegador tras haber retrocedido, THE
   Sistema SHALL avanzar correctamente en el historial de rutas visitadas.
5. THE Sistema SHALL eliminar el `useState<Pantalla>` de `App.tsx` una vez que toda
   la navegación pase por el router, para que no existan dos fuentes de verdad sobre
   la pantalla activa.
