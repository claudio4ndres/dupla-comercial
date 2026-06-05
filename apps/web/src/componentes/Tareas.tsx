import type { Tarea } from '../tipos'

interface Props {
  tareas: Tarea[]
  onVolver: () => void
}

export function Tareas({ tareas, onVolver }: Props) {
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
              El sistema arma las tareas a partir de la propuesta. Al confirmar, se disparan a ClickUp vía API.
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
                  <span>👤 {t.responsable}</span>
                  <span>⏱ {t.plazo}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="toolbar">
          <button
            className="btn primary"
            onClick={() => alert('Enviando tareas a ClickUp vía API… ✓ creadas. Reportes y responsables asignados.')}
          >
            ↗ Enviar a ClickUp
          </button>
          <button className="btn ghost" onClick={() => alert('Exportar a PPT')}>
            ⤓ PPT
          </button>
          <button className="btn ghost" onClick={() => alert('Exportar a Excel')}>
            ⤓ Excel
          </button>
        </div>

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
