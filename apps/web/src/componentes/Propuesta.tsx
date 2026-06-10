import { costoLinea, fmtCLP, MARGEN_VENTA, valorVenta, type Componente } from '../tipos'

interface Props {
  componentes: Componente[]
  onVolver: () => void
  onArmarTareas: () => void
  /** Descarga la cotización como .xlsx con el theme Capsulab (007). `vista`:
   * `interno` (costos + margen) o `cliente` (solo precios de venta). */
  onExportarExcel?: (vista: 'interno' | 'cliente') => void
  /** Descarga la propuesta como un DECK .pptx (cara comercial, vista cliente) — T18. */
  onExportarPpt?: () => void
}

export function Propuesta({ componentes, onVolver, onArmarTareas, onExportarExcel, onExportarPpt }: Props) {
  const exportar = onExportarExcel ?? (() => alert('Exportar a Excel'))
  const exportarPpt =
    onExportarPpt ?? (() => alert('Exportar propuesta a PPT — se generará la presentación para el cliente'))
  // `valor` es la tarifa/día por unidad: el costo de la línea es cantidad × días × valor.
  const costoTotal = componentes.reduce((acc, c) => acc + costoLinea(c), 0)
  const ventaTotal = valorVenta(costoTotal)

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
                <th style={{ textAlign: 'right' }}>Días</th>
                <th style={{ textAlign: 'right' }}>Valor/día</th>
                <th style={{ textAlign: 'right' }}>Costo</th>
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
                  <td className="num">{c.dias ?? 1}</td>
                  <td className="num">{fmtCLP(c.valor)}</td>
                  <td className="num">{fmtCLP(costoLinea(c))}</td>
                </tr>
              ))}
              <tr className="total-row">
                <td colSpan={5}>Costo total</td>
                <td className="num">{fmtCLP(costoTotal)}</td>
              </tr>
              <tr className="total-row">
                <td colSpan={5}>Valor venta · margen {Math.round(MARGEN_VENTA * 100)}%</td>
                <td className="num" style={{ color: 'var(--brand)' }}>
                  {fmtCLP(ventaTotal)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="toolbar">
          <button className="btn primary" onClick={onArmarTareas}>
            Armar tareas ▸
          </button>
          <button className="btn ghost" onClick={exportarPpt}>
            ⤓ PPT
          </button>
          <button className="btn ghost" onClick={() => exportar('interno')}>
            ⤓ Excel interno
          </button>
          <button className="btn ghost" onClick={() => exportar('cliente')}>
            ⤓ Excel cliente
          </button>
        </div>
      </div>
    </section>
  )
}
