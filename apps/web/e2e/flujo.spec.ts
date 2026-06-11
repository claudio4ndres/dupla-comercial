import { test, expect } from '@playwright/test'

const CORREO = 'javier@capsulab.cl'
const PASSWORD = 'capsulab2024'

/** Navega en el sidebar al ítem exacto por texto del nav-item. */
async function irA(page: Parameters<typeof test>[1] extends (args: { page: infer P }) => unknown ? P : never, etiqueta: string) {
  await page.locator('.nav-item', { hasText: new RegExp(`^${etiqueta}`) }).click()
}

test.describe('Login', () => {
  test('muestra el formulario de acceso', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Dupla Comercial')).toBeVisible()
    await expect(page.getByPlaceholder('tu@empresa.cl')).toBeVisible()
  })

  test('muestra error con credenciales incorrectas', async ({ page }) => {
    await page.goto('/')
    await page.getByPlaceholder('tu@empresa.cl').fill('malo@test.cl')
    await page.getByPlaceholder('••••••••').fill('wrongpassword')
    await page.getByRole('button', { name: 'Entrar' }).click()
    await expect(page.getByRole('alert')).toBeVisible()
  })

  test('inicia sesión con credenciales correctas', async ({ page }) => {
    await page.goto('/')
    await page.getByPlaceholder('tu@empresa.cl').fill(CORREO)
    await page.getByPlaceholder('••••••••').fill(PASSWORD)
    await page.getByRole('button', { name: 'Entrar' }).click()
    await expect(page.getByRole('heading', { name: 'Prepara tu espacio' })).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Flujo principal (requiere sesión)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.getByPlaceholder('tu@empresa.cl').fill(CORREO)
    await page.getByPlaceholder('••••••••').fill(PASSWORD)
    await page.getByRole('button', { name: 'Entrar' }).click()
    await expect(page.getByRole('heading', { name: 'Prepara tu espacio' })).toBeVisible({ timeout: 10000 })
  })

  test('Configuracion: muestra conectores de Gmail y ClickUp', async ({ page }) => {
    await expect(page.getByText('Correo · Gmail')).toBeVisible()
    await expect(page.getByText('Gestor de tareas · ClickUp')).toBeVisible()
    await expect(page.getByText('Gestor de tareas · Jira')).toBeVisible()
  })

  test('Configuracion: botón Continuar va a Bandeja', async ({ page }) => {
    await page.getByRole('button', { name: /Continuar a la bandeja/i }).click()
    await expect(page.getByRole('heading', { name: 'Bandeja de solicitudes' })).toBeVisible()
  })

  test('navega a Bandeja desde sidebar', async ({ page }) => {
    await irA(page, 'Bandeja')
    await expect(page.getByRole('heading', { name: 'Bandeja de solicitudes' })).toBeVisible()
  })

  test('Bandeja sin correo: muestra opción de conectar o estado conectado', async ({ page }) => {
    await irA(page, 'Bandeja')
    const hayConectar = await page.getByText('Conecta tu bandeja').isVisible().catch(() => false)
    const hayEscuchando = await page.locator('.listening').isVisible().catch(() => false)
    expect(hayConectar || hayEscuchando).toBe(true)
  })

  test('navega a Propuestas desde sidebar', async ({ page }) => {
    await page.locator('.nav-item', { hasText: 'Propuestas' }).click()
    await expect(page.locator('.sidebar .nav-item.active')).toContainText('Propuestas')
  })

  test('navega a Tareas desde sidebar', async ({ page }) => {
    await page.locator('.nav-item', { hasText: /^Tareas/ }).click()
    await expect(page.locator('.sidebar .nav-item.active')).toContainText('Tareas')
  })
})
