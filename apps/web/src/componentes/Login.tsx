import { useState, type FormEvent } from 'react'

interface Props {
  /** Se invoca con el correo cuando el usuario inicia sesión. */
  onEntrar: (correo: string) => void
}

/**
 * Pantalla de inicio de sesión (correo + contraseña).
 *
 * Por ahora es un mock: cualquier credencial entra al demo. Cuando se conecte
 * Supabase Auth, `onEntrar` pasará a llamar a `signInWithPassword` y la sesión
 * traerá el `empresa_id` para las políticas RLS. La contraseña NUNCA viaja a
 * otro lado que no sea el proveedor de Auth.
 */
export function Login({ onEntrar }: Props) {
  const [correo, setCorreo] = useState('')
  const [password, setPassword] = useState('')

  const puedeEntrar = correo.trim() !== '' && password.trim() !== ''

  function enviar(e: FormEvent) {
    e.preventDefault()
    if (!puedeEntrar) return
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
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
          />
        </label>

        <button type="submit" className="btn primary login-btn" disabled={!puedeEntrar}>
          Entrar
        </button>

        <p className="login-foot">
          Demo: aún no conectamos la autenticación real (Supabase Auth). Por ahora cualquier correo y
          contraseña te dejan entrar.
        </p>
      </form>
    </div>
  )
}
