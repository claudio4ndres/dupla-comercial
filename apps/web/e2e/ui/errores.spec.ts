// Spec 018 · Errores visibles (spec 014): Javo caído con Reintentar, export
// fallido con banner y guardado de propuesta fallido sin navegar.
import { expect, test } from '@playwright/test'
import { SOLICITUD_T1, iniciarSesion, irABandeja } from './soporte'

async function abrirChatT1(page: import('@playwright/test').Page) {
  await irABandeja(page)
  await page.getByText(SOLICITUD_T1.asunto).click()
  await page.getByTestId('elegir-tipo-1').click()
  await expect(page.getByTestId('javo-mensaje').first()).toBeVisible()
}

test('Javo caído: banner con Reintentar que reanuda sin duplicar el turno', async ({ page }) => {
  let caido = false
  await iniciarSesion(page, {
    intercepta: async (ruta, _metodo, route) => {
      if (ruta === '/conversaciones/responder' && caido) {
        await route.fulfill({ status: 502, contentType: 'application/json', body: '{}' })
        return true
      }
      return false
    },
  })
  await abrirChatT1(page)

  caido = true
  await page.getByTestId('javo-input').fill('cotiza promotoras')
  await page.getByTestId('javo-enviar').click()
  await expect(page.getByText(/javo no está disponible/i)).toBeVisible()

  // Reintentar con el backend recuperado: responde y el turno del usuario NO se duplica.
  caido = false
  await page.getByRole('button', { name: /reintentar/i }).click()
  await expect(page.getByTestId('javo-mensaje').last()).toContainText('¿Genero la propuesta?')
  await expect(page.locator('.msg.user', { hasText: 'cotiza promotoras' })).toHaveCount(1)
})

test('export fallido muestra un banner en la Propuesta', async ({ page }) => {
  let fallarExport = false
  await iniciarSesion(page, {
    intercepta: async (ruta, _metodo, route) => {
      if (/cotizacion\.xlsx$/.test(ruta) && fallarExport) {
        await route.fulfill({ status: 502, contentType: 'application/json', body: '{}' })
        return true
      }
      return false
    },
  })
  await abrirChatT1(page)
  await page.getByTestId('javo-input').fill('cotiza')
  await page.getByTestId('javo-enviar').click()
  await expect(page.getByTestId('componente-item').first()).toBeVisible()
  await page.getByTestId('generar-propuesta').click()
  await expect(page.getByRole('heading', { name: 'Propuesta resuelta' })).toBeVisible()

  fallarExport = true
  await page.getByRole('button', { name: /excel interno/i }).click()
  await expect(page.getByText(/no se pudo generar la descarga/i)).toBeVisible()
})

test('si guardar la propuesta falla, avisa en el chat y NO navega', async ({ page }) => {
  await iniciarSesion(page, {
    intercepta: async (ruta, metodo, route) => {
      if (/\/propuesta$/.test(ruta) && metodo === 'POST') {
        await route.fulfill({ status: 502, contentType: 'application/json', body: '{}' })
        return true
      }
      return false
    },
  })
  await abrirChatT1(page)
  await page.getByTestId('javo-input').fill('cotiza')
  await page.getByTestId('javo-enviar').click()
  await expect(page.getByTestId('componente-item').first()).toBeVisible()

  await page.getByTestId('generar-propuesta').click()
  await expect(page.getByText(/no se pudo guardar la propuesta/i)).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`/bandeja/${SOLICITUD_T1.id}/chat$`)) // sigue en el chat
})
