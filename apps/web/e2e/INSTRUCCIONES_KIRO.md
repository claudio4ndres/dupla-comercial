# Instrucciones para Kiro — Automatizar el e2e con Playwright

> Objetivo: reproducir con Playwright **todo el flujo del front** de Dupla Comercial,
> el mismo que hoy se valida a mano en el navegador:
>
> **login → (Gmail ya conectado) → bandeja con correos reales → abrir un correo →
> elegir Tipo 1/2 → conversar con Javo → Javo busca y LEE el Drive real → armar la
> cotización → generar la propuesta → tareas.**

---

## 1. Lo que YA existe — extiéndelo, no lo rehagas

- `@playwright/test` **1.49** instalado (`apps/web`).
- `apps/web/playwright.config.ts` → `baseURL: http://localhost:5174`, `headless`, `webServer: npm run dev` (reuseExistingServer).
- `apps/web/e2e/flujo.spec.ts` → cubre login + navegación por el sidebar. Usa selectores por **texto/clase** (frágiles).
- Scripts: `npm run test:e2e`, `npm run test:e2e:ui`.
- Env del front: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.

---

## 2. Decisiones clave — LÉELAS antes de codear

### 2.1 NO automatices el OAuth de Google/Gmail
Es frágil (bot-detection de Google, 2FA, pantalla de consentimiento) y **innecesario**:
la integración de Gmail **ya está conectada del lado servidor** para el tenant de prueba.
El refresh token vive en **Secret Manager** + una fila en la tabla `integraciones`; el front
solo lee el **estado**. El test debe **loguearse en la app** y **verificar que Gmail muestra
"Conectado"**. "Conectarse a Gmail" es un paso **manual, único, ya hecho**.
→ Si alguna vez hay que reconectar, se hace a mano UNA vez; nunca dentro del test.

### 2.2 Sesión de la app (Supabase) con `storageState` — login UNA sola vez
Usa un *project* `setup` que se loguea y guarda `storageState` (el `localStorage` con la
sesión de Supabase). Los demás specs **reusan** ese estado → sin re-login, rápido y estable.
(El front refresca el access token solo, así que la sesión persiste.)

### 2.3 Corre contra el ambiente donde Gmail está conectado
El flujo real (Gmail + Javo/Sonnet + Drive) vive en **prod/staging**, no en local.
Parametriza por env, NO hardcodees credenciales:
- `E2E_BASE_URL` (ej. la URL de Cloud Run), `E2E_EMAIL`, `E2E_PASSWORD`.
- En local con seed: `javier@capsulab.cl` / `capsulab2024`, **pero** ahí Gmail no está
  realmente conectado (no hay correos reales ni Javo con LLM real apuntando a un tenant vivo).

### 2.4 Esperas del LLM — lo MÁS importante
La conversación con Javo es asíncrona y lenta (Sonnet + búsqueda en Drive/web tardan 30–90s).
- **Nunca** `waitForTimeout` fijos.
- Espera por el **indicador "escribiendo/buscando"** que **aparece y luego DESAPARECE**,
  o por el elemento de resultado (un bubble nuevo de Javo / el panel de Componentes poblado /
  una Fuente citada).
- Timeouts generosos: **60s** para un turno normal, **90s** para uno con búsqueda en internet.
- **Afirma ESTRUCTURA, no el texto del LLM** (varía cada vez):
  - ✅ "apareció un bubble nuevo de Javo", "hay ≥1 Fuente citada", "el panel tiene ≥1 componente".
  - ❌ `toContainText('valla publicitaria $2.500.000')` — se rompe siempre.

---

## 3. Agrega `data-testid` al front (hoy hay 0)

Los selectores por texto se rompen con el LLM. Agrega estos `data-testid` (grep el texto/clase
actual de cada elemento para ubicarlo):

| Elemento | `data-testid` | Componente probable |
|---|---|---|
| Input email (login) | `login-email` | `Login.tsx` |
| Input password | `login-password` | `Login.tsx` |
| Botón Entrar | `login-submit` | `Login.tsx` |
| Estado del conector Gmail | `conector-gmail` | `Configuracion.tsx` |
| Botón "Continuar a la bandeja" | `ir-a-bandeja` | `Configuracion.tsx` |
| Banner "Escuchando nuevos correos" | `bandeja-estado` | `Bandeja.tsx` |
| Cada tarjeta de correo | `solicitud-card` | `Bandeja.tsx` |
| Card "Tipo 1 · Cotización" | `elegir-tipo-1` | `DetalleSolicitud.tsx` |
| Card "Tipo 2 · Ideas" | `elegir-tipo-2` | `DetalleSolicitud.tsx` |
| Input del chat | `javo-input` | `Chat.tsx` |
| Botón Enviar | `javo-enviar` | `Chat.tsx` |
| Indicador escribiendo/buscando | `javo-pensando` | `Chat.tsx` |
| Cada bubble de Javo | `javo-mensaje` | `Chat.tsx` |
| Cada item del panel Componentes | `componente-item` | panel del chat |
| Botón "Generar propuesta" | `generar-propuesta` | panel del chat |
| Cada Fuente citada | `fuente-citada` | panel/chat |
| Cada Recurso del Drive | `recurso-drive` | panel del chat |

> Si prefieres no tocar el front, se puede con `getByRole`/`getByText`, pero los testid son
> mucho más estables — recomendado agregarlos.

---

## 4. Config Playwright (ajústala)

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,            // turnos de LLM largos
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5174',
    headless: true,
    trace: 'on-first-retry',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'flujo',
      dependencies: ['setup'],
      use: { storageState: 'e2e/.auth/usuario.json' },
    },
  ],
  // Sin webServer cuando E2E_BASE_URL apunta a prod; solo en local.
})
```

---

## 5. Specs a escribir

### 5.1 `e2e/auth.setup.ts` — login + guardar storageState
```ts
import { test as setup, expect } from '@playwright/test'

setup('login', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('login-email').fill(process.env.E2E_EMAIL!)
  await page.getByTestId('login-password').fill(process.env.E2E_PASSWORD!)
  await page.getByTestId('login-submit').click()
  await expect(page.getByRole('heading', { name: 'Prepara tu espacio' }))
    .toBeVisible({ timeout: 15_000 })
  await page.context().storageState({ path: 'e2e/.auth/usuario.json' })
})
```

### 5.2 `e2e/bandeja.spec.ts` — Gmail conectado + correos reales
```ts
import { test, expect } from '@playwright/test'

test('Gmail conectado y la bandeja lista correos', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('conector-gmail')).toContainText('Conectado')
  await page.getByTestId('ir-a-bandeja').click()
  await expect(page.getByRole('heading', { name: 'Bandeja de solicitudes' })).toBeVisible()
  await expect(page.getByTestId('bandeja-estado')).toContainText('Escuchando')
  await expect(page.getByTestId('solicitud-card').first()).toBeVisible()
  expect(await page.getByTestId('solicitud-card').count()).toBeGreaterThan(0)
})
```

### 5.3 `e2e/javo-tipo1-drive.spec.ts` — Javo lee el Drive real (#1) + propuesta sin duplicados (#4)
```ts
import { test, expect } from '@playwright/test'
import { esperarRespuestaJavo, abrirCorreoPorAsunto } from './helpers'

test('Javo busca y lee un documento real del Drive y lo cita', async ({ page }) => {
  await abrirCorreoPorAsunto(page, /Lanzamiento/i)   // abre un correo Tipo 1
  await page.getByTestId('elegir-tipo-1').click()
  await esperarRespuestaJavo(page)                   // saludo inicial de Javo

  await page.getByTestId('javo-input').fill(
    "Busca en mi Drive el documento 'Matriz Contenido Web Capsulab 2025', ábrelo y dime qué contiene."
  )
  await page.getByTestId('javo-enviar').click()
  await esperarRespuestaJavo(page, { timeout: 90_000 })

  // Estructura, no texto: Javo respondió y citó al menos una fuente del Drive.
  await expect(page.getByTestId('javo-mensaje').last()).toBeVisible()
  await expect(page.getByTestId('fuente-citada').first()).toBeVisible()
})

test('Generar propuesta no duplica al re-generar (#4)', async ({ page }) => {
  await abrirCorreoPorAsunto(page, /Lanzamiento/i)
  await page.getByTestId('elegir-tipo-1').click()
  await page.getByTestId('javo-input').fill('Arma los componentes y las tareas para generar la propuesta.')
  await page.getByTestId('javo-enviar').click()
  await esperarRespuestaJavo(page)
  await expect(page.getByTestId('componente-item').first()).toBeVisible({ timeout: 30_000 })

  await page.getByTestId('generar-propuesta').click()
  await page.getByTestId('generar-propuesta').click()  // doble click / re-generar

  // En Propuestas debe haber UNA sola para esta solicitud (no duplicada).
  await page.locator('.nav-item', { hasText: 'Propuestas' }).click()
  // afirma el conteo de la propuesta de esa solicitud == 1 (ajusta el selector de fila)
})
```

### 5.4 `e2e/javo-tipo2-internet.spec.ts` — Tipo 2 busca en internet de verdad (#2)
```ts
import { test, expect } from '@playwright/test'
import { esperarRespuestaJavo, abrirCorreoPorAsunto } from './helpers'

test('Tipo 2: Javo busca referencias reales en internet y las cita', async ({ page }) => {
  await abrirCorreoPorAsunto(page, /Lanzamiento|Procarne/i)
  await page.getByTestId('elegir-tipo-2').click()
  await esperarRespuestaJavo(page)

  await page.getByTestId('javo-input').fill(
    'Busca en internet referencias reales de campañas de lanzamiento de fragancias. Pásame links.'
  )
  await page.getByTestId('javo-enviar').click()
  await esperarRespuestaJavo(page, { timeout: 90_000 })  // el web search es lento

  // Estructura: respondió y citó ≥1 fuente con URL http (resultado web real).
  await expect(page.getByTestId('javo-mensaje').last()).toBeVisible()
  const fuentes = page.getByTestId('fuente-citada')
  await expect(fuentes.first()).toBeVisible()
  // opcional: alguna fuente con href http
  // expect(await fuentes.getByRole('link').first().getAttribute('href')).toMatch(/^https?:\/\//)
})
```

### 5.5 `e2e/helpers.ts`
```ts
import { Page, expect } from '@playwright/test'

/** Espera a que Javo termine un turno: el indicador aparece y luego desaparece. */
export async function esperarRespuestaJavo(page: Page, { timeout = 60_000 } = {}) {
  const pensando = page.getByTestId('javo-pensando')
  await pensando.waitFor({ state: 'visible', timeout: 5_000 }).catch(() => {})
  await pensando.waitFor({ state: 'hidden', timeout })
}

/** Abre un correo de la bandeja por su asunto (regex). */
export async function abrirCorreoPorAsunto(page: Page, asunto: RegExp) {
  await page.goto('/')
  await page.getByTestId('ir-a-bandeja').click().catch(() => {})  // si está en onboarding
  await page.locator('.nav-item', { hasText: /^Bandeja/ }).click().catch(() => {})
  await page.getByTestId('solicitud-card').filter({ hasText: asunto }).first().click()
}
```

---

## 6. Cómo correr

```bash
cd apps/web
# instalar navegadores la primera vez
npx playwright install --with-deps chromium

# contra prod (Gmail conectado para el tenant de prueba)
E2E_BASE_URL="https://<tu-cloud-run>.run.app" \
E2E_EMAIL="<usuario>" E2E_PASSWORD="<pass>" \
  npm run test:e2e

# modo visual
... npm run test:e2e:ui
```

---

## 7. Caveats (sé honesto con esto)

- Contra **prod**, estos son **tests de humo e2e**, NO deterministas al 100%: dependen de que
  Gmail siga conectado, haya correos ingeridos y Javo (Sonnet) responda. Por eso se afirma
  **estructura**, no texto.
- Si quieres **determinismo total** (CI verde siempre), agrega un **modo test** en el backend
  que devuelva respuestas de Javo fijas (un flag/env que mockee el LLM y el Drive). Eso prueba
  el wiring del front, pero ya no el LLM real — son dos objetivos distintos; ten ambos.
- La búsqueda en internet (Tipo 2) puede tardar **>60s**; usa el timeout de 90s.

## 8. Apéndice — si DE VERDAD necesitas automatizar el OAuth de Google (no recomendado)

Google bloquea logins automatizados/headless con frecuencia. Si es imprescindible:
- Usa una **cuenta de prueba dedicada** sin 2FA.
- Usa un **`launchPersistentContext`** con un perfil de Chrome **ya autorizado una vez a mano**
  (reusa cookies de Google), en modo **headed**.
- Maneja la pantalla de consentimiento por selectores (cambian seguido → frágil).
- Aun así, espera flakiness. **Mejor**: deja Gmail conectado a mano (one-time) y no lo toques
  en el test (sección 2.1).
