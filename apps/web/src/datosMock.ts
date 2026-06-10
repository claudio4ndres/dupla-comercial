// Datos semilla para el demo (mock). Reemplazan a las llamadas reales:
//   - Bandeja  -> Gmail API (correos entrantes ya clasificados por Haiku)
//   - Componentes / valores -> Google Drive (tarifarios, costos)
//   - Tareas -> ClickUp API
// Mientras el backend no esté cableado, la UI corre 100% con esto.

import type { Componente, Empresa, OpcionProveedor, Tarea } from './tipos'

/** Recurso (archivo) que el sistema consultaría en el Drive de la empresa. */
export interface RecursoDrive {
  icono: string
  nombre: string
}

/** Componentes que Javo arma para la cotización Tipo 1 (valores del Drive). */
export const COMPONENTES_T1: Componente[] = [
  { nombre: 'Catering sopaipillas', detalle: 'Persona que prepara en sitio · 5h/día', cantidad: 1, valor: 120000 },
  { nombre: 'Promotores', detalle: 'Atención y entrega · 5h/día', cantidad: 2, valor: 65000 },
  { nombre: 'Producto e insumos', detalle: 'Sopaipillas + servilletas + bolsas', cantidad: 1, valor: 90000 },
  { nombre: 'Uniformes', detalle: 'Branding del cliente', cantidad: 2, valor: 18000 },
  { nombre: 'Coordinación producción', detalle: 'Logística + permisos', cantidad: 1, valor: 80000 },
]

/** Tareas que el sistema arma a partir de la propuesta (se disparan a ClickUp). */
export const TAREAS_T1: Tarea[] = [
  { nombre: 'Reclutar 2 promotores', area: 'RRHH', responsable: 'Coordinación', plazo: '3 días' },
  { nombre: 'Cotizar y contratar catering de sopaipillas', area: 'Producción', responsable: 'Javo', plazo: '2 días' },
  { nombre: 'Orden de compra de producto e insumos', area: 'Compras', responsable: 'Finanzas', plazo: '4 días' },
  { nombre: 'Diseñar y confeccionar uniformes con branding', area: 'Diseño', responsable: 'Estudio', plazo: '5 días' },
  { nombre: 'Gestionar permisos de activación en exterior', area: 'Legal', responsable: 'Coordinación', plazo: '6 días' },
  { nombre: 'Armar reporte y enviar propuesta al cliente', area: 'Comercial', responsable: 'Javo', plazo: '1 día' },
]

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
