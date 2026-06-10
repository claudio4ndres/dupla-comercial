-- =====================================================================
-- Seed · datos del cliente piloto Capsulab (demo presentable / MVP)
--
-- Objetivo: que el backend REAL (app.main + Supabase, RLS activa) muestre la
-- bandeja con datos creíbles SIN depender de OAuth de Gmail ni del LLM en vivo.
-- Todo lo que se ve en la demo (bandeja conectada + solicitudes clasificadas)
-- queda sembrado aquí; lo único en vivo es el chat con Javo (Sonnet).
--
-- Se aplica con:  supabase db reset   (corre migraciones + este seed como
-- `postgres`, superusuario que NO está sujeto a RLS).
-- =====================================================================

-- ── Empresa piloto ───────────────────────────────────────────────────
insert into empresas (id, nombre, color_marca, plan) values
  ('00000000-0000-0000-0000-0000000000c1', 'Capsulab', '#F04E37', 'piloto');

-- ── Usuario de la empresa (puente de auth para la demo) ───────────────
-- Para que supabase.auth.signInWithPassword funcione, auth.users necesita:
--   - encrypted_password (bcrypt de la contraseña real)
--   - email_confirmed_at (sin confirmar, Supabase rechaza el login)
--   - confirmation_token vacío
-- Contraseña del piloto: capsulab2024
insert into auth.users (
  instance_id, id, aud, role, email,
  encrypted_password,
  email_confirmed_at,
  raw_app_meta_data,
  raw_user_meta_data,
  created_at, updated_at,
  -- GoTrue NO soporta NULL en sus columnas de token (rompe el login con un 500
  -- "converting NULL to string"); van en '' (vacío).
  confirmation_token, recovery_token, email_change_token_new, email_change,
  email_change_token_current, phone_change, phone_change_token, reauthentication_token
) values (
  '00000000-0000-0000-0000-000000000000',
  '00000000-0000-0000-0000-0000000000a1',
  'authenticated', 'authenticated', 'javier@capsulab.cl',
  crypt('capsulab2024', gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}',
  '{}',
  now(), now(),
  '', '', '', '', '', '', '', ''
);

insert into usuarios (id, empresa_id, correo) values
  ('00000000-0000-0000-0000-0000000000a1',
   '00000000-0000-0000-0000-0000000000c1',
   'javier@capsulab.cl');

-- ── Bandeja conectada (Gmail) ─────────────────────────────────────────
-- Deja la bandeja en estado "conectado" para la demo, sin pasar por el OAuth en
-- vivo (frágil en escenario). El `token_ref` apunta al refresh token REAL en el
-- almacén de secretos local (.secretos.local.json, gitignored): así el poller puede
-- ingerir Gmail real en esta máquina. En otra sin ese secreto, el poller ingiere 0
-- sin romperse (quedan solo las solicitudes sembradas).
insert into integraciones (empresa_id, proveedor, token_ref, casilla, estado) values
  ('00000000-0000-0000-0000-0000000000c1',
   'gmail', 'secreto://gmail-refresh-00000000-0000-0000-0000-0000000000c1',
   'javier@capsulab.cl', 'conectado');

-- ── Solicitudes (correos ya ingeridos y clasificados) ─────────────────
-- La 212CH es el correo protagonista de la demo (Tipo 1: cotización concreta).
-- Llegan ya clasificadas, como si el poller + Haiku las hubieran triado al entrar
-- (clasificación pre-cacheada: instantánea y gratis en escenario). Si se quiere
-- mostrar la clasificación EN VIVO, existe POST /solicitudes/{id}/clasificar.
insert into solicitudes
  (id, empresa_id, remitente, correo_origen, asunto, cuerpo, resumen, tipo, estado, gmail_msg_id)
values
  -- 212 Carolina Herrera · Tipo 1 (protagonista)
  ('00000000-0000-0000-0000-000000000212',
   '00000000-0000-0000-0000-0000000000c1',
   'Carolina Herrera · 212', 'marketing@carolinaherrera.cl',
   'Cotización activación lanzamiento 212 VIP Black',
   'Hola Javo, necesitamos cotizar una activación para el relanzamiento de 212 VIP Black en tiendas. '
   || 'Queremos un módulo de sampling con promotoras en 3 tiendas de Santiago (Parque Arauco, Costanera '
   || 'Center y Mall Plaza Egaña) durante 4 días, 6 horas diarias. Incluye promotoras uniformadas, '
   || 'muestras de fragancia, un módulo de ambientación con la gráfica de la campaña y catering ligero '
   || 'para el equipo. ¿Nos pasan valores y disponibilidad?',
   'Cotización concreta: activación de sampling para el relanzamiento de 212 VIP Black en 3 tiendas de '
   || 'Santiago, 4 días × 6 h. Requiere promotoras uniformadas, muestras, módulo de ambientación y catering.',
   'tipo_1', 'nueva', 'demo-212vip-001'),

  -- Sampling de sopaipillas · Tipo 1
  ('00000000-0000-0000-0000-000000000501',
   '00000000-0000-0000-0000-0000000000c1',
   'Zona Espiga', 'contacto@zonaespiga.cl',
   'Cotización sampling de sopaipillas afuera del Metro',
   'Hola Javo, queremos cotizar regalar sopaipillas afuera del Metro. Activación de 5 horas diarias. '
   || 'Necesitamos catering, promotores, producto y uniformes. ¿Nos pasas valores?',
   'Cotización concreta: sampling de sopaipillas afuera del Metro, 5 horas diarias. Requieren catering, '
   || 'promotores, producto y uniforme.',
   'tipo_1', 'nueva', 'demo-sopaipillas-001'),

  -- Activación Fórmula 1 · Tipo 2 (ideas)
  ('00000000-0000-0000-0000-000000000502',
   '00000000-0000-0000-0000-0000000000c1',
   'Fórmula 1 LATAM', 'marketing@f1latam.com',
   'Necesitamos ideas — activación Fórmula 1',
   'Hola Javo, estamos viendo la campaña de la Fórmula 1 y necesitamos ideas de alto impacto para ver '
   || 'el proyecto.',
   'Pedido creativo: ideas de activación de alto impacto para campaña de Fórmula 1, sin brief cerrado.',
   'tipo_2', 'nueva', 'demo-f1-001');

-- ── Cotización resuelta de la 212CH (la que ve la pantalla Propuesta/Tareas) ──
-- Cadena: solicitud → conversacion → propuesta → componentes_propuesta + tareas.
-- Es como si Javo + Drive ya la hubieran armado en la conversación. El front la
-- lee por GET /solicitudes/{id}/propuesta (RLS por empresa). Las otras solicitudes
-- no tienen propuesta sembrada → 404 → el front usa su fallback.
insert into conversaciones (id, empresa_id, solicitud_id, tipo) values
  ('00000000-0000-0000-0000-0000000c0212',
   '00000000-0000-0000-0000-0000000000c1',
   '00000000-0000-0000-0000-000000000212', 'tipo_1');

-- `total` = costo total (Σ cantidad×días×valor/día). Con el modelo tarifa/día (T17):
-- 6×4×240000 + 1500×1×1200 + 3×1×380000 + 1×4×90000 + 1×1×450000 = 9.510.000.
insert into propuestas (id, empresa_id, conversacion_id, total, estado) values
  ('00000000-0000-0000-0000-000000090212',
   '00000000-0000-0000-0000-0000000000c1',
   '00000000-0000-0000-0000-0000000c0212', 9510000, 'borrador');

-- `valor_unitario` es la TARIFA POR DÍA por unidad; el costo de la línea es
-- cantidad × días × valor_unitario (modelo Fuchs, T17).
insert into componentes_propuesta (propuesta_id, nombre, detalle, proveedor, cantidad, dias, valor_unitario) values
  ('00000000-0000-0000-0000-000000090212',
   'Promotoras uniformadas', '6h/día · 3 tiendas', 'Staff BTL', 6, 4, 240000),
  ('00000000-0000-0000-0000-000000090212',
   'Muestras 212 VIP Black', 'Sampling 1.5 ml · stock activación', 'Capsulab Lab', 1500, 1, 1200),
  ('00000000-0000-0000-0000-000000090212',
   'Módulo de ambientación', 'Gráfica de campaña + mesón · por tienda', 'Taller 3D', 3, 1, 380000),
  ('00000000-0000-0000-0000-000000090212',
   'Catering equipo', 'Coffee + almuerzo staff', 'Muzia', 1, 4, 90000),
  ('00000000-0000-0000-0000-000000090212',
   'Coordinación y permisos', 'Logística 3 tiendas + permisos mall', 'Capsulab', 1, 1, 450000);

insert into tareas (empresa_id, propuesta_id, nombre, grupo, responsable, vencimiento) values
  ('00000000-0000-0000-0000-0000000000c1', '00000000-0000-0000-0000-000000090212',
   'Reclutar y agendar 6 promotoras', 'RRHH', 'Coordinación', '3 días'),
  ('00000000-0000-0000-0000-0000000000c1', '00000000-0000-0000-0000-000000090212',
   'Producir muestras y kit de sampling 212 VIP', 'Producción', 'Javo', '5 días'),
  ('00000000-0000-0000-0000-0000000000c1', '00000000-0000-0000-0000-000000090212',
   'Diseñar y montar 3 módulos de ambientación', 'Diseño', 'Estudio', '6 días'),
  ('00000000-0000-0000-0000-0000000000c1', '00000000-0000-0000-0000-000000090212',
   'Gestionar permisos en Parque Arauco, Costanera y Egaña', 'Legal', 'Coordinación', '7 días'),
  ('00000000-0000-0000-0000-0000000000c1', '00000000-0000-0000-0000-000000090212',
   'Confirmar catering del equipo (4 días)', 'Compras', 'Finanzas', '4 días'),
  ('00000000-0000-0000-0000-0000000000c1', '00000000-0000-0000-0000-000000090212',
   'Armar propuesta y enviar a Carolina Herrera', 'Comercial', 'Javo', '2 días');

-- ── Catálogo del Drive de Capsulab (lo que Javo consulta con buscar_en_drive) ──
-- Pre-extraído del Drive real (spec 005): `componente` con precios y `caso` con
-- trabajos anteriores para inspirar ideas (Tipo 2). El `origen` cita el recurso real.
-- En producción esto lo sincroniza el OAuth de Drive (fase 2); aquí va sembrado.
insert into catalogo (empresa_id, tipo, nombre, detalle, unidad, valor_unitario, proveedor, origen) values
  -- Componentes con precio (para cotizar · Tipo 1)
  ('00000000-0000-0000-0000-0000000000c1', 'componente',
   'Promotoras uniformadas', '6h/día · incluye uniforme con branding', 'persona (activación)',
   240000, 'RRHH BTL', 'PROVEEDORES — Tarifario promotores'),
  ('00000000-0000-0000-0000-0000000000c1', 'componente',
   'Catering equipo', 'Coffee break + almuerzo para el staff', 'día',
   90000, 'Catering Naty', 'PROVEEDORES — Catering'),
  ('00000000-0000-0000-0000-0000000000c1', 'componente',
   'Módulo de ambientación', 'Gráfica de campaña + mesón, por tienda', 'unidad',
   380000, 'Producción 3D', 'PRODUCCIÓN 3D'),
  ('00000000-0000-0000-0000-0000000000c1', 'componente',
   'Muestras de fragancia (sampling)', 'Vial 1.5 ml, costo por unidad', 'unidad',
   1200, 'Productos Lab', 'PRODUCTOS LAB 2025'),
  ('00000000-0000-0000-0000-0000000000c1', 'componente',
   'Coordinación y permisos retail', 'Logística multi-tienda + permisos de mall', 'proyecto',
   450000, NULL, 'Documentación - LEGAL'),
  ('00000000-0000-0000-0000-0000000000c1', 'componente',
   'Pantalla LED 2x4 mts P3 Outdoor', 'Gabinete 50x50 + visualista + montaje', 'unidad',
   550000, 'Prismaled', 'Modelo Cotización.xlsx'),
  ('00000000-0000-0000-0000-0000000000c1', 'componente',
   'Camión LED (vallas móviles)', 'Camión con pantalla LED para activación en calle', 'jornada',
   900000, 'Lucas Producción', 'worklist 26.04.23.xlsx'),
  ('00000000-0000-0000-0000-0000000000c1', 'componente',
   'Uniformes con branding', 'Confección + estampado del cliente', 'unidad',
   18000, 'Estudio Diseño', 'Diseño CAPSULAB'),
  -- Casos anteriores (para inspirar ideas · Tipo 2; sin precio)
  ('00000000-0000-0000-0000-0000000000c1', 'caso',
   'Netflix — Cerro San Cristóbal', 'Activación de marca: música, carro de flores y mapping en el cerro',
   NULL, NULL, NULL, 'Conciliaciones 2024.xlsx'),
  ('00000000-0000-0000-0000-0000000000c1', 'caso',
   'PUIG — The ICON', 'Activación con camión LED y sampling de fragancia + video caso',
   NULL, NULL, NULL, 'worklist 26.04.23.xlsx'),
  ('00000000-0000-0000-0000-0000000000c1', 'caso',
   'Piknic Electronik', 'Presencia de marca en evento masivo de música electrónica (food trucks, zona kids)',
   NULL, NULL, NULL, 'PRESENTACION PIKNIC 2021-2022_SCL.pdf'),
  ('00000000-0000-0000-0000-0000000000c1', 'caso',
   'Old Spice — Punch Machine', 'Activación interactiva (punch machine) en universidades',
   NULL, NULL, NULL, 'worklist 26.04.23.xlsx');

-- ── Miembros del equipo de Capsulab (roster para el selector "Asignado a") ────
-- Personas de prueba con su `rol` por área. La pantalla de Tareas las ofrece en un
-- selector por tarea; el asignado elegido viaja a la descripción de la tarea de
-- ClickUp (spec 0006). Es para pruebas/demo; el cableado real es fase posterior.
insert into miembros (empresa_id, nombre, rol) values
  ('00000000-0000-0000-0000-0000000000c1', 'Gabriela Lillo', 'RRHH'),
  ('00000000-0000-0000-0000-0000000000c1', 'Bruno Soto', 'Producción'),
  ('00000000-0000-0000-0000-0000000000c1', 'Carla Díaz', 'Diseño'),
  ('00000000-0000-0000-0000-0000000000c1', 'Diego Rojas', 'Compras'),
  ('00000000-0000-0000-0000-0000000000c1', 'Elena Vidal', 'Legal'),
  ('00000000-0000-0000-0000-0000000000c1', 'Felipe Muñoz', 'Comercial'),
  ('00000000-0000-0000-0000-0000000000c1', 'Ana Pérez', 'Coordinación');
