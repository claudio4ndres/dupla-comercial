import { useEffect, useState } from 'react'
import { listarListasClickUp } from '../api/clickup'
import type { EstadoCorreo } from '../api/integraciones'
import type { Pantalla, ProveedorCorreo } from '../tipos'

interface Props {
  /** Estado real de la bandeja de correo (proveedor/estado/casilla) que trae App. */
  estadoCorreo: EstadoCorreo
  /** Inicia la conexión OAuth del proveedor (reusa el handler de App). */
  onConectar: (proveedor: ProveedorCorreo) => void
  /** Desconecta la bandeja ("Cambiar") — reusa el handler de App. */
  onDesconectar: () => void
  /** Navega a otra pantalla (p. ej. 'inbox' al terminar el onboarding). */
  onIrA: (pantalla: Pantalla) => void
}

/**
 * Onboarding / Configuración post-login: cada empresa "prepara su espacio"
 * conectando SUS conectores (multi-tenant). Hoy: Correo (Gmail) y Gestor de
 * tareas (ClickUp habilitado, Jira "próximamente"). Se muestra al iniciar
 * sesión y también desde el ítem "Configuración" del menú lateral.
 *
 * NO reimplementa la lógica de conexión: el correo reusa los handlers
 * `onConectar/onDesconectar` de App (que hablan con el backend, regla de oro
 * #3) y ClickUp solo consulta `listarListasClickUp()` para saber si la empresa
 * ya tiene su gestor conectado.
 */
export function Configuracion({ estadoCorreo, onConectar, onDesconectar, onIrA }: Props) {
  // Listas reales del ClickUp de la empresa. `undefined` = aún cargando;
  // [] = sin conectar (o sin listas); con elementos = conectado.
  const [listasClickUp, setListasClickUp] = useState<{ id: string; nombre: string }[] | undefined>(
    undefined,
  )

  // Al montar (y por empresa, vía remonta App al cambiar de tenant) consulta si
  // ClickUp ya está conectado. Sin token, el backend devuelve [] (mostramos el
  // aviso de "conecta ClickUp"); ante fallo también [] (no rompe la pantalla).
  useEffect(() => {
    let activo = true
    listarListasClickUp().then((listas) => {
      if (activo) setListasClickUp(listas)
    })
    return () => {
      activo = false
    }
  }, [])

  const correoConectado = estadoCorreo.estado === 'conectado'
  const clickUpConectado = (listasClickUp?.length ?? 0) > 0

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
                <span className="conector-cat">Bandeja de entrada</span>
              </div>
              <span className={'conector-estado ' + (correoConectado ? 'on' : 'off')}>
                {correoConectado ? 'Conectado' : 'Sin conectar'}
              </span>
            </div>
            <div className="conector-body">
              {correoConectado ? (
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

          {/* Gestor de tareas · ClickUp (habilitado): estado por las listas reales. */}
          <div className="card conector">
            <div className="conector-head">
              <span className="conector-ico">✅</span>
              <div className="conector-id">
                <b>Gestor de tareas · ClickUp</b>
                <span className="conector-cat">Tareas del equipo</span>
              </div>
              <span className={'conector-estado ' + (clickUpConectado ? 'on' : 'off')}>
                {clickUpConectado ? 'Conectado' : 'Sin conectar'}
              </span>
            </div>
            <div className="conector-body">
              {clickUpConectado ? (
                <p className="conector-detalle">
                  Conectado · {listasClickUp!.length}{' '}
                  {listasClickUp!.length === 1 ? 'lista disponible' : 'listas disponibles'} para
                  enviar las tareas.
                </p>
              ) : (
                <>
                  <p className="conector-detalle">
                    Conecta ClickUp para enviar las tareas de cada propuesta a tu equipo.
                  </p>
                  <span className="conector-nota">(conector OAuth próximamente)</span>
                </>
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
          <button className="btn primary" onClick={() => onIrA('inbox')}>
            Continuar a la bandeja ▸
          </button>
        </div>
      </div>
    </section>
  )
}
