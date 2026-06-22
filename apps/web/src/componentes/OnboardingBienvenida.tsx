// Onboarding de bienvenida: slider a pantalla completa que se muestra UNA sola vez
// por usuario tras el login (gate por usuarios.onboarding_visto, vía SesionContext).
// Presenta el flujo de la herramienta en 5 slides: bandeja → tipos → chat → tareas.
import { useState, type CSSProperties } from 'react'

interface Slide {
  emoji: string
  titulo: string
  texto: string
}

const SLIDES: Slide[] = [
  {
    emoji: '🤖',
    titulo: 'Bienvenido a Dupla Comercial',
    texto: 'Soy Javo, tu dupla comercial senior. Te ayudo a resolver las solicitudes que llegan por correo — de la idea a la propuesta, y de la propuesta a las tareas.',
  },
  {
    emoji: '📥',
    titulo: 'Tu bandeja inteligente',
    texto: 'Los correos de tus clientes llegan a tu bandeja. Javo los lee, los clasifica y te deja un resumen claro — sin que muevas un dedo.',
  },
  {
    emoji: '🔀',
    titulo: 'Dos tipos de solicitud',
    texto: 'Tipo 1, cotización concreta: ya sabes qué hacer y Javo arma la cotización. Tipo 2, ideas: no hay brief cerrado, Javo propone conceptos y busca referencias contigo.',
  },
  {
    emoji: '💬',
    titulo: 'Conversa y aterriza la propuesta',
    texto: 'Chateas con Javo para definir componentes, horas y valores. Consulta tu Drive en vivo y deja todo listo para presentar al cliente en Excel o PPT.',
  },
  {
    emoji: '🗂️',
    titulo: 'De propuesta a tareas',
    texto: 'Cuando la propuesta está lista, Javo genera las tareas para tu equipo y las sincroniza con ClickUp. Tú supervisas, él ejecuta.',
  },
]

const sOverlay: CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', alignItems: 'center',
  justifyContent: 'center', padding: 24, background: 'rgba(20, 16, 12, 0.55)',
}
const sCard: CSSProperties = {
  position: 'relative', width: '100%', maxWidth: 560, minHeight: 540, background: '#fff',
  borderRadius: 20, padding: '36px 44px', display: 'flex', flexDirection: 'column',
  boxShadow: '0 24px 60px rgba(0,0,0,.18)',
}
const sTop: CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center' }
const sBrand: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 15, fontWeight: 600,
  color: 'var(--brand, #F04E37)',
}
const sSkip: CSSProperties = {
  border: 'none', background: 'transparent', color: '#a39d95', fontSize: 13, cursor: 'pointer', padding: '4px 8px',
}
const sStage: CSSProperties = { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }
const sInner: CSSProperties = { width: '100%', maxWidth: 440, textAlign: 'center' }
const sIco: CSSProperties = {
  width: 76, height: 76, margin: '0 auto', borderRadius: '50%',
  background: 'var(--brand-soft, rgba(240,78,55,.12))', display: 'flex',
  alignItems: 'center', justifyContent: 'center', fontSize: 38,
}
const sTitulo: CSSProperties = { margin: '20px 0 10px', fontSize: 23, fontWeight: 600, color: '#1a1714' }
const sTexto: CSSProperties = { margin: 0, color: '#6f6a64', fontSize: 16, lineHeight: 1.65 }
const sBottom: CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 18 }
const sNav: CSSProperties = { display: 'flex', gap: 10 }
const sBtn: CSSProperties = {
  border: '1px solid rgba(0,0,0,.18)', background: 'transparent', color: '#6f6a64',
  borderRadius: 10, padding: '9px 16px', fontSize: 14, cursor: 'pointer',
}
const sBtnPrim: CSSProperties = {
  border: 'none', background: 'var(--brand, #F04E37)', color: '#fff', fontWeight: 600,
  borderRadius: 10, padding: '9px 22px', fontSize: 14, cursor: 'pointer',
}

export function OnboardingBienvenida({ onCerrar }: { onCerrar: () => void }) {
  const [i, setI] = useState(0)
  const n = SLIDES.length
  const ultimo = i === n - 1
  const slide = SLIDES[i]

  return (
    <div style={sOverlay} role="dialog" aria-modal="true" aria-label="Bienvenida a Dupla Comercial">
      <div style={sCard}>
        <div style={sTop}>
          <span style={sBrand}>✨ Dupla Comercial</span>
          <button style={sSkip} onClick={onCerrar}>Saltar</button>
        </div>

        <div style={sStage}>
          <div style={sInner}>
            <div style={sIco} aria-hidden="true">{slide.emoji}</div>
            <h2 style={sTitulo}>{slide.titulo}</h2>
            <p style={sTexto}>{slide.texto}</p>
          </div>
        </div>

        <div style={sBottom}>
          <div style={{ display: 'flex', gap: 8 }}>
            {SLIDES.map((_, k) => (
              <span
                key={k}
                style={{
                  width: k === i ? 24 : 8, height: 8, borderRadius: k === i ? 4 : '50%',
                  background: k === i ? 'var(--brand, #F04E37)' : 'rgba(0,0,0,.18)', transition: 'all .25s',
                }}
              />
            ))}
          </div>
          <div style={sNav}>
            {i > 0 && (
              <button style={sBtn} onClick={() => setI(i - 1)}>Atrás</button>
            )}
            <button style={sBtnPrim} onClick={() => (ultimo ? onCerrar() : setI(i + 1))}>
              {ultimo ? 'Empezar' : 'Siguiente'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
