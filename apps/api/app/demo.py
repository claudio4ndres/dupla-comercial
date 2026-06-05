"""Composition root de DEMO: levanta la API REAL con dobles en memoria y datos
sembrados, para ver el flujo de conexión de correo en el navegador SIN GCP,
Supabase ni credenciales reales (regla de oro #3: cero secretos, cero red real).

Es código de desarrollo: NO se usa en producción ni en los tests (esos arman sus
propios dobles). Sólo reutiliza los endpoints reales de `app.main` y les inyecta
implementaciones en memoria vía `app.dependency_overrides`.

Cómo correrlo
-------------
1) Backend (esta carpeta, apps/api):
       uvicorn app.demo:app --reload --port 8000
2) Front (apps/web, en otra terminal):
       VITE_API_URL=http://localhost:8000 npm run dev
   Abre http://localhost:5174

Flujo clickable (extremo a extremo, todo simulado)
--------------------------------------------------
- La Bandeja arranca "sin conectar" (CA1).
- Clic en "Gmail" → el front pide la URL al backend (T14) y navega a una pantalla
  de consentimiento SIMULADA (no es Google real) → "Autorizar".
- Vuelve al front "Escuchando · Gmail" (CA2/T13).
- Panel de control en http://localhost:8000/demo para disparar el poller (T10-T12)
  y ver las solicitudes ingeridas. También puedes:
       curl -X POST localhost:8000/interno/poller/correo -H "X-Poller-Token: demo-token"
"""
from uuid import UUID

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.dependencias import (
    obtener_almacen_estado_oauth,
    obtener_almacen_secretos,
    obtener_cliente_oauth_google,
    obtener_config_oauth_gmail,
    obtener_empresa_actual,
    obtener_fabrica_cliente_gmail,
    obtener_repositorio_integraciones,
    obtener_repositorio_solicitudes,
    obtener_secreto_poller,
)
from app.main import app
from app.repositorios.estado_oauth import AlmacenEstadoOAuthEnMemoria
from app.repositorios.integraciones import RepositorioIntegracionesEnMemoria
from app.repositorios.solicitudes import RepositorioSolicitudesEnMemoria
from app.servicios.gmail import MensajeCorreo
from app.servicios.oauth_gmail import ConfigOAuthGmail, CredencialesGmail
from app.servicios.secretos import AlmacenSecretosEnMemoria

# --- Identidad y URLs de la demo (sin auth real: una empresa fija) -----------
EMPRESA_DEMO = UUID("0000c0de-0000-4000-8000-000000000001")
BACKEND = "http://localhost:8000"
FRONT = "http://localhost:5174"
SECRETO_POLLER_DEMO = "demo-token"

# Correos que el "Gmail" de demo entregará al poller (cero red).
_MENSAJES_DEMO = [
    MensajeCorreo(
        gmail_msg_id="demo-1",
        remitente="Zona Espiga",
        correo_origen="ventas@zonaespiga.cl",
        asunto="Sampling de sopaipillas afuera del Metro",
        cuerpo="Hola, queremos activar sampling de sopaipillas en 3 estaciones...",
    ),
    MensajeCorreo(
        gmail_msg_id="demo-2",
        remitente="Fórmula 1 LATAM",
        correo_origen="marketing@f1latam.com",
        asunto="Ideas de activación para el GP",
        cuerpo="Buscamos conceptos de alto impacto para la previa del Gran Premio...",
    ),
    MensajeCorreo(
        gmail_msg_id="demo-3",
        remitente="Netflix · Narnia",
        correo_origen="brand@netflix.com",
        asunto="Lanzamiento Las Crónicas de Narnia",
        cuerpo="Necesitamos una experiencia inmersiva para el estreno...",
    ),
]


class _GmailDemo:
    """Cliente Gmail de demo: entrega los correos fijos una vez y avanza el cursor;
    en polleos posteriores ya no hay "nuevos" (cero red, cero credenciales)."""

    def __init__(self, mensajes: list[MensajeCorreo]):
        self._mensajes = mensajes

    async def listar_nuevos(self, cursor):
        if cursor is not None:  # ya se ingirieron en un polleo anterior
            return [], cursor
        return list(self._mensajes), "demo-cursor-1"


class _FabricaGmailDemo:
    """Construye el cliente Gmail de la empresa (en la demo, siempre el mismo doble)."""

    def __init__(self, mensajes: list[MensajeCorreo]):
        self._mensajes = mensajes

    def crear(self, integracion):
        return _GmailDemo(self._mensajes)


class _OAuthDemo:
    """Canjea el `code` por credenciales fijas (no toca Google)."""

    async def canjear_codigo(self, code: str) -> CredencialesGmail:
        return CredencialesGmail(
            refresh_token="refresh-token-demo", casilla="piloto@capsulab.cl"
        )


# --- Estado compartido entre peticiones (singletons de proceso) --------------
_repo_integraciones = RepositorioIntegracionesEnMemoria([])  # arranca SIN conectar
_repo_solicitudes = RepositorioSolicitudesEnMemoria([])
_almacen_estado = AlmacenEstadoOAuthEnMemoria()
_almacen_secretos = AlmacenSecretosEnMemoria()
_fabrica_gmail = _FabricaGmailDemo(_MENSAJES_DEMO)
_oauth = _OAuthDemo()
_config = ConfigOAuthGmail(
    client_id="demo-client-id",
    redirect_uri=f"{BACKEND}/integraciones/correo/gmail/callback",
    url_post_conexion=f"{FRONT}/",
    # Apunta al simulador local en vez de a Google real (gracias a `url_autorizacion`).
    url_autorizacion=f"{BACKEND}/demo/google/consentir",
)

# --- Inyección de dobles sobre la app REAL -----------------------------------
app.dependency_overrides[obtener_repositorio_integraciones] = lambda: _repo_integraciones
app.dependency_overrides[obtener_repositorio_solicitudes] = lambda: _repo_solicitudes
app.dependency_overrides[obtener_almacen_estado_oauth] = lambda: _almacen_estado
app.dependency_overrides[obtener_almacen_secretos] = lambda: _almacen_secretos
app.dependency_overrides[obtener_cliente_oauth_google] = lambda: _oauth
app.dependency_overrides[obtener_fabrica_cliente_gmail] = lambda: _fabrica_gmail
app.dependency_overrides[obtener_config_oauth_gmail] = lambda: _config
app.dependency_overrides[obtener_empresa_actual] = lambda: EMPRESA_DEMO
app.dependency_overrides[obtener_secreto_poller] = lambda: SECRETO_POLLER_DEMO

# CORS: el front (vite :5174) hace fetch al backend (:8000). Sólo para la demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONT, "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Simulador de la pantalla de consentimiento de Google (sólo demo) --------
_PAGINA_CONSENTIMIENTO = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Consentimiento (simulado)</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#f6f8fc;margin:0;
    display:flex;min-height:100vh;align-items:center;justify-content:center}
  .card{background:#fff;border:1px solid #e3e8ef;border-radius:14px;max-width:420px;
    padding:32px;box-shadow:0 8px 30px rgba(0,0,0,.06);text-align:center}
  .sim{display:inline-block;background:#fdf3e3;color:#8a5a16;border:1px solid #f0d59a;
    border-radius:30px;font-size:12px;font-weight:700;padding:4px 12px;margin-bottom:18px}
  h1{font-size:19px;margin:6px 0 4px}
  p{color:#56607a;font-size:14px;line-height:1.5}
  .scope{background:#f1f4f9;border-radius:10px;padding:12px 14px;margin:18px 0;
    font-size:13px;color:#33405e;text-align:left}
  .btn{display:block;width:100%;border:none;border-radius:10px;padding:12px;font-size:15px;
    font-weight:600;cursor:pointer;text-decoration:none;box-sizing:border-box}
  .ok{background:#1a73e8;color:#fff;margin-top:8px}
  .no{background:transparent;color:#56607a;margin-top:8px}
</style></head>
<body><div class="card">
  <span class="sim">PANTALLA SIMULADA · no es Google real</span>
  <h1>Dupla Comercial quiere acceder a tu Gmail</h1>
  <p>piloto@capsulab.cl</p>
  <div class="scope">🔒 <b>Ver</b> tus correos electrónicos (solo lectura)
    <br><small>scope mínimo: gmail.readonly</small></div>
  <a class="btn ok" href="__DESTINO__">Autorizar acceso</a>
  <a class="btn no" href="__FRONT__">Cancelar</a>
</div></body></html>"""


@app.get("/demo/google/consentir", response_class=HTMLResponse, include_in_schema=False)
def demo_consentir(redirect_uri: str, state: str) -> HTMLResponse:
    """Simula el consentimiento de Google: al "Autorizar" vuelve al callback REAL
    con un `code` de demo y el `state` recibido (que el callback valida)."""
    destino = f"{redirect_uri}?code=demo-code&state={state}"
    html = _PAGINA_CONSENTIMIENTO.replace("__DESTINO__", destino).replace("__FRONT__", FRONT)
    return HTMLResponse(html)


@app.get("/demo/solicitudes", include_in_schema=False)
def demo_solicitudes() -> dict:
    """Introspección de demo: las solicitudes ingeridas por el poller."""
    sols = list(_repo_solicitudes._por_id.values())
    return {
        "total": len(sols),
        "solicitudes": [
            {
                "asunto": s.asunto,
                "remitente": s.remitente,
                "tipo": s.tipo,
                "estado": s.estado,
            }
            for s in sols
        ],
    }


_PANEL = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Demo · Dupla Comercial</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#e2e8f0;
    margin:0;padding:40px;line-height:1.5}
  .wrap{max-width:680px;margin:0 auto}
  h1{font-size:22px}code{background:#1e293b;padding:2px 6px;border-radius:6px;font-size:13px}
  button{background:#22c55e;color:#06210f;border:none;border-radius:10px;padding:12px 18px;
    font-size:15px;font-weight:700;cursor:pointer;margin:6px 8px 6px 0}
  button.alt{background:#38bdf8;color:#06223a}
  pre{background:#1e293b;border-radius:10px;padding:16px;overflow:auto;font-size:13px;
    white-space:pre-wrap}
  a{color:#7dd3fc}
</style></head>
<body><div class="wrap">
  <h1>Panel de demo · poller interno</h1>
  <p>El front vive en <a href="__FRONT__">__FRONT__</a>. Acá disparas el poller
     (lo que en producción hace Cloud Scheduler) y ves las solicitudes ingeridas.</p>
  <button onclick="poller()">Disparar poller</button>
  <button class="alt" onclick="verSolicitudes()">Ver solicitudes</button>
  <pre id="salida">Listo. Pulsa un botón.</pre>
</div>
<script>
  const out = document.getElementById('salida')
  async function poller(){
    const r = await fetch('__BACKEND__/interno/poller/correo', {
      method:'POST', headers:{'X-Poller-Token':'__TOKEN__'} })
    out.textContent = 'POST /interno/poller/correo → ' + r.status + '\\n' +
      JSON.stringify(await r.json(), null, 2)
  }
  async function verSolicitudes(){
    const r = await fetch('__BACKEND__/demo/solicitudes')
    out.textContent = JSON.stringify(await r.json(), null, 2)
  }
</script></body></html>"""


@app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo_panel() -> HTMLResponse:
    """Panel mínimo para disparar el poller y ver las solicitudes (sólo demo)."""
    html = (
        _PANEL.replace("__BACKEND__", BACKEND)
        .replace("__FRONT__", FRONT)
        .replace("__TOKEN__", SECRETO_POLLER_DEMO)
    )
    return HTMLResponse(html)
