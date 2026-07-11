# Spec 018 · Automatización E2E completa con Playwright

- **Estado:** aprobada
- **Tipo:** frontend (pruebas end-to-end)
- **Relacionada con:** toda la aplicación (login → bandeja → Javo → propuesta → tareas → exports → conectores)

## 1. Problema y por qué

Los e2e existentes cubren solo login y navegación de menú, exigen el stack real
(Supabase local + backend + seed, imposible en CI sin Docker) y usan selectores
frágiles. No hay red de seguridad automatizada para el flujo que vende el
producto: correo → conversación con Javo → propuesta → tareas → exports.

## 2. Usuarios y contexto

Desarrolladores y CI: una suite que corre en cualquier máquina y ejercita la app
real en un navegador real, con datos deterministas.

## 3. Alcance

**Incluye:**
- Suite `ui` (Playwright project default): front real + red mockeada con
  `page.route()` (Supabase auth y `/api/**` con fixtures espejo del seed
  Capsulab). 8 specs que cubren TODA la app.
- Suite `real` (los specs existentes, movidos a `e2e/real/`), gateada por
  `E2E_STACK=real` / `E2E_BASE_URL`, documentada en `e2e/README.md`.
- Soporte para entornos con Chromium preinstalado (`E2E_CHROMIUM`).

**No incluye (fuera de alcance):**
- Llamadas reales a Anthropic/Google/ClickUp desde e2e (determinismo/costo).
- Ampliar la suite `real` (queda como estaba, solo reorganizada).

## 4. Criterios de aceptación (un spec por CA)

- **CA1 · auth** — login ok aterriza en Configuración; credenciales malas
  muestran el error; cerrar sesión vuelve al login en `/`.
- **CA2 · onboarding** — el slider de bienvenida aparece una sola vez y
  "Continuar a la bandeja" navega a `/bandeja`.
- **CA3 · bandeja** — badges por tipo; Outlook/IMAP deshabilitados con
  "Próximamente"; fallo de carga → banner con Reintentar que recupera.
- **CA4 · flujo Tipo 1 completo** — abrir solicitud (`/bandeja/:id`) → Tipo 1 →
  chat (`/bandeja/:id/chat`) con saludo y chips → mensaje → componentes
  valorizados + fuentes → propuesta (`/propuestas/:id`, total y margen 40%) →
  exports (evento download con nombre correcto) → tareas → envío a ClickUp.
- **CA5 · flujo Tipo 2** — aviso de búsqueda en internet + fuente web citada.
- **CA6 · errores** — Javo 502 → banner + Reintentar sin duplicar turno;
  export fallido → banner; guardado de propuesta fallido → aviso sin navegar.
- **CA7 · rutas** — deep-links a detalle/chat/propuesta rehidratan; `reload`
  en el chat conserva la conversación; 404; botón atrás.
- **CA8 · salud de conectores** — mensajes 010-T9 por proveedor y "Probar
  conexión" de ClickUp con el resultado del verificador.

## 5. Consideraciones multi-tenant

Los mocks devuelven solo datos de la empresa demo; no hay datos reales ni
tokens (la sesión GoTrue es ficticia). La suite `real` sí ejercita RLS.

## 6. Aclaraciones pendientes

- Ninguna.
