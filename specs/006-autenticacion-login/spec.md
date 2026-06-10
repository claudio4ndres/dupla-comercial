# Spec 006 · Autenticación real (Login con Supabase Auth)

- **Estado:** borrador
- **Tipo:** full-stack (frontend + backend + datos)
- **Relacionada con:** multi-tenant · todas las features (bloquea acceso sin sesión real)

---

## 1. Problema y por qué

El login actual es un **mock**: cualquier correo y contraseña dejan entrar a la app.
No hay sesión real de Supabase, el `empresa_id` no viene del token, y la RLS de
Postgres nunca llega a filtrarse por usuario (el frontend envía un bearer vacío o
inventado). Esto significa que **cualquier persona con la URL puede ver y operar**
los datos de cualquier empresa.

Para salir del piloto y onboardear más empresas, necesitamos autenticación real:
`signInWithPassword` de Supabase Auth en el front, JWT válido en el backend, y el
`empresa_id` derivado del token para que las políticas RLS funcionen de verdad.

---

## 2. Usuarios y contexto

- **Gestor de proyecto (GP):** la persona que opera la app cada día. Entra con su
  correo y contraseña al arrancar la jornada. Si el navegador mantiene la sesión
  activa (cookie / localStorage), no debería tener que volver a loguearse.
- **Admin de empresa:** mismo flujo de login; la diferencia de rol (`admin` vs
  `gestor`) se gestiona en otra spec (invitaciones / gestión de usuarios).
- **Contexto de uso:** pantalla de login es la primera pantalla que ve quien no
  tiene sesión. Tras entrar, el usuario llega directo a la bandeja de su empresa.

---

## 3. Alcance

**Incluye:**
- Conectar el componente `Login.tsx` a `supabase.auth.signInWithPassword`.
- Persistir la sesión de Supabase (su cliente ya lo hace en `localStorage`).
- Leer el JWT de la sesión activa y enviarlo como `Authorization: Bearer <token>` en
  todas las llamadas al backend (módulos `api/`).
- El backend (`obtener_empresa_actual` ya implementado) verifica el JWT y extrae el
  `empresa_id`. Sin cambios en el backend salvo confirmar que funciona end-to-end.
- Logout: botón en la `Topbar` o menú de perfil que llama a
  `supabase.auth.signOut` y devuelve al login.
- Reemplazo del mock de `Sesion` en `App.tsx`: la sesión pasa a venir de Supabase.
- El `empresa_id` (UUID) pasa a vivir en la sesión real; la selección de empresa
  del `Sidebar` queda reservada solo para cuentas con más de una empresa (fuera de
  alcance por ahora, pero no se rompe).
- Crear cliente Supabase en el frontend (`supabase/client.ts`), con las variables
  de entorno ya disponibles en `.env.local`.
- Tests unitarios del componente `Login` actualizados para el flujo real (mock de
  `supabase.auth`).

**No incluye (fuera de alcance):**
- Recuperación de contraseña / "Olvidé mi contraseña".
- Registro de nuevas empresas o usuarios (onboarding).
- OAuth / login con Google para la app (distinto al OAuth de Gmail para la bandeja).
- Gestión de roles (`gestor` vs `admin`) ni permisos diferenciados por rol.
- Cambio de contraseña desde dentro de la app.
- Multi-empresa por usuario (un usuario con acceso a varias empresas).

---

## 4. Criterios de aceptación (de aquí salen los tests)

- **CA1** — Dado que el usuario ingresa un correo y contraseña correctos,
  Cuando hace clic en "Entrar",
  Entonces `supabase.auth.signInWithPassword` se llama con esas credenciales, la
  sesión queda activa y el usuario ve la bandeja de su empresa.

- **CA2** — Dado que el usuario ingresa credenciales incorrectas,
  Cuando hace clic en "Entrar",
  Entonces se muestra un mensaje de error ("Correo o contraseña incorrectos") y el
  usuario no entra a la app.

- **CA3** — Dado que el usuario tiene una sesión activa en el navegador (recargó la
  página o volvió al día siguiente),
  Cuando abre la app,
  Entonces no ve el login: va directo a la bandeja sin volver a pedir credenciales.

- **CA4** — Dado que el usuario está en la app y cierra sesión,
  Cuando hace clic en "Cerrar sesión",
  Entonces se llama `supabase.auth.signOut`, la sesión se borra, y vuelve al login.

- **CA5** — Dado que el usuario tiene sesión activa,
  Cuando el frontend llama a cualquier endpoint del backend,
  Entonces el JWT de Supabase viaja en el header `Authorization: Bearer <token>` y el
  backend puede verificarlo con `obtener_empresa_actual` sin lanzar 401.

- **CA6** — Dado que el JWT expira o es inválido (manipulado),
  Cuando el backend intenta verificarlo,
  Entonces responde `401` y el frontend redirige al login (no queda en una pantalla
  rota).

- **CA7** — Dado que el usuario no ingresa correo o la contraseña está vacía,
  Cuando intenta enviar el formulario,
  Entonces el botón "Entrar" permanece deshabilitado (validación local, sin llamar
  a Supabase).

---

## 5. Consideraciones multi-tenant

- La tabla `usuarios` vincula `auth.users.id` → `empresa_id`. Cada usuario pertenece a
  **una sola empresa**; el token JWT de Supabase trae ese `empresa_id` como claim
  (requiere un *custom access token hook* en Supabase, que ya existe en la lógica de
  `obtener_empresa_actual`).
- La empresa que ve el usuario en el `Sidebar` debe coincidir con el `empresa_id` del
  token, no con el mock de `EMPRESAS[0]`. El selector de empresa en el `Sidebar`
  queda deshabilitado/oculto para usuarios de una sola empresa.
- La RLS garantiza que aunque el frontend enviara un token de otra empresa, Postgres
  filtraría sus datos. El backend es una segunda barrera, no la única.

---

## 6. Decisiones técnicas tomadas

- **Cliente Supabase en el frontend:** un singleton en `apps/web/src/supabase/cliente.ts`
  construido con `createClient(VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY)`. Las vars
  ya existen en `.env.local`.
- **Flujo de sesión en `App.tsx`:** reemplazar `leerSesionGuardada` / `guardarSesion`
  (localStorage manual) por `supabase.auth.getSession()` al montar y
  `supabase.auth.onAuthStateChange` para actualizaciones reactivas.
- **Bearer token en las llamadas de API:** los módulos bajo `src/api/` deben leer el
  token activo con `supabase.auth.getSession()` antes de cada fetch e inyectarlo en el
  header. O bien, un wrapper de `fetch` centralizado que lo haga.
- **No se agrega una variable de entorno nueva:** `VITE_SUPABASE_URL` y
  `VITE_SUPABASE_ANON_KEY` ya están en `.env.local`.

---

## 7. Aclaraciones pendientes

- [NECESITA ACLARACIÓN: ¿Existe el *custom access token hook* de Supabase configurado
  en el proyecto local/prod para que el `empresa_id` llegue como claim del JWT?
  `obtener_empresa_actual` en el backend lo espera, pero si no está configurado el
  hook, el token no lo traerá y todos los endpoints devolverán 401.]
- [NECESITA ACLARACIÓN: ¿Los usuarios de prueba (ej: `gestor@capsulab.cl`) ya están
  creados en Supabase Auth local (tabla `auth.users`) y en la tabla `usuarios` con su
  `empresa_id`? Si no, hay que crearlos en `supabase/seed.sql` antes de implementar.]
