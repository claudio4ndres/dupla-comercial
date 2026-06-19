// BandejaContext — Contexto de la bandeja de solicitudes, propuestas y tareas globales.
// Extracción desde App.tsx (Iteración 3 del refactor de contextos).

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { obtenerSolicitudesOError } from '../api/solicitudes'
import { listarPropuestasOError, obtenerPropuesta, type PropuestaResumen } from '../api/propuestas'
import { listarTareasOError } from '../api/tareas'
import {
  ESTADO_DESCONECTADO,
  obtenerEstadoCorreo,
  type EstadoCorreo,
} from '../api/integraciones'
import { useSesion } from './SesionContext'
import { useSolicitud } from './SolicitudContext'
import type { Solicitud } from '../tipos'

// ── Interfaz del valor expuesto ──────────────────────────────────────────────

export interface BandejaContextValor {
  // Solicitudes
  solicitudes: Solicitud[]
  cargandoSolicitudes: boolean
  errorSolicitudes: boolean
  reintentoSolicitudes: number
  setReintentoSolicitudes: React.Dispatch<React.SetStateAction<number>>
  // Propuestas
  propuestas: PropuestaResumen[]
  cargandoPropuestas: boolean
  errorPropuestas: boolean
  reintentoPropuestas: number
  setReintentoPropuestas: React.Dispatch<React.SetStateAction<number>>
  // Tareas globales
  cargandoTareas: boolean
  errorTareas: boolean
  reintentoTareas: number
  setReintentoTareas: React.Dispatch<React.SetStateAction<number>>
  // Estado del correo (cargado internamente)
  estadoCorreo: EstadoCorreo
  cargandoCorreo: boolean
  // Acciones
  abrirPropuestaDesdeLista: (solicitudId: string) => Promise<void>
}

// ── Contexto con valor inicial undefined (para detectar uso fuera del provider) ─

const BandejaContext = createContext<BandejaContextValor | undefined>(undefined)

// ── Provider ─────────────────────────────────────────────────────────────────

export function BandejaProvider({ children }: { children: ReactNode }) {
  const { pantalla, empresa, irA } = useSesion()
  const { tareas, setSolicitudActual, setComponentes, setTareas } = useSolicitud()

  // Estado del correo (proveedor conectado, cargando)
  const [estadoCorreo, setEstadoCorreo] = useState<EstadoCorreo>(ESTADO_DESCONECTADO)
  const [cargandoCorreo, setCargandoCorreo] = useState(true)

  // Solicitudes de la empresa
  const [solicitudes, setSolicitudes] = useState<Solicitud[]>([])
  const [cargandoSolicitudes, setCargandoSolicitudes] = useState(true)
  const [errorSolicitudes, setErrorSolicitudes] = useState(false)
  const [reintentoSolicitudes, setReintentoSolicitudes] = useState(0)

  // Propuestas de la empresa
  const [propuestas, setPropuestas] = useState<PropuestaResumen[]>([])
  const [cargandoPropuestas, setCargandoPropuestas] = useState(true)
  const [errorPropuestas, setErrorPropuestas] = useState(false)
  const [reintentoPropuestas, setReintentoPropuestas] = useState(0)

  // Tareas globales (lista del menú)
  const [cargandoTareas, setCargandoTareas] = useState(true)
  const [errorTareas, setErrorTareas] = useState(false)
  const [reintentoTareas, setReintentoTareas] = useState(0)

  // ─── Efecto: cargar estado del correo al cambiar empresa ───────────────────
  useEffect(() => {
    let activo = true
    setCargandoCorreo(true)
    obtenerEstadoCorreo()
      .then((e) => {
        if (activo) setEstadoCorreo(e)
      })
      .finally(() => {
        if (activo) setCargandoCorreo(false)
      })
    return () => { activo = false }
  }, [empresa])

  // ─── Efecto: cargar solicitudes con auto-refresh de 20s ────────────────────
  useEffect(() => {
    if (pantalla !== 'inbox') return
    if (estadoCorreo.proveedor === null) {
      setSolicitudes([])
      return
    }
    let activo = true
    let esPrimera = true
    const cargar = () => {
      if (esPrimera) {
        setCargandoSolicitudes(true)
        setErrorSolicitudes(false)
      }
      return obtenerSolicitudesOError()
        .then((s) => {
          if (!activo) return
          setSolicitudes(s)
          setErrorSolicitudes(false)
        })
        .catch(() => {
          if (activo) setErrorSolicitudes(true)
        })
        .finally(() => {
          if (activo) setCargandoSolicitudes(false)
          esPrimera = false
        })
    }
    cargar()
    const intervalo = setInterval(cargar, 20000)
    return () => {
      activo = false
      clearInterval(intervalo)
    }
  }, [empresa, estadoCorreo.proveedor, pantalla, reintentoSolicitudes])

  // ─── Efecto: cargar propuestas al entrar a la pantalla "Propuestas" ────────
  useEffect(() => {
    if (pantalla !== 'propuestas') return
    let activo = true
    setCargandoPropuestas(true)
    setErrorPropuestas(false)
    listarPropuestasOError()
      .then((p) => {
        if (!activo) return
        setPropuestas(p)
        setErrorPropuestas(false)
      })
      .catch(() => {
        if (activo) setErrorPropuestas(true)
      })
      .finally(() => {
        if (activo) setCargandoPropuestas(false)
      })
    return () => { activo = false }
  }, [empresa, pantalla, reintentoPropuestas])

  // ─── Efecto: cargar tareas globales al entrar a "Tareas" sin tareas en estado ─
  useEffect(() => {
    if (pantalla !== 'tareas' || tareas.length > 0) return
    let activo = true
    setCargandoTareas(true)
    setErrorTareas(false)
    listarTareasOError()
      .then((t) => {
        if (!activo) return
        setTareas(t)
        setErrorTareas(false)
      })
      .catch(() => {
        if (activo) setErrorTareas(true)
      })
      .finally(() => {
        if (activo) setCargandoTareas(false)
      })
    return () => { activo = false }
  }, [empresa, pantalla, tareas.length, reintentoTareas, setTareas])

  // ─── Abrir detalle de una propuesta desde la lista del menú ────────────────
  async function abrirPropuestaDesdeLista(solicitudId: string) {
    const fila = propuestas.find((p) => p.solicitudId === solicitudId)
    const prop = await obtenerPropuesta(solicitudId)
    setComponentes(prop ? prop.componentes : [])
    setTareas(prop ? prop.tareas : [])
    setSolicitudActual({
      id: solicitudId,
      remitente: fila?.remitente ?? '',
      correo: '',
      tiempo: '',
      asunto: fila?.asunto ?? '',
      tipo: 't1',
      resumen: '',
      puntos: [],
      cuerpo: '',
    })
    irA('propuesta')
  }

  // ─── Valor del contexto ────────────────────────────────────────────────────

  const valor: BandejaContextValor = {
    solicitudes,
    cargandoSolicitudes,
    errorSolicitudes,
    reintentoSolicitudes,
    setReintentoSolicitudes,
    propuestas,
    cargandoPropuestas,
    errorPropuestas,
    reintentoPropuestas,
    setReintentoPropuestas,
    cargandoTareas,
    errorTareas,
    reintentoTareas,
    setReintentoTareas,
    estadoCorreo,
    cargandoCorreo,
    abrirPropuestaDesdeLista,
  }

  return <BandejaContext.Provider value={valor}>{children}</BandejaContext.Provider>
}

// ── Hook de acceso rápido con guard en español ───────────────────────────────

export function useBandeja(): BandejaContextValor {
  const ctx = useContext(BandejaContext)
  if (ctx === undefined) {
    throw new Error('useBandeja debe usarse dentro de BandejaProvider')
  }
  return ctx
}
