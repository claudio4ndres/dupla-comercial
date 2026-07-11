// Spec 018 · EL flujo completo Tipo 1: bandeja → detalle → chat con Javo →
// componentes valorizados → propuesta → tareas → ClickUp → exports.
import { expect, test } from '@playwright/test'
import { SOLICITUD_T1, iniciarSesion, irABandeja } from './soporte'

test('cotización Tipo 1 de punta a punta', async ({ page }) => {
  await iniciarSesion(page)
  await irABandeja(page)

  // 1 · Abrir la solicitud → URL real /bandeja/:id (React Router).
  await page.getByText(SOLICITUD_T1.asunto).click()
  await expect(page).toHaveURL(new RegExp(`/bandeja/${SOLICITUD_T1.id}$`))
  await expect(page.getByText(SOLICITUD_T1.resumen!)).toBeVisible()

  // 2 · Confirmar Tipo 1 → chat en /bandeja/:id/chat con el saludo de Javo.
  await page.getByTestId('elegir-tipo-1').click()
  await expect(page).toHaveURL(new RegExp(`/bandeja/${SOLICITUD_T1.id}/chat$`))
  await expect(page.getByTestId('javo-mensaje').first()).toContainText('Partamos por el brief')

  // 3 · Chips comerciales generados por Haiku (mockeado).
  await expect(page.getByText('Dame 2 opciones de presupuesto')).toBeVisible()

  // 4 · Enviar un mensaje → Javo responde y arma los componentes valorizados.
  await page.getByTestId('javo-input').fill('Son 3 días, cotiza promotoras y catering')
  await page.getByTestId('javo-enviar').click()
  await expect(page.getByTestId('javo-mensaje').last()).toContainText('¿Genero la propuesta?')
  await expect(page.getByTestId('componente-item')).toHaveCount(2)
  await expect(page.getByText('$1.950.000').first()).toBeVisible() // venta con margen 40%
  await expect(page.getByTestId('fuente-citada').first()).toContainText('Tarifario BTL 2026.xlsx')

  // 5 · Generar propuesta → se persiste y navega a /propuestas/:id.
  await page.getByTestId('generar-propuesta').click()
  await expect(page).toHaveURL(new RegExp(`/propuestas/${SOLICITUD_T1.id}$`))
  await expect(page.getByRole('heading', { name: 'Propuesta resuelta' })).toBeVisible()
  await expect(page.getByText('Promotoras uniformadas')).toBeVisible()
  await expect(page.getByText('$1.950.000')).toBeVisible()
  await expect(page.getByText(/margen 40%/i)).toBeVisible()

  // 6 · Exports: la descarga se dispara con el nombre correcto.
  const descargaExcel = page.waitForEvent('download')
  await page.getByRole('button', { name: /excel interno/i }).click()
  expect((await descargaExcel).suggestedFilename()).toBe(
    `cotizacion-interno-${SOLICITUD_T1.id}.xlsx`,
  )
  const descargaPpt = page.waitForEvent('download')
  await page.getByRole('button', { name: /ppt/i }).click()
  expect((await descargaPpt).suggestedFilename()).toBe(`cotizacion-${SOLICITUD_T1.id}.pptx`)

  // 7 · Armar tareas → asignación por rol + envío a ClickUp.
  await page.getByRole('button', { name: /armar tareas/i }).click()
  await expect(page.getByRole('heading', { name: 'Tareas generadas' })).toBeVisible()
  await expect(page.getByText('Reclutar promotoras')).toBeVisible()
  await page.getByRole('button', { name: /enviar a clickup/i }).click()
  await expect(page.getByText(/2 tareas creadas en ClickUp/i)).toBeVisible()
})
