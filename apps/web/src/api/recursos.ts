// Cliente de los recursos del Drive de la empresa (panel "Recursos · Drive" del chat).
//
// El backend (GET /catalogo/recursos) devuelve los origenes del catálogo de la empresa
// (RLS). Aquí se mapea cada uno a un `RecursoDrive` con un icono según su tipo. Antes
// este panel era un mock estático; ahora es dinámico por empresa.

import { cabecerasAuth } from './auth'
import type { RecursoDrive } from '../datosMock'

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

/** Icono según la extensión del recurso (o carpeta si no tiene extensión). */
function iconoPara(origen: string): string {
  const o = origen.toLowerCase()
  if (o.endsWith('.xlsx') || o.endsWith('.xls') || o.endsWith('.csv')) return '📊'
  if (o.endsWith('.pdf')) return '📄'
  if (o.endsWith('.pptx') || o.endsWith('.ppt')) return '📽️'
  if (o.endsWith('.docx') || o.endsWith('.doc')) return '📝'
  if (o.includes('.')) return '📄' // otro archivo
  return '📁' // sin extensión → carpeta del Drive
}

/**
 * Lee los recursos del Drive de la empresa desde el backend. Si el backend no responde
 * (caído o sin sesión), devuelve lista vacía para no romper el chat.
 */
export async function obtenerRecursosDrive(): Promise<RecursoDrive[]> {
  try {
    const r = await fetch(`${API_BASE}/catalogo/recursos`, { headers: cabecerasAuth() })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = (await r.json()) as string[]
    return data.map((origen) => ({ icono: iconoPara(origen), nombre: origen }))
  } catch {
    return []
  }
}
