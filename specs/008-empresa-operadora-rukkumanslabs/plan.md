# Plan 008 · Empresa operadora RukkumansLabs + usuario admin

- **Spec:** [spec.md](./spec.md) (estado: borrador)
- **Tipo:** datos (multi-tenant) + guía operativa. **No** toca pantallas del flujo
  Tipo 1 / Tipo 2 ni el backend de negocio.
- **Decisión clave:** es una feature de **solo datos**. NO se crean tablas, NO se
  cambian políticas RLS, NO se toca `empresa_actual()`. Se **añaden filas**: una
  empresa nueva (`RukkumansLabs`) y un usuario admin vinculado. La barrera
  multi-tenant ya existe (migración 0001); el valor de esta spec es **demostrar con
  un test** que esa barrera sigue intacta con DOS empresas reales conviviendo, y
  dejar la **guía** para que el humano provisione la cuenta de Auth.

> El agente NO crea cuentas de Supabase Auth ni contraseñas (CA7). Eso lo hace la
> persona. El agente solo: (a) escribe el test de aislamiento, (b) siembra la
> empresa en local, (c) inserta la fila en `usuarios` con el UID **ya existente** y
> (d) entrega los pasos manuales.

---

## 1. Datos

### 1.1 Nueva empresa (tabla `empresas`)
| columna | valor |
|---|---|
| `id` | `00000000-0000-0000-0000-0000000000d1` (UUID legible, aclaración #2 de la spec) |
| `nombre` | `RukkumansLabs` |
| `color_marca` | `#F04E37` (naranja base del producto, aclaración #3) |
| `plan` | `operador` (la distingue de los clientes `piloto`; es solo etiqueta, no habilita nada) |

### 1.2 Nuevo usuario admin (tabla `usuarios`)
| columna | valor |
|---|---|
| `id` | **UID real** de `auth.users` (lo genera Supabase al crear la cuenta; lo provee el humano) |
| `empresa_id` | `00000000-0000-0000-0000-0000000000d1` (RukkumansLabs) |
| `correo` | `cafigueroa@gmail.com` |
| `rol` | `admin` |

`usuarios.id` es **FK a `auth.users(id)`** (ver 0001): por eso la fila en `usuarios`
**no puede** insertarse antes de que exista la cuenta de Auth. El insert queda
**bloqueado** por el paso humano (CA7).

### 1.3 Convención de UUIDs (footgun resuelto)
El seed usa `…0000a1` como **`auth.users.id` de Javier** (Capsulab) —
`supabase/seed.sql:36`. Para **no** repetir ese literal en otro rol, la empresa
RukkumansLabs usa **`…0000d1`** (no `…a1`). Convención del seed, ya consistente:
- **Empresas** en letras distintas: Capsulab `…c1`, RukkumansLabs `…d1`.
- **Usuarios de Auth** en la serie `a`: Javier `…a1`, admin local de RukkumansLabs `…a2`.

Así ningún literal cumple dos papeles y se lee sin ambigüedad. La empresa Capsulab
sigue siendo `…0000c1` (intacta, CA4).

### 1.4 Lo que NO se hace
- **Sin migración nueva**: el esquema (tablas, RLS, `empresa_actual()`) ya soporta
  N empresas. Agregar un tenant es insertar filas, no migrar.
- **Sin casilla / integraciones** para RukkumansLabs: es operador sin correo propio
  por ahora (aclaración #1). Su espacio arranca **vacío**: sin solicitudes, sin
  propuestas, sin tareas, sin `integraciones`, sin `miembros`.
- **Sin poderes de `admin`**: hoy `admin` y `gestor` tienen el **mismo** acceso,
  acotado a su empresa por RLS (CA5). Super-admin cross-tenant y gestión de
  usuarios quedan **fuera de alcance** (otra spec).

---

## 2. Enfoque del seed (local) y de producción

### 2.1 Seed local — para `supabase db reset`
- Archivo: `supabase/seed.sql` (el mismo que ya siembra Capsulab; lo corre
  `supabase db reset` como `postgres`, superusuario **no** sujeto a RLS).
- Se agrega un bloque "**Empresa operadora RukkumansLabs**" que inserta:
  1. la fila en `empresas` (1.1), y
  2. una cuenta **local de Auth** en `auth.users` para `cafigueroa@gmail.com`
     siguiendo el **mismo patrón** que el bloque de Javier (`seed.sql:23-44`):
     `encrypted_password = crypt('<clave-dev>', gen_salt('bf'))`,
     `email_confirmed_at = now()`, y los tokens GoTrue en `''` (no `NULL`, o el
     login revienta con 500), y
  3. la fila en `usuarios` (1.2) apuntando a ese `auth.users.id` local.
- **Importante (CA7):** esta cuenta de `auth.users` del seed es **solo para
  desarrollo local** (igual que la de Javier, contraseña de juguete).
  **No** es la cuenta real de producción ni una credencial real: es el "puente de
  auth" para que `signInWithPassword` funcione en la demo local. La cuenta **real**
  de `cafigueroa@gmail.com` en el Supabase de prod la crea el **humano** (no el
  agente, no el seed de prod). El UID local del seed y el UID real de prod **no**
  tienen por qué coincidir, y no importa: el seed local nunca toca prod.
- UUID del `auth.users` local: `00000000-0000-0000-0000-0000000000a2` (serie `a`,
  distinto de `…a1` de Javier). La empresa es `…d1`. La fila de `usuarios` local usa
  ese mismo `…a2` como `id` y `…d1` como `empresa_id`.

### 2.2 Producción
- En prod **no** se ejecuta `seed.sql`. La provisión es manual y en dos mitades:
  - **Mitad humana (Auth):** la persona crea la cuenta `cafigueroa@gmail.com` en el
    Supabase Auth de prod (dashboard → Authentication → Add user, o invitación) y
    define la contraseña. Anota el **UID** que Supabase asigna.
  - **Mitad del agente (datos):** con ese UID a la vista, se ejecutan dos `INSERT`
    idempotentes contra la base de prod (vía `psql`/SQL editor, como `postgres`/owner
    que **bypassa RLS**): la empresa (1.1) y el usuario (1.2). Se versiona el SQL en
    `supabase/snippets/008_rukkumanslabs_prod.sql` (plantilla con un placeholder
    `:uid_real` para no commitear el UID hasta que exista).
- **Sin secretos en el repo:** el snippet de prod **no** lleva contraseñas ni el UID
  real hasta que el humano lo provea; solo el placeholder. Ninguna credencial real
  entra al repositorio (Definición de Terminado).

---

## 3. Pasos de provisión (orden y quién hace qué)

| # | Paso | Quién | Bloquea a |
|---|---|---|---|
| 1 | Escribir el test de aislamiento RLS de 2 empresas (rojo) | **Agente** | — |
| 2 | Escribir el test de resolución vía `empresa_actual()` para el admin | **Agente** | — |
| 3 | Sembrar RukkumansLabs en `seed.sql` (empresa + auth.users local + usuario local) | **Agente** | — |
| 4 | Verde local: `supabase db reset` + `supabase test db` pasan | **Agente** | — |
| 5 | **Crear la cuenta de Auth real `cafigueroa@gmail.com` en prod** y anotar su **UID** | **Humano** | 6 |
| 6 | Insertar empresa + usuario en **prod** con el UID real; verificar aislamiento en vivo | **Agente** (con el UID del paso 5) | — |

> El paso 5 es la **frontera humano/agente** y es **no negociable** (CA7): el agente
> nunca crea cuentas ni contraseñas. Hasta que el humano entregue el UID, el paso 6
> está **bloqueado**.

---

## 4. Estrategia de pruebas (TDD)

Todo determinista y **sin servicios reales** (CA6): la RLS se prueba contra una
**DB de Supabase LOCAL** con pgTAP (`supabase test db`); **nada** de Supabase de
prod, **ni** SDK de Anthropic, **ni** Gmail/Drive/ClickUp. No hay LLM ni red en
estos tests.

### 4.1 Aislamiento RLS con DOS empresas reales — `supabase/tests/rls_rukkumanslabs.test.sql`
Mismo idioma pgTAP que `rls_solicitudes.test.sql` / `rls_conversaciones.test.sql`:
sembrar como `postgres` (no sujeto a RLS), luego actuar como cada usuario con
`set local role authenticated` + `set_config('request.jwt.claims', json_build_object('sub', <uid>), true)`
para que `empresa_actual()` resuelva por `auth.uid()`.

- **Semilla:** las **dos** empresas (RukkumansLabs `…d1` y Capsulab `…c1`), sus dos
  usuarios en `auth.users` + `usuarios` (el de RukkumansLabs con `rol='admin'`, el de
  Capsulab con `rol='gestor'`), y **datos solo en Capsulab** (una `solicitud`, su
  `propuesta`, una `tarea`) para tener algo que NO deba filtrarse.
- **CA1 (ida):** actuando como el **admin de RukkumansLabs**, `count(*)` sobre
  `solicitudes`, `propuestas` y `tareas` = **0** (no ve nada de Capsulab).
- **CA2 (vuelta):** actuando como el **gestor de Capsulab**, NO ve la empresa
  RukkumansLabs (`select count(*) from empresas where id = '…d1'` = 0) ni su usuario
  (`select count(*) from usuarios where empresa_id = '…d1'` = 0); y sí ve sus propias
  filas de Capsulab (sanity: `solicitudes` = 1).
- **CA5 (admin = gestor):** sembrar **un segundo usuario** en RukkumansLabs con
  `rol='gestor'`; comprobar que admin y gestor de la **misma** empresa ven
  **exactamente lo mismo** (mismos `count(*)` sobre las tablas de su empresa). El
  `rol='admin'` no abre nada extra ni cross-tenant.

### 4.2 Resolución de empresa vía `empresa_actual()` — CA3
Puede vivir en el mismo archivo pgTAP (otro bloque) o en uno aparte:
- Actuando como el admin (`sub` = su `auth.uid()`), `select empresa_actual()` =
  `'00000000-0000-0000-0000-0000000000d1'::uuid` (RukkumansLabs), **no** la de
  Capsulab. Esto valida que el login del admin cae en su espacio (vacío).
- Sanity de "espacio vacío": como el admin, `count(*)` de `solicitudes` /
  `propuestas` / `tareas` / `miembros` / `integraciones` = 0.

### 4.3 CA4 (Capsulab intacto)
Cubierto **implícitamente**: el test no modifica filas de Capsulab y la suite
existente (`rls_solicitudes`, `rls_conversaciones`, `rls_integraciones`,
`rls_catalogo`, `conexion_correo`) debe seguir **verde** tras el seed nuevo. Un
`supabase db reset` + `supabase test db` sin regresiones es la evidencia.

### 4.4 Fuera de estos tests
- No se prueba el login del frontend ni el JWT (eso es de la spec 006).
- No se prueba "super-admin cross-tenant" — está fuera de alcance.
- No se llama a prod en ningún test (la verificación en vivo del paso 6 es un
  **chequeo operacional manual**, no un test de la suite).

---

## 5. Riesgos / notas

- **FK a `auth.users` ⇒ orden obligado:** la fila de `usuarios` (local o prod) falla
  si la cuenta de Auth no existe antes. En local lo resuelve el propio seed (crea el
  `auth.users` antes); en prod lo resuelve el paso humano (5 antes que 6).
- **Idempotencia en prod:** los `INSERT` de prod deben tolerar reejecución (p. ej.
  `on conflict (id) do nothing`) para no romper si el snippet se corre dos veces.
- **Sin debilitar la RLS:** no se altera `empresa_actual()` ni las políticas; el
  test 4.1 es justamente la prueba de regresión de que añadir el tenant no abrió una
  fuga. Si CA1/CA2 fallaran, la barrera estaría rota y la feature no está terminada.
- **Definición de Terminado (CLAUDE.md §7):** spec + plan + tareas presentes; tests
  de aislamiento/resolución existen **antes** del seed y pasan; RLS verificada con
  dos empresas; sin secretos ni UID real en el repo hasta el paso 6; commits en
  español.
