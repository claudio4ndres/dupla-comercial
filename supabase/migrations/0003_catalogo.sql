-- =====================================================================
-- Migración 0003 · Catálogo de la empresa (datos del Drive para Javo)
-- Base de datos 100% en ESPAÑOL · Multi-tenant con RLS (vigente desde 0001)
--
-- Representación COMPACTA y consultable de los recursos del Drive de cada
-- empresa: `componente` (con precio, para cotizar · Tipo 1) y `caso` (trabajos
-- anteriores, para inspirar ideas · Tipo 2). Javo lo consulta con la herramienta
-- `buscar_en_drive` (spec 005). En la demo se SIEMBRA pre-extraído desde el Drive
-- real; la conexión en vivo por OAuth es fase 2 (otra spec).
-- =====================================================================

create table catalogo (
  id             uuid primary key default gen_random_uuid(),
  empresa_id     uuid not null references empresas(id) on delete cascade,
  tipo           text not null default 'componente'
                 check (tipo in ('componente','caso')),
  nombre         text not null,
  detalle        text,
  unidad         text,                 -- 'jornada' | 'día' | 'unidad'… (componentes)
  valor_unitario numeric(12,2),        -- nullable: los 'caso' no tienen precio
  proveedor      text,
  origen         text,                 -- recurso del Drive de donde salió el dato
  creado_en      timestamptz not null default now()
);

alter table catalogo enable row level security;

-- Mismo patrón que el resto de tablas con empresa_id: acceso total DENTRO de la
-- empresa del usuario. La barrera multi-tenant es la RLS, no un filtro del backend.
create policy cat_empresa on catalogo
  for all using (empresa_id = empresa_actual())
  with check (empresa_id = empresa_actual());

create index idx_catalogo_empresa on catalogo(empresa_id);
