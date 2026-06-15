-- =====================================================================
-- Migración 0009 · Borrador de la cotización en curso del chat con Javo
-- Base de datos 100% en ESPAÑOL · Multi-tenant con RLS (vigente desde 0001)
--
-- PROBLEMA: la conversación con Javo persistía SOLO el texto de los mensajes (tabla
-- `mensajes`). Los COMPONENTES, TAREAS y FUENTES que Javo arma en el chat (vía las
-- tools proponer_componentes / proponer_tareas / buscar_en_drive) NO se guardaban en
-- el hilo. Al recargar o rehidratar la conversación, el chat reaparecía pero la
-- cotización armada (componentes valorizados / fuentes citadas) se PERDÍA, y "Generar
-- propuesta" podía quedar sin datos.
--
-- FIX: columna jsonb `cotizacion_borrador` en `conversaciones` con el ÚLTIMO estado de
-- la cotización en curso ({componentes, tareas, fuentes}). El endpoint
-- `POST /conversaciones/responder` la ACTUALIZA con lo último que Javo propuso, y
-- `GET /conversaciones/{solicitud_id}/cotizacion` la devuelve para que el front
-- repueble el panel del chat al rehidratar. Es el ESTADO EN CURSO (sin confirmar);
-- la propuesta confirmada sigue viviendo en `propuestas` + sus hijos (no se duplica).
--
-- RLS: NO se agrega ni cambia ninguna política. La columna cuelga de `conversaciones`,
-- que ya está protegida por `conv_empresa` (`for all using/with check
-- empresa_id = empresa_actual()`, 0001) — leer/escribir el borrador queda restringido
-- a la empresa del JWT por la misma barrera que el resto de la fila.
-- =====================================================================

alter table conversaciones
  add column if not exists cotizacion_borrador jsonb;

comment on column conversaciones.cotizacion_borrador is
  'Borrador de la cotización en curso del chat con Javo: último {componentes, tareas, '
  'fuentes} que propuso/citó, para repoblar el panel al rehidratar. NULL = sin borrador.';
