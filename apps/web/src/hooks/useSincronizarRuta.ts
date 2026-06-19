// useSincronizarRuta — Hook que sincroniza el estado `pantalla` del SesionContext
// con la URL del navegador. Se monta una sola vez en App.tsx.
//
// Estrategia bidireccional:
// - Cuando `pantalla` cambia (por UI) → pushState crea entrada en el historial.
// - Al montar (carga directa de URL) → lee la URL y setea la pantalla correspondiente.
// - Al pulsar "atrás" (popstate) → lee la nueva URL y actualiza `pantalla`.
//
// En ambiente de test (jsdom) window.history.pushState es un no-op y el hook
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

  // Pantalla → URL: cuando pantalla cambia, crear entrada en el historial.
  // pushState (en vez de replaceState) para que el botón "atrás" funcione.
  useEffect(() => {
    const rutaEsperada = RUTA_DE_PANTALLA[pantalla]
    if (rutaEsperada && window.location.pathname !== rutaEsperada) {
      window.history.pushState(null, '', rutaEsperada)
    }
  }, [pantalla])

  // URL → Pantalla: al montar, leer la URL y setear la pantalla correspondiente.
  // Solo se ejecuta una vez al cargar la app (deep link directo).
  // También escucha `popstate` para que el botón "atrás" actualice la pantalla.
  useEffect(() => {
    const path = window.location.pathname
    const p = PANTALLA_DE_RUTA[path]
    if (p) {
      irA(p)
    }

    // Listener de popstate: cuando el usuario pulsa "atrás" o "adelante",
    // el navegador cambia la URL y dispara este evento. Leemos la nueva URL
    // y actualizamos la pantalla del contexto.
    const handlePopState = () => {
      const nuevaRuta = window.location.pathname
      const nuevaPantalla = PANTALLA_DE_RUTA[nuevaRuta]
      if (nuevaPantalla) {
        irA(nuevaPantalla)
      }
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
