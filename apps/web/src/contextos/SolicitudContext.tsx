// SolicitudContext — Contexto de la solicitud activa, conversación con Javo y cotización.
// Extracción desde App.tsx (Iteración 2 del refactor de contextos).

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { conversarConJavo } from '../api/javo'
import { obtenerRecursosDrive } from '../api/recursos'
import { iniciarConversacion, obtenerCotizacionEnCurso, obtenerHistorialConversacion } from '../api/conversaciones'
import { guardarPropuesta, obtenerPropuesta } from '../api/propuestas'
import { useSesion } from './SesionContext'
import type { RecursoDrive } from '../datosMock'
import type {
  Componente,
  Fuente,
  Mensaje,
  Solicitud,
  Tarea,
  TipoConfirmado,
} from '../tipos'

// ── Interfaz del valor expuesto ──────────────────────────────────────────────

export interface SolicitudContextValor {
  solicitudActual: Solicitud | null
  tipo: TipoConfirmado
  mensajes: Mensaje[]
  componentes: Componente[]
  tareas: Tarea[]
  fuentes: Fuente[]
  enviando: boolean
  recursos: RecursoDrive[]
  // Acciones
  abrirSolicitud: (s: Solicitud) => void
  iniciarChat: (tipo: TipoConfirmado) => void
  enviarMensaje: (texto: string) => Promise<void>
  generarPropuesta: () => Promise<void>
  setTareas: (tareas: Tarea[]) => void
  // Setters expuestos para que App.tsx los use (abrirPropuestaDesdeLista)
  setSolicitudActual: (s: Solicitud | null) => void
  setComponentes: (c: Componente[]) => void
}

// ── Contexto con valor inicial undefined (para detectar uso fuera del provider) ─

const SolicitudContext = createContext<SolicitudContextValor | undefined>(undefined)

// ── Provider ─────────────────────────────────────────────────────────────────

export function SolicitudProvider({ children }: { children: ReactNode }) {
  const { empresa, irA } = useSesion()

  const [solicitudActual, setSolicitudActual] = useState<Solicitud | null>(null)
  const [tipo, setTipo] = useState<TipoConfirmado>('t1')
  const [mensajes, setMensajes] = useState<Mensaje[]>([])
  const [componentes, setComponentes] = useState<Componente[]>([])
  const [tareas, setTareas] = useState<Tarea[]>([])
  const [fuentes, setFuentes] = useState<Fuente[]>([])
  const [enviando, setEnviando] = useState(false)
  const [recursos, setRecursos] = useState<RecursoDrive[]>([])

  // ─── Efecto: recursos del Drive de la empresa (panel del chat) ─────────────
  useEffect(() => {
    let activo = true
    obtenerRecursosDrive().then((r) => {
      if (activo) setRecursos(r)
    })
    return () => { activo = false }
  }, [empresa])

  // ─── Abrir solicitud (navega a detalle) ────────────────────────────────────

  function abrirSolicitud(s: Solicitud) {
    setSolicitudActual(s)
    irA('detail')
  }

  // ─── Iniciar chat: limpiar estado, intro de Javo desde backend, rehidratar ──

  function iniciarChat(t: TipoConfirmado) {
    if (!solicitudActual) return
    const sol = solicitudActual
    setTipo(t)
    setComponentes([])
    setTareas([])
    setFuentes([])
    setMensajes([])
    setEnviando(true)
    irA('chat')

    // Pide el saludo inicial de Javo al backend
    iniciarConversacion(sol.id, t)
      .then((r) => {
        setMensajes([{ rol: 'javo', contenido: r.texto }])
      })
      .catch(() => {
        // Fallback: si el backend falla, mensaje genérico
        setMensajes([{ rol: 'javo', contenido: '¡Hola! 👋 Vamos a trabajar en esta solicitud.' }])
      })
      .finally(() => setEnviando(false))

    // Rehidrata el hilo persistido (T14)
    obtenerHistorialConversacion(sol.id).then((historial) => {
      if (historial.length) setMensajes(historial)
    })

    // Rehidrata la cotización en curso (0009)
    obtenerCotizacionEnCurso(sol.id).then((cot) => {
      if (cot.componentes.length || cot.tareas.length || cot.fuentes.length) {
        if (cot.componentes.length) setComponentes(cot.componentes)
        if (cot.tareas.length) setTareas(cot.tareas)
        if (cot.fuentes.length) setFuentes(cot.fuentes)
        return
      }
      obtenerPropuesta(sol.id).then((prop) => {
        if (prop && prop.componentes.length) setComponentes(prop.componentes)
      })
    })
  }

  // ─── Enviar mensaje al chat con Javo ───────────────────────────────────────

  async function enviarMensaje(texto: string) {
    if (!solicitudActual) return
    const nuevos: Mensaje[] = [...mensajes, { rol: 'usuario', contenido: texto }]
    if (tipo === 't2' && /internet|busca|referencia|opciones/i.test(texto)) {
      nuevos.push({ rol: 'sistema', contenido: 'Javo está buscando referencias y opciones en internet…' })
    }
    setMensajes(nuevos)
    setEnviando(true)

    const r = await conversarConJavo({ solicitudId: solicitudActual.id, tipo, mensajes: nuevos })
    setMensajes((prev) => [...prev, { rol: 'javo', contenido: r.texto }])
    setEnviando(false)

    if (r.componentes.length) setComponentes(r.componentes)
    if (r.tareas.length) setTareas(r.tareas)
    if (r.fuentes.length) setFuentes(r.fuentes)
  }

  // ─── Generar propuesta: persistir y navegar ────────────────────────────────

  async function generarPropuesta() {
    if (!solicitudActual) return
    const guardada =
      componentes.length || tareas.length
        ? await guardarPropuesta(solicitudActual.id, tipo, componentes, tareas)
        : await obtenerPropuesta(solicitudActual.id)
    if (guardada) {
      setComponentes(guardada.componentes)
      setTareas(guardada.tareas)
    }
    irA('propuesta')
  }

  // ─── Valor del contexto ────────────────────────────────────────────────────

  const valor: SolicitudContextValor = {
    solicitudActual,
    tipo,
    mensajes,
    componentes,
    tareas,
    fuentes,
    enviando,
    recursos,
    abrirSolicitud,
    iniciarChat,
    enviarMensaje,
    generarPropuesta,
    setTareas,
    setSolicitudActual,
    setComponentes,
  }

  return <SolicitudContext.Provider value={valor}>{children}</SolicitudContext.Provider>
}

// ── Hook de acceso rápido con guard en español ───────────────────────────────

export function useSolicitud(): SolicitudContextValor {
  const ctx = useContext(SolicitudContext)
  if (ctx === undefined) {
    throw new Error('useSolicitud debe usarse dentro de SolicitudProvider')
  }
  return ctx
}
