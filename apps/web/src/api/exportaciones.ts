// Cliente de exportación de la cotización a Excel (007).
//
// El backend (GET /solicitudes/{id}/cotizacion.xlsx) genera el .xlsx con el theme
// Capsulab y lo sirve como descarga. Aquí se pide con el JWT del usuario (RLS), se
// recibe el blob y se dispara la descarga en el navegador. Ante cualquier fallo
// (404 sin propuesta, backend caído) devuelve `false` para no romper la UI.

import { cabecerasAuthAsync } from './auth'

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

/** Vista del Excel: `interno` (costos + margen) o `cliente` (solo precios de venta). */
export type VistaExcel = 'interno' | 'cliente'

/**
 * Descarga la cotización de una solicitud como archivo .xlsx. `vista` elige entre el
 * documento interno (costos + margen) y el del cliente (solo precios de venta).
 * Devuelve `true` si la descarga se disparó, `false` ante error (sin romper la UI).
 */
export async function descargarCotizacionExcel(
  solicitudId: string,
  vista: VistaExcel = 'interno',
): Promise<boolean> {
  try {
    const r = await fetch(
      `${API_BASE}/solicitudes/${solicitudId}/cotizacion.xlsx?vista=${vista}`,
      { headers: await cabecerasAuthAsync() },
    )
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)

    const blob = await r.blob()
    const url = URL.createObjectURL(blob)
    const ancla = document.createElement('a')
    ancla.href = url
    ancla.download = `cotizacion-${vista}-${solicitudId}.xlsx`
    document.body.appendChild(ancla)
    ancla.click()
    ancla.remove()
    URL.revokeObjectURL(url)
    return true
  } catch {
    return false
  }
}

/**
 * Descarga la propuesta de una solicitud como un DECK .pptx (cara comercial, vista
 * cliente: solo precios de venta). Devuelve `true` si la descarga se disparó, `false`
 * ante error (404 sin propuesta, backend caído) — sin romper la UI.
 */
export async function descargarCotizacionPpt(solicitudId: string): Promise<boolean> {
  try {
    const r = await fetch(
      `${API_BASE}/solicitudes/${solicitudId}/propuesta.pptx`,
      { headers: await cabecerasAuthAsync() },
    )
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)

    const blob = await r.blob()
    const url = URL.createObjectURL(blob)
    const ancla = document.createElement('a')
    ancla.href = url
    ancla.download = `cotizacion-${solicitudId}.pptx`
    document.body.appendChild(ancla)
    ancla.click()
    ancla.remove()
    URL.revokeObjectURL(url)
    return true
  } catch {
    return false
  }
}
