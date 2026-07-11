// SolicitudContext — Contexto de la solicitud activa, conversación con Javo y cotización.
// Extracción desde App.tsx (Iteración 2 del refactor de contextos).

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { conversarConJavoOError } from '../api/javo'
import { obtenerRecursosDrive } from '../api/recursos'
import { iniciarConversacion, obtenerCotizacionEnCurso, obtenerHistorialConversacion, obtenerSugerencias } from '../api/conversaciones'
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
  /** Chips dinámicos generados por Haiku (vacío mientras se cargan). */
  chips: string[]
  /** El último turno de Javo falló (backend caído): la UI ofrece Reintentar (014). */
  errorJavo: boolean
  // Acciones
  abrirSolicitud: (s: Solicitud) => void
  iniciarChat: (tipo: TipoConfirmado) => void
  enviarMensaje: (texto: string) => Promise<void>
  /** Reenvía el último turno fallido SIN duplicar el mensaje del usuario (014). */
  reintentarMensaje: () => Promise<void>
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
  const [chips, setChips] = useState<string[]>([])
  const [errorJavo, setErrorJavo] = useState(false)

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
    setChips([])
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

    // Carga chips dinámicos (Haiku) — no bloquea el render del chat
    obtenerSugerencias(sol.id, t).then((c) => {
      if (c && c.length) setChips(c)
    })

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

  async function _conversar(historial: Mensaje[]) {
    if (!solicitudActual) return
    setEnviando(true)
    try {
      const r = await conversarConJavoOError({
        solicitudId: solicitudActual.id,
        tipo,
        mensajes: historial,
      })
      setErrorJavo(false)
      setMensajes((prev) => [...prev, { rol: 'javo', contenido: r.texto }])
      if (r.componentes.length) setComponentes(r.componentes)
      if (r.tareas.length) setTareas(r.tareas)
      if (r.fuentes.length) setFuentes(r.fuentes)
    } catch {
      // Backend caído: el turno del usuario ya está en el hilo; la UI muestra
      // el aviso con Reintentar (014). Ya no hay respuesta pregrabada.
      setErrorJavo(true)
    } finally {
      setEnviando(false)
    }
  }

  async function enviarMensaje(texto: string) {
    if (!solicitudActual) return
    const nuevos: Mensaje[] = [...mensajes, { rol: 'usuario', contenido: texto }]
    if (tipo === 't2' && /internet|busca|referencia|opciones/i.test(texto)) {
      nuevos.push({ rol: 'sistema', contenido: 'Javo está buscando referencias y opciones en internet…' })
    }
    setMensajes(nuevos)
    await _conversar(nuevos)
  }

  async function reintentarMensaje() {
    // Reenvía el historial TAL CUAL (el turno del usuario ya está): no duplica.
    if (!errorJavo) return
    await _conversar(mensajes)
  }

  // ─── Generar propuesta: persistir y navegar ────────────────────────────────

  async function generarPropuesta() {
    if (!solicitudActual) return
    if (componentes.length || tareas.length) {
      const guardada = await guardarPropuesta(solicitudActual.id, tipo, componentes, tareas)
      if (!guardada) {
        // El POST falló: no navegamos con una propuesta NO persistida (que
        // "desaparecería" al recargar). Avisamos en el hilo y el usuario reintenta.
        setMensajes((prev) => [...prev, {
          rol: 'sistema',
          contenido: 'No se pudo guardar la propuesta. Revisa tu conexión e inténtalo de nuevo.',
        }])
        return
      }
      setComponentes(guardada.componentes)
      setTareas(guardada.tareas)
    } else {
      const previa = await obtenerPropuesta(solicitudActual.id)
      if (previa) {
        setComponentes(previa.componentes)
        setTareas(previa.tareas)
      }
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
    chips,
    errorJavo,
    abrirSolicitud,
    iniciarChat,
    enviarMensaje,
    reintentarMensaje,
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
