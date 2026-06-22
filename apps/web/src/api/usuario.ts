// Cliente del usuario actual: lee/marca onboarding_visto (GET/PATCH /usuario), para
// decidir si mostrar el slider de bienvenida una sola vez por usuario. Mismo patrón
// tolerante que empresa.ts: ante error o sin sesión → null / no-op (no rompe nada).

import { cabecerasAuthAsync } from './auth'

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

interface UsuarioApi {
  onboarding_visto: boolean
}

/** Datos del usuario autenticado (hoy: onboarding_visto). null ante error/sin sesión. */
export async function obtenerUsuario(): Promise<UsuarioApi | null> {
  try {
    const r = await fetch(`${API_BASE}/usuario`, { headers: await cabecerasAuthAsync() })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = (await r.json()) as Partial<UsuarioApi>
    if (typeof data?.onboarding_visto !== 'boolean') return null
    return { onboarding_visto: data.onboarding_visto }
  } catch {
    return null
  }
}

/** Marca el onboarding de bienvenida como visto. Best-effort: ignora errores (el peor
 * caso es que el slider reaparezca la próxima vez). */
export async function marcarOnboardingVisto(): Promise<void> {
  try {
    await fetch(`${API_BASE}/usuario/onboarding-visto`, {
      method: 'PATCH',
      headers: await cabecerasAuthAsync(),
    })
  } catch {
    /* best-effort */
  }
}
