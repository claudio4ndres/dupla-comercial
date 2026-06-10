import { useEffect, useState } from 'react'
import type { Tarea, Miembro } from '../tipos'
import { enviarTareasAClickUp, listarListasClickUp, type ListaClickUp } from '../api/clickup'
import { listarMiembros } from '../api/miembros'

// Clave en localStorage donde se recuerda la lista de ClickUp elegida (por-empresa,
// como un conector). Así el GP no la re-elige cada vez que entra a Tareas.
const CLAVE_LISTA = 'clickup.lista_elegida'

interface Props {
  tareas: Tarea[]
  onVolver: () => void
  /** Solicitud cuya propuesta se envía a ClickUp (sus tareas). */
  solicitudId?: string
}

export function Tareas({ tareas, onVolver, solicitudId }: Props) {
  // Listas reales del ClickUp del usuario (para el selector de destino). Sin token,
  // el backend devuelve [] → mostramos el aviso "Conecta ClickUp".
  const [listas, setListas] = useState<ListaClickUp[]>([])
  const [listaElegida, setListaElegida] = useState<string>(
    () => localStorage.getItem(CLAVE_LISTA) ?? '',
  )
  const [cargandoListas, setCargandoListas] = useState(true)
  const [enviando, setEnviando] = useState(false)
  // Mensaje de resultado del envío (éxito o error) para mostrarle al usuario.
  const [resultado, setResultado] = useState<string>('')
  // Roster de la empresa + asignación elegida por tarea (nombre_tarea → persona).
  const [miembros, setMiembros] = useState<Miembro[]>([])
  const [asignados, setAsignados] = useState<Record<string, string>>({})

  // Carga las listas reales de ClickUp al montar (conector por empresa).
  useEffect(() => {
    let activo = true
    listarListasClickUp().then((ls) => {
      if (!activo) return
      setListas(ls)
      setCargandoListas(false)
      // Si la lista recordada ya no existe (o no había), preselecciona la primera.
      setListaElegida((prev) => {
        if (prev && ls.some((l) => l.id === prev)) return prev
        return ls.length ? ls[0].id : ''
      })
    })
    return () => {
      activo = false
    }
  }, [])

  // Carga el roster de la empresa y pre-asigna cada tarea al miembro cuyo rol calce
  // con su área (asignación dinámica, 0006). El GP puede cambiarla por tarea.
  useEffect(() => {
    let activo = true
    listarMiembros().then((ms) => {
      if (!activo) return
      setMiembros(ms)
      setAsignados((prev) => {
        const next = { ...prev }
        for (const t of tareas) {
          if (next[t.nombre]) continue
          const m = ms.find((x) => x.rol.toLowerCase() === t.area.toLowerCase())
          if (m) next[t.nombre] = m.nombre
        }
        return next
      })
    })
    return () => {
      activo = false
    }
  }, [tareas])

  // Recuerda la elección en localStorage para la próxima visita.
  function elegirLista(id: string) {
    setListaElegida(id)
    localStorage.setItem(CLAVE_LISTA, id)
  }

  const hayConexion = listas.length > 0
  const puedeEnviar = hayConexion && !!solicitudId && !!listaElegida && !enviando

  async function enviar() {
    if (!solicitudId) return
    setEnviando(true)
    setResultado('')
    const r = await enviarTareasAClickUp(solicitudId, listaElegida, asignados)
    setEnviando(false)
    if (r) {
      const plural = r.creadas === 1 ? 'tarea creada' : 'tareas creadas'
      setResultado(`✓ ${r.creadas} ${plural} en ClickUp.`)
    } else {
      setResultado('⚠ No se pudo enviar a ClickUp. Revisa la conexión e inténtalo de nuevo.')
    }
  }

  return (
    <section className="screen">
      <div className="wrap">
        <div className="back" onClick={onVolver}>
          ‹ Volver a la propuesta
        </div>
        <div className="section-head">
          <div>
            <h1 className="page">Tareas generadas</h1>
            <p className="sub">
              El sistema arma las tareas a partir de la propuesta. Elige la lista de ClickUp y créalas con un clic.
            </p>
          </div>
        </div>

        <div>
          {tareas.map((t) => (
            <div key={t.nombre} className="task">
              <div className="chk" />
              <div style={{ flex: 1 }}>
                <div className="tnm">{t.nombre}</div>
                <div className="tmeta">
                  <span className="tg">{t.area}</span>
                  <span>⏱ {t.plazo}</span>
                </div>
              </div>
              {miembros.length > 0 ? (
                <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ color: 'var(--muted)', fontSize: 12 }}>Asignado a</span>
                  <select
                    className="select"
                    value={asignados[t.nombre] ?? ''}
                    onChange={(e) => setAsignados((p) => ({ ...p, [t.nombre]: e.target.value }))}
                    aria-label={`Asignado a · ${t.nombre}`}
                  >
                    <option value="">Sin asignar</option>
                    {miembros.map((m) => (
                      <option key={m.id} value={m.nombre}>
                        {m.nombre} · {m.rol}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <span className="tmeta">👤 {t.responsable}</span>
              )}
            </div>
          ))}
        </div>

        <div className="toolbar">
          {hayConexion ? (
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: 'var(--muted)', fontSize: 13 }}>Lista destino</span>
              <select
                className="select"
                value={listaElegida}
                onChange={(e) => elegirLista(e.target.value)}
                aria-label="Lista de ClickUp destino"
              >
                {listas.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.espacio ? `${l.espacio} · ${l.nombre}` : l.nombre}
                  </option>
                ))}
              </select>
            </label>
          ) : !cargandoListas ? (
            <span style={{ color: 'var(--muted)', fontSize: 13 }}>
              🔌 Conecta ClickUp en Configuración para crear las tareas.
            </span>
          ) : null}

          <button className="btn primary" onClick={enviar} disabled={!puedeEnviar}>
            {enviando ? 'Enviando…' : '↗ Enviar a ClickUp'}
          </button>
          <button className="btn ghost" onClick={() => alert('Exportar a PPT')}>
            ⤓ PPT
          </button>
          <button className="btn ghost" onClick={() => alert('Exportar a Excel')}>
            ⤓ Excel
          </button>
        </div>

        {resultado ? (
          <div className="note" role="status">
            <span>◆</span>
            <div>{resultado}</div>
          </div>
        ) : null}

        <div className="note">
          <span>◆</span>
          <div>
            Cada empresa (Capsulab, Espiga, etc.) tiene su propio espacio aislado: sus correos, conversaciones,
            propuestas y conexiones a Drive/ClickUp/Gmail. La arquitectura multi-tenant permite vender el mismo
            producto a varios clientes.
          </div>
        </div>
      </div>
    </section>
  )
}
