// Datos semilla para el demo (mock). Reemplazan a las llamadas reales:
//   - Bandeja  -> Gmail API (correos entrantes ya clasificados por Haiku)
//   - Componentes / valores -> Google Drive (tarifarios, costos)
//   - Tareas -> ClickUp API
// Mientras el backend no esté cableado, la UI corre 100% con esto.

import type { Componente, Empresa, OpcionProveedor, Solicitud, Tarea } from './tipos'

/** Recurso (archivo) que el sistema consultaría en el Drive de la empresa. */
export interface RecursoDrive {
  icono: string
  nombre: string
}

/** Bandeja de solicitudes (orden de llegada). */
export const SOLICITUDES: Solicitud[] = [
  {
    id: 'espiga',
    remitente: 'Zona Espiga',
    correo: 'contacto@zonaespiga.cl',
    tiempo: '09:42',
    asunto: 'Cotización sampling de sopaipillas afuera del Metro',
    tipo: 't1',
    resumen:
      'Solicitud concreta de cotización para una activación de sampling: regalar sopaipillas afuera del Metro durante 5 horas diarias.',
    puntos: [
      'Activación tipo sampling en exterior (Metro)',
      '5 horas diarias',
      'Requieren catering, promotores, producto y uniforme',
      'Piden valores para evaluar',
    ],
    cuerpo: `Hola Javo, ¿cómo estás?

Queremos cotizar regalar sopaipillas afuera del Metro. La idea es una activación de sampling de 5 horas diarias.

Necesitamos el catering (alguien que haga las sopaipillas), un par de promotores, el producto y los uniformes. ¿Nos puedes pasar los valores para revisar el proyecto?

Saludos,
Equipo Zona Espiga`,
  },
  {
    id: 'f1',
    remitente: 'Fórmula 1 LATAM',
    correo: 'marketing@f1latam.com',
    tiempo: 'Ayer',
    asunto: 'Necesitamos ideas — activación Fórmula 1',
    tipo: 't2',
    resumen:
      'Solicitud creativa: el cliente está viendo la campaña de la Fórmula 1 y pide ideas de activación de alto impacto antes de definir el proyecto.',
    puntos: [
      'No hay brief cerrado todavía — buscan conceptos',
      'Campaña ligada a la Fórmula 1',
      'Quieren propuestas de alto impacto',
      'Hay que proponer ideas y luego definir acciones',
    ],
    cuerpo: `Hola Javo, ¿cómo está?

Estamos viendo la campaña de la Fórmula 1 y necesitamos ideas que nos puedas mandar para poder ver el proyecto.

Buscamos algo de alto impacto, que la gente recuerde. Quedamos atentos a lo que se te ocurra.

Saludos,
Marketing F1 LATAM`,
  },
  {
    id: 'narnia',
    remitente: 'Netflix · Narnia',
    correo: 'activaciones@partner.netflix.com',
    tiempo: '2 días',
    asunto: 'Activación estreno Narnia en cines (Octubre)',
    tipo: 'new',
    resumen:
      'Posible activación para el estreno de Narnia en cines durante octubre. Falta clasificar si es cotización concreta o pedido de ideas.',
    puntos: ['Estreno en cines · Octubre', 'Aún sin definir alcance', 'Por clasificar'],
    cuerpo: `Hola Javo,

Para el estreno de Narnia en octubre estamos pensando en algo en los cines. Te escribimos para empezar a conversar opciones.

Saludos.`,
  },
]

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

/** Empresas (tenants). La primera es la activa. White-label: cada una su color. */
export const EMPRESAS: Empresa[] = [
  { nombre: 'Capsulab', color: '#F04E37', marca: 'C', etiqueta: 'Plan piloto · BTL' },
  { nombre: 'Marca Demo', color: '#2c5fef', marca: 'M' },
  { nombre: 'Espiga', color: '#0E7C5A', marca: 'E' },
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

/** Archivos que el sistema mostraría desde el Drive de la empresa. */
export const RECURSOS_DRIVE: RecursoDrive[] = [
  { icono: '📄', nombre: 'Tarifario_promotores_2026.xlsx' },
  { icono: '📦', nombre: 'Costos_catering_sopaipilla.xlsx' },
  { icono: '🎽', nombre: 'Uniformes_proveedores.pdf' },
  { icono: '🏎️', nombre: 'Casos_activaciones_F1.pptx' },
]
