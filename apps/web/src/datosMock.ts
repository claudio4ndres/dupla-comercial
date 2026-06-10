// Datos semilla para el demo (mock). Reemplazan a las llamadas reales:
//   - Bandeja  -> Gmail API (correos entrantes ya clasificados por Haiku)
//   - Componentes / valores -> Google Drive (tarifarios, costos)
//   - Tareas -> ClickUp API
// Mientras el backend no esté cableado, la UI corre 100% con esto.

import type { Empresa, OpcionProveedor } from './tipos'

/** Recurso (archivo) que el sistema consultaría en el Drive de la empresa. */
export interface RecursoDrive {
  icono: string
  nombre: string
}

/**
 * Empresas (tenants). La primera es la activa. White-label: cada una su color.
 * Sólo Capsulab: es la única con datos reales y RLS del usuario piloto. Las
 * empresas de demo se quitaron porque al cambiarlas la bandeja quedaba vacía.
 */
export const EMPRESAS: Empresa[] = [
  { nombre: 'Capsulab', color: '#F04E37', marca: 'C', etiqueta: 'Plan piloto · BTL' },
]

/**
 * Proveedores de correo que la empresa puede conectar a su bandeja.
 * Por ahora es solo la UI de selección; la conexión real (OAuth Gmail /
 * Microsoft Graph / IMAP) y la escucha de correos entrantes se cablean en el
 * backend más adelante.
 */
export const PROVEEDORES_CORREO: OpcionProveedor[] = [
  { id: 'gmail', nombre: 'Gmail', icono: '📧' },
  { id: 'outlook', nombre: 'Outlook', icono: '📨' },
  { id: 'imap', nombre: 'Otro (IMAP)', icono: '✉️' },
]
