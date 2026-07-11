// useSolicitudDeRuta — Rehidrata la solicitud activa a partir del :id de la URL
// (spec 016). En navegación in-app la solicitud ya viene del contexto (sin
// fetch); en un deep-link o refresh se busca primero en la bandeja en memoria
// y, si no está, se pide la lista al backend (no hay GET por id).

import { useEffect, useState } from 'react'
import { obtenerSolicitudes } from '../api/solicitudes'
import { useSolicitud } from '../contextos/SolicitudContext'
import { useBandeja } from '../contextos/BandejaContext'
import type { Solicitud } from '../tipos'

export interface SolicitudDeRuta {
  /** La solicitud del :id de la URL, o null mientras se rehidrata. */
  solicitud: Solicitud | null
  /** true cuando el backend no conoce ese id (mostrar NotFound). */
  noEncontrada: boolean
}

export function useSolicitudDeRuta(id: string | undefined): SolicitudDeRuta {
  const { solicitudActual, setSolicitudActual } = useSolicitud()
  const { solicitudes } = useBandeja()
  // Guarda el id que NO existe (en vez de un booleano) para que al navegar a
  // otro :id el estado "no encontrada" no se filtre a la solicitud nueva.
  const [idNoEncontrado, setIdNoEncontrado] = useState<string | null>(null)

  const cargada = !!id && solicitudActual?.id === id

  useEffect(() => {
    if (!id || cargada) return
    let activo = true
    // 1) ¿Ya está en la bandeja cargada en memoria? 2) Si no, al backend.
    const enBandeja = solicitudes.find((s) => s.id === id)
    const promesa = enBandeja
      ? Promise.resolve<Solicitud | undefined>(enBandeja)
      : obtenerSolicitudes().then((lista) => lista.find((s) => s.id === id))
    promesa.then((s) => {
      if (!activo) return
      if (s) setSolicitudActual(s)
      else setIdNoEncontrado(id)
    })
    return () => {
      activo = false
    }
  }, [id, cargada, solicitudes, setSolicitudActual])

  return {
    solicitud: cargada ? solicitudActual : null,
    noEncontrada: !!id && idNoEncontrado === id,
  }
}
