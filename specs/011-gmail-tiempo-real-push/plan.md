# Plan 011 · Gmail en tiempo real (push/watch en vez de polling)

- **Spec:** [spec.md](./spec.md) (estado: borrador — tiene `[NECESITA ACLARACIÓN]`
  en §7; ver la **recomendación** abajo antes de implementar).
- **Tipo:** integración + backend (datos mínimos; sin frontend obligatorio).
- **Decisión clave:** **NO se reimplementa la ingesta.** El push es solo un
  *disparador* más rápido del MISMO camino que ya usa el poller:
  `fabrica_gmail.crear(integracion)` → `ingerir_correos_nuevos(integracion, gmail,
  …)` → `gmail.listar_nuevos(cursor)` (incremental por `historyId` con
  `users.history.list`, ya implementado en `gmail_real.py`). El webhook resuelve
  la integración por el `emailAddress` del mensaje push y dispara esa cadena. Se
  **reutilizan tal cual**: `ClienteGmailReal`/`FabricaClienteGmailReal`
  (`gmail_real.py`), `ingerir_correos_nuevos` (`ingesta_correo.py`), el repo de
  `integraciones` (versión servicio), el `AlmacenSecretos`, el clasificador Haiku,
  y el patrón de **secreto compartido** que protege el endpoint interno
  (`verificar_credencial_servicio` en `rutas/interno.py`, Spec 002 T12).

> **Frontera humano/agente (clave en esta feature):**
> - 🧑 **Humano/devops (config GCP):** crear el **topic Pub/Sub**, crear la
>   **suscripción push** apuntando a la URL del webhook, y otorgar **publish** a
>   `gmail-api-push@system.gserviceaccount.com` sobre el topic. Se documenta en
>   `despliegue.md`. El agente **no** aprovisiona infra ni maneja credenciales
>   reales.
> - 🤖 **Agente (código + tests, todo mockeado):** el endpoint webhook, registrar
>   el `watch`, persistir/renovar la expiración, la verificación del origen, y el
>   cableado del job de renovación. Todo con Gmail/Pub/Sub **mockeados**.

> Reglas de oro aplicables: **#2** (multi-tenant por RLS — el webhook fija
> `empresa_id` explícito, service role, anti-cruce); **#3** (credenciales solo en
> el backend — el refresh token sigue en `AlmacenSecretos`); **#4** (enrutar
> modelos — la clasificación reutilizada ya usa **Haiku 4.5**, no cambia). El LLM
> se sigue llamando **solo desde el backend** (la ingesta reutilizada).

---

## 1. Arquitectura (capas que toca)

```
Gmail (casilla empresa) --notifica--> Pub/Sub topic (operadora) --push--> POST /interno/gmail/push (FastAPI)
        ^                                                                          |
        | users.watch (registro + renovación diaria)                              v
        +---------------------------------------- ingerir_correos_nuevos(integracion, gmail, …)  [REUTILIZADO]
                                                                                   |
                                                                       gmail.listar_nuevos(cursor)  [REUTILIZADO]
                                                                                   |
                                                                       solicitudes (idempotente, RLS)
```

- **Backend (FastAPI):**
  - **Nuevo endpoint webhook** `POST /interno/gmail/push` en `rutas/interno.py`
    (junto al poller, es service-to-service / lo llama Pub/Sub). Pasos:
    1. **Verifica el origen** (ver §5): token secreto en la URL (piloto) o OIDC
       JWT de Pub/Sub (endurecido). Falla → `401/403`, sin ingesta (CA3).
    2. **Parsea el envelope de Pub/Sub**: `message.data` viene **base64**; al
       decodificar es un JSON `{"emailAddress": "...", "historyId": "..."}`
       (formato confirmado en la doc de Gmail push).
    3. **Resuelve la integración** por `emailAddress` (== `integraciones.casilla`)
       con el repo de **servicio** (sin JWT). Casilla desconocida → `2xx` y no
       hace nada (CA5/CA9).
    4. **Dispara la ingesta reutilizada**: `gmail = fabrica_gmail.crear(integ)` →
       `ingerir_correos_nuevos(integ, gmail, repo_solicitudes, repo_integraciones,
       clasificar=clasificar)`. **Idéntico al cuerpo del poller** (CA2). El
       `historyId` del push se ignora para la lógica: `listar_nuevos` ya avanza
       desde el `cursor` guardado; el push solo "despierta" la ingesta.
    5. Responde `2xx` rápido para que Pub/Sub **no reintente** (CA9).
  - **Nuevo servicio `servicios/gmail_watch.py`** (registro/renovación del
    watch), análogo a cómo `gmail_real.py` habla con la API REST de Gmail vía
    `httpx`:
    - `registrar_watch(integracion) -> EstadoWatch{expira_en, history_id}`:
      `POST {BASE_GMAIL}/watch` con body `{ "topicName": <topic>, "labelIds":
      ["INBOX"], "labelFilterBehavior": "INCLUDE" }`, usando el access token de la
      casilla (mismo refresh OAuth que ya hace `ClienteGmailReal._access_token`).
      Devuelve `historyId` + `expiration`. Refresh inválido → `ErrorAutenticacionGmail`.
    - `detener_watch(integracion)` (opcional, para desconectar):
      `POST {BASE_GMAIL}/stop`.
  - **Renovación**: un endpoint interno `POST /interno/gmail/watch/renovar` (o
    reutilizar el disparo del scheduler) que recorre las integraciones `gmail`
    conectadas y re-llama `registrar_watch`, actualizando la expiración. Aísla por
    empresa (un token caído marca `reconectar`, no corta a las demás — CA6).
- **Datos (Supabase):** **migración mínima** para persistir la expiración del
  watch en `integraciones` (ver §3). Sin tablas nuevas. La RLS `int_empresa` y el
  índice único de idempotencia ya existen (Spec 002).
- **Frontend:** **sin cambios obligatorios.** Opcional (fuera del core): un
  badge "tiempo real activo" derivado de `watch_expira_en` no nulo y futuro.
- **Infra (🧑 devops, no código):** topic Pub/Sub + suscripción push + permiso de
  publicación a la SA de Gmail + un 2º job de Cloud Scheduler (renovación diaria).

---

## 2. Contratos de API

| Método · ruta | Quién llama | Request | Response | Errores |
|---|---|---|---|---|
| `POST /interno/gmail/push` | **Pub/Sub** (público, verificado) | envelope Pub/Sub: `{ "message": { "data": "<base64 JSON {emailAddress, historyId}>", "messageId", "publishTime" }, "subscription" }` | `204`/`200` (rápido) | `401/403` origen inválido (CA3); siempre `2xx` ante payload malformado/casilla desconocida para que Pub/Sub no reintente (CA9) |
| `POST /interno/gmail/watch/renovar` | **Cloud Scheduler** (interno, `X-Poller-Token`) | — | `200 { casillas_renovadas, fallidas }` | `403` sin credencial de servicio |
| `POST /interno/poller/correo` *(ya existe, Spec 002)* | Cloud Scheduler | — | `ResumenPoller` | — (se **conserva** como fallback; CA7) |

- **Verificación del origen del push (CA3):** ver §5. Para (a) token en URL: el
  endpoint se registra como `…/interno/gmail/push?token=<secreto>` y compara en
  tiempo constante (espeja `verificar_credencial_servicio`). Para (b) OIDC: valida
  el `Authorization: Bearer <JWT>` (claims `iss`, `aud`, `email`, `email_verified`).
- **Registro inicial del watch:** se dispara al **conectar** la casilla (extender
  el callback OAuth de Gmail de la Spec 002 para llamar `registrar_watch` tras
  persistir la integración) y/o por el primer pase del job de renovación. El
  registro es **idempotente** (re-llamar `watch` simplemente renueva).

---

## 3. Datos — migración `0010_gmail_watch.sql` (mínima)

- `ALTER TABLE integraciones` agrega:
  - `watch_expira_en timestamptz` (NULL = sin tiempo real activo / aún no
    registrado). Para saber cuándo renovar y para diagnóstico/badge opcional.
  - *(opcional)* `watch_history_id text` — el `historyId` que devolvió `watch` al
    registrarse; informativo. **No** sustituye a `cursor` (la ingesta sigue
    avanzando por `cursor`). Si se considera redundante, se omite.
- **Sin tablas nuevas.** `integraciones` ya tiene `empresa_id`, `proveedor`,
  `token_ref`, `casilla`, `cursor`, `estado`, `unique(empresa_id, proveedor)` y la
  RLS `int_empresa`. El índice único de idempotencia
  `idx_solicitudes_gmail_msg (empresa_id, gmail_msg_id)` (Spec 002) es lo que hace
  **push y polling idempotentes entre sí** (CA4) — no se toca.
- **Repo `integraciones`:** agregar `actualizar_watch(empresa_id, expira_en,
  history_id=None)` (versión memoria + servicio/Supabase). Lectura: reutilizar
  `listar_por_proveedor("gmail")` para la renovación y
  `obtener_por_empresa_y_proveedor` ya existente. Para el webhook se necesita
  **resolver por casilla**: agregar `obtener_por_casilla(casilla, proveedor)`
  (memoria + servicio). Corre con **service role**.

---

## 4. Servicios (reutilización máxima)

- **`servicios/gmail_watch.py` (nuevo, mockeable):** habla con la API REST de
  Gmail vía `httpx`, **reusando el patrón de `gmail_real.py`** (refresh OAuth con
  `AlmacenSecretos`, `BASE_GMAIL`, `ErrorAutenticacionGmail`). Define un `Protocol`
  `GestorWatch { async registrar(integracion) -> EstadoWatch; async detener(
  integracion) -> None }` + implementación real `GestorWatchReal` + un doble en
  `tests/dobles.py` (CA8). Así el endpoint y el job dependen del Protocol, no del
  cliente real (igual que el poller depende de `FabricaClienteGmail`).
- **`ingerir_correos_nuevos` (`ingesta_correo.py`): SE REUTILIZA SIN CAMBIOS.** Ya
  es resiliente (token caído → `reconectar` sin caerse; Haiku falla → ingiere
  `sin_clasificar`; correo borrado → lo salta; auto-heal a `conectado`). El
  webhook le pasa exactamente lo que le pasa el poller.
- **`ClienteGmailReal.listar_nuevos` (`gmail_real.py`): SE REUTILIZA SIN
  CAMBIOS.** Su incremental por `historyId` (con re-sync ante `404` de history
  demasiado viejo) es justo lo que necesita el push.
- **Verificación del origen:** servicio chico `servicios/verificacion_pubsub.py`
  (o una función en `rutas/interno.py`) para (b) OIDC — verifica el JWT contra los
  certs públicos de Google (`iss ∈ {accounts.google.com,
  https://accounts.google.com}`, `aud` == audiencia configurada, `email` == SA del
  push, `email_verified == true`). Para (a) token-en-URL basta reusar
  `secrets.compare_digest` como en `verificar_credencial_servicio`.
- **LLM:** la clasificación reutilizada usa **Haiku 4.5** (Regla #4); el webhook no
  introduce llamadas LLM nuevas.

---

## 5. Seguridad (la superficie nueva)

El poller es **interno** (service-to-service). El webhook es **público** (lo llama
Pub/Sub desde internet) → es la principal preocupación de seguridad de esta
feature. Dos niveles, decididos por la aclaración de §7 de la spec:

- **(a) Token secreto en la URL (recomendado para el piloto):** la suscripción
  push de Pub/Sub apunta a `https://<api>/interno/gmail/push?token=<secreto>`.
  Solo Pub/Sub conoce la URL completa; el endpoint compara `token` en tiempo
  constante (`secrets.compare_digest`), espejando el patrón ya probado de
  `X-Poller-Token` (Spec 002 T12). Simple, sin dependencias nuevas. **Riesgo:** el
  token viaja en la query (usar HTTPS — Cloud Run lo es; no loggear la query
  completa).
- **(b) OIDC JWT de Pub/Sub (endurecido, recomendado para producción):** la
  suscripción se configura con una **service account**; Pub/Sub firma un **JWT**
  y lo envía en `Authorization: Bearer <JWT>`. El webhook lo verifica:
  - `iss` ∈ `{ "accounts.google.com", "https://accounts.google.com" }`,
  - `aud` == la audiencia configurada (p. ej. la URL del servicio),
  - `email` == la SA del push configurada,
  - `email_verified` == `true`,
  - firma válida contra los certs públicos de Google
    (`google.oauth2.id_token.verify_oauth2_token` o equivalente; import perezoso
    como el resto de clientes GCP del repo).
- **Endurecimiento común a ambos:** sigue exigiéndose `2xx` rápido; nunca se
  responde con datos de la integración; los errores se loggean por tipo (como ya
  hace el poller). El webhook **no** confía en el `emailAddress` para otra cosa que
  no sea *buscar* la integración (si no existe → no hace nada): no escala
  privilegios ni filtra entre tenants (CA5).

---

## 6. Estrategia de pruebas (TDD) — todo mockeado (CA8)

**Nada toca servicios reales:** Gmail (`watch`/`history`/`profile`), Pub/Sub (la
entrega y el JWT/token de origen) y el canje OAuth se **mockean** (dobles en
memoria o transporte `httpx` mockeado, como `test_cliente_gmail_real.py`). RLS
contra Supabase local (ya cubierta por la Spec 002; aquí se reutiliza).

- **Servicio watch (`gmail_watch.py`)** — transporte `httpx` mockeado, sin red:
  - `registrar_watch` hace `POST /watch` con `topicName` correcto y devuelve
    `{expiration, historyId}`; refresh inválido → `ErrorAutenticacionGmail` (CA1).
  - `detener_watch` hace `POST /stop` (si entra en alcance).
- **Webhook `POST /interno/gmail/push`** (pytest + httpx/TestClient, doble de
  Gmail + repos en memoria):
  - **CA2:** envelope con `message.data` base64 de `{emailAddress, historyId}` para
    una casilla conectada → invoca `ingerir_correos_nuevos` (misma del poller) →
    crea una solicitud por correo nuevo; responde `2xx`. (Verifica que **reutiliza**
    la ingesta, p. ej. afirmando sobre el repo de solicitudes y el avance de cursor,
    no reimplementando el parseo.)
  - **CA3:** sin token/JWT válido → `401/403` y **cero** ingesta; con credencial
    correcta → procesa.
  - **CA4:** un correo ya ingerido (mismo `gmail_msg_id`) → no duplica; un push tras
    un poll del mismo correo → no duplica (idempotencia compartida).
  - **CA5:** push para casilla de A no crea nada en B; casilla desconocida → `2xx`
    sin crear nada (anti-cruce; el `empresa_id` sale SIEMPRE de la integración
    resuelta).
  - **CA9:** `message.data` malformado / casilla sin integración / refresh que falla
    → el endpoint **no** revienta (responde `2xx` o el código que evita el reintento
    en bucle), loggea, y marca `reconectar` si corresponde.
- **Renovación `POST /interno/gmail/watch/renovar`**:
  - **CA6:** con 2 casillas conectadas, re-llama `registrar_watch` para ambas y
    actualiza `watch_expira_en`; si A falla el token, B se renueva igual (A queda
    `reconectar`).
  - **Protección (espeja T12):** sin `X-Poller-Token` → `403`.
- **Fallback (CA7):** test de que, con push "perdido" (no se invoca el webhook), el
  **poller existente** (Spec 002) igualmente ingiere desde el `cursor`; y que un
  poll seguido de un push del mismo correo no duplica (CA4). Reutiliza los tests de
  ingesta de la Spec 002.
- **Verificación de origen OIDC (si se elige (b)):** test que mockea el verificador
  del JWT (claims válidos → pasa; `aud`/`email`/`iss`/`email_verified` malos →
  rechaza). Para (a) token-en-URL: test de comparación en tiempo constante (igual
  que el del poller).
- **Datos / RLS:** la migración agrega `watch_expira_en` (+ opcional
  `watch_history_id`); test (SQL/pgTAP) de que la columna existe con su default y de
  que la RLS `int_empresa` sigue aislando A de B (se reutiliza la verificación de la
  Spec 002; no se crean políticas nuevas).
- **Anti-cruce de tenants en el webhook (clave):** test dedicado de que el webhook,
  corriendo con service role, escribe con el `empresa_id` de la integración de la
  casilla notificada y **jamás** lo infiere del ambiente (espeja T11 de la Spec 002).

---

## 7. Riesgos / decisiones abiertas

- **Infra nueva = costo/operación.** Topic Pub/Sub + suscripción push + permiso de
  publicación + un 2º job de Scheduler. Para **una** agencia piloto la latencia
  ~80 s es tolerable; el beneficio (segundos) se nota con más empresas/volumen.
  → **Ver la RECOMENDACIÓN abajo.**
- **Endpoint público (superficie de ataque).** Mitigado por la verificación de
  origen (§5) + `2xx` rápido + no exponer datos. Es la diferencia central con el
  poller (interno).
- **Watch caduca a 7 días.** Si el job diario de renovación falla varios días
  seguidos, el push se apaga silenciosamente → **el polling de respaldo lo cubre**
  (CA7). Conviene alertar si `watch_expira_en` quedó en el pasado.
- **Entrega "at-least-once" / pérdidas ocasionales de Pub/Sub.** Google dice que
  las notificaciones "pueden retrasarse o perderse ocasionalmente" y recomienda
  **fallback polling** — exactamente lo que mantenemos. La idempotencia
  `(empresa_id, gmail_msg_id)` absorbe los duplicados de "at-least-once".
- **Rate de 1 evento/seg por casilla.** Para el volumen del piloto es holgado; no
  requiere manejo especial.
- **OAuth de Google verificado y scope:** `users.watch` funciona con el scope ya
  pedido (`gmail.readonly` permite `watch`+`history`); no hace falta pedir scopes
  nuevos (menos fricción de verificación). Confirmar al implementar.
- **`empresa_id` desde la integración (no del ambiente):** el webhook hereda el
  mismo riesgo y la misma mitigación que el poller (service role + `empresa_id`
  explícito + test anti-cruce).

---

## RECOMENDACIÓN (líder técnico)

**Dejarlo DOCUMENTADO (esta spec) y NO implementarlo todavía.** Razones:

1. **La latencia actual ~80 s es aceptable** para un piloto de una sola agencia
   (Capsulab). El dolor real aún no está demostrado; implementar ahora es
   optimización prematura.
2. **Agrega infra y superficie nuevas** (topic Pub/Sub, suscripción push, permiso
   de publicación, endpoint **público**, 2º job de Scheduler) — más piezas que
   mantener y asegurar, en contra de la restricción de presupuesto (tiers
   gratuitos, mínima complejidad).
3. **El diseño es de bajo riesgo y barato cuando toque hacerlo**, porque
   **reutiliza** toda la ingesta (`listar_nuevos`/`ingerir_correos_nuevos`) y el
   patrón de seguridad del endpoint interno. El grueso del trabajo nuevo es el
   webhook + el watch + su renovación, no la lógica de correo.

**Gatillos para implementarlo (cuándo dejar de diferir):**
- entra la **2ª/3ª empresa** (la latencia se multiplica en percepción y el polling
  a 1 min empieza a pesar en cuota), o
- **Javier reporta** explícitamente que la latencia molesta en su flujo, o
- sube el **volumen de correos** y el polling frecuente se vuelve caro/ruidoso.

Mientras tanto, **mitigación barata sin infra:** el polling ya está; si se quiere
bajar un poco la latencia percibida, **acortar el auto-refresh del front** (de
~20 s a ~10 s) y/o el scheduler, sin tocar arquitectura.

> Antes de `/tareas 011` (más allá de tener la spec lista), conviene **resolver las
> `[NECESITA ACLARACIÓN]` de la spec** — sobre todo: ¿se hace ahora o post-piloto?,
> topic único vs. por empresa, y token-en-URL vs. OIDC.

---

Siguiente paso: **`/tareas 011`** (cuando se decida implementar; ver recomendación).
