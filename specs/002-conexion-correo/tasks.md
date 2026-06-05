# Tareas 002 · Conexión de correo y recepción de solicitudes

Orden TDD: cada tarea escribe **el test primero (rojo)**, luego el mínimo código
(verde), luego refactor. Tareas pequeñas, commit por tarea (en español). Gmail y el
OAuth van **mockeados** en todos los tests (CA6): cero llamadas reales, cero
credenciales reales.

> El corazón es el **servicio de ingesta** (T4–T5): puro, con Gmail mockeado, cubre
> CA3/CA4/CA7. Empezamos por los datos (la migración) y subimos hacia los endpoints
> y el front. El cableado real (Gmail/Secret Manager/Supabase/Scheduler) queda
> deferido al final, detrás de interfaces inyectables (igual que en la Spec 001).

## Datos (Supabase)

- [x] **T1 · Migración `0002_conexion_correo.sql` + idempotencia.** `ALTER TABLE
  integraciones` agrega `casilla text`, `cursor text`, `estado text not null default
  'conectado' check (estado in ('conectado','reconectar'))`, `actualizado_en
  timestamptz not null default now()`. Crea el índice único de idempotencia
  `idx_solicitudes_gmail_msg on solicitudes(empresa_id, gmail_msg_id) where
  gmail_msg_id is not null`. **Sin tablas nuevas.**
  - Test (SQL en `supabase/tests/`): las columnas nuevas existen con su default/check;
    un segundo `insert` de `solicitudes` con el mismo `(empresa_id, gmail_msg_id)`
    **falla** por el índice único (CA4 a nivel de datos). Verificar rojo (sin índice,
    duplica) → verde.
- [x] **T2 · RLS multi-tenant de `integraciones`.** La política `int_empresa` ya
  existe; esta tarea la **verifica**, no la crea.
  - Test (pgTAP en `supabase/tests/`): empresa A **no** ve la fila `integraciones` de
    empresa B (consideraciones multi-tenant de la spec).

## Servicio de ingesta (corazón · Gmail mockeado)

- [x] **T3 · Arnés de la capa de correo (interfaces + dobles).** Esquema Pydantic
  `Integracion { id, empresa_id, proveedor, token_ref, casilla, cursor, estado }`;
  `RepositorioIntegraciones` (Protocol) + implementación **en memoria**; extender el
  repositorio de solicitudes con `crear_desde_correo(empresa_id, gmail_msg_id, …)`
  **idempotente** (emula `on conflict do nothing`); `ClienteGmail` (Protocol:
  `listar_nuevos(cursor) -> (mensajes, nuevo_cursor)`, `obtener(msg_id) -> From/asunto/
  cuerpo`); doble `ClienteGmailFake` en `tests/dobles.py` (payload fijo, registra
  llamadas, **cero red** — CA6).
  - Test de humo: el `ClienteGmailFake` devuelve los mensajes fijados y registra las
    llamadas; el repo en memoria de integraciones guarda/lee por empresa.
- [x] **T4 · Servicio `ingerir_correos_nuevos(integracion, gmail_cliente, repo)`.**
  Pide a Gmail los mensajes nuevos desde `cursor`; por cada uno crea una `solicitud`
  (`tipo='sin_clasificar'`, `estado='nueva'`, `gmail_msg_id=<id>`, `empresa_id` de la
  integración); avanza `cursor`. Mapeo From→`remitente`/`correo_origen`,
  subject→`asunto`, texto plano→`cuerpo`.
  - Test CA3: 2 mensajes nuevos → 2 solicitudes (`sin_clasificar`/`nueva`) con el mapeo
    correcto y el `cursor` avanzado.
  - Test CA4: un mensaje cuyo `gmail_msg_id` ya existe → **no** duplica (idempotencia).
- [x] **T5 · Resiliencia del token (CA7).** Si el refresh/cliente Gmail lanza un error
  de autenticación, la integración pasa a `estado='reconectar'`, el servicio **no**
  lanza excepción y reporta el corte de esa empresa.
  - Test: cliente Gmail que falla la auth → integración queda `'reconectar'`, sin
    excepción y sin solicitudes creadas para esa empresa.

## Endpoints de usuario (FastAPI · token de Supabase → `empresa_id`)

- [x] **T6 · `GET /integraciones/correo`.** Devuelve el estado de la empresa del
  usuario. Dependencias inyectables (`obtener_repositorio_integraciones`,
  `obtener_empresa_actual`).
  - Test CA1: sin integración → `{proveedor:null, estado:null, casilla:null}`.
  - Test CA2: con integración conectada → `proveedor='gmail'`, `estado='conectado'`,
    `casilla` presente.
  - Test CA5: la respuesta **nunca** incluye `token_ref` ni ningún token.
- [x] **T7 · `POST /integraciones/correo/gmail/iniciar`.** Devuelve `{url}` de
  consentimiento de Google con scope mínimo `gmail.readonly` y un `state` anti-CSRF
  ligado a la empresa/sesión (almacén de `state` inyectable).
  - Test: responde una `url` que contiene el scope `gmail.readonly` y un `state`; el
    `state` queda registrado para validarse en el callback.
- [x] **T8 · `GET /integraciones/correo/gmail/callback?code=&state=`.** Valida `state`,
  canjea el `code` (cliente OAuth **mockeado**), guarda el refresh token vía
  `AlmacenSecretos` (impl local en test), escribe/actualiza `integraciones`
  (`token_ref`, `casilla`, `cursor` inicial, `estado='conectado'`) y redirige `302`.
  - Test CA5/CA6: con OAuth mockeado persiste la integración y la respuesta (`302`)
    **no** expone tokens; `state` inválido → `400`.
- [x] **T9 · `DELETE /integraciones/correo` (el "Cambiar").** Borra la integración y el
  secreto asociado (`AlmacenSecretos.borrar`).
  - Test: tras el `DELETE`, `GET /integraciones/correo` vuelve a `proveedor:null`; se
    invocó el borrado del secreto.

## Poller interno (service role)

- [x] **T10 · `POST /interno/poller/correo`.** Recorre las integraciones `gmail` e
  invoca `ingerir_correos_nuevos` por empresa. No expuesto al front. Responde un
  resumen `{empresas_procesadas, solicitudes_creadas}`.
  - Test CA3 (extremo a extremo, mockeado): 1 integración con 2 correos nuevos → 2
    solicitudes en la bandeja de esa empresa.
- [x] **T11 · Anti-cruce de tenants en el poller.** Corre con **service role** (sin JWT
  → la RLS no aplica): cada solicitud **debe** escribirse con el `empresa_id` de SU
  integración. Además, el fallo de una empresa no corta a las demás (CA7 a nivel de
  poller).
  - Test: con integraciones de empresa A y B, cada solicitud lleva el `empresa_id`
    correcto (jamás se mezclan); si A falla el token, B se procesa igual.
- [x] **T12 · Protección del endpoint interno.** Sólo Cloud Scheduler / service-to-
  service (OIDC o secreto compartido simulado por una dependencia inyectable).
  - Test: sin credencial de servicio → `401/403`; con ella → `200`.

## Frontend (apps/web · `fetch` mockeado)

- [x] **T13 · Estado real de la Bandeja desde el backend.** La Bandeja carga
  `GET /integraciones/correo` y pinta: *conectar* si `proveedor:null`, *Escuchando ·
  &lt;proveedor&gt;* si `'conectado'`, *reconectar* si `'reconectar'`. (El render de
  los estados ya lo cubre `Bandeja.test.tsx`; esto cablea la **carga**.)
  - Tests (vitest, `fetch` mock): `null` → botones de proveedor; `'conectado'` →
    "Escuchando nuevos correos"; `'reconectar'` → aviso de reconectar.
- [x] **T14 · Iniciar conexión Gmail desde el front.** Al hacer clic en "Gmail", el
  front llama `POST /integraciones/correo/gmail/iniciar` y navega a la `url` de
  consentimiento devuelta (CA2). `fetch` mockeado; la navegación stubbeada.
  - Test: clic en "Gmail" → se llama al endpoint y se usa la `url` devuelta (no se
    inventa la URL en el cliente).

## Cableado real (integración) — reemplaza los proveedores stub

> Igual que en la Spec 001 (T7a/b/c), estos van **después** de que el núcleo mockeado
> esté verde, y dependen de la spec de auth real (Supabase JWT) y de infra (GCP).

- [x] **TR1 · Cliente Gmail real + refresh OAuth.** `httpx`; cursor con `historyId`
  (`users.history.list`), fallback `after:` + baseline desde `users.getProfile`. El
  refresh token se resuelve perezosamente contra `AlmacenSecretos` (la fábrica queda
  síncrona como el Protocol). `app/servicios/gmail_real.py`.
  - Tests (sin red, transporte httpx mockeado): construcción sin disparar peticiones;
    con cursor usa `history.list`, mapea From/Subject/cuerpo (texto plano y multipart)
    y avanza el cursor; sin cursor usa `after:` y fija el baseline; refresh inválido o
    sin secreto → `ErrorAutenticacionGmail` (CA7). ✅ El cableado del provider
    (`obtener_fabrica_cliente_gmail`) va con TR2 (necesita el `AlmacenSecretos` real).
- [x] **TR2 · `AlmacenSecretos` real (Google Secret Manager).** `AlmacenSecretosSecretManager`
  en `app/servicios/secretos.py`: cada refresh token es un *secret* con una *version*
  por valor; el `token_ref` persistido es la ruta (`projects/<p>/secrets/<nombre>`),
  nunca el valor (CA5). Cliente de GCP inyectable (import perezoso del
  `SecretManagerServiceAsyncClient`); en dev/test la impl en memoria.
  - Tests (cliente de GCP mockeado, sin red): round-trip guardar→obtener; `guardar`
    tolera `AlreadyExists` (agrega versión); `obtener` inexistente → `None`; `borrar`
    elimina e idempotente ante `NotFound`. ✅
- [ ] **TR3 · Repositorios Supabase.** `service role` para el poller (fija `empresa_id`
  explícito) y repo con **JWT del usuario** para los endpoints (la RLS filtra, no el
  backend). Test de integración contra Supabase local (A no ve lo de B).
- [ ] **TR4 · Disparo del poller (operacional).** Cloud Scheduler → OIDC sobre
  `POST /interno/poller/correo` cada ~1–2 min; en dev se dispara a mano. Infra, no
  código de app.

---

Siguiente paso: `/implementar 002`.
