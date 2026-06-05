// Cliente del chat con Javo.
//
// IMPORTANTE (regla de oro #3): el LLM se llama SOLO desde el backend. Aquí NO
// se toca `api.anthropic.com` ni hay API key: el front habla con nuestro
// FastAPI, y FastAPI habla con Claude (Sonnet) usando prompt caching.
//
// Mientras el endpoint del backend no exista, `conversarConJavo` cae a una
// respuesta simulada (`respuestaFallback`) para que el demo se vea y funcione.

import type { Mensaje, TipoConfirmado } from '../tipos'

// Base de la API. En dev se puede apuntar con VITE_API_URL; por defecto el
// proxy/back en /api.
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

interface RespuestaJavo {
  texto: string
}

/**
 * Envía la conversación al backend y devuelve la respuesta de Javo.
 * Si el backend no responde, usa una respuesta simulada (demo offline).
 */
export async function conversarConJavo(params: {
  solicitudId: string
  tipo: TipoConfirmado
  mensajes: Mensaje[]
}): Promise<string> {
  try {
    const r = await fetch(`${API_BASE}/conversaciones/responder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        solicitud_id: params.solicitudId,
        tipo: params.tipo,
        // No mandamos los mensajes de sistema (avisos de UI).
        mensajes: params.mensajes
          .filter((m) => m.rol !== 'sistema')
          .map((m) => ({ rol: m.rol, contenido: m.contenido })),
      }),
    })
    if (!r.ok) throw new Error(`backend respondió ${r.status}`)
    const data = (await r.json()) as RespuestaJavo
    return data.texto?.trim() || respuestaFallback(params.tipo)
  } catch {
    // Backend aún no cableado o caído: demo offline.
    return respuestaFallback(params.tipo)
  }
}

/** Respuesta simulada cuando el LLM no está disponible (demo offline). */
export function respuestaFallback(tipo: TipoConfirmado): string {
  if (tipo === 't1') {
    return 'Perfecto. Entonces dejo: catering de sopaipillas, 2 promotores, producto e insumos y uniformes para 5h diarias. Sumo coordinación de producción. Los valores los cruzo con el tarifario del Drive. ¿Genero la propuesta? 🧾'
  }
  return (
    'Listo, te dejo 3 conceptos de alto impacto:\n' +
    '1) Proyección mapping de un auto F1 en una fachada del centro.\n' +
    '2) Auto a escala real con letrero LED en punto de alto flujo.\n' +
    '3) Activación de sampling con simulador de pit-stop.\n' +
    '¿Cuál aterrizamos?'
  )
}
