# Tareas 018 · Automatización E2E completa con Playwright

- [x] **T1** — Reorganización: specs existentes → `e2e/real/`; projects `ui` y
  `real` (gateada por `E2E_STACK`/`E2E_BASE_URL`) en `playwright.config.ts`;
  scripts `test:e2e` / `test:e2e:real`; soporte `E2E_CHROMIUM`.
- [x] **T2** — Infraestructura de mocks `e2e/ui/soporte.ts` (Supabase auth +
  backend con estado mutable + `intercepta` para fallos).
- [x] **T3** — Specs CA1-CA3: `auth`, `onboarding`, `bandeja`.
- [x] **T4** — Specs CA4-CA5: `flujo-tipo1` (punta a punta), `flujo-tipo2`.
- [x] **T5** — Specs CA6-CA8: `errores`, `rutas`, `salud-conectores`.
- [x] **T6** — `e2e/README.md` + suite `ui` completa en VERDE en este entorno;
  las suites unitarias y el build siguen verdes; commit en español.
