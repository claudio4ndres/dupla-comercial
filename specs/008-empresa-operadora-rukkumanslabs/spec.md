# Spec 008 · Empresa operadora RukkumansLabs + usuario admin

- **Estado:** borrador
- **Tipo:** datos (multi-tenant) + guía operativa
- **Relacionada con:** multi-tenant / autenticación (spec 006) / onboarding

## 1. Problema y por qué

Hoy una sola cuenta de Gmail personal (`cafigueroaarias@gmail.com`) cumple **dos
papeles a la vez**: es la **casilla** que el poller lee para Capsulab y, en la
práctica, la identidad con la que se opera la app. No existe una identidad de
**operador** separada del **cliente**. Esto enreda las pruebas y mezcla
conceptos: ¿quién es el dueño de la herramienta vs. quién es el cliente piloto?

La herramienta la opera **RukkumansLabs** (nosotros). **Capsulab** es el **cliente**
piloto. Separar ambos en tenants distintos deja el modelo limpio: el operador tiene
su propio espacio aislado y el cliente conserva el suyo intacto. Es la base correcta
para sumar más clientes (Espiga, etc.) sin volver a enredar identidades.

## 2. Usuarios y contexto

- **Admin de RukkumansLabs** (`cafigueroa@gmail.com`): la persona operadora (GP/dueño).
  Inicia sesión en la app y cae en el espacio de **RukkumansLabs** (que arranca vacío).
- **Gestor de Capsulab** (`javier@capsulab.cl`, ya existe, rol `gestor`): el cliente.
  No se toca; sigue viendo su bandeja, propuestas y tareas como hasta ahora.
- Momento del flujo: **antes** del flujo operativo (provisión de cuentas). No cambia
  ninguna pantalla del flujo Tipo 1 / Tipo 2.

## 3. Alcance

**Incluye:**
- Nueva **empresa** (tenant) `RukkumansLabs` en la tabla `empresas`.
- Nuevo **usuario** admin (`cafigueroa@gmail.com`, `rol='admin'`) vinculado a esa
  empresa en la tabla `usuarios` (referencia a `auth.users`).
- **Prueba de aislamiento RLS** entre RukkumansLabs y Capsulab (ambos sentidos).
- Aplicarlo al **seed local** (para `supabase db reset`) y a **producción**.
- **Guía** para que el humano cree la cuenta de Supabase Auth (paso suyo).

**No incluye (fuera de alcance):**
- **Super-admin cross-tenant**: que RukkumansLabs vea/administre a Capsulab (o a
  varios clientes) desde un mismo login. Es feature futura y toca la RLS a fondo.
- **Poderes especiales del rol `admin`**: hoy `admin` es solo etiqueta (mismo
  acceso que `gestor`, acotado a su empresa). Gestión de usuarios, invitaciones,
  permisos diferenciados → otra spec.
- **Crear la cuenta de Supabase Auth / contraseñas**: lo hace el **humano**, no el
  agente (creación de cuentas y credenciales es acción del usuario).
- Conectar integraciones (Gmail/Drive/ClickUp) de RukkumansLabs — ver aclaración.

## 4. Criterios de aceptación (de aquí salen los tests)

- **CA1 (aislamiento RLS, ida)** — Dado un admin autenticado de **RukkumansLabs** y
  datos existentes de **Capsulab** (solicitudes, propuestas, tareas), Cuando consulta
  esas tablas, Entonces **no ve ninguna fila de Capsulab**.
- **CA2 (aislamiento RLS, vuelta)** — Dado el gestor de **Capsulab**, Cuando consulta
  sus tablas, Entonces **no ve ninguna fila de RukkumansLabs** (ni la empresa ni sus
  usuarios).
- **CA3 (resolución de empresa)** — Dado el login `cafigueroa@gmail.com` vinculado en
  `usuarios` con `rol='admin'` y `empresa_id` = RukkumansLabs, Cuando inicia sesión,
  Entonces `empresa_actual()` (y el backend) resuelven su empresa como **RukkumansLabs**
  y la app muestra ese espacio (vacío, sin datos de otros tenants).
- **CA4 (Capsulab intacto)** — Dado `javier@capsulab.cl` y la casilla
  `cafigueroaarias@gmail.com`, Cuando se crea RukkumansLabs, Entonces Capsulab conserva
  **sin cambios** su usuario, su casilla, sus correos, propuestas y tareas.
- **CA5 (admin = gestor en acceso)** — Dado un admin y un gestor de la **misma**
  empresa, Cuando ambos operan, Entonces tienen **el mismo** acceso a los datos de su
  empresa (el rol `admin` no habilita nada cross-tenant ni gestión de usuarios).
- **CA6 (tests sin servicios reales — obligatorio)** — Dado los tests de aislamiento y
  de resolución de empresa, Cuando corren, Entonces **no llaman a Supabase real ni al
  SDK de Anthropic ni a Gmail/Drive/ClickUp**: la RLS se prueba contra una **DB de
  Supabase local** y cualquier API externa va **mockeada**.
- **CA7 (cuenta de Auth la crea el humano)** — Dado que crear cuentas/credenciales es
  acción del usuario, Cuando se implementa, Entonces el agente **no** crea la cuenta de
  Supabase Auth; solo prepara la empresa, el vínculo en `usuarios` (con el UID real ya
  existente) y la RLS, y entrega la guía de los pasos manuales.

## 5. Consideraciones multi-tenant

Es una feature **netamente multi-tenant**. La RLS (vigente desde la migración 0001)
debe garantizar que **RukkumansLabs nunca vea datos de Capsulab y viceversa**, vía
`empresa_actual()` = `empresa_id` de la fila del usuario en `usuarios`. Agregar el
nuevo tenant y su admin **no debe debilitar** esa función ni las políticas existentes.
La nueva empresa y el nuevo usuario solo añaden filas; no se cambian políticas. El
test de aislamiento (CA1/CA2) es la prueba de que la barrera sigue intacta con dos
empresas reales conviviendo.

## 6. Aclaraciones (resueltas)

- **#1 RESUELTA** — Cada **cliente** (Capsulab y futuros) conecta su **propio** correo y
  tiene su **propio ecosistema** (Gmail/Drive/ClickUp vía `integraciones` con su
  `empresa_id`); la RLS aísla cada ecosistema. **RukkumansLabs** es el **operador**: por
  ahora **sin casilla propia** (si luego la necesita, usa el mismo mecanismo por-tenant).
  El test de aislamiento (CA1/CA2) es justamente la garantía de "cada cliente, su
  ecosistema aislado".
- **#2 RESUELTA** — UUID de la **empresa**: `00000000-0000-0000-0000-0000000000d1`
  (legible, serie de empresas como Capsulab `…c1`). **NO usar `…a1`**: ese literal ya es
  el `auth.users.id` de Javier en el seed (`seed.sql:36`) y repetirlo confunde. Convención:
  los usuarios de Auth van en la serie `a` (Javier `…a1`, admin local de RukkumansLabs `…a2`);
  las empresas en letras distintas (Capsulab `…c1`, RukkumansLabs `…d1`).
- **#3 RESUELTA** — `color_marca`: naranja base del producto por ahora.
