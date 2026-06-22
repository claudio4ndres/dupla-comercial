-- =====================================================================
-- Migración 0011 · Flag de onboarding visto por usuario · Dupla Comercial
-- Marca si un usuario ya vio el onboarding de bienvenida (slider post-login).
-- El onboarding se muestra UNA sola vez por usuario. El backend lee y
-- actualiza este flag con la service role (salta RLS), por eso NO se tocan
-- políticas de Row Level Security.
-- =====================================================================

alter table usuarios
  add column if not exists onboarding_visto boolean not null default false;
