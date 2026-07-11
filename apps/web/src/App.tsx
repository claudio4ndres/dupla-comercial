// App.tsx — Layout de la aplicación + un contenedor por ruta (spec 016).
//
// Con React Router v7 el switch por `pantalla` desapareció: el Layout monta el
// marco (Sidebar/Topbar/scroll/onboarding) con un <Outlet/> y cada CONTENEDOR
// de ruta lee los contextos + useParams() y cablea las props reales de su
// pantalla presentacional (que no cambia). Los contenedores también REHIDRATAN
// el estado en deep-links/refresh — el bug que motivó la migración.

import { useEffect, useRef, useState } from 'react'
import { Outlet, useParams } from 'react-router'
import { Sidebar } from './componentes/Sidebar'
import { Topbar } from './componentes/Topbar'
import { Bandeja } from './componentes/Bandeja'
import { Configuracion } from './componentes/Configuracion'
import { DetalleSolicitud } from './componentes/DetalleSolicitud'
import { Chat } from './componentes/Chat'
import { Propuesta } from './componentes/Propuesta'
import { PropuestasLista } from './componentes/PropuestasLista'
import { Tareas } from './componentes/Tareas'
import { NotFound } from './componentes/NotFound'
import { OnboardingBienvenida } from './componentes/OnboardingBienvenida'
import { BannerError, CargandoLista } from './componentes/EstadoLista'
import {
  desconectarCorreo,
  iniciarConexionGmail,
} from './api/integraciones'
import { obtenerPropuesta } from './api/propuestas'
import { descargarCotizacionExcel, descargarCotizacionPpt } from './api/exportaciones'

import { SesionProvider, useSesion } from './contextos/SesionContext'
import { SolicitudProvider, useSolicitud } from './contextos/SolicitudContext'
import { BandejaProvider, useBandeja } from './contextos/BandejaContext'
import { useSolicitudDeRuta } from './hooks/useSolicitudDeRuta'
import type { Pantalla, ProveedorCorreo } from './tipos'

/** Navegación por defecto a URLs externas (OAuth); inyectable para tests. */
const NAVEGAR_NAVEGADOR = (url: string) => window.location.assign(url)

interface PropsConNavegar {
  /** Inyectable para tests: por defecto navega el navegador a la URL de OAuth. */
  onNavegar?: (url: string) => void
}

/** Handlers de conexión/desconexión del correo (compartidos por Configuración y Bandeja). */
function crearManejadoresCorreo(onNavegar: (url: string) => void) {
  return {
    async conectar(p: ProveedorCorreo) {
      if (p !== 'gmail') return
      try {
        const url = await iniciarConexionGmail()
        onNavegar(url)
      } catch {
        // Backend no cableado/caído: no navegamos a una URL inventada.
      }
    },
    async desconectar() {
      await desconectarCorreo()
    },
  }
}

// ── Raíz del árbol de rutas: providers DENTRO del router ─────────────────────
// SesionContext usa useNavigate/useLocation, así que los providers deben vivir
// bajo el RouterProvider. Orden: Sesion > Solicitud > Bandeja (Bandeja consume
// a los otros dos).

export function Raiz() {
  return (
    <SesionProvider>
      <SolicitudProvider>
        <BandejaProvider>
          <Outlet />
        </BandejaProvider>
      </SolicitudProvider>
    </SesionProvider>
  )
}

// ── Layout: marco de la app con <Outlet/> para la ruta activa ────────────────

export function Layout() {
  const { empresa, cerrarSesion, pantalla, irA, bienvenidaPendiente, cerrarBienvenida } = useSesion()
  const { solicitudActual } = useSolicitud()
  const { solicitudes } = useBandeja()

  // Estado estrictamente local de UI.
  const [menuAbierto, setMenuAbierto] = useState(false)

  // Wrapper local: irA del contexto + cerrar menú. El id de la solicitud activa
  // acompaña a las pantallas que lo necesitan en la URL (p. ej. "Conversaciones").
  function irANav(p: Pantalla) {
    irA(p, solicitudActual?.id)
    setMenuAbierto(false)
  }

  return (
    <div className="app">
      <Sidebar
        empresa={empresa}
        pantalla={pantalla}
        onIrA={irANav}
        conteoBandeja={solicitudes.length}
        menuAbierto={menuAbierto}
      />
      <div className={'scrim' + (menuAbierto ? ' show' : '')} onClick={() => setMenuAbierto(false)} />

      <div className="main">
        <Topbar empresa={empresa} pantalla={pantalla} onAbrirMenu={() => setMenuAbierto((v) => !v)} onCerrarSesion={cerrarSesion} />

        <div className="scroll">
          <Outlet />
        </div>
      </div>

      {bienvenidaPendiente && <OnboardingBienvenida onCerrar={cerrarBienvenida} />}
    </div>
  )
}

// ── /configuracion ───────────────────────────────────────────────────────────

export function RutaConfiguracion({ onNavegar = NAVEGAR_NAVEGADOR }: PropsConNavegar) {
  const { irA } = useSesion()
  const { estadoCorreo, cargandoCorreo } = useBandeja()
  const correo = crearManejadoresCorreo(onNavegar)

  return (
    <Configuracion
      estadoCorreo={estadoCorreo}
      cargandoCorreo={cargandoCorreo}
      onConectar={correo.conectar}
      onDesconectar={correo.desconectar}
      onIrA={irA}
      onNavegar={onNavegar}
    />
  )
}

// ── /bandeja ─────────────────────────────────────────────────────────────────

export function RutaBandeja({ onNavegar = NAVEGAR_NAVEGADOR }: PropsConNavegar) {
  const { abrirSolicitud } = useSolicitud()
  const {
    solicitudes,
    cargandoSolicitudes,
    errorSolicitudes,
    setReintentoSolicitudes,
    estadoCorreo,
  } = useBandeja()
  const correo = crearManejadoresCorreo(onNavegar)

  return (
    <Bandeja
      solicitudes={solicitudes}
      onAbrir={abrirSolicitud}
      proveedor={estadoCorreo.proveedor}
      estado={estadoCorreo.estado}
      onConectar={correo.conectar}
      onDesconectar={correo.desconectar}
      cargando={cargandoSolicitudes}
      error={errorSolicitudes}
      onReintentar={() => setReintentoSolicitudes((n) => n + 1)}
    />
  )
}

// ── /bandeja/:id — detalle de la solicitud ───────────────────────────────────

export function RutaDetalle() {
  const { id } = useParams()
  const { irA } = useSesion()
  const { iniciarChat } = useSolicitud()
  const { solicitud, noEncontrada } = useSolicitudDeRuta(id)

  if (noEncontrada) return <NotFound />
  if (!solicitud) return <PantallaCargando mensaje="Cargando solicitud…" />

  return <DetalleSolicitud solicitud={solicitud} onVolver={() => irA('inbox')} onElegirTipo={iniciarChat} />
}

// ── /bandeja/:id/chat — conversación con Javo ────────────────────────────────

export function RutaChat() {
  const { id } = useParams()
  const {
    tipo,
    mensajes,
    componentes,
    fuentes,
    enviando,
    recursos,
    chips,
    errorJavo,
    enviarMensaje,
    reintentarMensaje,
    generarPropuesta,
    rehidratarChat,
  } = useSolicitud()
  const { solicitud, noEncontrada } = useSolicitudDeRuta(id)

  // Rehidratación del hilo (deep-link/refresh): si el chat está vacío y NO hay
  // una conversación arrancando (iniciarChat ya rehidrata por su cuenta), se
  // repuebla desde el backend UNA vez por solicitud (el ref evita reintentos en
  // bucle cuando el backend no tiene historial).
  const rehidratado = useRef<string | null>(null)
  useEffect(() => {
    if (!id || rehidratado.current === id) return
    if (mensajes.length > 0 || enviando) {
      rehidratado.current = id
      return
    }
    rehidratado.current = id
    void rehidratarChat(id)
  }, [id, mensajes.length, enviando, rehidratarChat])

  if (noEncontrada) return <NotFound />
  if (!solicitud) return <PantallaCargando mensaje="Cargando conversación…" />

  return (
    <Chat
      solicitud={solicitud}
      tipo={tipo}
      mensajes={mensajes}
      componentes={componentes}
      fuentes={fuentes}
      recursos={recursos}
      chips={chips}
      enviando={enviando}
      errorJavo={errorJavo}
      onEnviar={enviarMensaje}
      onReintentar={reintentarMensaje}
      onGenerarPropuesta={generarPropuesta}
    />
  )
}

// ── /propuestas — lista de propuestas ────────────────────────────────────────

export function RutaPropuestas() {
  const {
    propuestas,
    cargandoPropuestas,
    errorPropuestas,
    setReintentoPropuestas,
    abrirPropuestaDesdeLista,
  } = useBandeja()

  return (
    <PropuestasLista
      propuestas={propuestas}
      onAbrir={abrirPropuestaDesdeLista}
      cargando={cargandoPropuestas}
      error={errorPropuestas}
      onReintentar={() => setReintentoPropuestas((n) => n + 1)}
    />
  )
}

// ── /propuestas/:id — propuesta resuelta de una solicitud ────────────────────

export function RutaPropuesta() {
  const { id } = useParams()
  const { irA } = useSesion()
  const {
    solicitudActual,
    componentes,
    setSolicitudActual,
    setComponentes,
    setTareas,
  } = useSolicitud()
  // Id cuya propuesta NO existe en el backend (deep-link sin propuesta guardada).
  const [idSinPropuesta, setIdSinPropuesta] = useState<string | null>(null)

  // La propuesta ya está en memoria cuando venimos del chat o de la lista.
  const idActual = solicitudActual?.id
  const cargada = !!id && idActual === id && componentes.length > 0

  // Rehidratación (deep-link/refresh): repuebla componentes/tareas desde el
  // backend — misma lógica que abrirPropuestaDesdeLista, pero a partir de la URL.
  useEffect(() => {
    if (!id || cargada) return
    let activo = true
    obtenerPropuesta(id).then((prop) => {
      if (!activo) return
      if (prop && prop.componentes.length) {
        setComponentes(prop.componentes)
        setTareas(prop.tareas)
        // Solicitud mínima para los exports; no pisa una solicitud ya cargada.
        if (idActual !== id) {
          setSolicitudActual({
            id,
            remitente: '',
            correo: '',
            tiempo: '',
            asunto: '',
            tipo: 't1',
            resumen: '',
            puntos: [],
            cuerpo: '',
          })
        }
      } else {
        setIdSinPropuesta(id)
      }
    })
    return () => {
      activo = false
    }
  }, [id, cargada, idActual, setComponentes, setTareas, setSolicitudActual])

  if (!cargada) {
    if (id && idSinPropuesta === id) {
      return <PantallaVacia mensaje="Abre una solicitud y conversa con Javo para generar su propuesta." />
    }
    return <PantallaCargando mensaje="Cargando propuesta…" />
  }

  return (
    <Propuesta
      componentes={componentes}
      onVolver={() => irA('chat', id)}
      onArmarTareas={() => irA('tareas')}
      onExportarExcel={id ? (vista) => descargarCotizacionExcel(id, vista) : undefined}
      onExportarPpt={id ? () => descargarCotizacionPpt(id) : undefined}
    />
  )
}

// ── /tareas — tareas generadas ───────────────────────────────────────────────

export function RutaTareas() {
  const { irA } = useSesion()
  const { solicitudActual, tareas } = useSolicitud()
  const { cargandoTareas, errorTareas, setReintentoTareas } = useBandeja()

  if (tareas.length) {
    return (
      <Tareas
        tareas={tareas}
        onVolver={() => irA('propuesta', solicitudActual?.id)}
        solicitudId={solicitudActual?.id}
        onExportarExcel={
          solicitudActual
            ? () => void descargarCotizacionExcel(solicitudActual.id, 'cliente')
            : undefined
        }
        onExportarPpt={
          solicitudActual ? () => void descargarCotizacionPpt(solicitudActual.id) : undefined
        }
      />
    )
  }

  if (errorTareas) {
    return (
      <section className="screen">
        <div className="wrap">
          <BannerError
            mensaje="No se pudieron cargar las tareas."
            onReintentar={() => setReintentoTareas((n) => n + 1)}
          />
        </div>
      </section>
    )
  }

  if (cargandoTareas) {
    return <PantallaCargando mensaje="Cargando tareas…" />
  }

  return <PantallaVacia mensaje="Aún no hay tareas. Genera una propuesta para que el sistema arme sus tareas." />
}

// ── Estados auxiliares ───────────────────────────────────────────────────────

/** Estado vacío simple cuando se navega a una pantalla sin datos que mostrar. */
function PantallaVacia({ mensaje }: { mensaje: string }) {
  return (
    <section className="screen">
      <div className="wrap">
        <div className="empty" style={{ marginTop: 40 }}>
          {mensaje}
        </div>
      </div>
    </section>
  )
}

/** "Cargando…" con el marco estándar de pantalla (mientras se rehidrata la ruta). */
function PantallaCargando({ mensaje }: { mensaje: string }) {
  return (
    <section className="screen">
      <div className="wrap">
        <CargandoLista mensaje={mensaje} />
      </div>
    </section>
  )
}

export default Layout
