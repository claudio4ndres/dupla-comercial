-- =====================================================================
-- Snippet 008 · Provisión en PRODUCCIÓN: empresa operadora RukkumansLabs
-- + su usuario admin. NO se ejecuta con `supabase db reset` (eso es el seed local).
-- Se corre A MANO contra la base de PROD (SQL editor / psql) como owner que
-- bypassa RLS, UNA vez que existe la cuenta de Auth real.
--
-- FRONTERA HUMANO/AGENTE (CA7): la cuenta `cafigueroa@gmail.com` en Supabase Auth
-- la crea la PERSONA (dashboard → Authentication → Add user). Este snippet NO crea
-- cuentas ni contraseñas: solo inserta las filas de DATOS con el UID YA existente.
--
-- USO: reemplaza el placeholder <<UID_REAL>> por el "User UID" que asignó Supabase
-- Auth a cafigueroa@gmail.com. NO commitear este archivo con el UID real adentro.
-- Es idempotente (on conflict do nothing): seguro de re-correr.
--
-- Convención de UUIDs (ver plan §1.3): empresa RukkumansLabs = …d1 (NO …a1, que es
-- el auth.users.id de Javier). Capsulab = …c1 (intacta).
-- =====================================================================

-- 1) Empresa operadora (tenant aparte, aislado por RLS de Capsulab)
insert into empresas (id, nombre, color_marca, plan) values
  ('00000000-0000-0000-0000-0000000000d1', 'RukkumansLabs', '#F04E37', 'operador')
on conflict (id) do nothing;

-- 2) Usuario admin, vinculado a la cuenta de Auth real (FK a auth.users(id)).
--    <<UID_REAL>> = User UID de cafigueroa@gmail.com en el Supabase Auth de prod.
insert into usuarios (id, empresa_id, correo, rol) values
  ('<<UID_REAL>>', '00000000-0000-0000-0000-0000000000d1', 'cafigueroa@gmail.com', 'admin')
on conflict (id) do nothing;

-- 3) Verificación (debe devolver 1 fila: el admin dentro de RukkumansLabs):
-- select u.correo, u.rol, e.nombre as empresa
--   from usuarios u join empresas e on e.id = u.empresa_id
--  where u.correo = 'cafigueroa@gmail.com';
