import { useEffect, useState } from 'react'
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
import { conversarConJavo } from './api/javo'
import {
  desconectarCorreo,
  ESTADO_DESCONECTADO,
  iniciarConexionGmail,
  obtenerEstadoCorreo,
  type EstadoCorreo,
} from './api/integraciones'
import { obtenerSolicitudes } from './api/solicitudes'
import { obtenerEmpresa } from './api/empresa'
import {
  guardarPropuesta,
  listarPropuestas,
  obtenerPropuesta,
  type PropuestaResumen,
} from './api/propuestas'
import { listarTareas } from './api/tareas'
import { descargarCotizacionExcel, descargarCotizacionPpt } from './api/exportaciones'
import { obtenerRecursosDrive } from './api/recursos'
import { obtenerHistorialConversacion } from './api/conversaciones'
import { supabase } from './supabase/cliente'
import { EMPRESAS, type RecursoDrive } from './datosMock'
import type {
  Componente,
  Empresa,
  Fuente,
  Mensaje,
  Pantalla,
  ProveedorCorreo,
  Sesion,
  Solicitud,
  Tarea,
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
  // Sesión reactiva: null = cargando (undefined), null = sin sesión, Sesion = autenticado.
  // Usamos undefined para distinguir "aún no sé" de "no hay sesión" y evitar flash del login.
  const [sesion, setSesion] = useState<Sesion | null | undefined>(undefined)

  useEffect(() => {
    // Leer sesión inicial desde el almacenamiento del cliente de Supabase.
    supabase.auth.getSession().then(({ data }) => {
      setSesion(data.session ? { correo: data.session.user.email ?? '' } : null)
    })
    // Suscribirse a cambios (login / logout / refresh de token).
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSesion(session ? { correo: session.user.email ?? '' } : null)
    })
    return () => subscription.unsubscribe()
  }, [])
  const [empresa, setEmpresa] = useState<Empresa>(EMPRESAS[0])
  // Landing post-login: el onboarding de Configuración (cada empresa "prepara su
  // espacio" conectando sus conectores). Desde ahí se continúa a la bandeja.
  const [pantalla, setPantalla] = useState<Pantalla>('configuracion')
  // Estado de la bandeja (proveedor + estado) según el backend (null = sin conectar).
  const [estadoCorreo, setEstadoCorreo] = useState<EstadoCorreo>(ESTADO_DESCONECTADO)
  // Solicitudes REALES de la empresa (las que el poller ingirió desde el correo).
  const [solicitudes, setSolicitudes] = useState<Solicitud[]>([])
  // Propuestas REALES de la empresa (lista del menú "Propuestas").
  const [propuestas, setPropuestas] = useState<PropuestaResumen[]>([])
  const [solicitudActual, setSolicitudActual] = useState<Solicitud | null>(null)
  const [tipo, setTipo] = useState<TipoConfirmado>('t1')
  const [mensajes, setMensajes] = useState<Mensaje[]>([])
  const [componentes, setComponentes] = useState<Componente[]>([])
  // Tareas de la cotización (vienen del backend junto con los componentes).
  const [tareas, setTareas] = useState<Tarea[]>([])
  // Fuentes que Javo citó en la conversación (recursos del Drive / web) — 005.
  const [fuentes, setFuentes] = useState<Fuente[]>([])
  // Recursos del Drive de la empresa (panel del chat): reales desde el catálogo.
  const [recursos, setRecursos] = useState<RecursoDrive[]>([])
  const [enviando, setEnviando] = useState(false)
  const [menuAbierto, setMenuAbierto] = useState(false)

  // White-label: el color de marca cambia según la empresa activa.
  useEffect(() => {
    const raiz = document.documentElement
    raiz.style.setProperty('--brand', empresa.color)
    raiz.style.setProperty('--brand-soft', empresa.color + '22')
  }, [empresa])

  // El header/branding (nombre, color) sale del tenant REAL del usuario, no del mock:
  // al haber sesión se pide la empresa al backend y se reemplaza el placeholder.
  useEffect(() => {
    if (!sesion) return
    let activo = true
    obtenerEmpresa().then((e) => {
      if (activo && e) setEmpresa(e)
    })
    return () => {
      activo = false
    }
  }, [sesion])

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

  // Recursos del Drive de la empresa (panel del chat): se leen del catálogo real
  // (ya no es un mock estático). Por empresa (cada tenant su Drive).
  useEffect(() => {
    let activo = true
    obtenerRecursosDrive().then((r) => {
      if (activo) setRecursos(r)
    })
    return () => {
      activo = false
    }
  }, [empresa])

  // Carga las solicitudes REALES cuando la bandeja está conectada y cada vez que
  // se vuelve a la pantalla de bandeja (así aparecen los correos que el poller
  // fue ingiriendo). Sin conexión, la lista queda vacía (ya no hay mock).
  useEffect(() => {
    if (estadoCorreo.estado !== 'conectado') {
      // Sin bandeja conectada no hay solicitudes que mostrar. Limpiar aquí es
      // sincronizar con el backend (no es estado derivado), de ahí el disable.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSolicitudes([])
      return
    }
    if (pantalla !== 'inbox') return
    let activo = true
    obtenerSolicitudes().then((s) => {
      if (activo) setSolicitudes(s)
    })
    return () => {
      activo = false
    }
  }, [empresa, estadoCorreo.estado, pantalla])

  // Carga la lista REAL de propuestas al entrar a la pantalla "Propuestas" del
  // menú (y al cambiar de empresa). Sin sesión/backend, queda vacía (sin mock).
  useEffect(() => {
    if (pantalla !== 'propuestas') return
    let activo = true
    listarPropuestas().then((p) => {
      if (activo) setPropuestas(p)
    })
    return () => {
      activo = false
    }
  }, [empresa, pantalla])

  // Carga la lista REAL de tareas al entrar a "Tareas" por el menú SIN tareas en
  // estado. Si se viene del flujo de una propuesta (tareas ya cargadas), se
  // respetan esas y no se pisan con la lista global.
  useEffect(() => {
    if (pantalla !== 'tareas' || tareas.length > 0) return
    let activo = true
    listarTareas().then((t) => {
      if (activo) setTareas(t)
    })
    return () => {
      activo = false
    }
  }, [empresa, pantalla, tareas.length])

  function irA(p: Pantalla) {
    setPantalla(p)
    setMenuAbierto(false)
  }

  function iniciarSesion(correo: string) {
    // onAuthStateChange ya actualizó `sesion`; este callback sólo sirve de
    // puente para que Login.tsx pueda seguir usando la misma prop `onEntrar`.
    void correo
  }

  async function cerrarSesion() {
    await supabase.auth.signOut()
    // onAuthStateChange pondrá sesion = null automáticamente.
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
    const sol = solicitudActual
    setTipo(t)
    setComponentes([])
    setTareas([])
    setFuentes([])
    setMensajes([{ rol: 'javo', contenido: introJavo(sol, t) }])
    irA('chat')
    // Rehidrata el hilo persistido (T14): si ya hubo conversación para esta
    // solicitud, reemplaza el saludo inicial; si no, el chat parte desde el saludo.
    obtenerHistorialConversacion(sol.id).then((historial) => {
      if (historial.length) setMensajes(historial)
    })
    // Precarga los componentes de la propuesta existente (T15): si esta solicitud ya
    // tiene cotización, el panel "Componentes" deja de estar vacío al abrir el chat.
    obtenerPropuesta(sol.id).then((prop) => {
      if (prop && prop.componentes.length) setComponentes(prop.componentes)
    })
  }

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

    // Javo propone los componentes (con su valor REAL del Drive y su origen) y cita
    // sus fuentes (005). Pueblan el panel lateral del chat; el GP los confirma y, al
    // "Generar propuesta", pasan a la cotización (spec 004). No se persisten aquí.
    if (r.componentes.length) setComponentes(r.componentes)
    if (r.tareas.length) setTareas(r.tareas)
    if (r.fuentes.length) setFuentes(r.fuentes)
  }

  async function generarPropuesta() {
    if (!solicitudActual) return
    // PERSISTE lo que Javo armó en el chat (componentes + tareas) y muestra lo guardado.
    // Si la conversación no propuso nada (componentes/tareas vacíos), intenta leer una
    // propuesta previa. Antes esto solo hacía GET → 404 con datos reales y se perdía
    // todo lo construido en el chat.
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

  // Abre el DETALLE de una propuesta desde la lista del menú. Pide la cotización
  // real (componentes + tareas) y arma un `solicitudActual` mínimo con los datos
  // de la fila (id, asunto, remitente) para que los botones de export sigan
  // funcionando; reutiliza la pantalla `'propuesta'` (la misma del chat).
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

  // undefined = aún resolviendo la sesión (evita flash al login en recarga).
  if (sesion === undefined) return null

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
            <PropuestasLista propuestas={propuestas} onAbrir={abrirPropuestaDesdeLista} />
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
              />
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
