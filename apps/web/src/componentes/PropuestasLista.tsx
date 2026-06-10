import { fmtCLP } from '../tipos'
import type { PropuestaResumen } from '../api/propuestas'

interface Props {
  propuestas: PropuestaResumen[]
  /** Abre el detalle de una propuesta a partir de su solicitud. */
  onAbrir: (solicitudId: string) => void
}

/**
 * Lista de propuestas de la empresa (entrada desde el menú "Propuestas"). Cada
 * fila muestra el asunto del correo, el remitente, el total (CLP) y el estado.
 * Al hacer clic se abre el detalle (la cotización resuelta) de esa solicitud.
 */
export function PropuestasLista({ propuestas, onAbrir }: Props) {
  return (
    <section className="screen">
      <div className="wrap">
        <div className="section-head">
          <div>
            <h1 className="page">Propuestas</h1>
            <p className="sub">
              Cotizaciones que Javo ya resolvió. Abre una para ver el detalle, exportarla o armar sus tareas.
            </p>
          </div>
        </div>

        {propuestas.length === 0 ? (
          <div className="empty" style={{ marginTop: 40 }}>
            Aún no hay propuestas. Abre una solicitud de la bandeja y conversa con Javo para generar la primera.
          </div>
        ) : (
          <div>
            {propuestas.map((p) => (
              <div key={p.id} className="mail" onClick={() => onAbrir(p.solicitudId)}>
                <div className="stripe" />
                <div className="row1">
                  <span className="from">{p.remitente}</span>
                  <span className="badge done">{p.estado}</span>
                  <span className="time">{fmtCLP(p.total)}</span>
                </div>
                <div className="subj">{p.asunto}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
