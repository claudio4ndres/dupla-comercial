// Spec 018 · Salud de conectores (spec 017 / 010-T9): mensajes por proveedor y
// "Probar conexión" de ClickUp.
import { expect, test } from '@playwright/test'
import { estadoInicial, iniciarSesion } from './soporte'

test('Gmail en reconectar muestra el mensaje 010-T9 con su botón', async ({ page }) => {
  const estado = estadoInicial()
  estado.estadoCorreo = { proveedor: 'gmail', estado: 'reconectar', casilla: 'javier@capsulab.cl' }
  await iniciarSesion(page, { estado })

  await expect(page.getByText(/la conexión con google expiró/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /reconectar gmail/i })).toBeVisible()
})

test('ClickUp: “Probar conexión” muestra el resultado del verificador', async ({ page }) => {
  await iniciarSesion(page)

  await page.getByRole('button', { name: /probar conexión/i }).click()
  await expect(page.getByText(/conexión verificada: 2 listas visibles/i)).toBeVisible()
})

test('ClickUp en reconectar muestra el mensaje 010-T9', async ({ page }) => {
  const estado = estadoInicial()
  estado.estadoClickup = { proveedor: 'clickup', estado: 'reconectar' }
  await iniciarSesion(page, { estado })

  await expect(page.getByText(/clickup se desconectó/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /reconectar clickup/i })).toBeVisible()
})
