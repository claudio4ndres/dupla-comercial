// Cliente del chat con Javo (003 + 005).
//
// IMPORTANTE (regla de oro #3): el LLM se llama SOLO desde el backend. Aquí NO se
// toca `api.anthropic.com` ni hay API key: el front habla con nuestro FastAPI, y
// FastAPI habla con Claude (Sonnet) usando tool-use (Drive + internet).
//
// La respuesta de Javo trae el `texto` + los `componentes` que propuso (con su origen
// del Drive) + las `fuentes` que citó. Si el backend no responde, cae a una respuesta
// simulada (`respuestaFallback`) para que el demo siga.

import { cabecerasAuthAsync } from './auth'
import type { Componente, Fuente, Mensaje, Tarea, TipoConfirmado } from '../tipos'

// Base de la API. En dev se puede apuntar con VITE_API_URL; por defecto el proxy /api.
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

interface ComponenteBackend {
  nombre: string
  detalle: string | null
  cantidad: number
  dias: number | null
  valor_unitario: number | null
  proveedor: string | null
  origen: string | null
}

interface TareaBackend {
  nombre: string
  area: string
  plazo: string | null
  responsable: string | null
}

interface RespuestaJavoBackend {
  texto: string
  componentes?: ComponenteBackend[]
  tareas?: TareaBackend[]
  fuentes?: Fuente[]
}

/** Respuesta de Javo ya mapeada a los tipos de la UI. */
export interface RespuestaJavo {
  texto: string
  componentes: Componente[]
  tareas: Tarea[]
  fuentes: Fuente[]
}

function aComponente(c: ComponenteBackend): Componente {
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

function aTarea(t: TareaBackend): Tarea {
  return {
    nombre: t.nombre,
    area: t.area,
    responsable: t.responsable ?? '',
    plazo: t.plazo ?? '',
  }
}

/**
 * Envía la conversación al backend y devuelve la respuesta de Javo (texto +
 * componentes propuestos + fuentes). PROPAGA el error (patrón `...OError`) si el
 * backend no responde: la UI muestra el fallo con Reintentar (spec 014) — ya no
 * hay respuesta pregrabada que disfrace un backend caído.
 */
export async function conversarConJavoOError(params: {
  solicitudId: string
  tipo: TipoConfirmado
  mensajes: Mensaje[]
}): Promise<RespuestaJavo> {
  const r = await fetch(`${API_BASE}/conversaciones/responder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await cabecerasAuthAsync()) },
    body: JSON.stringify({
      solicitud_id: params.solicitudId,
      tipo: params.tipo,
      // No mandamos los mensajes de sistema (avisos de UI).
      mensajes: params.mensajes
        .filter((m) => m.rol !== 'sistema')
        .map((m) => ({ rol: m.rol, contenido: m.contenido })),
    }),
  })
  if (!r.ok) throw new Error(`backend respondió ${r.status}`)
  const data = (await r.json()) as RespuestaJavoBackend
  return {
    texto: data.texto?.trim() || '(sin respuesta)',
    componentes: (data.componentes ?? []).map(aComponente),
    tareas: (data.tareas ?? []).map(aTarea),
    fuentes: data.fuentes ?? [],
  }
}
