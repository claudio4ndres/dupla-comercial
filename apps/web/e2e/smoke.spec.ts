import { test, expect } from '@playwright/test'

// Smoke local: ya logueado (storageState del auth.setup). Verifica que la cadena
// completa (front → backend → supabase local) renderiza el onboarding y la bandeja.
// Afirma ESTRUCTURA (headings + data-testid), no texto del LLM.

test('onboarding muestra el conector de Gmail', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Prepara tu espacio' })).toBeVisible()
  await expect(page.getByTestId('conector-gmail')).toBeVisible()
})

test('navega a la bandeja y carga su estado', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('ir-a-bandeja').click()
  await expect(page.getByRole('heading', { name: 'Bandeja de solicitudes' })).toBeVisible()
  // El banner de estado del conector aparece (escuchando / reconectar / sin conectar).
  await expect(page.getByTestId('bandeja-estado')).toBeVisible({ timeout: 10_000 })
})
