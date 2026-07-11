// Spec 018 · Flujo Tipo 2 (ideas): aviso de búsqueda en internet + fuentes web.
import { expect, test } from '@playwright/test'
import { SOLICITUD_T2, iniciarSesion, irABandeja } from './soporte'

test('pedido de ideas Tipo 2 con referencias de internet citadas', async ({ page }) => {
  await iniciarSesion(page)
  await irABandeja(page)

  await page.getByText(SOLICITUD_T2.asunto).click()
  await page.getByTestId('elegir-tipo-2').click()
  await expect(page).toHaveURL(new RegExp(`/bandeja/${SOLICITUD_T2.id}/chat$`))

  // Pedir internet dispara el aviso de sistema (gating de Tipo 2)…
  await page.getByTestId('javo-input').fill('Busca referencias en internet')
  await page.getByTestId('javo-enviar').click()
  await expect(page.getByText(/buscando referencias y opciones en internet/i)).toBeVisible()

  // …y la respuesta cita la fuente web.
  await expect(page.getByTestId('javo-mensaje').last()).toContainText('pit-stop')
  await expect(page.getByTestId('fuente-citada').first()).toContainText('Caso F1 Fanzone')
})
