-- =====================================================================
-- T5 · Prueba de RLS (Row Level Security) sobre `solicitudes`
-- Verifica el aislamiento multi-tenant A NIVEL DE DATOS: un usuario de la
-- empresa A no puede leer las solicitudes de la empresa B, aunque consulte
-- la tabla directamente (no basta con el filtro del backend).
--
-- Se corre con: `supabase test db` (pgTAP). Cada test va en una transacción
-- que se revierte al final, así que no ensucia la base.
-- =====================================================================

begin;
select plan(4);

-- ---------------------------------------------------------------------
-- Semilla: se inserta como `postgres` (superusuario que NO está sujeto a
-- RLS), de modo que existan filas de DOS empresas distintas.
-- ---------------------------------------------------------------------
insert into empresas (id, nombre) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Empresa A'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Empresa B');

-- usuarios.id referencia auth.users(id): hay que crear los usuarios de auth.
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

insert into solicitudes (id, empresa_id, remitente, asunto, cuerpo) values
  ('50111111-1111-1111-1111-111111111111',
   'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Zona Espiga', 'Sopaipillas',
   'Cotizar sampling de sopaipillas afuera del Metro.'),
  ('50222222-2222-2222-2222-222222222222',
   'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Otra Marca', 'Fórmula 1',
   'Ideas para una activación de Fórmula 1.');

-- ---------------------------------------------------------------------
-- Actuamos como el USUARIO A (rol `authenticated` + claim sub en el JWT).
-- `empresa_actual()` resolverá la empresa A a partir de auth.uid().
-- ---------------------------------------------------------------------
set local role authenticated;
select set_config(
  'request.jwt.claims',
  json_build_object('sub', 'a1111111-1111-1111-1111-111111111111')::text,
  true
);

select is(
  (select count(*) from solicitudes)::int, 1,
  'El usuario A ve exactamente 1 solicitud (la de su empresa)'
);
select is(
  (select count(*) from solicitudes
     where empresa_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')::int, 0,
  'El usuario A NO puede leer ninguna solicitud de la empresa B'
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
  (select count(*) from solicitudes)::int, 1,
  'El usuario B ve exactamente 1 solicitud (la de su empresa)'
);
select is(
  (select empresa_id from solicitudes limit 1),
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid,
  'La única solicitud visible para B es la de la empresa B'
);

select finish();
rollback;
