# Despliegue y encendido en vivo · 002 · Conexión de correo

Guía operacional para pasar la feature de **mockeado** a **real**. El código ya está
listo y cubierto por tests sin red; acá sólo se aprovisiona infra y credenciales. Nada
de esto vive en el repo: los secretos se inyectan por entorno / Secret Manager (regla
de oro #3).

> Resumen del flujo en producción: el front pide la URL de consentimiento → el usuario
> autoriza Gmail en Google → Google redirige al **callback** del backend → el backend
> canjea el `code`, guarda el `refresh_token` en **Secret Manager** y la integración en
> **Supabase** → **Cloud Scheduler** dispara el **poller** cada ~1–2 min, que lee los
> correos nuevos de cada casilla y crea solicitudes.

---

## 1. Variables de entorno (Cloud Run · servicio `api`)

Copia `apps/api/.env.example` y rellena los valores reales (en Cloud Run se cargan como
variables del servicio, no como archivo). Las nuevas para esta feature:

| Variable | De dónde sale | Quién la usa |
|---|---|---|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Web) | Canje del `code` y refresh del access token |
| `GOOGLE_REDIRECT_URI` | URL pública del callback, **idéntica** a la registrada en la consola | OAuth |
| `FRONTEND_URL` | URL de la Bandeja del front | A dónde redirige el callback al terminar |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API → `service_role` | Poller y callback (saltan RLS, fijan `empresa_id`) |
| `GCP_PROJECT_ID` | Proyecto de GCP donde viven los secretos | `AlmacenSecretos` (Secret Manager) |
| `POLLER_TOKEN` | Generar aleatorio: `openssl rand -hex 32` | Protege `POST /interno/poller/correo` |

`SUPABASE_SERVICE_ROLE_KEY` y `POLLER_TOKEN` son **secretos**: cárgalos como secret refs
de Cloud Run (o Secret Manager), nunca en texto plano ni en el front.

---

## 2. Google OAuth (Gmail, solo lectura)

1. Habilita **Gmail API** en el proyecto de GCP.
2. **OAuth consent screen**: tipo *External*, en *Testing* agrega las casillas piloto
   como *test users* (mientras no esté *verificada*, Google sólo deja entrar a esas).
3. **Scope mínimo**: `https://www.googleapis.com/auth/gmail.readonly`. No pidas más:
   pedir scopes amplios dispara la verificación de Google.
4. **Credentials → OAuth client ID (Web application)**: registra `GOOGLE_REDIRECT_URI`
   en *Authorized redirect URIs*. Debe ser EXACTA (mismo esquema, host y path) que la del
   backend: `https://<api>/integraciones/correo/gmail/callback`.

El backend ya pide `access_type=offline` + `prompt=consent` para recibir `refresh_token`
(ver `construir_url_consentimiento`). Si Google no devuelve `refresh_token`, el usuario
debe reconsentir (el cliente real lo detecta y avisa).

---

## 3. Google Secret Manager (refresh tokens)

- La **service account** del servicio Cloud Run `api` necesita el rol
  **`roles/secretmanager.admin`** (crear/leer/borrar versiones) en `GCP_PROJECT_ID`.
- Cada casilla se guarda como un *secret* (`gmail-refresh-<empresa_id>`) con una *version*
  por valor. En `integraciones.token_ref` se persiste la **ruta** del secreto, jamás el
  valor (CA5).
- No hay que crear los secretos a mano: el callback los crea (`create_secret` +
  `add_secret_version`, tolerando `AlreadyExists`).

---

## 4. Supabase (Auth + datos + RLS)

- **`empresa_id` en el JWT**: configura el *custom access token hook* para que cada token
  de usuario incluya el claim `empresa_id` (lo lee `obtener_empresa_actual`, HS256 con
  `SUPABASE_JWT_SECRET`).
- **Migraciones**: aplica `supabase/migrations/` (incluye `0002_conexion_correo.sql`: las
  columnas de `integraciones` y el índice único de idempotencia de `solicitudes`).
- **RLS**: la política `int_empresa` filtra `integraciones` por la empresa del JWT. El
  poller y el callback usan la `service_role` (saltan RLS) y por eso fijan `empresa_id`
  explícito en cada fila — nunca se infiere del ambiente (anti-cruce de tenants, T11).

---

## 5. TR4 · Disparo del poller (Cloud Scheduler)

El endpoint interno `POST /interno/poller/correo` **no** se expone al front. Lo dispara
Cloud Scheduler cada ~1–2 min. Dos formas de autenticarlo (el endpoint acepta el secreto
compartido hoy; OIDC es el endurecimiento recomendado):

**A) Secreto compartido (lo que valida el código hoy, T12):**

```bash
gcloud scheduler jobs create http poller-correo \
  --location=<region> \
  --schedule="*/2 * * * *" \
  --uri="https://<api>/interno/poller/correo" \
  --http-method=POST \
  --headers="X-Poller-Token=<POLLER_TOKEN>" \
  --attempt-deadline=120s
```

**B) OIDC (recomendado, sin secreto en el header):** que Scheduler firme la llamada con la
identidad de una service account y Cloud Run valide el token. Requiere que el servicio
`api` exija OIDC (siguiente iteración de `verificar_credencial_servicio`):

```bash
gcloud scheduler jobs create http poller-correo \
  --location=<region> --schedule="*/2 * * * *" \
  --uri="https://<api>/interno/poller/correo" --http-method=POST \
  --oidc-service-account-email=<sa>@<proj>.iam.gserviceaccount.com \
  --oidc-token-audience="https://<api>"
```

**Disparo manual en dev:**

```bash
curl -X POST http://localhost:8000/interno/poller/correo \
  -H "X-Poller-Token: $POLLER_TOKEN"
```

(En la demo en memoria el token es `demo-token`; ver el panel en `/demo`.)

---

## 6. Chequeo de integración en vivo (RLS · A no ve lo de B)

La RLS de `integraciones` ya está verificada por pgTAP (002·T2). Para validarla contra una
base real, con Supabase local (necesita Docker):

```bash
supabase start
supabase db reset          # aplica migrations + seed
# correr los tests SQL de supabase/tests/ (pgTAP): empresa A no ve la fila de B
```

Esto es operacional (no entra en la suite unitaria de `pytest`, que es sin red).

---

## 7. Checklist de encendido

- [ ] Variables del §1 cargadas en Cloud Run (secretos como secret refs).
- [ ] Gmail API habilitada; consent screen con test users; scope `gmail.readonly`.
- [ ] `GOOGLE_REDIRECT_URI` registrada EXACTA en la consola.
- [ ] Service account `api` con `secretmanager.admin`.
- [ ] Custom access token hook de Supabase poblando `empresa_id`.
- [ ] Migraciones aplicadas; RLS activa.
- [ ] Job de Cloud Scheduler creado (A o B) y probado.
- [ ] Conectar una casilla piloto end-to-end y ver solicitudes ingeridas.
