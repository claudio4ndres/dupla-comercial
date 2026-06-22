// SesionContext — Contexto de sesión, empresa activa y navegación de layout.
// Extracción desde App.tsx (Iteración 1 del refactor de contextos).

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { supabase } from '../supabase/cliente'
import { obtenerEmpresa } from '../api/empresa'
import { obtenerUsuario, marcarOnboardingVisto } from '../api/usuario'
import type { Empresa, Pantalla, Sesion } from '../tipos'

/** Valor por defecto neutro mientras el backend aún no responde con la empresa real. */
const EMPRESA_POR_DEFECTO: Empresa = { nombre: '', color: '#cccccc', marca: '?', etiqueta: '' }

// ── Interfaz del valor expuesto ──────────────────────────────────────────────

export interface SesionContextValor {
  /** undefined = aún resolviendo, null = sin sesión, Sesion = autenticado */
  sesion: Sesion | null | undefined
  empresa: Empresa
  setEmpresa: (e: Empresa) => void
  cerrarSesion: () => Promise<void>
  /** Pantalla activa (router simple por estado) */
  pantalla: Pantalla
  irA: (p: Pantalla) => void
  /** true cuando el usuario aún no vio el onboarding de bienvenida (slider 1 vez). */
  bienvenidaPendiente: boolean
  /** Marca el onboarding como visto (backend) y oculta el slider. */
  cerrarBienvenida: () => void
}

// ── Contexto con valor inicial undefined (para detectar uso fuera del provider) ─

const SesionContext = createContext<SesionContextValor | undefined>(undefined)

// ── Provider ─────────────────────────────────────────────────────────────────

export function SesionProvider({ children }: { children: ReactNode }) {
  // Estado de autenticación: undefined = aún no sé, null = sin sesión
  const [sesion, setSesion] = useState<Sesion | null | undefined>(undefined)
  const [empresa, setEmpresa] = useState<Empresa>(EMPRESA_POR_DEFECTO)
  // Landing post-login: configuración (onboarding de conectores)
  const [pantalla, setPantalla] = useState<Pantalla>('configuracion')
  // Slider de bienvenida: se muestra una sola vez por usuario (gate: onboarding_visto).
  const [bienvenidaPendiente, setBienvenidaPendiente] = useState(false)

  // ─── Efecto: sesión inicial + suscripción a cambios de auth ────────────────
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSesion(data.session ? { correo: data.session.user.email ?? '' } : null)
    })
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSesion(session ? { correo: session.user.email ?? '' } : null)
    })
    return () => subscription.unsubscribe()
  }, [])

  // ─── Efecto: al tener sesión, obtener empresa real del backend ─────────────
  useEffect(() => {
    if (!sesion) return
    let activo = true
    obtenerEmpresa().then((e) => {
      if (activo && e) setEmpresa(e)
    })
    return () => { activo = false }
  }, [sesion])

  // ─── Efecto: al tener sesión, decidir si mostrar el onboarding de bienvenida ─
  useEffect(() => {
    if (!sesion) return
    let activo = true
    obtenerUsuario().then((u) => {
      if (activo && u && !u.onboarding_visto) setBienvenidaPendiente(true)
    })
    return () => { activo = false }
  }, [sesion])

  // ─── Efecto: white-label (variables CSS de marca) ──────────────────────────
  useEffect(() => {
    const raiz = document.documentElement
    raiz.style.setProperty('--brand', empresa.color)
    raiz.style.setProperty('--brand-soft', empresa.color + '22')
  }, [empresa])

  // ─── Cerrar sesión ─────────────────────────────────────────────────────────
  const cerrarSesion = async () => {
    await supabase.auth.signOut()
  }

  // ─── Navegación simple ─────────────────────────────────────────────────────
  const irA = (p: Pantalla) => setPantalla(p)

  // ─── Cerrar el onboarding de bienvenida: persiste (best-effort) y oculta ────
  const cerrarBienvenida = () => {
    setBienvenidaPendiente(false)
    void marcarOnboardingVisto()
  }

  const valor: SesionContextValor = {
    sesion,
    empresa,
    setEmpresa,
    cerrarSesion,
    pantalla,
    irA,
    bienvenidaPendiente,
    cerrarBienvenida,
  }

  return <SesionContext.Provider value={valor}>{children}</SesionContext.Provider>
}

// ── Hook de acceso rápido con guard en español ───────────────────────────────

export function useSesion(): SesionContextValor {
  const ctx = useContext(SesionContext)
  if (ctx === undefined) {
    throw new Error('useSesion debe usarse dentro de SesionProvider')
  }
  return ctx
}
