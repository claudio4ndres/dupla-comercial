// Matchers de jest-dom (toBeInTheDocument, etc.) para todos los tests.
import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Con `isolate: false` todos los archivos comparten un mismo DOM (jsdom). Sin esto,
// los renders de un test quedan montados y "se filtran" al siguiente → errores
// "Found multiple elements". Desmontamos después de CADA test para aislarlos.
afterEach(() => {
  cleanup()
})
