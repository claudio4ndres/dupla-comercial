// Cliente de la conexión de correo (la bandeja).
//
// Regla de oro #3: los tokens/credenciales viven SOLO en el backend. El front
// únicamente pregunta "¿está conectada la bandeja?" (estado) y "dame la URL de
// consentimiento" para iniciar el OAuth. Nunca ve el `token_ref` (CA5): el
// backend lo omite de la respuesta.

import { cabecerasAuthAsync } from './auth'
import type { ProveedorCorreo } from '../tipos'

// Base de la API. En dev se apunta con VITE_API_URL; por defecto, el proxy /api.
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

/** Estado de la bandeja tal como lo expone el backend (GET /integraciones/correo). */
export interface EstadoCorreo {
  proveedor: ProveedorCorreo | null
  estado: 'conectado' | 'reconectar' | null
  casilla: string | null
}

/** Bandeja sin conectar (también es el fallback offline del demo). */
export const ESTADO_DESCONECTADO: EstadoCorreo = {
  proveedor: null,
  estado: null,
  casilla: null,
}

/**
 * Lee el estado de la bandeja desde el backend. Si el backend no responde
 * (aún sin cablear o caído), cae a "sin conectar" para que el demo se vea.
 */
export async function obtenerEstadoCorreo(): Promise<EstadoCorreo> {
  try {
    const r = await fetch(`${API_BASE}/integraciones/correo`, {
      headers: await cabecerasAuthAsync(),
    })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = (await r.json()) as Partial<EstadoCorreo>
    return {
      proveedor: data.proveedor ?? null,
      estado: data.estado ?? null,
      casilla: data.casilla ?? null,
    }
  } catch {
    return ESTADO_DESCONECTADO
  }
}

/**
 * Pide al backend la URL de consentimiento de Google para conectar Gmail.
 * Devuelve la `url` EXACTA del backend: el cliente nunca inventa la URL de OAuth
 * (el `state` anti-CSRF y el scope los fija el servidor). Si el backend falla,
 * propaga el error para que la UI no navegue a una URL inventada.
 */
export async function iniciarConexionGmail(): Promise<string> {
  const r = await fetch(`${API_BASE}/integraciones/correo/gmail/iniciar`, {
    method: 'POST',
    headers: await cabecerasAuthAsync(),
  })
  if (!r.ok) throw new Error(`backend respondió ${r.status}`)
  const data = (await r.json()) as { url: string }
  return data.url
}

/** Desconecta la bandeja (el "Cambiar"). Borra integración + secreto en el backend. */
export async function desconectarCorreo(): Promise<void> {
  await fetch(`${API_BASE}/integraciones/correo`, {
    method: 'DELETE',
    headers: await cabecerasAuthAsync(),
  })
}
