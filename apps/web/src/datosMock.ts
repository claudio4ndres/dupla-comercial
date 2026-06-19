// Datos pendientes de migrar al backend: PROVEEDORES_CORREO

import type { OpcionProveedor } from './tipos'

/** Recurso (archivo) que el sistema consultaría en el Drive de la empresa. */
export interface RecursoDrive {
  icono: string
  nombre: string
}

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
