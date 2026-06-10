// Cliente de la propuesta / cotización (004).
//
// El backend (GET /solicitudes/{id}/propuesta) devuelve la cotización resuelta:
// componentes valorizados + tareas, en la forma canónica en español. Aquí —la capa
// de API del front— se mapea a los tipos de la UI (`Componente`/`Tarea`), igual que
// hace `solicitudes.ts`. Si el backend no tiene propuesta (404) o cae, devolvemos
// `null` para que la UI use su fallback (la demo no se rompe).

import { cabecerasAuth } from './auth'
import type { Componente, Tarea } from '../tipos'

// Base de la API. En dev se apunta con VITE_API_URL; por defecto, el proxy /api.
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

interface ComponenteBackend {
  nombre: string
  detalle: string | null
  proveedor: string | null
  cantidad: number
  valor_unitario: number
}

interface TareaBackend {
  nombre: string
  grupo: string | null
  responsable: string | null
  vencimiento: string | null
}

interface PropuestaBackend {
  id: string
  total: number
  estado: string
  componentes: ComponenteBackend[]
  tareas: TareaBackend[]
}

/** La cotización ya mapeada a los tipos que consume la UI. */
export interface PropuestaResuelta {
  componentes: Componente[]
  tareas: Tarea[]
}

function aComponente(c: ComponenteBackend): Componente {
  return {
    nombre: c.nombre,
    detalle: c.detalle ?? '',
    proveedor: c.proveedor ?? undefined,
    cantidad: c.cantidad,
    valor: c.valor_unitario,
  }
}

function aTarea(t: TareaBackend): Tarea {
  return {
    nombre: t.nombre,
    area: t.grupo ?? '',
    responsable: t.responsable ?? '',
    plazo: t.vencimiento ?? '',
  }
}

/**
 * Lee la cotización real de una solicitud. Devuelve `null` si no hay propuesta
 * (404) o si el backend no responde, para que el front caiga a su fallback.
 */
export async function obtenerPropuesta(solicitudId: string): Promise<PropuestaResuelta | null> {
  try {
    const r = await fetch(`${API_BASE}/solicitudes/${solicitudId}/propuesta`, {
      headers: cabecerasAuth(),
    })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = (await r.json()) as PropuestaBackend
    return {
      componentes: data.componentes.map(aComponente),
      tareas: data.tareas.map(aTarea),
    }
  } catch {
    return null
  }
}
