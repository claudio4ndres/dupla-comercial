import type { ReactNode } from 'react'
import type { Empresa, Pantalla } from '../tipos'

interface Props {
  /** Empresa activa (viene del backend vía SesionContext). */
  empresa: Empresa
  pantalla: Pantalla
  onIrA: (pantalla: Pantalla) => void
  conteoBandeja: number
  menuAbierto: boolean
}

/** Ítems de navegación con su ícono (SVG inline, como el prototipo). */
const NAV: { id: Pantalla; etiqueta: string; icono: ReactNode }[] = [
  {
    id: 'inbox',
    etiqueta: 'Bandeja',
    icono: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M4 5h16v14H4z" />
        <path d="M4 7l8 6 8-6" />
      </svg>
    ),
  },
  {
    id: 'chat',
    etiqueta: 'Conversaciones',
    icono: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M4 5h16v11H8l-4 4z" />
      </svg>
    ),
  },
  {
    id: 'propuestas',
    etiqueta: 'Propuestas',
    icono: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M6 3h9l4 4v14H6z" />
        <path d="M14 3v5h5" />
      </svg>
    ),
  },
  {
    id: 'tareas',
    etiqueta: 'Tareas',
    icono: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M9 11l2 2 4-4" />
        <rect x="4" y="4" width="16" height="16" rx="3" />
      </svg>
    ),
  },
]

export function Sidebar({
  empresa,
  pantalla,
  onIrA,
  conteoBandeja,
  menuAbierto,
}: Props) {
  return (
    <aside className={'sidebar' + (menuAbierto ? ' show' : '')}>
      <div className="ws">
        <div className="ws-mark" style={{ background: empresa.color }}>
          {empresa.marca}
        </div>
        <div>
          <div className="ws-name">{empresa.nombre}</div>
          <div className="ws-tag">{empresa.etiqueta ?? 'Plan piloto · BTL'}</div>
        </div>
      </div>

      <div className="nav-label">Operación</div>
      {NAV.map((item) => (
        <div
          key={item.id}
          className={'nav-item' + (pantalla === item.id ? ' active' : '')}
          onClick={() => onIrA(item.id)}
        >
          {item.icono}
          {item.etiqueta}
          {item.id === 'inbox' && <span className="count">{conteoBandeja}</span>}
        </div>
      ))}

      <div className="nav-label">Cuenta</div>
      <div
        className={'nav-item' + (pantalla === 'configuracion' ? ' active' : '')}
        onClick={() => onIrA('configuracion')}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
        </svg>
        Configuración
      </div>

      <div className="side-foot">
        <div className="avatar">JA</div>
        <div>
          <div className="nm">Javo</div>
          <div className="rl">Gestor de proyectos</div>
        </div>
      </div>
    </aside>
  )
}
