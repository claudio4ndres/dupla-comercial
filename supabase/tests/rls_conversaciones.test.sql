-- =====================================================================
-- T13 · Prueba de RLS sobre `conversaciones` y `mensajes`
-- Aislamiento multi-tenant A NIVEL DE DATOS: un usuario de la empresa A no
-- puede leer la conversación ni los mensajes de la empresa B, aunque consulte
-- las tablas directo. `mensajes` NO tiene `empresa_id`: su RLS se valida vía la
-- conversación padre (política `msg_empresa`), así que esto cubre justamente ese
-- caso (que no se filtre solo en el backend).
--
-- Se corre con: `supabase test db` (pgTAP). Cada test va en una transacción
-- que se revierte al final, así que no ensucia la base.
-- =====================================================================
begin;
select plan(5);

-- Semilla como `postgres` (superusuario, NO sujeto a RLS): dos empresas.
insert into empresas (id, nombre) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Empresa A'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Empresa B');

-- usuarios.id referencia auth.users(id): creamos los usuarios de auth.
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

-- Una solicitud + una conversación + un mensaje por cada empresa.
insert into solicitudes (id, empresa_id, remitente, asunto, cuerpo) values
  ('50111111-1111-1111-1111-111111111111',
   'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Zona Espiga', 'Sopaipillas', 'Cotizar.'),
  ('50222222-2222-2222-2222-222222222222',
   'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Otra Marca', 'Fórmula 1', 'Ideas.');

insert into conversaciones (id, empresa_id, solicitud_id, tipo) values
  ('c0111111-1111-1111-1111-111111111111',
   'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
   '50111111-1111-1111-1111-111111111111', 'tipo_1'),
  ('c0222222-2222-2222-2222-222222222222',
   'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
   '50222222-2222-2222-2222-222222222222', 'tipo_2');

insert into mensajes (conversacion_id, rol, contenido) values
  ('c0111111-1111-1111-1111-111111111111', 'usuario', 'Mensaje privado de A'),
  ('c0222222-2222-2222-2222-222222222222', 'usuario', 'Mensaje privado de B');

-- ---------------------------------------------------------------------
-- USUARIO A: `empresa_actual()` resuelve A desde auth.uid().
-- ---------------------------------------------------------------------
set local role authenticated;
select set_config(
  'request.jwt.claims',
  json_build_object('sub', 'a1111111-1111-1111-1111-111111111111')::text,
  true
);

select is(
  (select count(*) from conversaciones)::int, 1,
  'El usuario A ve exactamente 1 conversación (la de su empresa)'
);
select is(
  (select count(*) from mensajes)::int, 1,
  'El usuario A ve exactamente 1 mensaje (el de su conversación)'
);
select is(
  (select contenido from mensajes limit 1), 'Mensaje privado de A',
  'El único mensaje visible para A es el de su propia conversación'
);

-- ---------------------------------------------------------------------
-- USUARIO B: debe ver solo lo suyo (simétrico).
-- ---------------------------------------------------------------------
reset role;
set local role authenticated;
select set_config(
  'request.jwt.claims',
  json_build_object('sub', 'b1111111-1111-1111-1111-111111111111')::text,
  true
);

select is(
  (select count(*) from mensajes)::int, 1,
  'El usuario B ve exactamente 1 mensaje (el de su conversación)'
);
select is(
  (select contenido from mensajes limit 1), 'Mensaje privado de B',
  'El único mensaje visible para B es el de su propia conversación'
);

select finish();
rollback;
