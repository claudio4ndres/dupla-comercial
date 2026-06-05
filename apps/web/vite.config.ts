/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Puerto fijo propio: el 5173 (default de Vite) ya lo usa otro proyecto.
  // strictPort: si 5174 está ocupado, falla en vez de saltar a otro puerto.
  server: { port: 5174, strictPort: true },
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
    isolate: false,
  },
})
