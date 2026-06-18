# Design Document — `navegacion-router`

## Overview

El objetivo de esta feature es reemplazar el enrutamiento por estado
(`useState<Pantalla>`) de `App.tsx` por **React Router v7** en modo SPA, usando
`createBrowserRouter` y `RouterProvider`. Cada pantalla recibe su propia URL semántica,
el botón "atrás" del navegador funciona correctamente y se habilitan los deep links a
pantallas con `id` (solicitudes, propuestas).

La migración es **incremental**: se introduce el router, se protegen todas las rutas con
un componente `RutaProtegida` y se migra pantalla a pantalla empezando por `/bandeja`,
sin romper ningún test existente de `App.test.tsx`.

### Relación con otras specs

- **`refactor-app-contextos`**: si esta spec se implementa en paralelo o después,
  `SesionContext`, `BandejaContext` y `SolicitudContext` reemplazan los props que hoy se
  pasan a pantallas. El diseño de `navegacion-router` es compatible con ese refactor: las
  rutas consumen contextos o loaders, no props de `App`.
- **`refactor-app-contextos` Req 1**: `SesionContext` expone `sesion`, `empresa` e `irA`.
  Tras el router, `irA` se reemplaza por `useNavigate`; el contexto puede mantenerlo como
  wrapper o eliminarlo cuando la migración esté completa.

---

## Architecture

### Visión de alto nivel

```
main.tsx
  └── StrictMode
        └── RouterProvider (router = createBrowserRouter)
              ├── / → RedireccionRaiz (redirige según sesión)
              ├── /login → Login (ruta pública; redirige a /bandeja si ya hay sesión)
              ├── RutaProtegida (layout con Sidebar + Topbar)
              │     ├── /bandeja → Bandeja
              │     ├── /bandeja/:id → DetalleSolicitud (loader: fetchSolicitud)
              │     ├── /bandeja/:id/chat → Chat (loader: fetchSolicitud si falta)
              │     ├── /bandeja/:id/propuesta → Propuesta (loader: fetchSolicitud)
              │     ├── /propuestas → PropuestasLista
              │     ├── /propuestas/:id → Propuesta (loader: fetchPropuesta)
              │     ├── /tareas → Tareas
              │     └── /configuracion → Configuracion
              └── * → NotFound (404)
```

### Estrategia de migración incremental

Se migra ruta a ruta para minimizar el riesgo de regresión:

1. **Paso 0** — Instalar `react-router` (versión exacta), crear `src/router.tsx` con el
   árbol inicial, envolver `main.tsx` con `RouterProvider`. `App.tsx` sigue funcionando
   como layout general mientras el router gestiona las URLs.
2. **Paso 1** — Migrar `/bandeja` (pantalla más usada). Reemplazar `setPantalla('inbox')`
   por `useNavigate('/bandeja')`.
3. **Paso 2** — Migrar `/bandeja/:id` + loader de solicitud (deep link habilitado).
4. **Paso 3** — Migrar `/bandeja/:id/chat` y `/bandeja/:id/propuesta`.
5. **Paso 4** — Migrar `/propuestas`, `/propuestas/:id`, `/tareas`, `/configuracion`.
6. **Paso 5** — Migrar `Sidebar` y `Topbar` a `<Link>`/`<NavLink>`. Eliminar prop
   `onIrA`. Eliminar `useState<Pantalla>` de `App.tsx`.
7. **Paso 6** — Configurar SPA fallback en Vite (dev) y en `produccion.py` (Cloud Run).

Cada paso se acompaña de un ciclo rojo → verde → refactor y pasa los tests antes de
avanzar al siguiente.

---

## Components and Interfaces

### `src/router.tsx`

Archivo nuevo. Define y exporta el router principal. No contiene lógica de negocio.

```tsx
import { createBrowserRouter } from 'react-router'
import { RutaProtegida } from './componentes/RutaProtegida'
import { RedireccionRaiz } from './componentes/RedireccionRaiz'
// ... importaciones de pantallas

export const router = createBrowserRouter([
  { path: '/', element: <RedireccionRaiz /> },
  { path: '/login', element: <LoginConGuardia /> },
  {
    element: <RutaProtegida />,           // layout que envuelve rutas privadas
    children: [
      { path: '/configuracion', element: <Configuracion ... /> },
      { path: '/bandeja',       element: <Bandeja ... /> },
      {
        path: '/bandeja/:id',
        element: <DetalleSolicitud ... />,
        loader: cargarSolicitud,          // async: fetch al backend por id
        errorElement: <ErrorSolicitud />,
      },
      {
        path: '/bandeja/:id/chat',
        element: <Chat ... />,
        loader: cargarSolicitudSiNecesario,
      },
      {
        path: '/bandeja/:id/propuesta',
        element: <Propuesta ... />,
        loader: cargarSolicitudSiNecesario,
      },
      { path: '/propuestas',    element: <PropuestasLista ... /> },
      {
        path: '/propuestas/:id',
        element: <Propuesta ... />,
        loader: cargarPropuesta,
      },
      { path: '/tareas',        element: <Tareas ... /> },
    ],
  },
  { path: '*', element: <NotFound /> },
])
```

### `src/componentes/RutaProtegida.tsx`

Componente nuevo. Actúa como guard de autenticación **y** como layout que envuelve
todas las rutas privadas (contiene `Sidebar`, `Topbar` y el área de contenido).

```tsx
import { Navigate, Outlet, useLocation } from 'react-router'
import { useSesion } from '../contextos/SesionContext'   // cuando exista
// o leer sesion directamente de supabase si el contexto aún no está migrado

export function RutaProtegida() {
  const sesion = useSesionActual()   // undefined | null | Sesion
  const location = useLocation()

  if (sesion === undefined) return null   // aún resolviendo → sin flash
  if (sesion === null) {
    // Guarda la URL destino para el post-login redirect
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return (
    <div className="app">
      <Sidebar ... />
      <div className="main">
        <Topbar ... />
        <div className="scroll">
          <Outlet />              {/* pantalla hija activa */}
        </div>
      </div>
    </div>
  )
}
```

Tres estados de sesión manejados en un solo lugar:

| `sesion`    | Comportamiento                                              |
|-------------|-------------------------------------------------------------|
| `undefined` | Renderiza `null` (evita flash de login o de contenido)      |
| `null`      | `<Navigate to="/login" state={{ from: location }}>` replace |
| `Sesion`    | Renderiza `<Outlet />` (pantalla hija)                      |

### `src/componentes/Sidebar.tsx` — cambios

Reemplazar los `onClick → onIrA` por `<NavLink>` de React Router:

```tsx
// ANTES
<div className={'nav-item' + (pantalla === item.id ? ' active' : '')}
     onClick={() => onIrA(item.id)}>

// DESPUÉS
<NavLink
  to={RUTA_DE[item.id]}
  className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}
>
```

Mapa `id → ruta`:

```ts
const RUTA_DE: Record<string, string> = {
  inbox:          '/bandeja',
  propuestas:     '/propuestas',
  tareas:         '/tareas',
  configuracion:  '/configuracion',
  chat:           '/bandeja',   // el chat no es ítem de menú; chat apunta a bandeja
}
```

Props eliminadas de `Sidebar`: `pantalla`, `onIrA`.  
Props que permanecen: `empresas`, `empresaActiva`, `onCambiarEmpresa`, `conteoBandeja`,
`menuAbierto`.

### `src/componentes/Topbar.tsx` — cambios

`Topbar` usa `pantalla` solo para calcular el nombre de la pantalla activa
(`NOMBRE_PANTALLA[pantalla]`). Con el router, se reemplaza por `useMatch` o
`useLocation` para derivar el nombre desde la URL.

```tsx
// Antes: pantalla: Pantalla (prop)
// Después: leer la ruta activa del hook useLocation / useMatch
const location = useLocation()
const nombre = nombreDesdePath(location.pathname)
```

Props eliminadas de `Topbar`: `pantalla`.  
Props que permanecen: `empresa`, `onAbrirMenu`, `onCerrarSesion`.

### `src/componentes/Login.tsx` — cambios

Tras el login exitoso, redirigir a la URL original (si viene de un deep link protegido)
o al landing por defecto:

```tsx
import { useNavigate, useLocation } from 'react-router'

function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const desde = (location.state as { from?: Location })?.from?.pathname ?? '/configuracion'

  async function enviar(e: FormEvent) {
    // ... lógica de signInWithPassword existente ...
    if (!err) {
      navigate(desde, { replace: true })
    }
  }
}
```

La prop `onEntrar` puede mantenerse con firma `(correo: string) => void` para
compatibilidad con tests existentes (puede ser no-op o llamarse antes del navigate).

### Loaders de rutas con `:id`

Los loaders de React Router v7 son funciones `async` que se ejecutan antes de renderizar
la ruta. Se definen en `router.tsx` y se consumen con `useLoaderData()` en el componente.

```ts
// Loader de /bandeja/:id
async function cargarSolicitud({ params }: { params: { id: string } }) {
  const solicitud = await obtenerSolicitudPorId(params.id)
  if (!solicitud) throw new Response('No encontrada', { status: 404 })
  return solicitud
}
```

```ts
// Loader de /bandeja/:id/chat — solo carga si no hay contexto en memoria
async function cargarSolicitudSiNecesario({ params }: { params: { id: string } }) {
  // Si hay SolicitudContext con el mismo id, devuelve null (ya está en memoria)
  // Si no, fetch al backend
  const enContexto = getSolicitudContextual(params.id)   // helper de contexto
  if (enContexto) return null
  return await cargarSolicitud({ params })
}
```

Cuando el loader lanza `Response` con status 404, el `errorElement` del segmento de ruta
renderiza automáticamente el componente de error correspondiente.

### `src/componentes/RedireccionRaiz.tsx`

```tsx
import { Navigate } from 'react-router'
import { useSesionActual } from '../hooks/useSesionActual'

export function RedireccionRaiz() {
  const sesion = useSesionActual()
  if (sesion === undefined) return null
  return <Navigate to={sesion ? '/bandeja' : '/login'} replace />
}
```

### `src/componentes/NotFound.tsx`

```tsx
import { Link } from 'react-router'
export function NotFound() {
  return (
    <section className="screen">
      <div className="wrap">
        <h1 className="page">Página no encontrada</h1>
        <p>La URL no corresponde a ninguna pantalla de Dupla Comercial.</p>
        <Link to="/bandeja" className="btn primary">Volver a la bandeja</Link>
      </div>
    </section>
  )
}
```

---

## Data Models

### Eliminación de `Pantalla` de `tipos.ts`

El tipo `Pantalla` se elimina progresivamente conforme cada pantalla migra al router.
Durante la migración incremental puede coexistir (con un comentario de deprecación). Una
vez completada la migración:

```ts
// ELIMINAR de tipos.ts:
export type Pantalla = 'configuracion' | 'inbox' | 'detail' | 'chat' | ...
```

`Topbar`, `Sidebar` y `Configuracion` dejan de importar `Pantalla`. `App.tsx` deja de
declarar `useState<Pantalla>`.

### `location.state` para post-login redirect

React Router almacena el state en el historial del navegador. El contrato acordado:

```ts
// Al redirigir a /login desde RutaProtegida:
state: { from: location }   // location es el objeto Location de useLocation()

// En Login.tsx, al completar el login:
const desde = (location.state as { from?: { pathname: string } })?.from?.pathname
             ?? '/configuracion'
navigate(desde, { replace: true })
```

### Parámetros de ruta

| Ruta                        | Param  | Tipo     | Fuente                       |
|-----------------------------|--------|----------|------------------------------|
| `/bandeja/:id`              | `id`   | `string` | `solicitud.id` del backend   |
| `/bandeja/:id/chat`         | `id`   | `string` | heredado del padre           |
| `/bandeja/:id/propuesta`    | `id`   | `string` | heredado del padre           |
| `/propuestas/:id`           | `id`   | `string` | `propuesta.solicitudId`      |

---

## Correctness Properties

*Una propiedad es una característica o comportamiento que debe ser verdadero en todas las
ejecuciones válidas del sistema: una declaración formal de lo que el software debe hacer.
Las propiedades sirven como puente entre las especificaciones legibles por humanos y las
garantías de corrección verificables automáticamente.*

### Property 1: RutaProtegida respeta los tres estados de sesión

*Para cualquier* estado de sesión (`undefined`, `null`, o un objeto `Sesion` válido
con cualquier correo), el componente `RutaProtegida` debe: renderizar `null` si es
`undefined`, redirigir a `/login` si es `null`, y renderizar el `<Outlet>` (hijo) si
es un objeto válido.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

### Property 2: Preservación de URL de destino en redirect a login

*Para cualquier* ruta protegida `/r` del árbol del router, cuando un usuario sin sesión
navega directamente a `/r`, el redirect a `/login` debe incluir en `location.state.from`
la ruta original `/r`, de modo que tras el login exitoso el sistema pueda redirigir
de vuelta a `/r` en lugar del landing por defecto.

**Validates: Requirements 2.5, 9.2, 9.3**

### Property 3: Carga directa de solicitud por id

*Para cualquier* `id` de solicitud válido, al cargar directamente la URL
`/bandeja/:id` (sin estado previo en memoria), el loader de la ruta debe hacer fetch
al backend con ese `id` y el componente `DetalleSolicitud` debe renderizar los datos
devueltos. Si el `id` no existe, debe renderizarse el `errorElement` de esa ruta.

**Validates: Requirements 4.3, 4.4, 7.1**

### Property 4: NavLink del Sidebar refleja la ruta activa

*Para cualquier* ruta del sidebar (`/bandeja`, `/propuestas`, `/tareas`,
`/configuracion`), cuando el router está en esa ruta, el `<NavLink>` correspondiente
en `Sidebar` debe tener la clase CSS `active`, y los demás ítems del sidebar deben
carecer de esa clase.

**Validates: Requirements 6.1, 6.2, 6.3**

### Property 5: Login con sesión activa redirige a /bandeja

*Para cualquier* sesión válida (cualquier objeto `Sesion` con cualquier correo),
cuando la ruta `/login` se renderiza con esa sesión, el sistema debe redirigir a
`/bandeja` sin mostrar el formulario de login.

**Validates: Requirements 3.4**

### Property 6: Carga directa de propuesta por id

*Para cualquier* `id` de solicitud con propuesta existente, al cargar directamente
`/propuestas/:id`, el loader debe hacer fetch al backend con ese `id` y el componente
`Propuesta` debe renderizar los componentes y tareas devueltos. Si el `id` no
corresponde a ninguna propuesta, debe renderizarse el `errorElement`.

**Validates: Requirements 5.3, 5.4**

---

## Error Handling

### Errores de loader (id inexistente)

Cuando un loader lanza `Response` con `status: 404`, React Router renderiza
automáticamente el `errorElement` de esa ruta. Se definen dos componentes de error:

- `ErrorSolicitud` — para `/bandeja/:id` y sub-rutas. Muestra "Solicitud no encontrada"
  con enlace a `/bandeja`.
- `ErrorPropuesta` — para `/propuestas/:id`. Muestra "Propuesta no encontrada" con
  enlace a `/propuestas`.

Ambos usan `useRouteError()` de React Router para leer el status y mostrar un mensaje
apropiado:

```tsx
import { useRouteError, Link } from 'react-router'

export function ErrorSolicitud() {
  const error = useRouteError()
  const es404 = (error as Response)?.status === 404
  return (
    <section className="screen">
      <div className="wrap">
        <p className="empty">{es404 ? 'Solicitud no encontrada.' : 'Error al cargar la solicitud.'}</p>
        <Link to="/bandeja" className="btn primary">Volver a la bandeja</Link>
      </div>
    </section>
  )
}
```

### Errores de red en loaders

Si el loader falla por error de red (fetch rechazado), lanza la excepción al `errorElement`
de la ruta. El `errorElement` distingue entre `Response` (404 controlado) y `Error`
(fallo de red) para mostrar el mensaje adecuado.

### Estado de carga mientras el loader resuelve

React Router v7 ofrece `useNavigation().state === 'loading'` para detectar que un loader
está en progreso. Se puede usar en `RutaProtegida` para mostrar un indicador de carga
global sobre el área de contenido mientras se carga la solicitud o propuesta.

```tsx
// En RutaProtegida:
const navigation = useNavigation()
const cargando = navigation.state === 'loading'

return (
  <div className="main">
    <Topbar ... />
    <div className="scroll">
      {cargando && <CargandoLista mensaje="Cargando…" />}
      <Outlet />
    </div>
  </div>
)
```

### Ruta no encontrada (`*`)

Se usa `path: '*'` al final del árbol del router para capturar cualquier URL no definida
y renderizar `<NotFound />` con un enlace de vuelta a `/bandeja`.

---

## Testing Strategy

### Adaptación de `App.test.tsx`

Los tests existentes usan `render(<App />)` sin ningún router envolvente. Para que
sigan pasando con la nueva arquitectura:

**Opción A — `MemoryRouter` en el wrapper de test** (recomendada):  
`App.tsx` pasa a ser un componente de layout puro que espera estar dentro de un router.
En los tests, el wrapper de `@testing-library/react` incluye un `MemoryRouter`:

```tsx
// src/test/setup.ts o en cada test que lo necesite
import { MemoryRouter } from 'react-router'

function renderApp(initialPath = '/configuracion') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <App />
    </MemoryRouter>
  )
}
```

**Opción B — Separar `AppLayout` de `main.tsx`**:  
`router.tsx` mantiene el árbol de rutas completo. `App.tsx` se convierte en el layout
(`RutaProtegida` + sus hijos). Los tests de `App.test.tsx` usan `createMemoryRouter` +
`RouterProvider` en lugar de `render(<App />)` directamente. Es más fiel al árbol real
pero requiere más cambios en los tests.

La **Opción A** es la que minimiza cambios en `App.test.tsx` y respeta el criterio del
Req 8.4 ("sin mocks adicionales de React Router en los tests actuales").

Concretamente: `App.tsx` recibe una prop interna `_testRouter?: boolean` o el helper
`renderApp` de los tests inyecta el `MemoryRouter` como se muestra arriba. Los tests
que navegan (`await user.click(screen.getByText('Propuestas'))`) seguirán funcionando
porque `NavLink`/`useNavigate` respetan el `MemoryRouter` de contexto.

### Tests unitarios de `RutaProtegida`

```tsx
// src/componentes/RutaProtegida.test.tsx
it('con sesion=undefined, no renderiza nada', () => {
  renderConRouter(<RutaProtegida />, { sesion: undefined })
  expect(document.body).toBeEmptyDOMElement()
})

it('con sesion=null, redirige a /login', () => {
  const { ruta } = renderConRouter(<RutaProtegida />, { sesion: null })
  expect(ruta.pathname).toBe('/login')
})

it('con sesion válida, renderiza el contenido hijo', () => {
  renderConRouter(<RutaProtegida><p>Hola</p></RutaProtegida>, { sesion: { correo: 'x@x.cl' } })
  expect(screen.getByText('Hola')).toBeInTheDocument()
})
```

### Tests de navegación del Sidebar

```tsx
// src/componentes/Sidebar.test.tsx
it.each(['/bandeja', '/propuestas', '/tareas', '/configuracion'])(
  'el ítem correspondiente a %s tiene clase active cuando esa es la ruta',
  (ruta) => {
    renderEnRuta(<Sidebar ... />, ruta)
    const item = screen.getByRole('link', { name: nombreDelItem(ruta) })
    expect(item).toHaveClass('active')
    // El resto de ítems no tienen 'active'
  }
)
```

### Library de property-based testing

Se usa **[fast-check](https://fast-check.dev/)** (vitest/jest compatible), que es la
librería de PBT más establecida del ecosistema Node/TypeScript. Mínimo 100 iteraciones
por propiedad.

Instalación:
```bash
npm install --save-dev fast-check   # versión exacta: 3.x.x
```

```ts
// Ejemplo de property test para RutaProtegida
import fc from 'fast-check'

it('Property 1: RutaProtegida respeta los tres estados de sesión', () => {
  // Para cualquier correo válido, la sesión activa debe renderizar el hijo
  fc.assert(
    fc.property(
      fc.emailAddress(),
      (correo) => {
        const { container } = renderConRouter(
          <RutaProtegida />,
          { sesion: { correo } }
        )
        expect(container).not.toBeEmptyDOMElement()
        expect(locationActual()).not.toBe('/login')
      }
    ),
    { numRuns: 100 }
  )
})
// Feature: navegacion-router, Property 1: RutaProtegida respeta los tres estados de sesión
```

### Configuración SPA en Vite (dev)

Vite ya incluye soporte para SPA fallback. Se activa añadiendo `appType: 'spa'` (que es
el valor por defecto en Vite cuando hay un `index.html`). Para confirmar que el proxy no
intercepta las rutas del cliente, verificar que `vite.config.ts` **no** tenga un proxy
que capture rutas no-API (el proxy actual solo captura `/api`, lo que es correcto).

No es necesario ningún cambio adicional en `vite.config.ts` para el fallback en
desarrollo: Vite sirve `index.html` para cualquier ruta que no coincida con un asset o
con el proxy `/api`.

### Configuración SPA en Cloud Run (`produccion.py`)

El archivo `produccion.py` ya usa `StaticFiles(html=True)`, lo que activa el fallback:
FastAPI sirve `index.html` cuando no encuentra el archivo estático solicitado. Sin embargo,
esta configuración **solo funciona para rutas sin extensión de archivo**. Para rutas como
`/bandeja/abc123`, FastAPI busca `app/web/bandeja/abc123` como directorio y, si no existe,
cae al fallback de `StaticFiles`.

La conducta exacta depende de la versión de Starlette. Para garantizar el fallback en
**todas** las rutas de la SPA (incluyendo paths con varios segmentos), se agrega una ruta
catch-all explícita en `produccion.py`:

```python
# En produccion.py, DESPUÉS del mount de /api y ANTES del mount de /:
from fastapi.responses import FileResponse

SPA_INDEX = ESTATICOS / "index.html"

@raiz.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """Sirve index.html para cualquier ruta que no sea /api ni un asset estático."""
    # Los assets (*.js, *.css, *.png…) ya los sirve el StaticFiles mount.
    # Este endpoint solo captura rutas del router del cliente (sin extensión).
    return FileResponse(SPA_INDEX)
```

Orden de los mounts y rutas en `produccion.py`:

```
1. raiz.mount("/api", api)                   → API FastAPI
2. raiz.mount("/", StaticFiles(…, html=True)) → assets compilados (JS, CSS, etc.)
3. @raiz.get("/{full_path:path}")             → SPA fallback (catch-all)
```

> **Nota de orden:** FastAPI evalúa los mounts antes que las rutas declaradas. El mount
> `/api` captura primero; el mount `/` sirve assets; la ruta catch-all solo llega a
> ejecutarse cuando el archivo no existe en el directorio de estáticos. En la práctica,
> con `html=True` en `StaticFiles`, el fallback ya está implícito para la mayoría de
> casos. La ruta explícita es un seguro adicional para paths con múltiples segmentos.

### Resumen del plan de tests

| Área                         | Tipo de test           | Librería       |
|------------------------------|------------------------|----------------|
| `RutaProtegida` (3 estados)  | Property-based + Unit  | fast-check + vitest |
| Post-login redirect          | Property-based         | fast-check + vitest |
| Loader `/bandeja/:id`        | Property-based         | fast-check + vitest |
| NavLink activo en Sidebar    | Property-based         | fast-check + vitest |
| Login con sesión → /bandeja  | Property-based         | fast-check + vitest |
| Loader `/propuestas/:id`     | Property-based         | fast-check + vitest |
| Redirecciones de `/`         | Unit (example)         | vitest         |
| Ruta 404 (`*`)               | Unit (example)         | vitest         |
| Compatibilidad App.test.tsx  | Suite existente        | vitest         |
| SPA fallback Cloud Run       | Integration (manual)   | —              |
| Build sin errores            | CI (npm run build)     | —              |
