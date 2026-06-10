/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import { configDefaults } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// ── Dirección del backend local ──────────────────────────────────────────────
// Aquí (y SOLO aquí) se define dónde vive el backend FastAPI en desarrollo.
// Para apuntarlo a otro host/puerto, cambia esta única línea.
//
// Usamos 127.0.0.1 a propósito (NO "localhost"): uvicorn escucha en IPv4, y
// "localhost" puede resolver primero a IPv6 (::1), dejando el proxy sin conexión
// aunque el backend esté arriba. 127.0.0.1 va directo al IPv4 correcto.
const BACKEND_LOCAL = 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Puerto fijo propio: el 5173 (default de Vite) ya lo usa otro proyecto.
  // strictPort: si 5174 está ocupado, falla en vez de saltar a otro puerto.
  //
  // proxy `/api` → backend (BACKEND_LOCAL). El front pide rutas RELATIVAS
  // (`/api/...`, ver `API_BASE` en src/api/*.ts) y Vite las reenvía al backend
  // del lado del servidor: así NO hay CORS en dev y no hace falta `VITE_API_URL`.
  // `rewrite` quita el prefijo `/api` porque el backend expone `/solicitudes`,
  // `/gmail/...` sin ese prefijo.
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': {
        target: BACKEND_LOCAL,
        changeOrigin: true,
        rewrite: (ruta) => ruta.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: true,
    // Sandbox: los workers tipo `fork` (IPC de child_process) no arrancan
    // ("Timeout waiting for worker to respond"). Los `threads` usan
    // worker_threads (MessageChannel en memoria) y sí arrancan. Sintaxis
    // Vitest 4: opciones top-level (poolOptions fue removido).
    pool: 'threads',
    fileParallelism: false,
    // Los tests e2e son de Playwright (corren con `playwright.config.ts`, no con
    // vitest); se excluyen para que vitest no intente levantarlos.
    exclude: [...configDefaults.exclude, 'e2e/**'],
    // isolate: true (default) → cada archivo de test corre con su propio registro de
    // módulos. Necesario porque varios archivos usan `vi.mock('./supabase/cliente')`;
    // con isolate:false los mocks se filtran entre archivos y se rompen entre sí.
    isolate: true,
  },
})
