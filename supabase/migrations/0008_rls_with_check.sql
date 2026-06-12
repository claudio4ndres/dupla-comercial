-- 0008 · Hardening RLS: agrega WITH CHECK a msg_empresa y comp_empresa.
--
-- Auditoría multi-tenant: estas 2 políticas usaban `for all using (...)` SIN
-- `with check`, así que el INSERT/UPDATE de `mensajes` y `componentes_propuesta` no
-- tenía validación write-side a nivel de fila (solo lo respaldaba la FK al padre). Las
-- demás políticas sí traen `with check`. Espejamos el `using` como `with check`: escribir
-- una fila exige que su padre (conversación / propuesta) pertenezca a la empresa del JWT.

drop policy if exists msg_empresa on mensajes;
create policy msg_empresa on mensajes
  for all using (
    exists (
      select 1 from conversaciones c
      where c.id = mensajes.conversacion_id and c.empresa_id = empresa_actual()
    )
  ) with check (
    exists (
      select 1 from conversaciones c
      where c.id = mensajes.conversacion_id and c.empresa_id = empresa_actual()
    )
  );

drop policy if exists comp_empresa on componentes_propuesta;
create policy comp_empresa on componentes_propuesta
  for all using (
    exists (
      select 1 from propuestas p
      where p.id = componentes_propuesta.propuesta_id and p.empresa_id = empresa_actual()
    )
  ) with check (
    exists (
      select 1 from propuestas p
      where p.id = componentes_propuesta.propuesta_id and p.empresa_id = empresa_actual()
    )
  );
