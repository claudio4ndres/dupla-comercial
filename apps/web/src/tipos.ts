// Tipos del frontend. Nombres en español (regla de oro del proyecto).
// El modelo refleja el prototipo: solicitudes que llegan por correo, que el
// humano clasifica en Tipo 1 (cotización) o Tipo 2 (ideas), conversa con Javo
// y baja a propuesta + tareas.
//
// Nota: la UI usa los valores cortos `t1`/`t2`/`new` porque coinciden con las
// clases CSS del prototipo (.badge.t1, .type-card.t2…). Cuando se conecte el
// backend, se mapean con la enum de la tabla `solicitudes`
// (tipo_1 / tipo_2 / sin_clasificar) en la capa de API.

/** Clasificación de una solicitud. `new` = aún sin clasificar. */
export type TipoSolicitud = 't1' | 't2' | 'new'

/** Tipo confirmado por el humano para empezar a conversar (no existe `new`). */
export type TipoConfirmado = 't1' | 't2'

export interface Solicitud {
  id: string
  remitente: string // empresa/persona que escribe
  correo: string // dirección de correo
  tiempo: string // "09:42", "Ayer", "2 días"
  asunto: string
  /** Clasificación sugerida; la decisión final la confirma el humano (CA4). */
  tipo: TipoSolicitud
  resumen: string // una o dos frases (el "qué")
  puntos: string[] // bullets del resumen
  /** Cuerpo original del correo (Javier pidió poder verlo completo). */
  cuerpo: string
}

export interface Componente {
  nombre: string
  detalle: string
  cantidad: number
  valor: number // TARIFA POR DÍA por unidad en CLP (modelo Fuchs, T17)
  dias?: number // días de la partida; costo = cantidad × días × valor (default 1)
  origen?: string // recurso del Drive de donde salió el valor (005)
  proveedor?: string // quién provee la partida (catering, promotores…) — Excel (007)
}

/** Origen citable de un dato que usó Javo: recurso del Drive o resultado web (005). */
export interface Fuente {
  titulo: string
  referencia: string
}

export interface Tarea {
  nombre: string
  area: string // RRHH, Producción, Compras, Diseño, Legal, Comercial…
  responsable: string
  plazo: string
}

export interface Empresa {
  nombre: string
  color: string // color de marca (white-label)
  marca: string // inicial que se muestra en el cuadro
  etiqueta?: string // plan / segmento
}

/** Proveedor de correo que la empresa conecta a su bandeja. */
export type ProveedorCorreo = 'gmail' | 'outlook' | 'imap'

/** Opción de proveedor que se ofrece en la bandeja para conectar. */
export interface OpcionProveedor {
  id: ProveedorCorreo
  nombre: string
  icono: string // emoji por ahora; luego el logo real del proveedor
}

/**
 * Sesión iniciada. Hoy es un mock (cualquier credencial entra al demo);
 * más adelante lo respalda Supabase Auth y trae el `empresa_id` para RLS.
 */
export interface Sesion {
  correo: string
}

/** Mensaje en la conversación con Javo. */
export interface Mensaje {
  rol: 'usuario' | 'javo' | 'sistema'
  contenido: string
}

/** Pantallas de la app (router simple por estado).
 * `configuracion` = onboarding post-login para conectar los conectores de la
 * empresa (correo + gestor de tareas); `propuestas` (plural) = lista de
 * propuestas del menú; `propuesta` (singular) = detalle de una (la cotización
 * que viene del chat). */
export type Pantalla = 'configuracion' | 'inbox' | 'detail' | 'chat' | 'propuestas' | 'propuesta' | 'tareas'

/** Etiqueta corta para el badge de la bandeja. */
export const ETIQUETA_TIPO: Record<TipoSolicitud, string> = {
  t1: 'Tipo 1 · Cotización',
  t2: 'Tipo 2 · Creativa',
  new: 'Sin clasificar',
}

/** Etiqueta larga (pantalla de detalle / sugerencia). */
export const ETIQUETA_TIPO_LARGA: Record<TipoSolicitud, string> = {
  t1: 'Tipo 1 · Cotización concreta',
  t2: 'Tipo 2 · Ideas / propuesta creativa',
  new: 'Sin clasificar',
}

/** Nombre visible de cada proveedor de correo (para la etiqueta "Escuchando · …"). */
export const NOMBRE_PROVEEDOR: Record<ProveedorCorreo, string> = {
  gmail: 'Gmail',
  outlook: 'Outlook',
  imap: 'Otro (IMAP)',
}

/** Formatea un monto en pesos chilenos. */
export const fmtCLP = (n: number): string => '$' + n.toLocaleString('es-CL')

// --- Precios de la cotización (T16/T17) -------------------------------------
// `valor` de cada componente es el COSTO (tarifa por día por unidad). El costo de la
// línea es cantidad × días × valor. El precio de VENTA aplica el margen por defecto.
/** Margen de venta por defecto (40%): VALOR VENTA = costo / (1 − margen). */
export const MARGEN_VENTA = 0.4
/** Costo de una línea: cantidad × días × tarifa/día (días = 1 si no viene). */
export const costoLinea = (c: Componente): number => c.cantidad * (c.dias ?? 1) * c.valor
/** Precio de venta a partir del costo, con el margen por defecto. */
export const valorVenta = (costo: number): number => Math.round(costo / (1 - MARGEN_VENTA))
