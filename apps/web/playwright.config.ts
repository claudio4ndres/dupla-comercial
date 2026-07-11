import { defineConfig } from '@playwright/test'

// Dos suites (spec 018):
//
// * `ui` (default): front real (Vite) + red MOCKEADA con page.route() — Supabase
//   auth y /api/** responden fixtures deterministas. Corre en cualquier máquina/CI
//   sin Docker, Supabase ni claves. Cubre TODOS los flujos de la app.
// * `real` (+ su `setup`): los specs contra el stack completo (Supabase local con
//   seed + backend FastAPI + front). Solo corre con E2E_STACK=real o E2E_BASE_URL
//   apuntando a un despliegue. Ver e2e/README.md.
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5174'
const isLocal = !process.env.E2E_BASE_URL
const stackReal = process.env.E2E_STACK === 'real' || !!process.env.E2E_BASE_URL

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL,
    headless: true,
    trace: 'on-first-retry',
    // El video exige el ffmpeg de la MISMA revisión de Playwright; con un
    // Chromium externo (E2E_CHROMIUM) se apaga para no exigir `playwright install`.
    video: process.env.E2E_CHROMIUM ? 'off' : 'retain-on-failure',
    // Entornos con Chromium preinstalado en otra revisión (p. ej. CI/remoto con
    // PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD): apuntar E2E_CHROMIUM al binario evita
    // el `playwright install`. Sin la variable, Playwright usa su navegador.
    ...(process.env.E2E_CHROMIUM && {
      launchOptions: { executablePath: process.env.E2E_CHROMIUM },
    }),
  },
  projects: [
    // Suite mockeada: toda la app, determinista, sin servicios externos.
    { name: 'ui', testMatch: /ui\/.*\.spec\.ts/ },
    // Stack real (gateado): login de verdad contra Supabase + backend.
    ...(stackReal
      ? [
          { name: 'setup', testMatch: /real\/auth\.setup\.ts/ },
          {
            name: 'real',
            testMatch: /real\/.*\.spec\.ts/,
            dependencies: ['setup'],
            use: { storageState: 'e2e/.auth/usuario.json' },
          },
        ]
      : []),
  ],
  ...(isLocal && {
    webServer: {
      command: 'npm run dev',
      url: 'http://localhost:5174',
      reuseExistingServer: true,
      env: {
        // Host FICTICIO de Supabase: la suite ui intercepta /auth/v1/** con
        // page.route(), así que nunca se resuelve. La suite real exporta los
        // valores verdaderos por entorno antes de correr (pisan estos).
        VITE_SUPABASE_URL: process.env.VITE_SUPABASE_URL ?? 'http://supabase-e2e.local',
        VITE_SUPABASE_ANON_KEY: process.env.VITE_SUPABASE_ANON_KEY ?? 'anon-e2e',
      },
    },
  }),
})
