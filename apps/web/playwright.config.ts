import { defineConfig } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5174'
const isLocal = !process.env.E2E_BASE_URL

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL,
    headless: true,
    trace: 'on-first-retry',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'flujo',
      dependencies: ['setup'],
      use: { storageState: 'e2e/.auth/usuario.json' },
    },
  ],
  ...(isLocal && {
    webServer: {
      command: 'npm run dev',
      url: 'http://localhost:5174',
      reuseExistingServer: true,
    },
  }),
})
