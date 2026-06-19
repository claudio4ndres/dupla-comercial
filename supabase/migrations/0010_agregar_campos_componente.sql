-- Agregar columnas faltantes a componentes_propuesta para persistir
-- la información completa que Javo propone (días, proveedor, origen).
--
-- NOTA: `dias` y `proveedor` ya se agregaron en migraciones 0004 y 0005.
-- Solo queda `origen` (nombre del archivo del Drive de donde salió el valor).

ALTER TABLE componentes_propuesta
  ADD COLUMN IF NOT EXISTS dias integer NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS proveedor text,
  ADD COLUMN IF NOT EXISTS origen text;
