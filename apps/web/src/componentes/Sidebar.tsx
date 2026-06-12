import { useState, type ReactNode } from 'react'
import type { Empresa, Pantalla } from '../tipos'

interface Props {
  empresas: Empresa[]
  empresaActiva: Empresa
  onCambiarEmpresa: (empresa: Empresa) => void
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
  empresas,
  empresaActiva,
  onCambiarEmpresa,
  pantalla,
  onIrA,
  conteoBandeja,
  menuAbierto,
}: Props) {
  const [menuEmpresas, setMenuEmpresas] = useState(false)

  return (
    <aside className={'sidebar' + (menuAbierto ? ' show' : '')}>
      <div className="ws" onClick={() => setMenuEmpresas((v) => !v)}>
        <div className="ws-mark" style={{ background: empresaActiva.color }}>
          {empresaActiva.marca}
        </div>
        <div>
          <div className="ws-name">{empresaActiva.nombre}</div>
          <div className="ws-tag">{empresaActiva.etiqueta ?? 'Plan piloto · BTL'}</div>
        </div>
        <div className="ws-caret">▾</div>
      </div>

      <div className={'ws-menu' + (menuEmpresas ? ' open' : '')}>
        {empresas.map((e) => {
          const activa = e.nombre === empresaActiva.nombre
          return (
            <div
              key={e.nombre}
              className="ws-item"
              onClick={() => {
                onCambiarEmpresa(e)
                setMenuEmpresas(false)
              }}
            >
              <span className="dot" style={{ background: e.color }}>
                {e.marca}
              </span>
              {e.nombre}
              {activa && <span style={{ marginLeft: 'auto', fontSize: 11, color: '#a39b87' }}>activo</span>}
            </div>
          )
        })}
        {/* Alta de empresa: aún no hay flujo de onboarding self-service, así que el
            control va DESHABILITADO (no debe parecer funcional). Se habilitará cuando
            exista el alta de empresa. */}
        <button
          type="button"
          className="ws-item add"
          disabled
          title="Próximamente"
          style={{
            width: '100%',
            textAlign: 'left',
            background: 'transparent',
            border: 'none',
            font: 'inherit',
            color: 'inherit',
            opacity: 0.5,
            cursor: 'not-allowed',
          }}
        >
          ＋ Nueva empresa
        </button>
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
