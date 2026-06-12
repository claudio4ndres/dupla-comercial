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
 * Versión async: resuelve el token con `supabase.auth.getSession()`, que
 * **auto-refresca** el access_token si está vencido (a diferencia de la versión
 * síncrona, que lee el token crudo de localStorage y puede estar caducado).
 *
 * Esta es la que deben usar TODOS los clientes de API autenticados: tras ~1h el
 * token expira y, sin refresco, el backend responde 401 y las pantallas (la
 * bandeja, etc.) quedan vacías en silencio.
 *
 * Si `getSession()` no entrega token (p. ej. en tests con jsdom, donde el cliente
 * de Supabase no tiene una sesión persistida real), cae a la lectura síncrona de
 * localStorage (`cabecerasAuth`) como respaldo, para no romper el flujo offline.
 */
export async function cabecerasAuthAsync(): Promise<Record<string, string>> {
  try {
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    if (token) return { Authorization: `Bearer ${token}` }
  } catch {
    // getSession falló (red/almacenamiento): caemos al respaldo síncrono.
  }
  return cabecerasAuth()
}
