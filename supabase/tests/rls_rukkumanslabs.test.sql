-- =====================================================================
-- Spec 008 · Empresa operadora RukkumansLabs + usuario admin
-- T1 (CA1/CA2/CA5) + T2 (CA3) · Prueba de aislamiento RLS con DOS empresas
-- REALES conviviendo: RukkumansLabs (operador) y Capsulab (cliente).
--
-- Demuestra que añadir el tenant operador NO debilita la barrera multi-tenant
-- (RLS vigente desde 0001 + empresa_actual()): RukkumansLabs nunca ve datos de
-- Capsulab y viceversa, y el `rol='admin'` NO habilita nada cross-tenant
-- (mismo acceso que `gestor`, acotado a su empresa).
--
-- Sin servicios reales (CA6): es pgTAP contra la DB de Supabase LOCAL; no toca
-- prod, ni el SDK de Anthropic, ni Gmail/Drive/ClickUp.
--
-- Se corre con: `supabase test db`, que aplica migraciones + seed.sql y LUEGO
-- corre este archivo en una transacción que se revierte (rollback). Por eso la
-- semilla compartida con el seed (empresa RukkumansLabs …d1, Capsulab …c1, admin
-- …a2, el gestor Javier de Capsulab …a1) ya EXISTE: aquí se referencia con
-- `on conflict (id) do nothing` (idempotente y robusto), y solo se INSERTA lo que
-- el seed no trae: el segundo gestor de RukkumansLabs (…a3, para CA5) y una cadena
-- de datos de Capsulab con UUIDs propios (algo que NO debe filtrarse).
--
-- UUIDs (aclaración #2 de la spec, NO inventar otros):
--   · Empresa RukkumansLabs = …d1   · Empresa Capsulab = …c1
--   · auth.users serie `a`: admin RukkumansLabs = …a2 · Javier (Capsulab) = …a1
--     (gestor extra de RukkumansLabs para CA5 = …a3)
-- =====================================================================
begin;
select plan(15);

-- ---------------------------------------------------------------------
-- Semilla: se inserta como rol con privilegios (postgres, NO sujeto a RLS),
-- igual que el resto de la suite.
--
-- Entidades compartidas con seed.sql → `on conflict (id) do nothing` para que el
-- test sea idempotente sobre la base ya sembrada (y autosuficiente si no lo está).
-- ---------------------------------------------------------------------
insert into empresas (id, nombre, color_marca, plan) values
  ('00000000-0000-0000-0000-0000000000d1', 'RukkumansLabs', '#F04E37', 'operador'),
  ('00000000-0000-0000-0000-0000000000c1', 'Capsulab',      '#F04E37', 'piloto')
on conflict (id) do nothing;

-- usuarios.id referencia auth.users(id): aseguramos los usuarios de auth.
--   …a2 = admin de RukkumansLabs (rol='admin')        ← viene del seed
--   …a1 = Javier, gestor de Capsulab (rol='gestor')   ← viene del seed
--   …a3 = SEGUNDO usuario de RukkumansLabs (rol='gestor', para CA5) ← propio del test
insert into auth.users (instance_id, id, aud, role, email) values
  ('00000000-0000-0000-0000-000000000000',
   '00000000-0000-0000-0000-0000000000a2', 'authenticated', 'authenticated', 'cafigueroa@gmail.com'),
  ('00000000-0000-0000-0000-000000000000',
   '00000000-0000-0000-0000-0000000000a1', 'authenticated', 'authenticated', 'javier@capsulab.cl')
on conflict (id) do nothing;

-- Gestor extra de RukkumansLabs (solo para CA5): no está en el seed; email único
-- (auth.users tiene índice único parcial por email).
insert into auth.users (instance_id, id, aud, role, email) values
  ('00000000-0000-0000-0000-000000000000',
   '00000000-0000-0000-0000-0000000000a3', 'authenticated', 'authenticated', 'gestor008@rukkumanslabs.cl');

insert into usuarios (id, empresa_id, correo, rol) values
  ('00000000-0000-0000-0000-0000000000a2',
   '00000000-0000-0000-0000-0000000000d1', 'cafigueroa@gmail.com', 'admin'),
  ('00000000-0000-0000-0000-0000000000a1',
   '00000000-0000-0000-0000-0000000000c1', 'javier@capsulab.cl',   'gestor')
on conflict (id) do nothing;

insert into usuarios (id, empresa_id, correo, rol) values
  ('00000000-0000-0000-0000-0000000000a3',
   '00000000-0000-0000-0000-0000000000d1', 'gestor008@rukkumanslabs.cl', 'gestor');

-- Datos SOLO en Capsulab (cadena propia con UUIDs no usados por el seed): 1
-- solicitud → 1 conversación → 1 propuesta → 1 tarea. Es lo que NO debe filtrarse
-- al operador. RukkumansLabs no recibe NINGUNA fila de negocio (espacio vacío).
insert into solicitudes (id, empresa_id, remitente, asunto, cuerpo) values
  ('00000000-0000-0000-0000-000000000c51',
   '00000000-0000-0000-0000-0000000000c1', 'Zona Espiga', 'Sopaipillas',
   'Cotizar sampling de sopaipillas afuera del Metro.');

insert into conversaciones (id, empresa_id, solicitud_id, tipo) values
  ('00000000-0000-0000-0000-000000000c52',
   '00000000-0000-0000-0000-0000000000c1',
   '00000000-0000-0000-0000-000000000c51', 'tipo_1');

insert into propuestas (id, empresa_id, conversacion_id, total, estado) values
  ('00000000-0000-0000-0000-000000000c53',
   '00000000-0000-0000-0000-0000000000c1',
   '00000000-0000-0000-0000-000000000c52', 100000, 'borrador');

insert into tareas (empresa_id, propuesta_id, nombre) values
  ('00000000-0000-0000-0000-0000000000c1',
   '00000000-0000-0000-0000-000000000c53', 'Reclutar promotoras');

-- =====================================================================
-- BLOQUE 1 · Admin de RukkumansLabs (…a2)
--   CA3: empresa_actual() resuelve RukkumansLabs (…d1), no Capsulab.
--   CA1: no ve NADA de Capsulab (solicitudes/propuestas/tareas = 0).
--   T2 : su espacio arranca vacío (miembros/integraciones = 0).
-- =====================================================================
set local role authenticated;
select set_config(
  'request.jwt.claims',
  json_build_object('sub', '00000000-0000-0000-0000-0000000000a2')::text,
  true
);

-- CA3 · resolución de empresa: el login del admin cae en SU espacio.
select is(
  empresa_actual(),
  '00000000-0000-0000-0000-0000000000d1'::uuid,
  'CA3 · empresa_actual() del admin resuelve RukkumansLabs (…d1), no Capsulab'
);

-- CA1 · aislamiento (ida): no ve solicitudes/propuestas/tareas de Capsulab.
select is(
  (select count(*) from solicitudes)::int, 0,
  'CA1 · el admin de RukkumansLabs ve 0 solicitudes (ninguna de Capsulab)'
);
select is(
  (select count(*) from propuestas)::int, 0,
  'CA1 · el admin de RukkumansLabs ve 0 propuestas (ninguna de Capsulab)'
);
select is(
  (select count(*) from tareas)::int, 0,
  'CA1 · el admin de RukkumansLabs ve 0 tareas (ninguna de Capsulab)'
);

-- T2 · sanity de "espacio vacío" del operador.
select is(
  (select count(*) from miembros)::int, 0,
  'T2 · el espacio de RukkumansLabs no tiene miembros'
);
select is(
  (select count(*) from integraciones)::int, 0,
  'T2 · el espacio de RukkumansLabs no tiene integraciones'
);

-- =====================================================================
-- BLOQUE 2 · Gestor de Capsulab (Javier, …a1)
--   CA2: no ve la empresa RukkumansLabs (…d1) ni sus usuarios; y SÍ ve lo suyo.
-- =====================================================================
reset role;
set local role authenticated;
select set_config(
  'request.jwt.claims',
  json_build_object('sub', '00000000-0000-0000-0000-0000000000a1')::text,
  true
);

select is(
  (select count(*) from empresas
     where id = '00000000-0000-0000-0000-0000000000d1')::int, 0,
  'CA2 · el gestor de Capsulab NO ve la empresa RukkumansLabs (…d1)'
);
select is(
  (select count(*) from usuarios
     where empresa_id = '00000000-0000-0000-0000-0000000000d1')::int, 0,
  'CA2 · el gestor de Capsulab NO ve a los usuarios de RukkumansLabs'
);
-- Sanity: sí ve sus propias filas (la barrera no le tapa lo suyo). Hay datos del
-- seed + los del test, por eso se compara contra > 0 (no un conteo exacto).
select ok(
  (select count(*) from solicitudes) > 0,
  'CA2 · el gestor de Capsulab sí ve solicitudes de su empresa'
);
select ok(
  (select count(*) from propuestas) > 0,
  'CA2 · el gestor de Capsulab sí ve propuestas de su empresa'
);
select ok(
  (select count(*) from tareas) > 0,
  'CA2 · el gestor de Capsulab sí ve tareas de su empresa'
);

-- =====================================================================
-- BLOQUE 3 · Segundo usuario de RukkumansLabs con rol='gestor' (…a3)
--   CA5: admin y gestor de la MISMA empresa ven EXACTAMENTE lo mismo; el
--   rol='admin' no abre nada extra ni cross-tenant.
-- =====================================================================
reset role;
set local role authenticated;
select set_config(
  'request.jwt.claims',
  json_build_object('sub', '00000000-0000-0000-0000-0000000000a3')::text,
  true
);

select is(
  empresa_actual(),
  '00000000-0000-0000-0000-0000000000d1'::uuid,
  'CA5 · el gestor de RukkumansLabs resuelve la misma empresa que el admin (…d1)'
);
select is(
  (select count(*) from solicitudes)::int, 0,
  'CA5 · el gestor de RukkumansLabs ve 0 solicitudes (igual que el admin)'
);
select is(
  (select count(*) from propuestas)::int, 0,
  'CA5 · el gestor de RukkumansLabs ve 0 propuestas (igual que el admin)'
);
select is(
  (select count(*) from tareas)::int, 0,
  'CA5 · el gestor de RukkumansLabs ve 0 tareas (igual que el admin)'
);

select finish();
rollback;
