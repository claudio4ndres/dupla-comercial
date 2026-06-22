// Cliente del historial de conversación con Javo (T14).
//
// El backend (GET /conversaciones/{solicitudId}) devuelve el hilo persistido de esa
// solicitud (RLS por empresa). Se usa para REHIDRATAR el chat al abrir la solicitud:
// así la conversación sobrevive a un refresh / re-entrada. Si no hay hilo o el backend
// cae, devuelve [] y el chat parte desde el saludo de Javo.

import { cabecerasAuthAsync } from './auth'
import type { Componente, Fuente, Mensaje, Tarea, TipoConfirmado } from '../tipos'

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

// ── Sugerencias dinámicas (chips generados por Haiku) ────────────────────────

/** Obtiene 3 chips contextuales del backend (generados por Haiku). */
export async function obtenerSugerencias(
  solicitudId: string,
  tipo: TipoConfirmado,
): Promise<string[]> {
  try {
    const r = await fetch(`${API_BASE}/conversaciones/${solicitudId}/sugerencias`, {
      method: 'POST',
      headers: {
        ...(await cabecerasAuthAsync()),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ tipo }),
    })
    if (!r.ok) return []
    const data = (await r.json()) as { chips?: string[] }
    return data.chips ?? []
  } catch {
    return []
  }
}

// ── Iniciar conversación (saludo de Javo desde el backend) ───────────────────

/** Llama al backend para generar el saludo inicial de Javo según el tipo. */
export async function iniciarConversacion(
  solicitudId: string,
  tipo: TipoConfirmado,
): Promise<{ texto: string }> {
  const r = await fetch(`${API_BASE}/conversaciones/${solicitudId}/iniciar`, {
    method: 'POST',
    headers: {
      ...(await cabecerasAuthAsync()),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ tipo }),
  })
  if (!r.ok) throw new Error(`backend respondió ${r.status}`)
  return (await r.json()) as { texto: string }
}

/** Lee el hilo persistido de una solicitud. [] si no hay o si el backend no responde. */
export async function obtenerHistorialConversacion(solicitudId: string): Promise<Mensaje[]> {
  try {
    const r = await fetch(`${API_BASE}/conversaciones/${solicitudId}`, {
      headers: await cabecerasAuthAsync(),
    })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = (await r.json()) as { rol: string; contenido: string }[]
    return data.map((m) => ({ rol: m.rol as Mensaje['rol'], contenido: m.contenido }))
  } catch {
    return []
  }
}

// ── Borrador de la cotización en curso (0009) ────────────────────────────────
// El backend persiste, junto a la conversación, lo ÚLTIMO que Javo propuso
// (componentes/tareas) y citó (fuentes). Al rehidratar el chat, el front lee este
// borrador para REPOBLAR el panel (antes solo se rehidrataba el texto del hilo, y la
// cotización armada se perdía al recargar / re-entrar a la solicitud).

interface ComponenteBorradorBackend {
  nombre: string
  detalle: string | null
  cantidad: number
  dias: number | null
  valor_unitario: number | null
  proveedor: string | null
  origen: string | null
}

interface TareaBorradorBackend {
  nombre: string
  area: string
  plazo: string | null
  responsable: string | null
}

interface CotizacionBorradorBackend {
  componentes?: ComponenteBorradorBackend[]
  tareas?: TareaBorradorBackend[]
  fuentes?: Fuente[]
}

/** La cotización en curso ya mapeada a los tipos de la UI. */
export interface CotizacionEnCurso {
  componentes: Componente[]
  tareas: Tarea[]
  fuentes: Fuente[]
}

function aComponente(c: ComponenteBorradorBackend): Componente {
  return {
    nombre: c.nombre,
    detalle: c.detalle ?? '',
    cantidad: c.cantidad ?? 1,
    dias: c.dias ?? undefined,
    valor: c.valor_unitario ?? 0,
    proveedor: c.proveedor ?? undefined,
    origen: c.origen ?? undefined,
  }
}

function aTarea(t: TareaBorradorBackend): Tarea {
  return {
    nombre: t.nombre,
    area: t.area,
    responsable: t.responsable ?? '',
    plazo: t.plazo ?? '',
  }
}

/**
 * Lee el borrador de la cotización en curso de una solicitud (componentes/tareas/
 * fuentes). Si no hay borrador o el backend cae, devuelve una cotización vacía para
 * que el panel no se rompa (el chat parte sin cotización en curso).
 */
export async function obtenerCotizacionEnCurso(solicitudId: string): Promise<CotizacionEnCurso> {
  try {
    const r = await fetch(`${API_BASE}/conversaciones/${solicitudId}/cotizacion`, {
      headers: await cabecerasAuthAsync(),
    })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = (await r.json()) as CotizacionBorradorBackend
    return {
      componentes: (data.componentes ?? []).map(aComponente),
      tareas: (data.tareas ?? []).map(aTarea),
      fuentes: data.fuentes ?? [],
    }
  } catch {
    return { componentes: [], tareas: [], fuentes: [] }
  }
}
