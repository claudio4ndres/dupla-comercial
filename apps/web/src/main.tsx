import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { SesionProvider } from './contextos/SesionContext'
import { SolicitudProvider } from './contextos/SolicitudContext'
import { BandejaProvider } from './contextos/BandejaContext'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SesionProvider>
      <SolicitudProvider>
        <BandejaProvider>
          <App />
        </BandejaProvider>
      </SolicitudProvider>
    </SesionProvider>
  </StrictMode>,
)
