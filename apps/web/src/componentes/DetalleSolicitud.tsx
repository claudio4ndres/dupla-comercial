import { useState } from 'react'
import type { Solicitud, TipoConfirmado } from '../tipos'

interface Props {
  solicitud: Solicitud
  onVolver: () => void
  onElegirTipo: (tipo: TipoConfirmado) => void
}

export function DetalleSolicitud({ solicitud, onVolver, onElegirTipo }: Props) {
  const [verCorreo, setVerCorreo] = useState(false)

  return (
    <section className="screen">
      <div className="wrap">
        <div className="back" onClick={onVolver}>
          ‹ Volver a la bandeja
        </div>

        <div className="card">
          <div className="meta">
            <div>
              De<b>{solicitud.remitente}</b>
            </div>
            <div>
              Correo<b>{solicitud.correo}</b>
            </div>
            <div>
              Recibido<b>{solicitud.tiempo}</b>
            </div>
          </div>

          <div className="ai-summary">
            <div className="tag">
              <svg className="spark" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2l2.4 6.6L21 11l-6.6 2.4L12 20l-2.4-6.6L3 11l6.6-2.4z" />
              </svg>
              Resumen del correo
            </div>
            {/* Si Javo aún no resumió el correo (p. ej. ingerido sin clasificar),
                mostramos un preview del cuerpo para que nunca quede vacío. */}
            <p>
              {solicitud.resumen ||
                ((solicitud.cuerpo ?? '').trim().slice(0, 400) +
                  ((solicitud.cuerpo ?? '').trim().length > 400 ? '…' : '')) ||
                'Sin contenido.'}
            </p>
            <ul>
              {solicitud.puntos.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </div>

          <div className="full-toggle" onClick={() => setVerCorreo((v) => !v)}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 5h16v14H4z" />
              <path d="M4 7l8 6 8-6" />
            </svg>
            Ver correo completo
            <span style={{ marginLeft: 'auto' }}>{verCorreo ? '▴' : '▾'}</span>
          </div>
          {verCorreo && <div className="full-body open">{solicitud.cuerpo}</div>}
        </div>

        <div className="choose">
          <h3>¿Qué tipo de solicitud es?</h3>
          <div className="type-grid">
            <div data-testid="elegir-tipo-1" className="type-card t1" onClick={() => onElegirTipo('t1')}>
              <div className="ico">🧾</div>
              <h4>Tipo 1 · Cotización concreta</h4>
              <p>Ya se sabe qué hacer. Javo te ayuda a definir los componentes y armar la cotización.</p>
            </div>
            <div data-testid="elegir-tipo-2" className="type-card t2" onClick={() => onElegirTipo('t2')}>
              <div className="ico">💡</div>
              <h4>Tipo 2 · Ideas / propuesta</h4>
              <p>Hay que proponer. Javo brainstormea contigo y, si lo pides, busca opciones en internet.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
