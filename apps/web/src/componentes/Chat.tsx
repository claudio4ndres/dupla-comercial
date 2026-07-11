import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import {
  costoLinea,
  fmtCLP,
  valorVenta,
  type Componente,
  type Fuente,
  type Mensaje,
  type Solicitud,
  type TipoConfirmado,
} from '../tipos'
import type { RecursoDrive } from '../datosMock'
import { BannerError } from './EstadoLista'

interface Props {
  solicitud: Solicitud
  tipo: TipoConfirmado
  mensajes: Mensaje[]
  componentes: Componente[]
  /** Fuentes que Javo citó (recursos del Drive / web) — 005. */
  fuentes: Fuente[]
  /** Recursos del Drive de la empresa (reales desde el catálogo). */
  recursos: RecursoDrive[]
  /** Chips dinámicos generados por Haiku (vacío = usa fallback estático). */
  chips?: string[]
  enviando: boolean
  /** El último turno de Javo falló: se muestra el aviso con Reintentar (014). */
  errorJavo?: boolean
  onEnviar: (texto: string) => void
  /** Reenvía el último turno fallido (014). */
  onReintentar?: () => void
  onGenerarPropuesta: () => void
}

const CHIPS_FALLBACK: Record<TipoConfirmado, string[]> = {
  t1: ['Son 3 días de activación', 'Suma coordinación de producción', 'Genera la propuesta'],
  t2: ['Busca opciones en internet 🌐', 'Dame 3 ideas de alto impacto', 'Aterriza la idea ganadora'],
}

export function Chat({ solicitud, tipo, mensajes, componentes, fuentes, recursos, chips, enviando, errorJavo, onEnviar, onReintentar, onGenerarPropuesta }: Props) {
  const [texto, setTexto] = useState('')
  const cajaMensajes = useRef<HTMLDivElement>(null)
  const areaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll al último mensaje y mientras Javo "escribe".
  useEffect(() => {
    const caja = cajaMensajes.current
    if (caja) caja.scrollTop = caja.scrollHeight
  }, [mensajes, enviando])

  function enviar(valor: string) {
    const limpio = valor.replace(' 🌐', '').trim()
    if (!limpio || enviando) return
    onEnviar(limpio)
    setTexto('')
    if (areaRef.current) areaRef.current.style.height = 'auto'
  }

  function alTeclear(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      enviar(texto)
    }
  }

  const costoTotal = componentes.reduce((acc, c) => acc + costoLinea(c), 0)

  return (
    <section className="screen">
      <div style={{ padding: '14px 18px 0' }}>
        <div className="chat-layout">
          {/* Columna de conversación */}
          <div className="chat-col">
            <div className="chat-head">
              <div className="javo">J</div>
              <div>
                <div className="nm">Javo · asistente</div>
                <div className="st">
                  <span className="led" /> en línea · Claude
                </div>
              </div>
              <div className="ctx">Re: {solicitud.asunto}</div>
            </div>

            <div className="messages" ref={cajaMensajes}>
              {mensajes.map((m, i) => {
                if (m.rol === 'sistema') return <div key={i} className="msg sys">🌐 {m.contenido}</div>
                return (
                  <div key={i} className={'msg ' + (m.rol === 'usuario' ? 'user' : 'bot')} {...(m.rol === 'javo' ? { 'data-testid': 'javo-mensaje' } : {})}>
                    {m.contenido}
                  </div>
                )
              })}
              {enviando && (
                <div data-testid="javo-pensando" className="typing">
                  <span />
                  <span />
                  <span />
                </div>
              )}
              {errorJavo && !enviando && (
                <BannerError
                  mensaje="Javo no está disponible en este momento."
                  onReintentar={onReintentar}
                />
              )}
            </div>

            <div className="chips">
              {(chips && chips.length > 0 ? chips : CHIPS_FALLBACK[tipo]).map((c) => (
                <span key={c} className="chip" onClick={() => enviar(c)}>
                  {c}
                </span>
              ))}
            </div>

            <div className="composer">
              <textarea
                data-testid="javo-input"
                ref={areaRef}
                rows={1}
                placeholder="Escríbele a Javo…"
                value={texto}
                onChange={(e) => {
                  setTexto(e.target.value)
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
                }}
                onKeyDown={alTeclear}
              />
              <button data-testid="javo-enviar" className="send" disabled={enviando} onClick={() => enviar(texto)} aria-label="Enviar">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 2L11 13M22 2l-7 20-4-9-9-4z" />
                </svg>
              </button>
            </div>
          </div>

          {/* Panel lateral */}
          <div className="side">
            <div className="panel">
              <div className="ph">
                <h4>Componentes</h4>
                <span className={'badge ' + tipo}>{tipo === 't1' ? 'Tipo 1' : 'Tipo 2'}</span>
              </div>
              <div className="pb">
                {componentes.length === 0 ? (
                  <div className="empty">Conversa con Javo para que arme los componentes de la cotización.</div>
                ) : (
                  <>
                    {componentes.map((c) => (
                      <div key={c.nombre} data-testid="componente-item" className="comp-row">
                        <div>
                          <div className="nm">{c.nombre}</div>
                          <div className="det">
                            {c.detalle} ×{c.cantidad}
                            {(c.dias ?? 1) > 1 ? ` · ${c.dias} días` : ''}
                            {c.origen ? <span className="origen"> · 📄 {c.origen}</span> : null}
                          </div>
                        </div>
                        <div className="val">{fmtCLP(costoLinea(c))}</div>
                      </div>
                    ))}
                    <div className="comp-row" style={{ marginTop: 6 }}>
                      <div className="nm">Costo total</div>
                      <div className="val">{fmtCLP(costoTotal)}</div>
                    </div>
                    <div className="comp-row">
                      <div className="nm">Valor venta</div>
                      <div className="val" style={{ color: 'var(--brand)' }}>
                        {fmtCLP(valorVenta(costoTotal))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="panel">
              <div className="ph">
                <h4>Recursos · Drive</h4>
              </div>
              <div className="pb">
                {recursos.length === 0 ? (
                  <div className="empty">Sin recursos indexados en el Drive todavía.</div>
                ) : (
                  recursos.map((r) => (
                    <div key={r.nombre} data-testid="recurso-drive" className="drive-file">
                      <span className="fi">{r.icono}</span> {r.nombre}
                    </div>
                  ))
                )}
              </div>
            </div>

            {fuentes.length > 0 && (
              <div className="panel">
                <div className="ph">
                  <h4>Fuentes citadas</h4>
                </div>
                <div className="pb">
                  {fuentes.map((f, i) => (
                    <div key={i} data-testid="fuente-citada" className="drive-file">
                      <span className="fi">🔗</span> {f.titulo}
                      <span style={{ color: 'var(--muted)' }}> · {f.referencia}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button data-testid="generar-propuesta" className="btn dark" style={{ justifyContent: 'center' }} onClick={onGenerarPropuesta}>
              Generar propuesta ▸
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
