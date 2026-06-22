// Tests de propiedades (PBT) para las fórmulas puras de dominio.
// Valida costoLinea y valorVenta con entradas arbitrarias del rango de negocio.

import { test } from '@fast-check/vitest'
import fc from 'fast-check'
import { describe, expect } from 'vitest'
import { costoLinea, valorVenta, type Componente } from './tipos'

describe('costoLinea — PBT', () => {
  // Feature: tests-chat-propuesta, Property 1: Multiplicación exacta de costoLinea
  test.prop([
    fc.integer({ min: 1, max: 1000 }),
    fc.integer({ min: 1, max: 365 }),
    fc.integer({ min: 1, max: 10_000_000 }),
  ])(
    'costoLinea({ cantidad, dias, valor }) === cantidad × dias × valor',
    (cantidad, dias, valor) => {
      const c: Componente = { nombre: 'test', detalle: '', cantidad, valor, dias }
      expect(costoLinea(c)).toBe(cantidad * dias * valor)
    },
  )

  // Feature: tests-chat-propuesta, Property 5: Idempotencia del valor por defecto de dias
  test.prop([
    fc.integer({ min: 1, max: 1000 }),
    fc.integer({ min: 1, max: 10_000_000 }),
  ])(
    'costoLinea({ dias: undefined }) === costoLinea({ dias: 1 })',
    (cantidad, valor) => {
      const sinDias: Componente = { nombre: 'x', detalle: '', cantidad, valor }
      const conUnDia: Componente = { nombre: 'x', detalle: '', cantidad, valor, dias: 1 }
      expect(costoLinea(sinDias)).toBe(costoLinea(conUnDia))
    },
  )
})

describe('valorVenta — PBT', () => {
  // Feature: tests-chat-propuesta, Property 2: El margen de venta siempre incrementa el precio
  test.prop([fc.integer({ min: 0, max: 100_000_000 })])(
    'valorVenta(costo) >= costo',
    (costo) => {
      expect(valorVenta(costo)).toBeGreaterThanOrEqual(costo)
    },
  )

  // Feature: tests-chat-propuesta, Property 3: valorVenta produce siempre un número entero
  test.prop([fc.integer({ min: 0, max: 100_000_000 })])(
    'Number.isInteger(valorVenta(costo))',
    (costo) => {
      expect(Number.isInteger(valorVenta(costo))).toBe(true)
    },
  )
})
