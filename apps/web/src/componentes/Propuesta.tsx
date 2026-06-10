import { fmtCLP, type Componente } from '../tipos'

interface Props {
  componentes: Componente[]
  onVolver: () => void
  onArmarTareas: () => void
  /** Descarga la cotización como .xlsx con el theme Capsulab (007). */
  onExportarExcel?: () => void
}

export function Propuesta({ componentes, onVolver, onArmarTareas, onExportarExcel }: Props) {
  const total = componentes.reduce((acc, c) => acc + c.valor * c.cantidad, 0)

  return (
    <section className="screen">
      <div className="wrap">
        <div className="back" onClick={onVolver}>
          ‹ Volver a la conversación
        </div>
        <div className="section-head">
          <div>
            <h1 className="page">Propuesta resuelta</h1>
            <p className="sub">Componentes definidos en la conversación y valorizados con datos del Drive.</p>
          </div>
        </div>

        <div className="card">
          <table className="ptable">
            <thead>
              <tr>
                <th>Componente</th>
                <th>Detalle</th>
                <th style={{ textAlign: 'right' }}>Cant.</th>
                <th style={{ textAlign: 'right' }}>Valor unit.</th>
                <th style={{ textAlign: 'right' }}>Subtotal</th>
              </tr>
            </thead>
            <tbody>
              {componentes.map((c) => (
                <tr key={c.nombre}>
                  <td>
                    <b>{c.nombre}</b>
                    {c.proveedor ? (
                      <div style={{ color: 'var(--muted)', fontSize: 12 }}>🏷️ {c.proveedor}</div>
                    ) : null}
                  </td>
                  <td style={{ color: 'var(--muted)' }}>{c.detalle}</td>
                  <td className="num">{c.cantidad}</td>
                  <td className="num">{fmtCLP(c.valor)}</td>
                  <td className="num">{fmtCLP(c.valor * c.cantidad)}</td>
                </tr>
              ))}
              <tr className="total-row">
                <td colSpan={4}>Total propuesta</td>
                <td className="num">{fmtCLP(total)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="toolbar">
          <button className="btn primary" onClick={onArmarTareas}>
            Armar tareas ▸
          </button>
          <button
            className="btn ghost"
            onClick={() => alert('Exportar propuesta a PPT — se generará la presentación para el cliente')}
          >
            ⤓ PPT
          </button>
          <button
            className="btn ghost"
            onClick={onExportarExcel ?? (() => alert('Exportar a Excel'))}
          >
            ⤓ Excel
          </button>
        </div>
      </div>
    </section>
  )
}
