// Cliente del conector ClickUp (enviar las tareas de la propuesta a ClickUp).
//
// IMPORTANTE (regla de oro #3): el token de ClickUp vive SOLO en el backend; el front
// nunca lo toca. Aquí el front habla con nuestro FastAPI, que a su vez habla con la API
// de ClickUp. Dos operaciones:
//   * `listarListasClickUp()` → puebla el SELECTOR de lista destino (las listas reales
//     del usuario). Sin token configurado el backend devuelve [] → el front muestra el
//     aviso "Conecta ClickUp". Ante cualquier fallo, también [] (no rompe la pantalla).
//   * `enviarTareasAClickUp(solicitudId, listaId)` → crea las tareas de la propuesta en
//     la lista elegida y devuelve `{creadas}`; ante error, `null` (igual que solicitudes.ts).

import { cabecerasAuth } from './auth'

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

/** Una lista de ClickUp para el selector de destino (forma plana del backend). */
export interface ListaClickUp {
  id: string
  nombre: string
  espacio: string
}

/**
 * Lee las listas reales del ClickUp de la empresa desde el backend. Si no hay token
 * configurado el backend responde [] (el front muestra "conecta ClickUp"); ante
 * cualquier otro fallo (502, red caída) también devuelve [] para no romper la UI.
 */
export async function listarListasClickUp(): Promise<ListaClickUp[]> {
  try {
    const r = await fetch(`${API_BASE}/clickup/listas`, { headers: cabecerasAuth() })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = await r.json()
    // Defensa: si el backend devolviera algo inesperado, no rompemos el selector.
    return Array.isArray(data) ? (data as ListaClickUp[]) : []
  } catch {
    return []
  }
}

/**
 * Crea las tareas de la propuesta como tareas reales en ClickUp, en la lista elegida.
 * `listaId` vacío → no se manda y el backend usa su lista por defecto (fallback).
 * `asignados` (opcional, 0006) es el mapa nombre_de_tarea → persona asignada que el
 * usuario eligió en el selector de la pantalla de Tareas; viaja en el cuerpo JSON y el
 * backend lo pone en la descripción de cada tarea. Devuelve `{creadas: N}` si todo
 * salió bien, o `null` ante error (sin lista → 400, sin propuesta → 404, ClickUp caído
 * → 502, red caída) — sin romper la UI.
 */
export async function enviarTareasAClickUp(
  solicitudId: string,
  listaId: string,
  asignados: Record<string, string> = {},
): Promise<{ creadas: number } | null> {
  try {
    const qs = listaId ? `?lista_id=${encodeURIComponent(listaId)}` : ''
    const r = await fetch(`${API_BASE}/solicitudes/${solicitudId}/tareas/clickup${qs}`, {
      method: 'POST',
      // Content-Type explícito: mandamos JSON con el mapa de asignaciones (el backend
      // lo trata como opcional, así que {} es un cuerpo válido = comportamiento actual).
      headers: { ...cabecerasAuth(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ asignados }),
    })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    return (await r.json()) as { creadas: number }
  } catch {
    return null
  }
}
