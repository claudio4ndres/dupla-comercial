-- =====================================================================
-- Migración 0007 · Una sola propuesta por conversación (#4, Sev ALTA)
-- Base de datos 100% en ESPAÑOL · Multi-tenant con RLS (vigente desde 0001)
--
-- PROBLEMA: `propuestas.conversacion_id` no era único y la conversación se reutiliza
-- por (solicitud, tipo). `RepositorioPropuestasSupabase.crear` siempre INSERTABA, así
-- que un clic doble en "Generar propuesta" creaba 2+ propuestas sobre la MISMA
-- conversación, con componentes/tareas duplicados; además la descarga (Excel/PPT/
-- ClickUp) podía leer una versión vieja/arbitraria.
--
-- FIX: índice ÚNICO en `conversacion_id`. Con esto, "una conversación → a lo sumo una
-- propuesta": el repo resuelve la idempotencia (busca la existente y la REEMPLAZA en
-- vez de duplicar), y este UNIQUE es la barrera dura que respalda esa invariante.
--
-- No cambia la RLS (no agrega acceso). Los enums de estado YA soportan el ciclo de
-- vida del #7: `propuestas.estado` ∈ (borrador|aprobada|enviada) y `solicitudes.estado`
-- ∈ (nueva|en_conversacion|propuesta|enviada) desde 0001 — no se tocan aquí.
--
-- OJO datos existentes: si una conversación ya tuviera >1 propuesta (por el bug), este
-- índice fallaría al crearse. Se dejan sólo las MÁS RECIENTES por conversación antes de
-- crear el índice (limpieza idempotente y segura: sólo borra los duplicados viejos).
-- =====================================================================

-- 1) Limpieza: por cada conversación con duplicados, conservar la propuesta más nueva
--    (mayor `creado_en`) y borrar las demás. El ON DELETE CASCADE de 0001 arrastra sus
--    `componentes_propuesta` y `tareas`, así que no quedan hijos huérfanos.
delete from propuestas p
using propuestas mas_nueva
where p.conversacion_id = mas_nueva.conversacion_id
  and p.id <> mas_nueva.id
  and (
        p.creado_en < mas_nueva.creado_en
        or (p.creado_en = mas_nueva.creado_en and p.id < mas_nueva.id)
      );

-- 2) Invariante dura: a lo sumo UNA propuesta por conversación.
create unique index if not exists ux_propuestas_conversacion
  on propuestas (conversacion_id);
