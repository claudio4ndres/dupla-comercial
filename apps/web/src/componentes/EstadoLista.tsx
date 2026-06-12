// Estados compartidos de las pantallas de lista (Bandeja, Propuestas, Tareas):
// "Cargando…" mientras llega la primera respuesta del backend y un banner de
// error discreto con "Reintentar" si la carga falla. Se extraen aquí para que
// las tres listas se vean igual y no se duplique el markup (auditoría #9).

interface BannerErrorProps {
  /** Reintenta la carga. Si no se pasa, el botón no se muestra. */
  onReintentar?: () => void
  /** Texto del banner. Por defecto, un mensaje genérico de "no se pudo cargar". */
  mensaje?: string
}

/**
 * Banner discreto de error de carga, con botón de reintento. Reemplaza al
 * "vacío silencioso" que mostraba la UI cuando un GET fallaba (los clientes de
 * api/ tragan el error y devolvían []), para que el usuario sepa que hubo un
 * fallo y pueda reintentar.
 */
export function BannerError({ onReintentar, mensaje = 'No se pudo cargar.' }: BannerErrorProps) {
  return (
    <div className="listening reconnect" role="alert" style={{ marginTop: 18 }}>
      <span className="led-warn" />
      {mensaje}
      {onReintentar ? (
        <button className="link-mini" onClick={onReintentar}>
          Reintentar
        </button>
      ) : null}
    </div>
  )
}

/**
 * Indicador de "Cargando…" mientras llega la primera respuesta del backend.
 * Usa el mismo bloque `.empty` que los estados vacíos para mantener el estilo,
 * pero comunica que está cargando (no que "no hay datos").
 */
export function CargandoLista({ mensaje = 'Cargando…' }: { mensaje?: string }) {
  return (
    <div className="empty" role="status" style={{ marginTop: 40 }}>
      {mensaje}
    </div>
  )
}
