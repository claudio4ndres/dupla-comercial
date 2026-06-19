import { useState } from 'react'
import { Sidebar } from './componentes/Sidebar'
import { Topbar } from './componentes/Topbar'
import { Bandeja } from './componentes/Bandeja'
import { Configuracion } from './componentes/Configuracion'
import { DetalleSolicitud } from './componentes/DetalleSolicitud'
import { Chat } from './componentes/Chat'
import { Propuesta } from './componentes/Propuesta'
import { PropuestasLista } from './componentes/PropuestasLista'
import { Tareas } from './componentes/Tareas'
import { Login } from './componentes/Login'
import { BannerError, CargandoLista } from './componentes/EstadoLista'
import {
  desconectarCorreo,
  iniciarConexionGmail,
} from './api/integraciones'
import { descargarCotizacionExcel, descargarCotizacionPpt } from './api/exportaciones'

import { useSesion } from './contextos/SesionContext'
import { useSolicitud } from './contextos/SolicitudContext'
import { useBandeja } from './contextos/BandejaContext'
import type {
  Pantalla,
  ProveedorCorreo,
} from './tipos'

interface AppProps {
  /** Inyectable para tests: por defecto navega el navegador a la URL de OAuth. */
  onNavegar?: (url: string) => void
}

function App({ onNavegar = (url: string) => window.location.assign(url) }: AppProps = {}) {
  // Estado de sesión, empresa y navegación provienen del contexto.
  const { sesion, empresa, cerrarSesion, pantalla, irA: irAContexto } = useSesion()

  // Estado de la solicitud activa, chat y cotización provienen del contexto.
  const {
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
  } = useSolicitud()

  // Estado de la bandeja (solicitudes, propuestas, tareas globales, correo) del contexto.
  const {
    solicitudes,
    cargandoSolicitudes,
    errorSolicitudes,
    setReintentoSolicitudes,
    propuestas,
    cargandoPropuestas,
    errorPropuestas,
    setReintentoPropuestas,
    cargandoTareas,
    errorTareas,
    setReintentoTareas,
    estadoCorreo,
    cargandoCorreo,
    abrirPropuestaDesdeLista,
  } = useBandeja()

  // Estado estrictamente local de UI.
  const [menuAbierto, setMenuAbierto] = useState(false)

  // Wrapper local: irA del contexto + cerrar menú (estado local de UI).
  function irA(p: Pantalla) {
    irAContexto(p)
    setMenuAbierto(false)
  }

  function iniciarSesion(correo: string) {
    void correo
  }

  async function conectarProveedor(p: ProveedorCorreo) {
    if (p !== 'gmail') return
    try {
      const url = await iniciarConexionGmail()
      onNavegar(url)
    } catch {
      // Backend no cableado/caído: no navegamos a una URL inventada.
    }
  }

  async function desconectarProveedor() {
    await desconectarCorreo()
  }

  // undefined = aún resolviendo la sesión (evita flash al login en recarga).
  if (sesion === undefined) return null

  // Sin sesión iniciada, no se entra a la app: primero el login.
  if (!sesion) {
    return <Login onEntrar={iniciarSesion} />
  }

  return (
    <div className="app">
      <Sidebar
        empresa={empresa}
        pantalla={pantalla}
        onIrA={irA}
        conteoBandeja={solicitudes.length}
        menuAbierto={menuAbierto}
      />
      <div className={'scrim' + (menuAbierto ? ' show' : '')} onClick={() => setMenuAbierto(false)} />

      <div className="main">
        <Topbar empresa={empresa} pantalla={pantalla} onAbrirMenu={() => setMenuAbierto((v) => !v)} onCerrarSesion={cerrarSesion} />

        <div className="scroll">
          {pantalla === 'configuracion' && (
            <Configuracion
              estadoCorreo={estadoCorreo}
              cargandoCorreo={cargandoCorreo}
              onConectar={conectarProveedor}
              onDesconectar={desconectarProveedor}
              onIrA={irA}
              onNavegar={onNavegar}
            />
          )}

          {pantalla === 'inbox' && (
            <Bandeja
              solicitudes={solicitudes}
              onAbrir={abrirSolicitud}
              proveedor={estadoCorreo.proveedor}
              estado={estadoCorreo.estado}
              onConectar={conectarProveedor}
              onDesconectar={desconectarProveedor}
              cargando={cargandoSolicitudes}
              error={errorSolicitudes}
              onReintentar={() => setReintentoSolicitudes((n) => n + 1)}
            />
          )}

          {pantalla === 'detail' &&
            (solicitudActual ? (
              <DetalleSolicitud solicitud={solicitudActual} onVolver={() => irA('inbox')} onElegirTipo={iniciarChat} />
            ) : (
              <PantallaVacia mensaje="Abre una solicitud desde la bandeja." />
            ))}

          {pantalla === 'chat' &&
            (solicitudActual ? (
              <Chat
                solicitud={solicitudActual}
                tipo={tipo}
                mensajes={mensajes}
                componentes={componentes}
                fuentes={fuentes}
                recursos={recursos}
                enviando={enviando}
                onEnviar={enviarMensaje}
                onGenerarPropuesta={generarPropuesta}
              />
            ) : (
              <PantallaVacia mensaje="Abre una solicitud de la bandeja para conversar con Javo." />
            ))}

          {pantalla === 'propuestas' && (
            <PropuestasLista
              propuestas={propuestas}
              onAbrir={abrirPropuestaDesdeLista}
              cargando={cargandoPropuestas}
              error={errorPropuestas}
              onReintentar={() => setReintentoPropuestas((n) => n + 1)}
            />
          )}

          {pantalla === 'propuesta' &&
            (componentes.length ? (
              <Propuesta
                componentes={componentes}
                onVolver={() => irA('chat')}
                onArmarTareas={() => irA('tareas')}
                onExportarExcel={
                  solicitudActual
                    ? (vista) => void descargarCotizacionExcel(solicitudActual.id, vista)
                    : undefined
                }
                onExportarPpt={
                  solicitudActual ? () => void descargarCotizacionPpt(solicitudActual.id) : undefined
                }
              />
            ) : (
              <PantallaVacia mensaje="Abre una solicitud y conversa con Javo para generar su propuesta." />
            ))}

          {pantalla === 'tareas' &&
            (tareas.length ? (
              <Tareas
                tareas={tareas}
                onVolver={() => irA('propuesta')}
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
            ) : errorTareas ? (
              <section className="screen">
                <div className="wrap">
                  <BannerError
                    mensaje="No se pudieron cargar las tareas."
                    onReintentar={() => setReintentoTareas((n) => n + 1)}
                  />
                </div>
              </section>
            ) : cargandoTareas ? (
              <section className="screen">
                <div className="wrap">
                  <CargandoLista mensaje="Cargando tareas…" />
                </div>
              </section>
            ) : (
              <PantallaVacia mensaje="Aún no hay tareas. Genera una propuesta para que el sistema arme sus tareas." />
            ))}
        </div>
      </div>
    </div>
  )
}

/** Estado vacío simple cuando se navega a una pantalla sin solicitud activa. */
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

export default App
