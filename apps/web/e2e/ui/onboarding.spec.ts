// Spec 018 · Onboarding: slider de bienvenida una sola vez + continuar a la bandeja.
import { expect, test } from '@playwright/test'
import { estadoInicial, iniciarSesion, irABandeja } from './soporte'

test('usuario nuevo ve el slider de bienvenida y al cerrarlo no reaparece', async ({ page }) => {
  const estado = estadoInicial()
  estado.onboardingVisto = false
  await iniciarSesion(page, { estado })

  // El slider aparece sobre la configuración; "Saltar" lo cierra y persiste.
  await expect(page.getByRole('button', { name: 'Saltar' })).toBeVisible()
  await page.getByRole('button', { name: 'Saltar' }).click()
  await expect(page.getByRole('button', { name: 'Saltar' })).not.toBeVisible()

  // El PATCH marcó onboarding_visto: al recargar, ya no aparece.
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Prepara tu espacio' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Saltar' })).not.toBeVisible()
})

test('“Continuar a la bandeja” navega a /bandeja con las solicitudes', async ({ page }) => {
  await iniciarSesion(page)
  await irABandeja(page)
  await expect(page.getByRole('heading', { name: 'Bandeja de solicitudes' })).toBeVisible()
})
