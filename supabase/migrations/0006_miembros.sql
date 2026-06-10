-- =====================================================================
-- Migración 0006 · Miembros del equipo de la empresa (roster para pruebas/demo)
-- Base de datos 100% en ESPAÑOL · Multi-tenant con RLS (vigente desde 0001)
--
-- Roster de personas de prueba con su `rol` (RRHH, Producción, Diseño…), EN NUESTRA
-- base (no en ClickUp). Alimenta el selector "Asignado a" de la pantalla de Tareas:
-- el asignado elegido fluye al envío a ClickUp (va en la descripción de la tarea).
-- Es para pruebas/demo; el cableado real con cuentas de ClickUp es fase posterior.
-- =====================================================================

create table miembros (
  id         uuid primary key default gen_random_uuid(),
  empresa_id uuid not null references empresas(id) on delete cascade,
  nombre     text not null,
  rol        text not null,
  creado_en  timestamptz not null default now()
);

alter table miembros enable row level security;

-- Mismo patrón que el resto de tablas con empresa_id: acceso total DENTRO de la
-- empresa del usuario. La barrera multi-tenant es la RLS, no un filtro del backend.
create policy miembros_empresa on miembros
  for all using (empresa_id = empresa_actual())
  with check (empresa_id = empresa_actual());

create index idx_miembros_empresa on miembros(empresa_id);
