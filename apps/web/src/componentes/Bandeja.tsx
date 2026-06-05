import { ETIQUETA_TIPO, NOMBRE_PROVEEDOR, type ProveedorCorreo, type Solicitud } from '../tipos'
import { PROVEEDORES_CORREO } from '../datosMock'

interface Props {
  solicitudes: Solicitud[]
  onAbrir: (solicitud: Solicitud) => void
  /** Proveedor de correo conectado, o `null` si aún no se conecta ninguno. */
  proveedor: ProveedorCorreo | null
  /**
   * Estado de la conexión según el backend: `'conectado'` (escuchando),
   * `'reconectar'` (token caído, CA7) o `null`/sin dato (se asume conectado si
   * hay proveedor). Opcional para no romper usos previos.
   */
  estado?: 'conectado' | 'reconectar' | null
  onConectar: (proveedor: ProveedorCorreo) => void
  onDesconectar: () => void
}

/** Color de la franja izquierda según el tipo sugerido. */
function colorStripe(tipo: Solicitud['tipo']): string {
  if (tipo === 't2') return 'var(--t2)'
  if (tipo === 'new') return '#cdbf90'
  return 'var(--brand)'
}

export function Bandeja({ solicitudes, onAbrir, proveedor, estado, onConectar, onDesconectar }: Props) {
  return (
    <section className="screen">
      <div className="wrap">
        <div className="section-head">
          <div>
            <h1 className="page">Bandeja de solicitudes</h1>
            <p className="sub">
              Correos entrantes. El sistema arma un resumen para que revises rápido sin perder el criterio
              creativo — tú decides el tipo.
            </p>
          </div>
        </div>

        {proveedor === null ? (
          <div className="connect">
            <div className="connect-text">
              <b>Conecta tu bandeja de entrada</b>
              <span>
                Elige tu proveedor para empezar a recibir los correos y que Javo los clasifique
                automáticamente.
              </span>
            </div>
            <div className="connect-options">
              {PROVEEDORES_CORREO.map((p) => (
                <button key={p.id} className="btn ghost prov" onClick={() => onConectar(p.id)}>
                  <span className="prov-ico">{p.icono}</span>
                  {p.nombre}
                </button>
              ))}
            </div>
          </div>
        ) : estado === 'reconectar' ? (
          <div className="listening reconnect">
            <span className="led-warn" />
            Reconecta tu bandeja · <b>{NOMBRE_PROVEEDOR[proveedor]}</b> — el acceso expiró.
            <button className="link-mini" onClick={() => onConectar(proveedor)}>
              Reconectar
            </button>
          </div>
        ) : (
          <div className="listening">
            <span className="led-live" />
            Escuchando nuevos correos · <b>{NOMBRE_PROVEEDOR[proveedor]}</b>
            <button className="link-mini" onClick={onDesconectar}>
              Cambiar
            </button>
          </div>
        )}

        <div>
          {solicitudes.map((s) => (
            <div key={s.id} className="mail" onClick={() => onAbrir(s)}>
              <div className="stripe" style={{ background: colorStripe(s.tipo) }} />
              <div className="row1">
                <span className="from">{s.remitente}</span>
                <span className={'badge ' + s.tipo}>{ETIQUETA_TIPO[s.tipo]}</span>
                <span className="time">{s.tiempo}</span>
              </div>
              <div className="subj">{s.asunto}</div>
              <div className="snip">{s.resumen}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
