"""Composition root de DEMO con GOOGLE REAL: prueba el OAuth de Gmail de verdad.

A diferencia de `app.demo` (que SIMULA todo, incluido Google), aquí el cliente
OAuth, la config y la fábrica de Gmail son los REALES (se construyen desde `.env`),
así puedes "ver la conexión" de verdad: consentimiento real de Google, canje real
del `code` y refresh token real. Sólo se mockea la INFRAESTRUCTURA que todavía no
montamos, para no necesitar Supabase ni GCP:
  - persistencia de la integración → repo EN MEMORIA (en vez de Supabase),
  - almacén de secretos (refresh token) → EN MEMORIA (en vez de Secret Manager),
  - identidad de empresa → empresa fija (el login sigue mock),
  - estado anti-CSRF del OAuth → EN MEMORIA.

Es código de DESARROLLO: NO se usa en producción ni en los tests (esos arman sus
propios dobles). Reutiliza los endpoints reales de `app.main`.

Requisitos en apps/api/.env:
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI=http://localhost:8000/integraciones/correo/gmail/callback

Requisitos en Google Cloud Console (los hace el usuario, no el código):
  - Pantalla de consentimiento OAuth configurada (modo "Testing").
  - Gmail API habilitada.
  - El redirect URI de arriba registrado como "URI de redireccionamiento autorizado".
  - Tu propio Gmail agregado como "usuario de prueba".

Cómo correrlo (desde apps/api):
    uvicorn app.demo_gmail_real:app --reload --port 8000
Luego abre http://localhost:8000/demo y pulsa "Conectar Gmail".
"""
from uuid import UUID

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import obtener_settings
from app.dependencias import (
    obtener_almacen_estado_oauth,
    obtener_almacen_secretos,
    obtener_config_oauth_gmail,
    obtener_empresa_actual,
    obtener_fabrica_cliente_gmail,
    obtener_repositorio_integraciones,
    obtener_repositorio_integraciones_servicio,
    obtener_repositorio_solicitudes,
    obtener_repositorio_solicitudes_servicio,
    obtener_secreto_poller,
)
from app.main import app
from app.repositorios.estado_oauth import AlmacenEstadoOAuthEnMemoria
from app.repositorios.integraciones import RepositorioIntegracionesEnMemoria
from app.repositorios.solicitudes import RepositorioSolicitudesEnMemoria
from app.servicios.gmail_real import FabricaClienteGmailReal
from app.servicios.oauth_gmail import ConfigOAuthGmail
from app.servicios.secretos import AlmacenSecretosEnMemoria

EMPRESA_DEMO = UUID("0000c0de-0000-4000-8000-000000000001")
BACKEND = "http://localhost:8000"
FRONT = "http://localhost:5174"
SECRETO_POLLER_DEMO = "demo-token"

# --- Prerrequisito: sin credenciales reales de Google no hay nada que probar -----
_settings = obtener_settings()
_faltantes = [
    nombre
    for nombre, valor in (
        ("GOOGLE_CLIENT_ID", _settings.google_client_id),
        ("GOOGLE_CLIENT_SECRET", _settings.google_client_secret),
        ("GOOGLE_REDIRECT_URI", _settings.google_redirect_uri),
    )
    if not valor
]
if _faltantes:
    raise RuntimeError(
        "Faltan credenciales de Google en apps/api/.env: "
        + ", ".join(_faltantes)
        + ". Esta demo usa el OAuth REAL de Google; rellénalas y reintenta."
    )

class _AlmacenEstadoOAuthDemo(AlmacenEstadoOAuthEnMemoria):
    """Demo-only: `consumir` NO borra el `state`, así un reintento o el botón
    "atrás" del navegador sobre el callback no rompe el flujo con un crudo
    `{"detail":"state inválido o expirado"}`. Un `state` que nunca emitimos sigue
    devolviendo None → 400 (correcto). En la implementación REAL el anti-replay
    (borrado de un solo uso) SÍ aplica; esto es comodidad de desarrollo."""

    async def consumir(self, state: str) -> UUID | None:
        return self._por_state.get(state)


# --- Estado en memoria (singletons de proceso): SÓLO la infraestructura externa --
_repo_integraciones = RepositorioIntegracionesEnMemoria([])  # arranca SIN conectar
_repo_solicitudes = RepositorioSolicitudesEnMemoria([])  # las que el poller ingiera
_almacen_estado = _AlmacenEstadoOAuthDemo()
_almacen_secretos = AlmacenSecretosEnMemoria()

# Config REAL (client_id + redirect_uri desde `.env`); sólo cambiamos a dónde vuelve
# el navegador tras conectar: al FRONT real (apps/web en :5174), para ver la bandeja
# "Escuchando · Gmail". `url_autorizacion` queda en su default = el endpoint REAL de Google.
_config_real = ConfigOAuthGmail(
    client_id=_settings.google_client_id,
    redirect_uri=_settings.google_redirect_uri,
    url_post_conexion=f"{FRONT}/",
)

# Fábrica de Gmail REAL para el poller, pero apuntando al MISMO almacén de secretos
# EN MEMORIA donde el callback guardó el refresh token. Sin esto, la dependencia real
# `obtener_fabrica_cliente_gmail` arma la fábrica llamando DIRECTO a Secret Manager
# (que ni siquiera está instalado aquí), así que el poller no encontraría el token y
# se caía con `ModuleNotFoundError: No module named 'google'`.
_fabrica_gmail_real = FabricaClienteGmailReal(
    almacen=_almacen_secretos,
    client_id=_settings.google_client_id,
    client_secret=_settings.google_client_secret,
)

# --- Inyección: se mockea almacenamiento + identidad; el OAuth queda REAL ---------
app.dependency_overrides[obtener_repositorio_integraciones] = lambda: _repo_integraciones
app.dependency_overrides[obtener_repositorio_integraciones_servicio] = (
    lambda: _repo_integraciones
)
# El poller ESCRIBE las solicitudes con el repo de SERVICIO; el endpoint GET
# /solicitudes las LEE con el repo del usuario (JWT). En la demo ambos apuntan al
# MISMO repo en memoria, así lo que el poller ingiere aparece en la bandeja.
app.dependency_overrides[obtener_repositorio_solicitudes] = lambda: _repo_solicitudes
app.dependency_overrides[obtener_repositorio_solicitudes_servicio] = (
    lambda: _repo_solicitudes
)
app.dependency_overrides[obtener_almacen_estado_oauth] = lambda: _almacen_estado
app.dependency_overrides[obtener_almacen_secretos] = lambda: _almacen_secretos
app.dependency_overrides[obtener_config_oauth_gmail] = lambda: _config_real
app.dependency_overrides[obtener_empresa_actual] = lambda: EMPRESA_DEMO
app.dependency_overrides[obtener_secreto_poller] = lambda: SECRETO_POLLER_DEMO
app.dependency_overrides[obtener_fabrica_cliente_gmail] = lambda: _fabrica_gmail_real
# OJO: NO se overridean `obtener_cliente_oauth_google` ni `obtener_fabrica_cliente_gmail`:
# esos son los REALES (desde `.env`), que es justo lo que queremos ejercitar aquí.

# CORS: el front (Vite en :5174) hace fetch cross-origin al backend (:8000). Sin esto,
# el navegador bloquea GET/POST/DELETE de la bandeja y la conexión "falla en silencio".
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONT, "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Páginas mínimas para hacer el flujo clickable (sólo demo) --------------------
_INDICE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Demo · Conectar Gmail (real)</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#e2e8f0;
    margin:0;padding:40px;line-height:1.5}
  .wrap{max-width:620px;margin:0 auto}
  h1{font-size:22px}
  .tag{display:inline-block;background:#0b3b2e;color:#6ee7b7;border:1px solid #134e3a;
    border-radius:30px;font-size:12px;font-weight:700;padding:4px 12px;margin-bottom:14px}
  button{background:#22c55e;color:#06210f;border:none;border-radius:10px;padding:12px 18px;
    font-size:15px;font-weight:700;cursor:pointer;margin:8px 0}
  pre{background:#1e293b;border-radius:10px;padding:16px;overflow:auto;font-size:13px;
    white-space:pre-wrap}
  code{background:#1e293b;padding:2px 6px;border-radius:6px;font-size:13px}
</style></head>
<body><div class="wrap">
  <span class="tag">GOOGLE REAL · almacenamiento en memoria</span>
  <h1>Conectar Gmail (OAuth real)</h1>
  <p>Al pulsar el botón, el backend arma la URL de consentimiento <b>real</b> de Google
     (scope <code>gmail.readonly</code>) y te redirige. Tras autorizar, Google vuelve al
     callback y verás la casilla conectada.</p>
  <button onclick="conectar()">Conectar Gmail</button>
  <pre id="out">Listo. Pulsa el botón para empezar.</pre>
</div>
<script>
  async function conectar(){
    const out = document.getElementById('out')
    out.textContent = 'Pidiendo URL de consentimiento al backend…'
    try{
      const r = await fetch('/integraciones/correo/gmail/iniciar', {method:'POST'})
      const data = await r.json()
      out.textContent = 'Redirigiendo a Google…\\n' + data.url
      window.location = data.url
    }catch(e){ out.textContent = 'Error: ' + e }
  }
</script></body></html>"""


@app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo_indice() -> HTMLResponse:
    """Página de inicio: un botón que arranca el consentimiento real de Gmail."""
    return HTMLResponse(_INDICE)


_CONECTADO = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Demo · Estado de conexión</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#e2e8f0;
    margin:0;padding:40px;line-height:1.5}
  .wrap{max-width:620px;margin:0 auto}
  .card{background:#1e293b;border-radius:12px;padding:24px;font-size:18px}
  .ok{color:#6ee7b7}.warn{color:#fbbf24}
  a{color:#7dd3fc}
</style></head>
<body><div class="wrap">
  <div class="card" id="estado">Verificando estado de la conexión…</div>
  <p><a href="/demo">← Volver</a></p>
</div>
<script>
  fetch('/integraciones/correo').then(r=>r.json()).then(d=>{
    const el = document.getElementById('estado')
    if(d.estado === 'conectado'){
      el.innerHTML = '<span class="ok">✅ Conectado</span><br>' +
        'Proveedor: ' + d.proveedor + '<br>Casilla: <b>' + d.casilla + '</b>'
    }else{
      el.innerHTML = '<span class="warn">⚠️ Aún sin conectar.</span> ' +
        'Si recién autorizaste y ves esto, revisa la consola del backend.'
    }
  }).catch(e=>{ document.getElementById('estado').textContent = 'Error: ' + e })
</script></body></html>"""


@app.get("/demo/conectado", response_class=HTMLResponse, include_in_schema=False)
def demo_conectado() -> HTMLResponse:
    """Página de retorno tras el callback: muestra la casilla conectada (CA2)."""
    return HTMLResponse(_CONECTADO)
