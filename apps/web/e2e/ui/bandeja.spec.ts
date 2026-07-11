// Spec 018 · Bandeja: badges por tipo, proveedores deshabilitados y error visible.
import { expect, test } from '@playwright/test'
import { estadoInicial, iniciarSesion, irABandeja } from './soporte'

test('lista las solicitudes con su badge de tipo', async ({ page }) => {
  await iniciarSesion(page)
  await irABandeja(page)

  await expect(page.getByText('Zona Espiga')).toBeVisible()
  await expect(page.getByText('Tipo 1 · Cotización')).toBeVisible()
  await expect(page.getByText('Tipo 2 · Creativa')).toBeVisible()
  await expect(page.getByText('Sin clasificar')).toBeVisible()
})

test('sin correo conectado, Outlook e IMAP van deshabilitados con Próximamente', async ({ page }) => {
  const estado = estadoInicial()
  estado.estadoCorreo = { proveedor: null, estado: null, casilla: null }
  await iniciarSesion(page, { estado })
  await page.getByTestId('ir-a-bandeja').click()

  await expect(page.getByRole('button', { name: /gmail/i })).toBeEnabled()
  await expect(page.getByRole('button', { name: /outlook/i })).toBeDisabled()
  await expect(page.getByRole('button', { name: /otro \(imap\)/i })).toBeDisabled()
})

test('si las solicitudes fallan, hay banner con Reintentar que recupera la lista', async ({ page }) => {
  let fallar = true
  await iniciarSesion(page, {
    intercepta: async (ruta, metodo, route) => {
      if (ruta === '/solicitudes' && metodo === 'GET' && fallar) {
        await route.fulfill({ status: 502, contentType: 'application/json', body: '{}' })
        return true
      }
      return false
    },
  })
  await page.getByTestId('ir-a-bandeja').click()

  await expect(page.getByText(/no se pudieron cargar las solicitudes/i)).toBeVisible()
  fallar = false
  await page.getByRole('button', { name: /reintentar/i }).click()
  await expect(page.getByTestId('solicitud-card').first()).toBeVisible()
})
