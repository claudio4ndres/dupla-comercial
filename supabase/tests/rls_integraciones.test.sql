-- =====================================================================
-- T2 (Spec 002) · Prueba de RLS sobre `integraciones`
-- Verifica el aislamiento multi-tenant A NIVEL DE DATOS: un usuario de la
-- empresa A no puede leer la integración (conexión de correo) de la empresa
-- B. La política `int_empresa` ya existe desde 0001; este test la BLINDA
-- como regresión (la conexión + sus secretos son sensibles).
--
-- Para que el test tenga dientes (y no pase "en vacío"), primero confirma
-- que como `postgres` (superusuario, NO sujeto a RLS) se ven LAS DOS filas:
-- así, cuando A ve solo 1, sabemos que es la RLS quien filtra.
--
-- Se corre con: `supabase test db` (pgTAP), en transacción con rollback.
-- =====================================================================

begin;
select plan(6);

-- ---------------------------------------------------------------------
-- Semilla como `postgres`: dos empresas, sus usuarios de auth y una
-- integración de Gmail por empresa.
-- ---------------------------------------------------------------------
insert into empresas (id, nombre) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Empresa A'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Empresa B');

insert into auth.users (instance_id, id, aud, role, email) values
  ('00000000-0000-0000-0000-000000000000',
   'a1111111-1111-1111-1111-111111111111', 'authenticated', 'authenticated', 'a@test.cl'),
  ('00000000-0000-0000-0000-000000000000',
   'b1111111-1111-1111-1111-111111111111', 'authenticated', 'authenticated', 'b@test.cl');

insert into usuarios (id, empresa_id, correo) values
  ('a1111111-1111-1111-1111-111111111111',
   'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'a@test.cl'),
  ('b1111111-1111-1111-1111-111111111111',
   'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'b@test.cl');

insert into integraciones (empresa_id, proveedor, token_ref, casilla) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'gmail',
   'secreto://empresa-a', 'a@test.cl'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'gmail',
   'secreto://empresa-b', 'b@test.cl');

-- ---- 1 · Como postgres (sin RLS) se ven LAS DOS integraciones ---------
select is(
  (select count(*) from integraciones)::int, 2,
  'Como superusuario se ven las 2 integraciones (la RLS no aplica a postgres)'
);

-- ---------------------------------------------------------------------
-- Actuamos como el USUARIO A (rol `authenticated` + claim sub en el JWT).
-- ---------------------------------------------------------------------
set local role authenticated;
select set_config(
  'request.jwt.claims',
  json_build_object('sub', 'a1111111-1111-1111-1111-111111111111')::text,
  true
);

select is(
  (select count(*) from integraciones)::int, 1,
  'El usuario A ve exactamente 1 integración (la de su empresa)'
);
select is(
  (select count(*) from integraciones
     where empresa_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')::int, 0,
  'El usuario A NO puede leer la integración de la empresa B'
);
select is(
  (select empresa_id from integraciones limit 1),
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid,
  'La única integración visible para A es la de la empresa A'
);

-- ---------------------------------------------------------------------
-- Actuamos como el USUARIO B: debe ver solo lo suyo (simétrico).
-- ---------------------------------------------------------------------
reset role;
set local role authenticated;
select set_config(
  'request.jwt.claims',
  json_build_object('sub', 'b1111111-1111-1111-1111-111111111111')::text,
  true
);

select is(
  (select count(*) from integraciones)::int, 1,
  'El usuario B ve exactamente 1 integración (la de su empresa)'
);
select is(
  (select empresa_id from integraciones limit 1),
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid,
  'La única integración visible para B es la de la empresa B'
);

select finish();
rollback;
