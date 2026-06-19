// useSincronizarRuta — Hook que sincroniza el estado `pantalla` del SesionContext
// con la URL del navegador. Se monta una sola vez en App.tsx.
//
// Estrategia bidireccional:
// - Cuando `pantalla` cambia (por UI) → actualiza la URL sin navegar (replaceState).
// - Al montar (carga directa de URL) → lee la URL y setea la pantalla correspondiente.
//
// En ambiente de test (jsdom) window.location.pathname es siempre "/" y el hook
// no interfiere con los tests existentes.

import { useEffect } from 'react'
import { useSesion } from '../contextos/SesionContext'
import type { Pantalla } from '../tipos'

/** Mapeo pantalla → ruta URL (para las pantallas que tienen ruta propia). */
const RUTA_DE_PANTALLA: Record<Pantalla, string> = {
  configuracion: '/configuracion',
  inbox: '/bandeja',
  detail: '/bandeja', // detail necesita :id, fallback a bandeja
  chat: '/bandeja', // chat necesita :id/chat, fallback a bandeja
  propuestas: '/propuestas',
  propuesta: '/propuestas', // propuesta singular necesita :id, fallback a lista
  tareas: '/tareas',
}

/** Mapeo inverso: ruta URL → pantalla (solo rutas de primer nivel). */
const PANTALLA_DE_RUTA: Record<string, Pantalla> = {
  '/configuracion': 'configuracion',
  '/bandeja': 'inbox',
  '/propuestas': 'propuestas',
  '/tareas': 'tareas',
}

/**
 * Sincroniza bidireccionalemente `pantalla` (estado del contexto) ↔ URL del navegador.
 * Debe montarse una sola vez en el componente raíz de la app (App.tsx).
 */
export function useSincronizarRuta() {
  const { pantalla, irA } = useSesion()

  // Pantalla → URL: cuando pantalla cambia, actualizar la URL sin navegación real.
  useEffect(() => {
    const rutaEsperada = RUTA_DE_PANTALLA[pantalla]
    if (rutaEsperada && window.location.pathname !== rutaEsperada) {
      window.history.replaceState(null, '', rutaEsperada)
    }
  }, [pantalla])

  // URL → Pantalla: al montar, leer la URL y setear la pantalla correspondiente.
  // Solo se ejecuta una vez al cargar la app (deep link directo).
  useEffect(() => {
    const path = window.location.pathname
    const p = PANTALLA_DE_RUTA[path]
    if (p) {
      irA(p)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
