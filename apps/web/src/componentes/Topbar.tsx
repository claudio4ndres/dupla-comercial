import type { Empresa, Pantalla } from '../tipos'

interface Props {
  empresa: Empresa
  pantalla: Pantalla
  onAbrirMenu: () => void
  onCerrarSesion: () => void
}

const NOMBRE_PANTALLA: Record<Pantalla, string> = {
  configuracion: 'Configuración · conectores',
  inbox: 'Bandeja de solicitudes',
  detail: 'Solicitud',
  chat: 'Conversación con Javo',
  propuestas: 'Propuestas',
  propuesta: 'Propuesta resuelta',
  tareas: 'Tareas generadas',
}

export function Topbar({ empresa, pantalla, onAbrirMenu, onCerrarSesion }: Props) {
  return (
    <div className="topbar">
      <div className="menu-btn" onClick={onAbrirMenu}>
        <svg width="18" height="18" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2" fill="none">
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </div>
      <div className="crumb">
        <b>{empresa.nombre}</b> <span>· {NOMBRE_PANTALLA[pantalla]}</span>
      </div>
      <div className="spacer" />
      <span className="pill">
        <span className="led" /> Claude conectado
      </span>
      <button
        className="btn ghost"
        style={{ fontSize: '0.8rem', padding: '4px 10px' }}
        onClick={onCerrarSesion}
        title="Cerrar sesión"
      >
        Salir
      </button>
    </div>
  )
}
