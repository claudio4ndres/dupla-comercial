-- 0005 · "días" por línea de la cotización (spec 004 · modelo tarifa/día, T17).
--
-- Decisión de negocio: `valor_unitario` es la TARIFA POR DÍA (por unidad) y el costo
-- de la línea es `cantidad × días × valor_unitario` (como el archivo modelo Capsulab
-- "Fuchs": COSTO = Cantidad × días × valor unitario). Antes los días venían plegados
-- dentro de `valor_unitario`; ahora se modelan explícitos.
--
-- `nullable`-safe: default 1, así las filas existentes equivalen a "sin multiplicar
-- por días" hasta que se recarguen con su valor real.

alter table componentes_propuesta
  add column if not exists dias integer not null default 1;
