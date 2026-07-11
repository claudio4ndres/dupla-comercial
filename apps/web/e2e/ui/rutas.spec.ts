// Spec 018 · React Router v7 (spec 016): deep-links, refresh que rehidrata y 404.
import { expect, test } from '@playwright/test'
import { SOLICITUD_T1, estadoInicial, iniciarSesion, irABandeja } from './soporte'

test('deep-link a /bandeja/:id muestra el detalle sin pasar por la bandeja', async ({ page }) => {
  await iniciarSesion(page)
  await page.goto(`/bandeja/${SOLICITUD_T1.id}`)
  await expect(page.getByText(SOLICITUD_T1.resumen!)).toBeVisible()
  await expect(page.getByTestId('elegir-tipo-1')).toBeVisible()
})

test('deep-link a /bandeja/:id/chat rehidrata historial y panel persistidos', async ({ page }) => {
  const estado = estadoInicial()
  estado.historial[SOLICITUD_T1.id] = [
    { rol: 'javo', contenido: 'Retomemos: teníamos 6 promotoras por 3 días.' },
  ]
  estado.cotizacion[SOLICITUD_T1.id] = {
    componentes: [
      { nombre: 'Promotoras uniformadas', detalle: '3 tiendas', cantidad: 6, dias: 3, valor_unitario: 35000, proveedor: null, origen: null },
    ],
    tareas: [],
    fuentes: [],
  }
  await iniciarSesion(page, { estado })

  await page.goto(`/bandeja/${SOLICITUD_T1.id}/chat`)
  await expect(page.getByTestId('javo-mensaje').first()).toContainText('Retomemos')
  await expect(page.getByTestId('componente-item').first()).toContainText('Promotoras uniformadas')
})

test('refrescar el chat conserva la conversación (el bug A-1 del QA, resuelto)', async ({ page }) => {
  await iniciarSesion(page)
  await irABandeja(page)
  await page.getByText(SOLICITUD_T1.asunto).click()
  await page.getByTestId('elegir-tipo-1').click()
  await page.getByTestId('javo-input').fill('cotiza promotoras')
  await page.getByTestId('javo-enviar').click()
  await expect(page.getByTestId('componente-item').first()).toBeVisible()

  await page.reload()
  // El hilo y el panel vuelven desde el backend (mock con estado persistido).
  await expect(page.getByTestId('javo-mensaje').last()).toContainText('¿Genero la propuesta?')
  await expect(page.getByTestId('componente-item').first()).toBeVisible()
})

test('deep-link a /propuestas/:id repuebla la propuesta persistida', async ({ page }) => {
  const estado = await iniciarSesion(page)
  // Persistimos la propuesta simulando el flujo previo (POST del backend mockeado).
  await irABandeja(page)
  await page.getByText(SOLICITUD_T1.asunto).click()
  await page.getByTestId('elegir-tipo-1').click()
  await page.getByTestId('javo-input').fill('cotiza')
  await page.getByTestId('javo-enviar').click()
  await expect(page.getByTestId('componente-item').first()).toBeVisible()
  await page.getByTestId('generar-propuesta').click()
  await expect(page.getByRole('heading', { name: 'Propuesta resuelta' })).toBeVisible()
  expect(estado.propuestas[SOLICITUD_T1.id]).toBeTruthy()

  await page.reload()
  await expect(page.getByRole('heading', { name: 'Propuesta resuelta' })).toBeVisible()
  await expect(page.getByText('Promotoras uniformadas')).toBeVisible()
})

test('una URL desconocida muestra el 404 con vuelta a la bandeja', async ({ page }) => {
  await iniciarSesion(page)
  await page.goto('/una-ruta-que-no-existe')
  await expect(page.getByText(/volver a la bandeja/i)).toBeVisible()
})

test('el botón atrás del navegador funciona entre pantallas', async ({ page }) => {
  await iniciarSesion(page)
  await irABandeja(page)
  await page.getByText(SOLICITUD_T1.asunto).click()
  await expect(page).toHaveURL(new RegExp(`/bandeja/${SOLICITUD_T1.id}$`))

  await page.goBack()
  await expect(page).toHaveURL(/\/bandeja$/)
  await expect(page.getByRole('heading', { name: 'Bandeja de solicitudes' })).toBeVisible()
})
