// Cliente de la empresa (tenant) del usuario: el header/branding sale del backend
// (GET /empresa, filtrado por el JWT del usuario), NO de un mock. Aquí se mapea
// {id, nombre, color_marca, plan} al tipo `Empresa` del front. Ante error, sin sesión
// o forma inesperada → null, y el front conserva su empresa actual (no rompe el demo
// offline), igual que `miembros.ts` / `tareas.ts`.

import { cabecerasAuth } from './auth'
import type { Empresa } from '../tipos'

// Base de la API. En dev se apunta con VITE_API_URL; por defecto, el proxy /api.
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

interface EmpresaApi {
  id: string
  nombre: string
  color_marca: string
  plan: string
}

/**
 * Trae la empresa REAL del usuario autenticado para pintar el header (nombre, color
 * de marca, inicial, etiqueta de plan). Si el backend no responde, no hay sesión, o la
 * forma es inesperada → null (el front mantiene su empresa actual).
 */
export async function obtenerEmpresa(): Promise<Empresa | null> {
  try {
    const r = await fetch(`${API_BASE}/empresa`, { headers: cabecerasAuth() })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = (await r.json()) as Partial<EmpresaApi>
    if (!data || !data.nombre) return null
    return {
      nombre: data.nombre,
      color: data.color_marca ?? '#F04E37',
      marca: (data.nombre.trim()[0] ?? '·').toUpperCase(),
      etiqueta: data.plan ? `Plan ${data.plan} · BTL` : undefined,
    }
  } catch {
    return null
  }
}
