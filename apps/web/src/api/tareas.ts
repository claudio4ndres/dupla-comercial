// Cliente de la lista de tareas de la empresa (pantalla "Tareas" del menú).
//
// El backend (GET /tareas) devuelve las tareas en la forma canónica en español
// (`grupo`/`vencimiento`); aquí —la capa de API del front— se mapea al tipo de
// la UI (`Tarea`), igual que hace `aTarea` en `propuestas.ts` (grupo → área,
// vencimiento → plazo, nulos → string vacío). Ante error o sin sesión → lista
// vacía, como hacen `solicitudes.ts` y `recursos.ts`.

import { cabecerasAuthAsync } from './auth'
import type { Tarea } from '../tipos'

// Base de la API. En dev se apunta con VITE_API_URL; por defecto, el proxy /api.
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

interface TareaBackend {
  nombre: string
  grupo: string | null
  responsable: string | null
  vencimiento: string | null
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
 * Lista las tareas de la empresa y PROPAGA el error si el backend no responde.
 * La usa el caller (App.tsx) que quiere distinguir "vacío real" de "fallo de
 * carga" para mostrar un banner de reintento.
 */
export async function listarTareasOError(): Promise<Tarea[]> {
  const r = await fetch(`${API_BASE}/tareas`, { headers: await cabecerasAuthAsync() })
  if (!r.ok) throw new Error(`backend respondió ${r.status}`)
  const data = (await r.json()) as TareaBackend[]
  return data.map(aTarea)
}

/**
 * Lista las tareas de la empresa para la pantalla "Tareas" del menú. Si el
 * backend no responde (caído o sin sesión), cae a lista vacía para no romper
 * el demo (mismo manejo de errores que `obtenerSolicitudes`).
 */
export async function listarTareas(): Promise<Tarea[]> {
  try {
    return await listarTareasOError()
  } catch {
    return []
  }
}
