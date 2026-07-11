# Spec 016 · Migración del front a React Router v7 (rutas reales)

- **Estado:** aprobada
- **Tipo:** frontend
- **Relacionada con:** navegación por `pantalla` (SesionContext), deep-links y refresh

## 1. Problema y por qué

Hoy la navegación del front es un "router por estado": `pantalla` vive en
`SesionContext` y `App.tsx` hace un switch. El hook `useSincronizarRuta`
sincroniza pantalla↔URL **solo a nivel raíz** (`/bandeja`, `/propuestas`…), así
que un **deep-link o un refresh en el detalle, el chat o una propuesta pierde
el estado**: la URL cae al fallback y el usuario vuelve a la bandeja con la
conversación "desaparecida". Además `src/router.tsx` era un cascarón con props
vacías que nunca se conectó.

## 2. Usuarios y contexto

El usuario de la agencia comparte links ("mira esta propuesta"), recarga la
pestaña en medio de un chat con Javo o usa el botón atrás. Todo eso debe
llevarlo a la pantalla correcta **con sus datos rehidratados** desde el backend.

## 3. Alcance

**Incluye:**
- Rutas reales con React Router v7: `/` (redirección según sesión),
  `/configuracion`, `/bandeja`, `/bandeja/:id`, `/bandeja/:id/chat`,
  `/propuestas`, `/propuestas/:id`, `/tareas` y `*` (NotFound).
- Providers (Sesion > Solicitud > Bandeja) **dentro** del router para poder usar
  `useNavigate`/`useLocation` en los contextos.
- `irA(p, id?)` sobre `useNavigate`; `pantalla` DERIVADA de la URL (se mantiene
  el tipo `Pantalla` y la API pública para Sidebar/Topbar y tests).
- Rehidratación en refresh/deep-link: solicitud (`/bandeja/:id`), historial +
  cotización en curso (`/bandeja/:id/chat`, vía `rehidratarChat`), propuesta
  (`/propuestas/:id`, vía `obtenerPropuesta`).
- Descomposición de `App.tsx` en Layout (con `<Outlet/>`) + un contenedor por
  ruta que cablea contextos → props de las pantallas presentacionales.
- Eliminación de `useSincronizarRuta` y reconstrucción de `router.tsx`.

**No incluye (fuera de alcance):**
- Cambios en las pantallas presentacionales (Bandeja, Chat, Propuesta…): sus
  props y tests quedan intactos.
- Loaders/actions de React Router (se usa useEffect + contextos, menos invasivo).
- Backend (`apps/api`): sin cambios.

## 4. Criterios de aceptación (de aquí salen los tests)

- **CA1** — Dado un deep-link a `/bandeja/:id`, Cuando la solicitud no está en
  memoria, Entonces se rehidrata (lista del contexto o `obtenerSolicitudes()`)
  y se muestra el detalle; si el id no existe, se ve NotFound.
- **CA2** — Dado un deep-link a `/bandeja/:id/chat`, Cuando el hilo está vacío,
  Entonces se repuebla con `obtenerHistorialConversacion` +
  `obtenerCotizacionEnCurso` (los mensajes previos quedan visibles).
- **CA3** — Dado un clic en una solicitud de la bandeja, Entonces la URL pasa a
  `/bandeja/:id` y se ve el detalle (navegación in-app crea historial real).
- **CA4** — Dado un deep-link a `/propuestas/:id` sin componentes en memoria,
  Entonces se repuebla vía `obtenerPropuesta(id)` y se ve la propuesta.
- **CA5** — Dado que NO hay sesión, Cuando se entra a cualquier ruta protegida,
  Entonces se muestra el Login (y al entrar se conserva la URL destino).
- **CA6** — La suite existente (170 tests) sigue verde: `pantalla` sigue
  reflejando la ruta activa y los flujos de App no cambian de comportamiento.
