# Plan 002 · Conexión de correo y recepción de solicitudes

- **Spec:** [spec.md](./spec.md) (estado: aprobada)
- **Decisión clave:** se **reutiliza la tabla `integraciones`** existente (ya modela
  `gmail` + `token_ref` a Secret Manager, con `unique(empresa_id, proveedor)`), en vez
  de crear una tabla nueva; solo se le agregan columnas de estado de polling. **Gmail
  primero** (Capsulab usa Google Workspace). Recepción por **polling** (no push) para
  el piloto.

## 1. Arquitectura
- Front (React) → FastAPI → Gmail API. El **refresh token** vive en **Secret Manager**;
  la fila `integraciones` solo guarda `token_ref`. Extiende la Regla de oro #3 a las
  credenciales de Gmail (nunca en el frontend).
- **Conectar (una vez)** — OAuth de Google, scope mínimo `gmail.readonly`:
  1. El front pide la URL de consentimiento → `POST /integraciones/correo/gmail/iniciar`.
  2. El usuario (Javier) autoriza en Google.
  3. Google redirige al backend `…/callback`; el backend canjea el `code`, guarda el
     refresh token en Secret Manager y escribe/actualiza `integraciones`
     (`token_ref`, `casilla`, `cursor` inicial, `estado='conectado'`).
  4. Redirige de vuelta a la app; la bandeja queda "escuchando".
- **Recepción (continuo)** — un job de **polling** recorre las integraciones gmail e
  ingiere los correos nuevos de cada una:
  - Disparo: Cloud Scheduler → `POST /interno/poller/correo` (service-to-service,
    protegido), cada ~1–2 min. En dev se corre a mano.
  - Por empresa: refresca el access token; pide a Gmail los mensajes nuevos desde
    `cursor`; por cada mensaje crea una `solicitud` (`tipo='sin_clasificar'`,
    `estado='nueva'`, `gmail_msg_id=<id>`); avanza `cursor`.
  - El poller corre con **service role** (sin JWT de usuario → la RLS no aplica), así
    que **debe** fijar `empresa_id` explícitamente desde la integración y jamás de un
    contexto ambiente.

## 2. Contrato de API
- `GET /integraciones/correo` → estado de la empresa del usuario.
  `200 → { "proveedor": "gmail" | null, "estado": "conectado" | "reconectar" | null,
  "casilla": str | null }`. **Nunca** incluye tokens (CA5).
- `POST /integraciones/correo/gmail/iniciar` → `{ "url": <consent_url> }` (con `state`
  anti-CSRF ligado a la empresa/sesión).
- `GET /integraciones/correo/gmail/callback?code=&state=` → valida `state`, canjea y
  persiste; redirige a la app (`302`).
- `DELETE /integraciones/correo` → desconecta (borra la integración + el secreto). Es
  el "Cambiar" de la bandeja.
- `POST /interno/poller/correo` → **interno** (Cloud Scheduler / OIDC). Recorre las
  integraciones gmail e ingiere. No expuesto al front.
- Auth de los endpoints de usuario: token de Supabase; la `empresa_id` se deriva del
  token en el backend, **nunca** del cliente.

## 3. OAuth Gmail + polling
- **Scope mínimo:** `gmail.readonly` (solo leemos; enviar está fuera de alcance →
  menos permisos, menos riesgo).
- **Cursor de avance:** `historyId` de Gmail (incremental vía `users.history.list`) o,
  como fallback, query `after:`/`internalDate`. Se guarda en `integraciones.cursor`.
- **Idempotencia (CA4):** `solicitudes.gmail_msg_id` (ya existe) + índice único
  `(empresa_id, gmail_msg_id)`; insert con `on conflict do nothing`.
- **Token expirado/revocado (CA7):** si el refresh falla → `integraciones.estado =
  'reconectar'`, se corta esa empresa y el poller sigue con las demás; la bandeja lo
  refleja sin caerse.
- **Mapeo correo → solicitud:** `remitente` = nombre del From; `correo_origen` = email
  del From; `asunto` = subject; `cuerpo` = texto plano del mensaje.

## 4. Datos — migración `0002_conexion_correo.sql`
- `ALTER TABLE integraciones` agrega: `casilla text`, `cursor text`,
  `estado text not null default 'conectado' check (estado in ('conectado','reconectar'))`,
  `actualizado_en timestamptz not null default now()`. (Ya tiene `empresa_id`,
  `proveedor`, `token_ref`, `unique(empresa_id, proveedor)` y la política RLS
  `int_empresa`.)
- Índice único de idempotencia:
  `create unique index idx_solicitudes_gmail_msg on solicitudes(empresa_id, gmail_msg_id)
  where gmail_msg_id is not null;`
- **Sin tablas nuevas.** La RLS ya cubre `integraciones` y `solicitudes`.

## 5. Estrategia de pruebas (TDD)
- **Servicio** `ingerir_correos_nuevos(empresa_id, gmail_cliente)` con **Gmail
  mockeado** (CA6, cero llamadas reales):
  - 2 mensajes nuevos → 2 solicitudes nuevas (`sin_clasificar` / `nueva`) (CA3).
  - mensaje con `gmail_msg_id` ya existente → **no** duplica (CA4).
  - refresh de token falla → `estado='reconectar'`, no lanza excepción ni corta a
    otras empresas (CA7).
- **Endpoints** (pytest + httpx/TestClient):
  - `GET /integraciones/correo`: sin integración → `proveedor=null` (CA1); con
    integración → `'conectado'` + `casilla` (CA2).
  - `iniciar` devuelve una `url` con `state`; `callback` con Gmail mockeado persiste la
    integración y **no** devuelve tokens (CA5/CA6).
- **Multi-tenant / RLS** (SQL en `supabase/tests/`): empresa A no ve la integración ni
  las solicitudes de empresa B.
- **Anti-cruce de tenants en el poller:** test que verifica que escribe con el
  `empresa_id` de la integración (service role no debe mezclar empresas).
- **Front** (vitest): el estado "escuchando / conectar" de la Bandeja se alimenta del
  status del backend (`GET /integraciones/correo`) con `fetch` mockeado. El render de
  los estados ya está cubierto por `Bandeja.test.tsx`.

## 6. Riesgos / abiertos
- **Poller sin contexto de usuario (RLS no aplica):** corre con service role;
  mitigación: escribir siempre con el `empresa_id` de la integración + test anti-cruce.
- **Verificación OAuth de Google:** los scopes de Gmail pueden requerir verificación;
  en piloto se usa el modo *testing* con usuarios de prueba (Capsulab). Operacional.
- **Secret Manager en dev:** detrás de una interfaz `almacen_secretos` inyectable
  (implementación local para tests) para no bloquear el desarrollo.
- **Auth real (Supabase JWT) aún no montada:** como en el Plan 001, se inyecta la
  `empresa_id` con una dependencia simulable hasta que exista la spec de auth.
- **Cloud Scheduler / Run jobs:** infra de despliegue; en dev el poller se dispara a
  mano vía el endpoint interno.
