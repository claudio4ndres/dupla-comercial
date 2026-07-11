import { useEffect, useState } from 'react'
import {
  desconectarClickup,
  ESTADO_CLICKUP_DESCONECTADO,
  iniciarConexionClickup,
  obtenerEstadoClickup,
  verificarClickup,
  type EstadoClickup,
} from '../api/clickup'
import type { EstadoCorreo } from '../api/integraciones'
import type { Pantalla, ProveedorCorreo } from '../tipos'

interface Props {
  /** Estado real de la bandeja de correo (proveedor/estado/casilla) que trae App. */
  estadoCorreo: EstadoCorreo
  /**
   * ¿App aún espera la PRIMERA respuesta del estado de correo? Mientras sea true no
   * sabemos si Gmail está conectado, así que la tarjeta muestra "Comprobando…" en
   * vez de "Sin conectar" (evita el flash que parecía desconexión al volver aquí).
   * Default false: si App no lo pasa, se asume resuelto (compat con tests/usos).
   */
  cargandoCorreo?: boolean
  /** Inicia la conexión OAuth del proveedor (reusa el handler de App). */
  onConectar: (proveedor: ProveedorCorreo) => void
  /** Desconecta la bandeja ("Cambiar") — reusa el handler de App. */
  onDesconectar: () => void
  /** Navega a otra pantalla (p. ej. 'inbox' al terminar el onboarding). */
  onIrA: (pantalla: Pantalla) => void
  /**
   * Navega el navegador a una URL externa (la de consentimiento de ClickUp).
   * Inyectable para tests; por defecto redirige la pestaña actual, igual que el
   * OAuth de Gmail en App.
   */
  onNavegar?: (url: string) => void
}

/**
 * Onboarding / Configuración post-login: cada empresa "prepara su espacio"
 * conectando SUS conectores (multi-tenant). Hoy: Correo (Gmail) y Gestor de
 * tareas (ClickUp con OAuth real, Jira "próximamente"). Se muestra al iniciar
 * sesión y también desde el ítem "Configuración" del menú lateral.
 *
 * NO reimplementa la lógica de conexión: el correo reusa los handlers
 * `onConectar/onDesconectar` de App (que hablan con el backend, regla de oro
 * #3) y ClickUp consulta su estado per-empresa (`obtenerEstadoClickup`) e inicia
 * / desconecta el OAuth vía el backend (espejo de Gmail). El token de ClickUp
 * JAMÁS llega al front (CA5): solo se manejan proveedor/estado.
 */
export function Configuracion({
  estadoCorreo,
  cargandoCorreo = false,
  onConectar,
  onDesconectar,
  onIrA,
  onNavegar = (url: string) => window.location.assign(url),
}: Props) {
  // Estado real del conector ClickUp de la empresa (existencia de la integración,
  // no conteo de listas). `undefined` = aún cargando; luego {proveedor, estado}.
  const [estadoClickUp, setEstadoClickUp] = useState<EstadoClickup | undefined>(undefined)

  // Al montar (y por empresa, vía remonta App al cambiar de tenant) consulta el
  // estado del conector. Sin integración → "Sin conectar"; token revocado/401 →
  // "Reconectar" (CA6); ante fallo cae a desconectado (no rompe la pantalla).
  useEffect(() => {
    let activo = true
    obtenerEstadoClickup().then((e) => {
      if (activo) setEstadoClickUp(e)
    })
    return () => {
      activo = false
    }
  }, [])

  // "Conectar"/"Reconectar": pide la URL de consentimiento al backend y navega.
  // El front NUNCA inventa la URL (el `state` anti-CSRF lo fija el servidor); si
  // el backend falla, no navegamos a una URL inventada (igual que Gmail).
  async function conectarClickUp() {
    try {
      const url = await iniciarConexionClickup()
      onNavegar(url)
    } catch {
      // Backend no cableado/caído: no navegamos.
    }
  }

  // "Cambiar": desconecta ClickUp de la empresa en el backend y deja la tarjeta
  // en "Sin conectar" (el secreto se borra en el backend; el front no lo toca).
  async function desconectarClickUp() {
    await desconectarClickup()
    setEstadoClickUp(ESTADO_CLICKUP_DESCONECTADO)
  }

  // "Probar conexión" (spec 017): POST /clickup/verificar prueba el token contra
  // ClickUp y auto-repara el estado; el resultado se muestra y el chip se actualiza.
  const [resultadoVerificacion, setResultadoVerificacion] = useState<string | null>(null)
  async function probarConexionClickUp() {
    const r = await verificarClickup()
    if (!r) {
      setResultadoVerificacion('No se pudo verificar la conexión. Inténtalo de nuevo.')
      return
    }
    setResultadoVerificacion(r.mensaje)
    if (r.estado === 'conectado' || r.estado === 'reconectar') {
      setEstadoClickUp({ proveedor: 'clickup', estado: r.estado } as EstadoClickup)
    }
  }

  const correoConectado = estadoCorreo.estado === 'conectado'
  // Token de Google expirado/revocado: la tarjeta pide reconectar (010-T9).
  const correoReconectar = estadoCorreo.estado === 'reconectar'
  // Mientras App resuelve el estado real, no afirmamos "Sin conectar": la tarjeta
  // queda en "Comprobando…" (solo si aún no sabemos que está conectado).
  const correoComprobando = cargandoCorreo && !correoConectado
  const clickUpConectado = estadoClickUp?.estado === 'conectado'
  const clickUpReconectar = estadoClickUp?.estado === 'reconectar'

  return (
    <section className="screen">
      <div className="wrap">
        <div className="section-head">
          <div>
            <h1 className="page">Prepara tu espacio</h1>
            <p className="sub">
              Conecta tu correo y tu gestor de tareas; cada empresa usa sus propias cuentas.
            </p>
          </div>
        </div>

        <div className="conectores">
          {/* Correo · Gmail (habilitado): estado real desde el backend. */}
          <div className="card conector">
            <div className="conector-head">
              <span className="conector-ico">📧</span>
              <div className="conector-id">
                <b>Correo · Gmail</b>
                <span className="conector-cat">
                  Bandeja de entrada · incluye Google Drive (tarifarios de Javo)
                </span>
              </div>
              <span
                data-testid="conector-gmail"
                className={
                  'conector-estado ' +
                  (correoConectado
                    ? 'on'
                    : correoReconectar
                      ? 'warn'
                      : correoComprobando
                        ? 'loading'
                        : 'off')
                }
              >
                {correoConectado
                  ? 'Conectado'
                  : correoReconectar
                    ? 'Reconectar'
                    : correoComprobando
                      ? 'Comprobando…'
                      : 'Sin conectar'}
              </span>
            </div>
            <div className="conector-body">
              {correoReconectar ? (
                <>
                  {/* Mensaje por proveedor (spec 010 · T9): sin tokens, solo el estado. */}
                  <p className="conector-detalle">
                    La conexión con Google expiró. Vuelve a conectar para seguir leyendo
                    tu correo y tu Drive.
                  </p>
                  <button className="btn primary" onClick={() => onConectar('gmail')}>
                    Reconectar Gmail
                  </button>
                </>
              ) : correoComprobando ? (
                <p className="conector-detalle">Comprobando la conexión de tu Gmail…</p>
              ) : correoConectado ? (
                <>
                  <p className="conector-detalle">
                    Escuchando la casilla <b>{estadoCorreo.casilla ?? 'conectada'}</b>.
                  </p>
                  <button className="btn ghost" onClick={onDesconectar}>
                    Cambiar
                  </button>
                </>
              ) : (
                <>
                  <p className="conector-detalle">
                    Autoriza tu Gmail para que Javo lea los correos entrantes y los clasifique.
                  </p>
                  <button className="btn primary" onClick={() => onConectar('gmail')}>
                    Conectar Gmail
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Gestor de tareas · ClickUp (OAuth real): estado per-empresa, espejo de Gmail. */}
          <div className="card conector">
            <div className="conector-head">
              <span className="conector-ico">✅</span>
              <div className="conector-id">
                <b>Gestor de tareas · ClickUp</b>
                <span className="conector-cat">Tareas del equipo</span>
              </div>
              <span
                className={
                  'conector-estado ' +
                  (clickUpConectado ? 'on' : clickUpReconectar ? 'warn' : 'off')
                }
              >
                {clickUpConectado ? 'Conectado' : clickUpReconectar ? 'Reconectar' : 'Sin conectar'}
              </span>
            </div>
            <div className="conector-body">
              {clickUpConectado ? (
                <>
                  <p className="conector-detalle">
                    Conectado · las tareas de cada propuesta se envían a tu ClickUp.
                  </p>
                  <button className="btn ghost" onClick={desconectarClickUp}>
                    Cambiar ClickUp
                  </button>
                  <button className="btn ghost" onClick={() => void probarConexionClickUp()}>
                    Probar conexión
                  </button>
                </>
              ) : clickUpReconectar ? (
                <>
                  {/* Mensaje por proveedor (spec 010 · T9). */}
                  <p className="conector-detalle">
                    ClickUp se desconectó. Vuelve a conectar para crear tareas.
                  </p>
                  <button className="btn primary" onClick={conectarClickUp}>
                    Reconectar ClickUp
                  </button>
                </>
              ) : (
                <>
                  <p className="conector-detalle">
                    Conecta ClickUp para enviar las tareas de cada propuesta a tu equipo.
                  </p>
                  <button className="btn primary" onClick={conectarClickUp}>
                    Conectar ClickUp
                  </button>
                </>
              )}
              {resultadoVerificacion && (
                <p className="conector-detalle" role="status">
                  {resultadoVerificacion}
                </p>
              )}
            </div>
          </div>

          {/* Gestor de tareas · Jira (deshabilitado): tarjeta en gris, no clickable. */}
          <div className="card conector deshabilitado" aria-disabled="true">
            <div className="conector-head">
              <span className="conector-ico">🧩</span>
              <div className="conector-id">
                <b>Gestor de tareas · Jira</b>
                <span className="conector-cat">Tareas del equipo</span>
              </div>
              <span className="badge new">Próximamente</span>
            </div>
            <div className="conector-body">
              <p className="conector-detalle">
                Pronto podrás enviar las tareas a Jira. Por ahora usa ClickUp.
              </p>
            </div>
          </div>

          {/* Drive · Google: nota corta, va con la misma conexión de Gmail. */}
          <div className="card conector">
            <div className="conector-head">
              <span className="conector-ico">🗂️</span>
              <div className="conector-id">
                <b>Drive · Google</b>
                <span className="conector-cat">Tarifarios y costos</span>
              </div>
            </div>
            <div className="conector-body">
              <p className="conector-detalle">
                Va con tu conexión de Google (mismo acceso que Gmail).
              </p>
            </div>
          </div>
        </div>

        <div className="toolbar">
          <button data-testid="ir-a-bandeja" className="btn primary" onClick={() => onIrA('inbox')}>
            Continuar a la bandeja ▸
          </button>
        </div>
      </div>
    </section>
  )
}
