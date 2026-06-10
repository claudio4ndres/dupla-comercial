// Cliente del roster de miembros de la empresa (selector "Asignado a" de Tareas, 0006).
//
// El backend (GET /miembros) devuelve el roster en forma plana en español
// (`{id, nombre, rol}`), filtrado por la empresa del usuario (RLS). Aquí —la capa de
// API del front— se devuelve tal cual (el tipo ya calza con `Miembro`). Ante error o
// sin sesión → lista vacía, como hacen `tareas.ts`, `solicitudes.ts` y `recursos.ts`,
// para no romper el demo offline.

import { cabecerasAuth } from './auth'
import type { Miembro } from '../tipos'

// Base de la API. En dev se apunta con VITE_API_URL; por defecto, el proxy /api.
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

/**
 * Lista el roster de la empresa para poblar el selector "Asignado a" de la pantalla
 * de Tareas. Si el backend no responde (caído o sin sesión), o devuelve algo
 * inesperado, cae a lista vacía (mismo manejo de errores que `listarTareas`).
 */
export async function listarMiembros(): Promise<Miembro[]> {
  try {
    const r = await fetch(`${API_BASE}/miembros`, { headers: cabecerasAuth() })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = await r.json()
    // Defensa: si el backend devolviera algo inesperado, no rompemos el selector.
    return Array.isArray(data) ? (data as Miembro[]) : []
  } catch {
    return []
  }
}
