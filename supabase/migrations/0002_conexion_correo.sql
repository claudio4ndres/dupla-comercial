-- =====================================================================
-- Migración 0002 · Conexión de correo y recepción de solicitudes
-- Base de datos 100% en ESPAÑOL · Multi-tenant con RLS (ya vigente)
--
-- NO crea tablas nuevas: reutiliza `integraciones` (que ya modela
-- `proveedor='gmail'` + `token_ref` al secreto en GCP Secret Manager) y le
-- agrega el estado del polling. La RLS de `integraciones` y `solicitudes`
-- ya está activa desde 0001 (políticas `int_empresa` / `sol_empresa`).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Estado de polling en `integraciones`
--    - casilla:        correo conectado (p. ej. javier@capsulab.cl)
--    - cursor:         avance de lectura (historyId de Gmail / fallback)
--    - estado:         'conectado' | 'reconectar' (token expirado/revocado)
--    - actualizado_en: última vez que el backend tocó la fila
-- ---------------------------------------------------------------------
alter table integraciones
  add column casilla        text,
  add column cursor         text,
  add column estado         text not null default 'conectado'
                            check (estado in ('conectado','reconectar')),
  add column actualizado_en timestamptz not null default now();

-- ---------------------------------------------------------------------
-- 2) Idempotencia de la ingesta (CA4)
--    Un mensaje de Gmail se ingiere UNA sola vez por empresa. El índice es
--    PARCIAL (where gmail_msg_id is not null) para que las solicitudes que
--    aún no tienen id de proveedor (carga manual / otros orígenes) no
--    choquen entre sí por NULL.
-- ---------------------------------------------------------------------
create unique index idx_solicitudes_gmail_msg
  on solicitudes (empresa_id, gmail_msg_id)
  where gmail_msg_id is not null;
