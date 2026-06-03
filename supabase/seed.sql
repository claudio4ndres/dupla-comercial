-- =====================================================================
-- Seed · datos del cliente piloto Capsulab
-- (Las solicitudes de ejemplo replican las del prototipo)
-- =====================================================================

insert into empresas (id, nombre, color_marca, plan) values
  ('00000000-0000-0000-0000-0000000000c1', 'Capsulab', '#F04E37', 'piloto');

insert into solicitudes (empresa_id, remitente, correo_origen, asunto, cuerpo, resumen, tipo, estado) values
  ('00000000-0000-0000-0000-0000000000c1',
   'Zona Espiga', 'contacto@zonaespiga.cl',
   'Cotización sampling de sopaipillas afuera del Metro',
   'Hola Javo, queremos cotizar regalar sopaipillas afuera del Metro. Activación de 5 horas diarias. Necesitamos catering, promotores, producto y uniformes. ¿Nos pasas valores?',
   'Cotización concreta: sampling de sopaipillas afuera del Metro, 5 horas diarias. Requieren catering, promotores, producto y uniforme.',
   'tipo_1', 'nueva'),
  ('00000000-0000-0000-0000-0000000000c1',
   'Fórmula 1 LATAM', 'marketing@f1latam.com',
   'Necesitamos ideas — activación Fórmula 1',
   'Hola Javo, estamos viendo la campaña de la Fórmula 1 y necesitamos ideas de alto impacto para ver el proyecto.',
   'Pedido creativo: ideas de activación de alto impacto para campaña de Fórmula 1, sin brief cerrado.',
   'tipo_2', 'nueva');
