// Cliente de la bandeja de solicitudes (los correos que el poller ingirió).
//
// El backend devuelve la forma canónica en español (`tipo_1`/`tipo_2`/
// `sin_clasificar`); aquí —la capa de API del front— se mapea a los códigos
// cortos de la UI (`t1`/`t2`/`new`), que coinciden con las clases CSS del
// prototipo. Así el resto del front sigue hablando su propio dialecto.

import { cabecerasAuth } from './auth'
import type { Solicitud, TipoSolicitud } from '../tipos'

// Base de la API. En dev se apunta con VITE_API_URL; por defecto, el proxy /api.
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

/** Forma plana que expone el backend en GET /solicitudes (nunca trae empresa_id). */
interface SolicitudBackend {
  id: string
  remitente: string
  correo_origen: string | null
  asunto: string
  cuerpo: string
  resumen: string | null
  tipo: string // 'sin_clasificar' | 'tipo_1' | 'tipo_2'
  estado: string
  recibido_en: string | null // ISO 8601 (de `creado_en`); null si la fila no la trae.
}

/** Mapea la enum canónica de la tabla `solicitudes` al código corto de la UI. */
const MAPA_TIPO: Record<string, TipoSolicitud> = {
  tipo_1: 't1',
  tipo_2: 't2',
  sin_clasificar: 'new',
}

/**
 * Formatea la fecha de recepción (ISO) para la tarjeta de la bandeja: día + mes
 * corto en español de Chile (ej. "09-jun"). Sin fecha o fecha inválida → ''.
 */
function formatearFecha(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('es-CL', { day: '2-digit', month: 'short' })
}

function aSolicitud(s: SolicitudBackend): Solicitud {
  return {
    id: s.id,
    remitente: s.remitente || s.correo_origen || '(sin remitente)',
    correo: s.correo_origen ?? '',
    tiempo: formatearFecha(s.recibido_en), // fecha del correo (de `creado_en`).
    asunto: s.asunto,
    tipo: MAPA_TIPO[s.tipo] ?? 'new',
    resumen: s.resumen ?? '',
    puntos: [], // sin bullets todavía: se llenarán al clasificar/resumir.
    cuerpo: s.cuerpo,
  }
}

/**
 * Lee las solicitudes reales de la empresa desde el backend. Si el backend no
 * responde (caído o aún sin cablear), cae a lista vacía para no romper el demo.
 */
export async function obtenerSolicitudes(): Promise<Solicitud[]> {
  try {
    const r = await fetch(`${API_BASE}/solicitudes`, { headers: cabecerasAuth() })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = (await r.json()) as SolicitudBackend[]
    return data.map(aSolicitud)
  } catch {
    return []
  }
}
