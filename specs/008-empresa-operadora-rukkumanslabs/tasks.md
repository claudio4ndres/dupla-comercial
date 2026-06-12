# Tareas 008 · Empresa operadora RukkumansLabs + usuario admin

Orden TDD: cada tarea escribe **el test primero (rojo)**, luego el mínimo cambio
(verde), luego refactor. Tareas pequeñas, commit por tarea (en español). Es una
feature de **solo datos**: no se crean tablas ni se cambian políticas RLS; se
**añaden filas** y se **prueba** que el aislamiento sigue intacto.

> Todos los tests corren contra **Supabase LOCAL** (pgTAP, `supabase test db`).
> **Sin servicios reales** (CA6): nada de Supabase de prod, ni SDK de Anthropic, ni
> Gmail/Drive/ClickUp. **El agente NO crea cuentas de Auth ni contraseñas** (CA7):
> eso es el **paso humano T4**, que **bloquea** a T5 y T6.
>
> **UUIDs (aclaración #2 de la spec):** empresa RukkumansLabs = `…d1`; su `auth.users`
> local = `…a2`. NO usar `…a1` (es el `auth.users.id` de Javier). Capsulab = `…c1`.

---

## Pruebas + seed local (las hace el agente, todo local)

- [ ] **T1 · Test de aislamiento RLS entre dos empresas (CA1/CA2/CA5).**
  - 🔴 `supabase/tests/rls_rukkumanslabs.test.sql` (pgTAP, mismo idioma que
    `rls_solicitudes.test.sql`): sembrar como `postgres` **dos** empresas —
    RukkumansLabs `00000000-0000-0000-0000-0000000000d1` y Capsulab `…c1` — con sus
    usuarios en `auth.users` + `usuarios` (RukkumansLabs `rol='admin'`, Capsulab
    `rol='gestor'`, **más** un segundo usuario `rol='gestor'` en RukkumansLabs para
    CA5) y **datos solo en Capsulab** (1 solicitud + 1 propuesta + 1 tarea). Actuar
    como cada usuario con `set local role authenticated` +
    `set_config('request.jwt.claims', json_build_object('sub', <uid>), true)`.
    Asertar: **CA1** admin de RukkumansLabs ve 0 en solicitudes/propuestas/tareas;
    **CA2** gestor de Capsulab NO ve la empresa `…d1` ni sus usuarios (count 0) y sí
    ve lo suyo; **CA5** admin y gestor de RukkumansLabs ven exactamente lo mismo.
    Verificar **rojo** primero (correr el test **antes** de que exista la fila
    sembrada / con una aserción que falle), para confirmar que prueba lo correcto.
  - 🟢 Ajustar la semilla del propio test hasta que las aserciones pasen. **No** se
    cambian políticas RLS ni `empresa_actual()` (solo se añaden filas de semilla).

- [ ] **T2 · Test de resolución de empresa del admin vía `empresa_actual()` (CA3).**
  - 🔴 En el mismo archivo pgTAP (bloque nuevo) o en uno aparte: actuando como el
    admin de RukkumansLabs (`sub` = su `auth.uid()`), asertar
    `empresa_actual() = '00000000-0000-0000-0000-0000000000d1'::uuid` (RukkumansLabs,
    **no** Capsulab) y que su espacio está **vacío** (count 0 en solicitudes /
    propuestas / tareas / miembros / integraciones). Verificar rojo.
  - 🟢 Apoyar la aserción con la semilla del test; sin tocar la función.

- [ ] **T3 · Seed local de RukkumansLabs (empresa + auth local + usuario).**
  - 🔴 Test/manual reproducible: tras `supabase db reset`, debe existir
    `empresas` con `nombre='RukkumansLabs'` (`…d1`) y un `usuarios` con
    `correo='cafigueroa@gmail.com'`, `rol='admin'`, `empresa_id='…d1'`. (La prueba
    formal de aislamiento ya la dan T1/T2; aquí basta una verificación de presencia.)
  - 🟢 Agregar a `supabase/seed.sql` un bloque "Empresa operadora RukkumansLabs":
    (1) `insert into empresas` (`…d1`, `RukkumansLabs`, `#F04E37`, `plan='operador'`);
    (2) `insert into auth.users` para `cafigueroa@gmail.com` con UUID **local** propio
    `00000000-0000-0000-0000-0000000000a2` siguiendo el patrón del bloque de Javier
    (`crypt('<clave-dev>', gen_salt('bf'))`, `email_confirmed_at=now()`, tokens en
    `''`); (3) `insert into usuarios` (`…a2`, `…d1`, `cafigueroa@gmail.com`, `'admin'`).
    Dejar un **comentario** aclarando que la empresa RukkumansLabs es `…d1` y que la
    serie `a` (`…a1` Javier, `…a2` admin local) es para `auth.users`. Cuenta y clave
    del seed son **de juguete, solo dev** (no es la credencial real de prod). Verde:
    `supabase db reset` + `supabase test db` pasan **sin regresiones** (CA4: Capsulab
    intacto; la suite existente sigue verde).

## Provisión a producción (cruza la frontera humano/agente)

- [ ] **T4 · 🧑 PASO HUMANO (BLOQUEANTE) — crear la cuenta de Auth real.** La
  **persona** crea `cafigueroa@gmail.com` en el **Supabase Auth de producción**
  (dashboard → Authentication → Add user / invitación) y define su contraseña; luego
  **anota el UID** que Supabase asigna. **El agente NO ejecuta este paso** (CA7: crear
  cuentas y credenciales es acción del usuario). **Bloquea T5 y T6.** Entregable de la
  spec: estos pasos quedan documentados aquí como guía (no hay test automatizado).

- [ ] **T5 · 🔒 Bloqueada por T4 — insertar la fila en `usuarios` con el UID real.**
  - Preparar `supabase/snippets/008_rukkumanslabs_prod.sql`: `INSERT` idempotentes
    (`on conflict (id) do nothing`) de la **empresa** (`…d1`, RukkumansLabs) y del
    **usuario** (`id = :uid_real`, `empresa_id='…d1'`, `correo='cafigueroa@gmail.com'`,
    `rol='admin'`). El snippet se versiona con **placeholder** `:uid_real`: **no** se
    commitea el UID real ni contraseña alguna (sin secretos en el repo). El `INSERT`
    de `usuarios` solo es válido **una vez** que exista la cuenta de Auth (FK a
    `auth.users`); por eso depende de T4.

- [ ] **T6 · 🔒 Bloqueada por T4/T5 — aplicar a producción y verificar aislamiento en
  vivo.** Con el UID real provisto en T4, ejecutar el snippet de T5 contra la base de
  **prod** (como owner que bypassa RLS). Verificación operacional manual: con el
  admin `cafigueroa@gmail.com` autenticado, su bandeja arranca **vacía** y **no** ve
  datos de Capsulab; Capsulab sigue **intacto** (CA4). Es un **chequeo operacional**,
  no un test de la suite (la garantía automatizada de aislamiento ya está en T1/T2
  contra local, CA6).

---

Leyenda: 🧑 = paso humano · 🔒 = bloqueada por el paso humano.

Resumen de cobertura: **CA1/CA2/CA5** → T1 · **CA3** → T2 · **CA4** → T3 (sin
regresiones) + T6 (en vivo) · **CA6** → todos los tests son pgTAP local sin servicios
reales · **CA7** → T4 (humano) bloquea T5/T6.

Siguiente paso: `/implementar 008`.
