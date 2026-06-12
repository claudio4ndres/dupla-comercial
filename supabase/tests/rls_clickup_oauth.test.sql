-- =====================================================================
-- Spec 009 · ClickUp OAuth por empresa
-- T9 (CA4) · Prueba de AISLAMIENTO RLS de la integración de ClickUp.
--
-- Demuestra la barrera multi-tenant SOBRE LOS DATOS: la integración
-- `proveedor='clickup'` pertenece a una `empresa_id` y la política
-- `int_empresa` (ya vigente desde 0001: `empresa_id = empresa_actual()`)
-- impide que un tenant lea/use el ClickUp de otro. Es la prueba de que
-- A JAMÁS ve ni resuelve el `token_ref` de B (CA4): RukkumansLabs, que
-- nunca conectó ClickUp, aparece "Sin conectar" aunque Capsulab sí esté
-- conectada.
--
-- Sin servicios reales (CA8): es pgTAP contra la DB de Supabase LOCAL; no
-- toca prod, ni el SDK de Anthropic, ni la API de ClickUp ni su canje OAuth.
-- El `token_ref` sembrado es FICTICIO (no es un token real).
--
-- Se corre con: `supabase test db`, que aplica migraciones + seed.sql y
-- LUEGO corre este archivo en una transacción que se revierte (rollback).
-- Por eso la semilla compartida con el seed (Capsulab …c1, RukkumansLabs
-- …d1, Javier …a1, admin …a2) ya EXISTE: aquí se referencia con
-- `on conflict (id) do nothing` (idempotente y robusto, como hace
-- rls_rukkumanslabs), y solo se INSERTA lo propio del test: la integración
-- `clickup` de Capsulab (el seed solo trae la de gmail).
--
-- UUIDs (NO inventar otros, son los del seed):
--   · Empresa Capsulab      = …c1   · Empresa RukkumansLabs = …d1
--   · Javier (gestor Capsulab, rol='gestor')  = …a1
--   · admin de RukkumansLabs (rol='admin')    = …a2
-- =====================================================================
begin;
select plan(4);

-- ---------------------------------------------------------------------
-- Semilla como rol con privilegios (postgres, NO sujeto a RLS).
--
-- Entidades compartidas con seed.sql → `on conflict (id) do nothing` para
-- que el test sea idempotente sobre la base ya sembrada (y autosuficiente
-- si no lo está).
-- ---------------------------------------------------------------------
insert into empresas (id, nombre, color_marca, plan) values
  ('00000000-0000-0000-0000-0000000000c1', 'Capsulab',      '#F04E37', 'piloto'),
  ('00000000-0000-0000-0000-0000000000d1', 'RukkumansLabs', '#F04E37', 'operador')
on conflict (id) do nothing;

-- usuarios.id referencia auth.users(id): aseguramos los usuarios de auth.
--   …a1 = Javier, gestor de Capsulab (rol='gestor')   ← viene del seed
--   …a2 = admin de RukkumansLabs (rol='admin')        ← viene del seed
insert into auth.users (instance_id, id, aud, role, email) values
  ('00000000-0000-0000-0000-000000000000',
   '00000000-0000-0000-0000-0000000000a1', 'authenticated', 'authenticated', 'javier@capsulab.cl'),
  ('00000000-0000-0000-0000-000000000000',
   '00000000-0000-0000-0000-0000000000a2', 'authenticated', 'authenticated', 'cafigueroa@gmail.com')
on conflict (id) do nothing;

insert into usuarios (id, empresa_id, correo, rol) values
  ('00000000-0000-0000-0000-0000000000a1',
   '00000000-0000-0000-0000-0000000000c1', 'javier@capsulab.cl',   'gestor'),
  ('00000000-0000-0000-0000-0000000000a2',
   '00000000-0000-0000-0000-0000000000d1', 'cafigueroa@gmail.com', 'admin')
on conflict (id) do nothing;

-- Integración de ClickUp SOLO en Capsulab: token_ref FICTICIO (referencia
-- al secreto en Secret Manager, jamás el token en claro), estado 'conectado'.
-- El seed solo trae la de gmail de Capsulab, por eso esta es propia del test.
-- RukkumansLabs NO recibe NINGUNA integración clickup (parte "Sin conectar").
-- `on conflict do nothing` por si una corrida previa del puente la dejó.
insert into integraciones (empresa_id, proveedor, token_ref, casilla, estado) values
  ('00000000-0000-0000-0000-0000000000c1', 'clickup',
   'secreto://clickup-token-00000000-0000-0000-0000-0000000000c1',
   'Capsulab Workspace', 'conectado')
on conflict (empresa_id, proveedor) do nothing;

-- =====================================================================
-- BLOQUE 1 · Javier, gestor de Capsulab (…a1)
--   CA4: VE su propia integración clickup (la barrera no le tapa lo suyo).
--   Capsulab tiene además la integración gmail del seed, por eso se filtra
--   por `proveedor='clickup'` para contar exactamente la de ClickUp.
-- =====================================================================
set local role authenticated;
select set_config(
  'request.jwt.claims',
  json_build_object('sub', '00000000-0000-0000-0000-0000000000a1')::text,
  true
);

select is(
  (select count(*) from integraciones where proveedor = 'clickup')::int, 1,
  'CA4 · Javier (Capsulab) VE su integración clickup (count 1) → panel "Conectado"'
);

-- =====================================================================
-- BLOQUE 2 · admin de RukkumansLabs (…a2)
--   CA4: NO ve la integración clickup de Capsulab (RLS la filtra) → su panel
--   sería "Sin conectar"; y RukkumansLabs tampoco tiene una clickup propia.
--   Es la prueba de que un tenant JAMÁS ve/usa el ClickUp de otro.
-- =====================================================================
reset role;
set local role authenticated;
select set_config(
  'request.jwt.claims',
  json_build_object('sub', '00000000-0000-0000-0000-0000000000a2')::text,
  true
);

-- (2) No ve la clickup de Capsulab: la `int_empresa` la oculta.
select is(
  (select count(*) from integraciones where proveedor = 'clickup')::int, 0,
  'CA4 · el admin de RukkumansLabs NO ve la integración clickup de Capsulab → "Sin conectar"'
);

-- (3) Sanity explícito: ninguna fila clickup apunta a la empresa de Capsulab
-- (no es que exista pero "filtrada por proveedor": directamente NO es visible).
select is(
  (select count(*) from integraciones
     where empresa_id = '00000000-0000-0000-0000-0000000000c1')::int, 0,
  'CA4 · el admin de RukkumansLabs NO ve NINGUNA integración de Capsulab (ni la de su token)'
);

-- (4) RukkumansLabs no tiene ninguna integración clickup PROPIA: su espacio
-- arranca sin ClickUp (lo que el panel refleja como "Sin conectar").
select is(
  (select count(*) from integraciones)::int, 0,
  'CA4 · RukkumansLabs no tiene ninguna integración clickup propia (espacio sin conectar)'
);

select finish();
rollback;
