# E2E con Playwright (spec 018)

Dos suites con propósitos distintos:

## Suite `ui` (default) — toda la app, sin servicios externos

El front corre de verdad (Vite + React + supabase-js + React Router) en un
Chromium real, pero **toda la red está mockeada** con `page.route()`:

- Supabase auth (`/auth/v1/**`) responde una sesión GoTrue ficticia — el login
  se hace por la pantalla real.
- El backend (`/api/**`) responde fixtures deterministas en español, espejo del
  seed de Capsulab y de los dobles del backend (ver `ui/soporte.ts`).

Cubre: login/logout, onboarding, bandeja (badges, proveedores, errores), el
flujo completo Tipo 1 (chat con Javo → componentes valorizados → propuesta →
tareas → ClickUp → exports), Tipo 2 (internet + fuentes), errores visibles
(Javo caído + Reintentar), deep-links/refresh del router y salud de conectores.

```bash
npm run test:e2e            # = playwright test --project=ui
```

Sin Docker, sin Supabase, sin claves. En entornos con Chromium preinstalado en
otra revisión (p. ej. CI remoto con `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`):

```bash
E2E_CHROMIUM=/opt/pw-browsers/chromium npm run test:e2e
```

## Suite `real` — stack completo (local)

Los specs de `e2e/real/` (login real + smoke + flujo) ejercitan la cadena
front → backend → Supabase auth. Requisitos:

1. `supabase start && supabase db reset` (Docker; aplica migraciones + seed).
2. Backend: `cd apps/api && uvicorn app.main:app --reload` (con su `.env`).
3. Exportar `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` (los de `supabase
   status`) y, si no usas el seed, `E2E_EMAIL` / `E2E_PASSWORD`.

```bash
npm run test:e2e:real       # = E2E_STACK=real playwright test --project=setup --project=real
```

También puede apuntarse a un despliegue con `E2E_BASE_URL=https://...` (activa
la suite real y desactiva el webServer local).

## Convenciones

- Selectores por `data-testid` (tabla en `INSTRUCCIONES_KIRO.md`) o roles
  accesibles; nada de clases CSS en specs nuevos.
- Fixtures y helpers en `ui/soporte.ts`: `iniciarSesion(page, {estado,
  intercepta})` — `estado` muta el "backend" por test, `intercepta` simula
  fallos puntuales (502/abort) antes del comportamiento feliz.
- No asertar textos largos de Javo: usar datos estructurados (componentes,
  totales, fuentes) y testids.
