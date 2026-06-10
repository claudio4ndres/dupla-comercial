-- 0004 · Proveedor por línea de la cotización (specs 004 / 007).
--
-- El Excel de la cotización con el theme Capsulab tiene una columna PROVEEDOR; ese
-- dato vive por componente de la propuesta (quién provee esa partida: catering,
-- promotoras, producción, etc.). Es `nullable`: las propuestas ya creadas quedan
-- sin proveedor hasta que se complete, sin romper nada.
--
-- No cambia la RLS: `componentes_propuesta` ya se filtra vía su `propuesta` →
-- `conversacion` → empresa; agregar una columna no abre acceso nuevo.

alter table componentes_propuesta
  add column if not exists proveedor text;
