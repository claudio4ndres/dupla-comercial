// Cliente del conector ClickUp (estado del conector + envío de tareas).
//
// IMPORTANTE (regla de oro #3): el token de ClickUp vive SOLO en el backend; el front
// nunca lo toca. Aquí el front habla con nuestro FastAPI, que a su vez habla con la API
// de ClickUp. Operaciones:
//   * `obtenerEstadoClickup()` → ¿la EMPRESA tiene ClickUp conectado? (panel de
//     Configuración, espejo de Gmail). Sin integración → "Sin conectar"; con token
//     revocado/401 el backend marca "reconectar" (CA6). Ante fallo cae a desconectado.
//   * `iniciarConexionClickup()` → URL de consentimiento OAuth (el front la navega; el
//     `state` anti-CSRF lo fija el backend, el front NUNCA inventa la URL).
//   * `desconectarClickup()` → el "Cambiar": borra integración + secreto en el backend.
//   * `listarListasClickUp()` → puebla el SELECTOR de lista destino (las listas reales
//     del usuario). Sin token configurado el backend devuelve [] → el front muestra el
//     aviso "Conecta ClickUp". Ante cualquier fallo, también [] (no rompe la pantalla).
//   * `enviarTareasAClickUp(solicitudId, listaId)` → crea las tareas de la propuesta en
//     la lista elegida y devuelve `{creadas}`; ante error, `null` (igual que solicitudes.ts).
//
// El token de ClickUp JAMÁS viaja al frontend (CA5): el backend lo omite del
// response_model y estos clientes solo mapean proveedor/estado.

import { cabecerasAuthAsync } from './auth'

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

/** Estado del conector ClickUp de la empresa (GET /clickup/estado). Sin token. */
export interface EstadoClickup {
  proveedor: 'clickup' | null
  estado: 'conectado' | 'reconectar' | null
}

/** ClickUp sin conectar (también es el fallback ante error del backend). */
export const ESTADO_CLICKUP_DESCONECTADO: EstadoClickup = {
  proveedor: null,
  estado: null,
}

/** Una lista de ClickUp para el selector de destino (forma plana del backend). */
export interface ListaClickUp {
  id: string
  nombre: string
  espacio: string
}

/**
 * Lee el estado del conector ClickUp de la empresa autenticada (por-tenant).
 * Espejo de `obtenerEstadoCorreo`: con integración → {proveedor:'clickup', estado};
 * sin integración → todo null ("Sin conectar"); token revocado/401 → estado
 * 'reconectar' (CA6). Si el backend no responde, cae a "desconectado" (no rompe el
 * panel). Solo mapea proveedor/estado: el token nunca se expone (CA5).
 */
export async function obtenerEstadoClickup(): Promise<EstadoClickup> {
  try {
    const r = await fetch(`${API_BASE}/clickup/estado`, { headers: await cabecerasAuthAsync() })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = (await r.json()) as Partial<EstadoClickup>
    return {
      proveedor: data.proveedor ?? null,
      estado: data.estado ?? null,
    }
  } catch {
    return ESTADO_CLICKUP_DESCONECTADO
  }
}

/**
 * Pide al backend la URL de consentimiento de ClickUp para conectar el conector.
 * Devuelve la `url` EXACTA del backend: el cliente nunca inventa la URL de OAuth
 * (el `state` anti-CSRF lo fija el servidor). Si el backend falla, propaga el error
 * para que la UI no navegue a una URL inventada (igual que Gmail).
 */
export async function iniciarConexionClickup(): Promise<string> {
  const r = await fetch(`${API_BASE}/clickup/iniciar`, {
    method: 'POST',
    headers: await cabecerasAuthAsync(),
  })
  if (!r.ok) throw new Error(`backend respondió ${r.status}`)
  const data = (await r.json()) as { url: string }
  return data.url
}

/**
 * Desconecta ClickUp de la empresa (el "Cambiar"). Borra integración + secreto en el
 * backend. Ante fallo de red no propaga (igual que `desconectarCorreo`): el panel
 * vuelve a "Sin conectar" en la UI sin romperse.
 */
export async function desconectarClickup(): Promise<void> {
  try {
    await fetch(`${API_BASE}/clickup`, {
      method: 'DELETE',
      headers: await cabecerasAuthAsync(),
    })
  } catch {
    // Red caída: no rompemos el flujo de "Cambiar".
  }
}

/**
 * Lee las listas reales del ClickUp de la empresa desde el backend. Si no hay token
 * configurado el backend responde [] (el front muestra "conecta ClickUp"); ante
 * cualquier otro fallo (502, red caída) también devuelve [] para no romper la UI.
 */
export async function listarListasClickUp(): Promise<ListaClickUp[]> {
  try {
    const r = await fetch(`${API_BASE}/clickup/listas`, { headers: await cabecerasAuthAsync() })
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
      headers: { ...(await cabecerasAuthAsync()), 'Content-Type': 'application/json' },
      body: JSON.stringify({ asignados }),
    })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    return (await r.json()) as { creadas: number }
  } catch {
    return null
  }
}
