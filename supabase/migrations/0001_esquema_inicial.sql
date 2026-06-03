-- =====================================================================
-- Migración 0001 · Esquema inicial · Dupla Comercial
-- Base de datos 100% en ESPAÑOL · Multi-tenant con Row Level Security (RLS)
-- Postgres / Supabase
-- =====================================================================

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- TABLAS
-- ---------------------------------------------------------------------

create table empresas (
  id            uuid primary key default gen_random_uuid(),
  nombre        text not null,
  color_marca   text not null default '#F04E37',
  plan          text not null default 'piloto',
  creado_en     timestamptz not null default now()
);

-- usuarios: vinculados a auth.users de Supabase, pertenecen a UNA empresa
create table usuarios (
  id            uuid primary key references auth.users(id) on delete cascade,
  empresa_id    uuid not null references empresas(id) on delete cascade,
  correo        text not null,
  rol           text not null default 'gestor',     -- gestor | admin
  creado_en     timestamptz not null default now()
);

create table solicitudes (
  id            uuid primary key default gen_random_uuid(),
  empresa_id    uuid not null references empresas(id) on delete cascade,
  remitente     text not null,
  correo_origen text,
  asunto        text not null,
  cuerpo        text not null,
  resumen       text,
  tipo          text not null default 'sin_clasificar'
                check (tipo in ('sin_clasificar','tipo_1','tipo_2')),
  estado        text not null default 'nueva'
                check (estado in ('nueva','en_conversacion','propuesta','enviada')),
  gmail_msg_id  text,
  creado_en     timestamptz not null default now()
);

create table conversaciones (
  id            uuid primary key default gen_random_uuid(),
  empresa_id    uuid not null references empresas(id) on delete cascade,
  solicitud_id  uuid not null references solicitudes(id) on delete cascade,
  tipo          text not null check (tipo in ('tipo_1','tipo_2')),
  creado_en     timestamptz not null default now()
);

create table mensajes (
  id               uuid primary key default gen_random_uuid(),
  conversacion_id  uuid not null references conversaciones(id) on delete cascade,
  rol              text not null check (rol in ('usuario','asistente','sistema')),
  contenido        text not null,
  creado_en        timestamptz not null default now()
);

create table propuestas (
  id               uuid primary key default gen_random_uuid(),
  empresa_id       uuid not null references empresas(id) on delete cascade,
  conversacion_id  uuid not null references conversaciones(id) on delete cascade,
  total            numeric(12,2) not null default 0,
  estado           text not null default 'borrador'
                   check (estado in ('borrador','aprobada','enviada')),
  creado_en        timestamptz not null default now()
);

create table componentes_propuesta (
  id             uuid primary key default gen_random_uuid(),
  propuesta_id   uuid not null references propuestas(id) on delete cascade,
  nombre         text not null,
  detalle        text,
  cantidad       integer not null default 1,
  valor_unitario numeric(12,2) not null default 0
);

create table tareas (
  id            uuid primary key default gen_random_uuid(),
  empresa_id    uuid not null references empresas(id) on delete cascade,
  propuesta_id  uuid not null references propuestas(id) on delete cascade,
  nombre        text not null,
  grupo         text,
  responsable   text,
  vencimiento   text,
  clickup_id    text,
  estado        text not null default 'pendiente'
                check (estado in ('pendiente','enviada','completada')),
  creado_en     timestamptz not null default now()
);

create table integraciones (
  id            uuid primary key default gen_random_uuid(),
  empresa_id    uuid not null references empresas(id) on delete cascade,
  proveedor     text not null check (proveedor in ('gmail','drive','clickup')),
  token_ref     text not null,        -- referencia al secreto en GCP Secret Manager
  creado_en     timestamptz not null default now(),
  unique (empresa_id, proveedor)
);

-- ---------------------------------------------------------------------
-- AISLAMIENTO MULTI-TENANT
-- Función que devuelve la empresa del usuario autenticado.
-- SECURITY DEFINER => evita recursión de RLS al consultar 'usuarios'.
-- ---------------------------------------------------------------------

create or replace function empresa_actual()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select empresa_id from usuarios where id = auth.uid()
$$;

-- ---------------------------------------------------------------------
-- ACTIVAR RLS Y POLÍTICAS
-- Cada usuario solo ve/edita filas de SU empresa.
-- ---------------------------------------------------------------------

alter table empresas              enable row level security;
alter table usuarios              enable row level security;
alter table solicitudes           enable row level security;
alter table conversaciones        enable row level security;
alter table mensajes              enable row level security;
alter table propuestas            enable row level security;
alter table componentes_propuesta enable row level security;
alter table tareas                enable row level security;
alter table integraciones         enable row level security;

-- empresas: el usuario ve solo su propia empresa
create policy emp_propia on empresas
  for select using (id = empresa_actual());

-- usuarios: ve a los de su misma empresa
create policy usr_misma_empresa on usuarios
  for select using (empresa_id = empresa_actual());

-- patrón estándar para tablas con empresa_id: acceso total dentro de la empresa
create policy sol_empresa  on solicitudes
  for all using (empresa_id = empresa_actual()) with check (empresa_id = empresa_actual());
create policy conv_empresa on conversaciones
  for all using (empresa_id = empresa_actual()) with check (empresa_id = empresa_actual());
create policy prop_empresa on propuestas
  for all using (empresa_id = empresa_actual()) with check (empresa_id = empresa_actual());
create policy tar_empresa  on tareas
  for all using (empresa_id = empresa_actual()) with check (empresa_id = empresa_actual());
create policy int_empresa  on integraciones
  for all using (empresa_id = empresa_actual()) with check (empresa_id = empresa_actual());

-- mensajes y componentes no tienen empresa_id directo: se valida vía el padre
create policy msg_empresa on mensajes
  for all using (
    exists (
      select 1 from conversaciones c
      where c.id = mensajes.conversacion_id and c.empresa_id = empresa_actual()
    )
  );

create policy comp_empresa on componentes_propuesta
  for all using (
    exists (
      select 1 from propuestas p
      where p.id = componentes_propuesta.propuesta_id and p.empresa_id = empresa_actual()
    )
  );

-- ---------------------------------------------------------------------
-- ÍNDICES
-- ---------------------------------------------------------------------
create index idx_solicitudes_empresa   on solicitudes(empresa_id);
create index idx_conversaciones_empresa on conversaciones(empresa_id);
create index idx_mensajes_conversacion on mensajes(conversacion_id);
create index idx_propuestas_empresa    on propuestas(empresa_id);
create index idx_tareas_empresa        on tareas(empresa_id);
