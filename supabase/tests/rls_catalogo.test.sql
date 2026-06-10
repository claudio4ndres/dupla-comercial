-- =====================================================================
-- 005 · Prueba de RLS sobre `catalogo` (CA5)
-- Aislamiento multi-tenant A NIVEL DE DATOS: un usuario de la empresa A no
-- puede leer el catálogo de la empresa B, aunque consulte la tabla directo.
--
-- Se corre con: `supabase test db` (pgTAP). Cada test va en una transacción
-- que se revierte al final, así que no ensucia la base.
-- =====================================================================
begin;
select plan(3);

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

insert into catalogo (empresa_id, tipo, nombre, valor_unitario) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'componente', 'Promotoras', 240000),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'componente', 'Pantalla LED', 550000);

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
  (select count(*) from catalogo)::int, 1,
  'El usuario A ve exactamente 1 fila de catálogo (la de su empresa)'
);
select is(
  (select count(*) from catalogo
     where empresa_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')::int, 0,
  'El usuario A NO puede leer el catálogo de la empresa B'
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
  (select nombre from catalogo limit 1), 'Pantalla LED',
  'La única fila visible para B es la de la empresa B'
);

select finish();
rollback;
