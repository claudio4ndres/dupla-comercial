-- 0012 · Spec 015: state anti-CSRF del OAuth persistente (multi-instancia).
--
-- El `state` liga el inicio del consentimiento con su callback. Antes vivía en
-- memoria del proceso: con varias instancias de Cloud Run, el callback podía
-- aterrizar en otra instancia y fallar. Ahora vive en la base y se consume con
-- un DELETE que devuelve la fila (consumo atómico, anti-replay).
--
-- Tabla de INFRAESTRUCTURA del backend: la toca SOLO la service role. RLS
-- habilitada SIN políticas → ningún JWT de usuario puede leer ni escribir
-- (excepción documentada a la regla de oro #2: no hay filas "del usuario" que
-- filtrar; el aislamiento lo da el state opaco + empresa_id fijado por el backend).

create table estados_oauth (
  state text primary key,
  empresa_id uuid not null references empresas(id) on delete cascade,
  creado_en timestamptz not null default now(),
  expira_en timestamptz not null
);

comment on table estados_oauth is
  'State anti-CSRF de los flujos OAuth (gmail/clickup): consumo único, caduca a los 10 min.';

alter table estados_oauth enable row level security;

-- Limpieza oportunista: índice para barrer expirados (job/manual).
create index estados_oauth_expira_en_idx on estados_oauth (expira_en);
