import { useState, type FormEvent } from 'react'
import { supabase } from '../supabase/cliente'

interface Props {
  /** Se invoca con el correo cuando la sesión queda activa. */
  onEntrar: (correo: string) => void
}

export function Login({ onEntrar }: Props) {
  const [correo, setCorreo] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(false)

  const puedeEntrar = correo.trim() !== '' && password.trim() !== '' && !cargando

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (!puedeEntrar) return
    setCargando(true)
    setError(null)
    const { error: err } = await supabase.auth.signInWithPassword({
      email: correo.trim(),
      password,
    })
    setCargando(false)
    if (err) {
      setError('Correo o contraseña incorrectos')
      return
    }
    onEntrar(correo.trim())
  }

  return (
    <div className="login">
      <form className="login-card" onSubmit={enviar}>
        <div className="login-brand">
          <div className="login-logo">J</div>
          <div>
            <div className="login-title">Dupla Comercial</div>
            <div className="login-sub">Inicia sesión para entrar a tu bandeja</div>
          </div>
        </div>

        <label className="field">
          <span>Correo</span>
          <input
            data-testid="login-email"
            type="email"
            value={correo}
            onChange={(e) => setCorreo(e.target.value)}
            placeholder="tu@empresa.cl"
            autoComplete="email"
          />
        </label>

        <label className="field">
          <span>Contraseña</span>
          <input
            data-testid="login-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
          />
        </label>

        {error && <p className="login-error" role="alert">{error}</p>}

        <button data-testid="login-submit" type="submit" className="btn primary login-btn" disabled={!puedeEntrar}>
          {cargando ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
