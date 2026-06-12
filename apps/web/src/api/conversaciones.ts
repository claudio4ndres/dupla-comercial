// Cliente del historial de conversación con Javo (T14).
//
// El backend (GET /conversaciones/{solicitudId}) devuelve el hilo persistido de esa
// solicitud (RLS por empresa). Se usa para REHIDRATAR el chat al abrir la solicitud:
// así la conversación sobrevive a un refresh / re-entrada. Si no hay hilo o el backend
// cae, devuelve [] y el chat parte desde el saludo de Javo.

import { cabecerasAuthAsync } from './auth'
import type { Mensaje } from '../tipos'

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

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
