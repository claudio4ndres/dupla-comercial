import { test as setup, expect } from '@playwright/test'

// Smoke de login + setup de sesión para los demás specs (storageState).
// Usa los data-testid del front (login-email/password/submit). Credenciales del
// SEED local por defecto; en prod se pasan por E2E_EMAIL / E2E_PASSWORD.
const EMAIL = process.env.E2E_EMAIL ?? 'javier@capsulab.cl'
const PASSWORD = process.env.E2E_PASSWORD ?? 'capsulab2024'

setup('login', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('login-email').fill(EMAIL)
  await page.getByTestId('login-password').fill(PASSWORD)
  await page.getByTestId('login-submit').click()
  // Login OK → cae al onboarding "Prepara tu espacio" (toda la cadena front→backend→supabase auth).
  await expect(page.getByRole('heading', { name: 'Prepara tu espacio' })).toBeVisible({
    timeout: 15_000,
  })
  await page.context().storageState({ path: 'e2e/.auth/usuario.json' })
})
