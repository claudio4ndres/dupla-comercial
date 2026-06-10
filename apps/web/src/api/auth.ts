// Cabecera de autorización para las llamadas al backend.
// Lee el JWT de la sesión activa de Supabase; si no hay sesión, devuelve {}.
import { supabase } from '../supabase/cliente'

/**
 * Cabeceras de autorización para `fetch`. Devuelve `{ Authorization: Bearer … }`
 * con el JWT de la sesión activa de Supabase, o {} si no hay sesión.
 *
 * Es síncrono: usa la caché en memoria que mantiene el cliente de Supabase.
 * Funciona en todos los entornos (dev, test, prod) sin variables de entorno
 * adicionales.
 */
export function cabecerasAuth(): Record<string, string> {
  // Lee el access_token de la sesión que Supabase persiste en localStorage (clave
  // `sb-<ref>-auth-token`). Es síncrono y confiable: el campo interno `_session`
  // cambió entre versiones de supabase-js y no siempre está poblado al montar.
  try {
    const clave = Object.keys(localStorage).find((k) => k.includes('auth-token'))
    const crudo = clave ? localStorage.getItem(clave) : null
    const token = crudo ? (JSON.parse(crudo) as { access_token?: string }).access_token : undefined
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch {
    return {}
  }
}

/**
 * Versión async: resuelve el token desde el almacenamiento persistente. Usar
 * cuando se necesita el token antes de que onAuthStateChange haya disparado
 * (ej: llamadas al montar el componente).
 */
export async function cabecerasAuthAsync(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}
