// Spec 018 · Autenticación: login por la UI real (Supabase mockeado), error de
// credenciales y cierre de sesión.
import { expect, test } from '@playwright/test'
import { CORREO_E2E, iniciarSesion, mockApi, mockSupabaseAuth } from './soporte'

test('login exitoso aterriza en Configuración (Prepara tu espacio)', async ({ page }) => {
  await iniciarSesion(page)
  await expect(page).toHaveURL(/\/configuracion$/)
  await expect(page.getByText('Correo · Gmail')).toBeVisible()
})

test('credenciales inválidas muestran el error y no entran', async ({ page }) => {
  await mockSupabaseAuth(page, { credencialesInvalidas: true })
  await mockApi(page)
  await page.goto('/')
  await page.getByTestId('login-email').fill(CORREO_E2E)
  await page.getByTestId('login-password').fill('clave-mala')
  await page.getByTestId('login-submit').click()

  await expect(page.getByText(/correo o contraseña incorrectos/i)).toBeVisible()
  await expect(page.getByTestId('login-email')).toBeVisible() // sigue en el login
})

test('cerrar sesión vuelve al login en /', async ({ page }) => {
  await iniciarSesion(page)
  await page.getByRole('button', { name: /salir/i }).click()

  await expect(page.getByTestId('login-email')).toBeVisible()
  await expect(page).toHaveURL(/\/$/)
})
