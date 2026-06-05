import { useEffect, useState } from 'react'
import { Sidebar } from './componentes/Sidebar'
import { Topbar } from './componentes/Topbar'
import { Bandeja } from './componentes/Bandeja'
import { DetalleSolicitud } from './componentes/DetalleSolicitud'
import { Chat } from './componentes/Chat'
import { Propuesta } from './componentes/Propuesta'
import { Tareas } from './componentes/Tareas'
import { Login } from './componentes/Login'
import { conversarConJavo } from './api/javo'
import {
  desconectarCorreo,
  ESTADO_DESCONECTADO,
  iniciarConexionGmail,
  obtenerEstadoCorreo,
  type EstadoCorreo,
} from './api/integraciones'
import { COMPONENTES_T1, EMPRESAS, SOLICITUDES, TAREAS_T1 } from './datosMock'
import type {
  Componente,
  Empresa,
  Mensaje,
  Pantalla,
  ProveedorCorreo,
  Sesion,
  Solicitud,
  TipoConfirmado,
} from './tipos'

/** Primer mensaje de Javo al iniciar la conversación, según el tipo. */
function introJavo(solicitud: Solicitud, tipo: TipoConfirmado): string {
  if (tipo === 't1') {
    return (
      `¡Hola! 👋 Leí el correo de ${solicitud.remitente}. Es una cotización concreta: ` +
      `${solicitud.resumen.toLowerCase()}\n\n` +
      'Vamos armando los componentes. ¿Confirmas que cotizamos catering, promotores, producto y ' +
      'uniforme para 5 horas diarias? ¿Cuántos días dura la activación?'
    )
  }
  return (
    `¡Hola! 👋 Leí el correo de ${solicitud.remitente}. Es un pedido de ideas, sin brief cerrado todavía.\n\n` +
    'Te tiro algunos conceptos para partir. Si quieres, puedo buscar referencias y opciones en ' +
    'internet — solo dime "busca en internet".'
  )
}

interface AppProps {
  /** Inyectable para tests: por defecto navega el navegador a la URL de OAuth. */
  onNavegar?: (url: string) => void
}

function App({ onNavegar = (url: string) => window.location.assign(url) }: AppProps = {}) {
  const [sesion, setSesion] = useState<Sesion | null>(null)
  const [empresa, setEmpresa] = useState<Empresa>(EMPRESAS[0])
  const [pantalla, setPantalla] = useState<Pantalla>('inbox')
  // Estado de la bandeja (proveedor + estado) según el backend (null = sin conectar).
  const [estadoCorreo, setEstadoCorreo] = useState<EstadoCorreo>(ESTADO_DESCONECTADO)
  const [solicitudActual, setSolicitudActual] = useState<Solicitud | null>(null)
  const [tipo, setTipo] = useState<TipoConfirmado>('t1')
  const [mensajes, setMensajes] = useState<Mensaje[]>([])
  const [componentes, setComponentes] = useState<Componente[]>([])
  const [enviando, setEnviando] = useState(false)
  const [menuAbierto, setMenuAbierto] = useState(false)

  // White-label: el color de marca cambia según la empresa activa.
  useEffect(() => {
    const raiz = document.documentElement
    raiz.style.setProperty('--brand', empresa.color)
    raiz.style.setProperty('--brand-soft', empresa.color + '22')
  }, [empresa])

  // Carga el estado real de la bandeja desde el backend (T13) y lo recarga al
  // cambiar de empresa (cada tenant tiene su propia conexión).
  useEffect(() => {
    let activo = true
    obtenerEstadoCorreo().then((e) => {
      if (activo) setEstadoCorreo(e)
    })
    return () => {
      activo = false
    }
  }, [empresa])

  function irA(p: Pantalla) {
    setPantalla(p)
    setMenuAbierto(false)
  }

  function iniciarSesion(correo: string) {
    // Mock: cualquier credencial entra. Luego: Supabase Auth + empresa_id (RLS).
    setSesion({ correo })
  }

  function cambiarEmpresa(e: Empresa) {
    setEmpresa(e)
    // Cada empresa (tenant) conecta su propia bandeja: al cambiar, se resetea
    // (el efecto sobre [empresa] recarga el estado real desde el backend).
    setEstadoCorreo(ESTADO_DESCONECTADO)
    irA('inbox')
  }

  async function conectarProveedor(p: ProveedorCorreo) {
    // Sólo Gmail en esta etapa (Spec 002). El backend entrega la URL de
    // consentimiento (con el `state` anti-CSRF y el scope mínimo `gmail.readonly`);
    // el front NUNCA la inventa (regla de oro #3). Tras autorizar, Google vuelve
    // al callback y el backend deja la integración en 'conectado'.
    if (p !== 'gmail') return
    try {
      const url = await iniciarConexionGmail()
      onNavegar(url)
    } catch {
      // Backend no cableado/caído: no navegamos a una URL inventada.
    }
  }

  async function desconectarProveedor() {
    // El "Cambiar": borra integración + secreto en el backend y vuelve a "conectar".
    await desconectarCorreo()
    setEstadoCorreo(ESTADO_DESCONECTADO)
  }

  function abrirSolicitud(s: Solicitud) {
    setSolicitudActual(s)
    irA('detail')
  }

  function iniciarChat(t: TipoConfirmado) {
    if (!solicitudActual) return
    setTipo(t)
    setComponentes([])
    setMensajes([{ rol: 'javo', contenido: introJavo(solicitudActual, t) }])
    irA('chat')
  }

  async function enviarMensaje(texto: string) {
    if (!solicitudActual) return
    const nuevos: Mensaje[] = [...mensajes, { rol: 'usuario', contenido: texto }]
    if (tipo === 't2' && /internet|busca|referencia|opciones/i.test(texto)) {
      nuevos.push({ rol: 'sistema', contenido: 'Javo está buscando referencias y opciones en internet…' })
    }
    setMensajes(nuevos)
    setEnviando(true)

    const respuesta = await conversarConJavo({ solicitudId: solicitudActual.id, tipo, mensajes: nuevos })
    setMensajes((prev) => [...prev, { rol: 'javo', contenido: respuesta }])
    setEnviando(false)

    // Demo: cuando Javo ofrece generar la propuesta (Tipo 1), poblamos componentes.
    if (tipo === 't1' && /propuesta|componentes|cotiza/i.test(respuesta) && componentes.length === 0) {
      setComponentes(COMPONENTES_T1)
    }
  }

  function generarPropuesta() {
    if (componentes.length === 0) setComponentes(COMPONENTES_T1)
    irA('propuesta')
  }

  // Para navegación directa por el menú, mostramos datos de ejemplo si no hay aún.
  const componentesPropuesta = componentes.length ? componentes : COMPONENTES_T1

  // Sin sesión iniciada, no se entra a la app: primero el login.
  if (!sesion) {
    return <Login onEntrar={iniciarSesion} />
  }

  return (
    <div className="app">
      <Sidebar
        empresas={EMPRESAS}
        empresaActiva={empresa}
        onCambiarEmpresa={cambiarEmpresa}
        pantalla={pantalla}
        onIrA={irA}
        conteoBandeja={SOLICITUDES.length}
        menuAbierto={menuAbierto}
      />
      <div className={'scrim' + (menuAbierto ? ' show' : '')} onClick={() => setMenuAbierto(false)} />

      <div className="main">
        <Topbar empresa={empresa} pantalla={pantalla} onAbrirMenu={() => setMenuAbierto((v) => !v)} />

        <div className="scroll">
          {pantalla === 'inbox' && (
            <Bandeja
              solicitudes={SOLICITUDES}
              onAbrir={abrirSolicitud}
              proveedor={estadoCorreo.proveedor}
              estado={estadoCorreo.estado}
              onConectar={conectarProveedor}
              onDesconectar={desconectarProveedor}
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
                enviando={enviando}
                onEnviar={enviarMensaje}
                onGenerarPropuesta={generarPropuesta}
              />
            ) : (
              <PantallaVacia mensaje="Abre una solicitud de la bandeja para conversar con Javo." />
            ))}

          {pantalla === 'propuesta' && (
            <Propuesta
              componentes={componentesPropuesta}
              onVolver={() => irA('chat')}
              onArmarTareas={() => irA('tareas')}
            />
          )}

          {pantalla === 'tareas' && <Tareas tareas={TAREAS_T1} onVolver={() => irA('propuesta')} />}
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
