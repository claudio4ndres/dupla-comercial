-- =====================================================================
-- T1 (Spec 002) · Migración 0002 · estado de polling + idempotencia
-- Verifica A NIVEL DE DATOS lo que agrega la migración 0002:
--   1) Columnas nuevas en `integraciones` (casilla, cursor, estado,
--      actualizado_en) con su default y su check de `estado`.
--   2) Índice único parcial de idempotencia sobre
--      `solicitudes(empresa_id, gmail_msg_id)`: no se ingiere dos veces el
--      mismo mensaje de Gmail en la misma empresa (CA4), pero varios NULL
--      conviven (correos aún sin id de proveedor).
--
-- Se corre con: `supabase test db` (pgTAP). Cada test va en una transacción
-- que se revierte al final, así que no ensucia la base.
-- =====================================================================

begin;
select plan(10);

-- ---------------------------------------------------------------------
-- Semilla mínima: una empresa (UUID propio para no chocar con el seed
-- de Capsulab `…00c1` ni con el test de RLS `aaaa…/bbbb…`).
-- Se inserta como `postgres` (superusuario, no sujeto a RLS).
-- ---------------------------------------------------------------------
insert into empresas (id, nombre) values
  ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'Empresa C');

-- ---- 1..4 · Columnas nuevas en `integraciones` -----------------------
select has_column('integraciones', 'casilla',
  'integraciones tiene la columna `casilla`');
select has_column('integraciones', 'cursor',
  'integraciones tiene la columna `cursor`');
select has_column('integraciones', 'estado',
  'integraciones tiene la columna `estado`');
select has_column('integraciones', 'actualizado_en',
  'integraciones tiene la columna `actualizado_en`');

-- ---- 5 · `estado` es NOT NULL ----------------------------------------
select col_not_null('integraciones', 'estado',
  '`estado` es NOT NULL');

-- ---- 6 · `estado` por defecto = 'conectado' --------------------------
insert into integraciones (empresa_id, proveedor, token_ref) values
  ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'gmail', 'secreto://ref-gmail');
select is(
  (select estado from integraciones
     where empresa_id = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
       and proveedor = 'gmail'),
  'conectado',
  'Al conectar, `estado` arranca en ''conectado'' por defecto'
);

-- ---- 7 · el check rechaza un `estado` inválido -----------------------
select throws_ok(
  $$ insert into integraciones (empresa_id, proveedor, token_ref, estado)
     values ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'drive',
             'secreto://ref-drive', 'basura') $$,
  '23514',
  null,
  '`estado` solo admite ''conectado'' o ''reconectar'' (check)'
);

-- ---- 8 · 'reconectar' es un `estado` válido --------------------------
select lives_ok(
  $$ insert into integraciones (empresa_id, proveedor, token_ref, estado)
     values ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'clickup',
             'secreto://ref-clickup', 'reconectar') $$,
  '`estado` = ''reconectar'' es válido (token expirado/revocado)'
);

-- ---- 9 · Idempotencia: mismo `gmail_msg_id` no se duplica (CA4) -------
insert into solicitudes (empresa_id, remitente, asunto, cuerpo, gmail_msg_id) values
  ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'Marca', 'Asunto', 'Cuerpo', 'gmail-msg-1');
select throws_ok(
  $$ insert into solicitudes (empresa_id, remitente, asunto, cuerpo, gmail_msg_id)
     values ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'Marca', 'Asunto', 'Cuerpo', 'gmail-msg-1') $$,
  '23505',
  null,
  'No se ingiere dos veces el mismo gmail_msg_id en la misma empresa (idempotencia)'
);

-- ---- 10 · El índice es PARCIAL: varios NULL conviven -----------------
select lives_ok(
  $$ insert into solicitudes (empresa_id, remitente, asunto, cuerpo, gmail_msg_id) values
       ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'M1', 'A1', 'C1', null),
       ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'M2', 'A2', 'C2', null) $$,
  'Dos solicitudes sin gmail_msg_id (NULL) conviven: el índice es parcial'
);

select finish();
rollback;
