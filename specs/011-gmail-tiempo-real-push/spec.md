# Spec 011 · Gmail en tiempo real (push/watch en vez de polling)

- **Estado:** borrador
- **Tipo:** integración + backend (datos mínimos; sin frontend)
- **Relacionada con:** bandeja (ingesta de correos) · multi-tenant · es la
  **"evolución a producción"** que la Spec 002 dejó documentada explícitamente
  (§6: *"Gmail `users.watch` + Pub/Sub (push instantáneo)… queda fuera de alcance
  pero el modelo de datos no debe impedirlo"*). NO reemplaza la ingesta: la
  **reutiliza**.

## 1. Problema y por qué

Hoy un correo nuevo tarda en aparecer en la bandeja porque la recepción es por
**polling**:

- Cloud Scheduler dispara `POST /interno/poller/correo` cada ~1 min (Spec 002,
  TR4 / `despliegue.md`).
- El front se auto-refresca cada ~20 s.
- Peor caso ≈ **~80 s** entre que el correo llega a Gmail y aparece en la bandeja
  (hasta 60 s del scheduler + hasta 20 s del front).

Para Javo (el gestor) esa latencia se siente como "la app va atrasada respecto a
mi Gmail": abre el correo en Gmail antes de verlo en Dupla. El objetivo es
**casi-instantáneo**: cuando llega un correo, que la solicitud aparezca en
segundos, sin esperar al siguiente tick del scheduler.

La arquitectura estándar de Google para esto es **push**: `Gmail API
users.watch` → un **topic de Google Cloud Pub/Sub** → una notificación que
Pub/Sub entrega a un **endpoint webhook** del backend; el webhook dispara la
**ingesta incremental que YA existe** (`listar_nuevos` por `historyId`). Gmail
entrega la notificación "típicamente en pocos segundos".

> **Importante (encaje con el presupuesto):** esto agrega **infra nueva** (un
> topic Pub/Sub + permisos + un endpoint público). La latencia actual ~80 s es
> *aceptable* para el piloto. Esta spec deja el QUÉ y el POR QUÉ listos; la
> decisión de *cuándo* implementarlo (ahora vs. post-piloto) se discute en §6 y
> en la recomendación del plan. El polling **se mantiene como respaldo** pase lo
> que pase.

## 2. Usuarios y contexto

Javo (gestor), desde la **Bandeja**. No cambia ninguna pantalla: el correo
simplemente aparece **antes**. La conexión sigue siendo **por empresa (tenant)**:
cada empresa ya conectó su casilla con OAuth (Spec 002); esta feature registra un
`watch` **por casilla conectada** para que sus correos lleguen por push.

No hay UI nueva obligatoria. Como mucho, un indicador opcional de "tiempo real
activo" en el estado de la conexión (fuera del alcance core; ver §3).

## 3. Alcance

**Incluye:**

- **Registrar `users.watch` por casilla** (una vez por integración `gmail`
  conectada y al reconectar): le dice a Gmail que publique notificaciones de
  correos nuevos en el topic Pub/Sub de la empresa-operadora. Guarda la
  expiración del watch.
- **Endpoint webhook** (p. ej. `POST /interno/gmail/push`) que:
  1. **valida que el origen es Pub/Sub** (no cualquiera de internet);
  2. lee del mensaje push el `emailAddress` de la casilla;
  3. resuelve la **integración** de esa casilla y **dispara la ingesta
     incremental REUSANDO `ingerir_correos_nuevos` / `listar_nuevos`** (NO se
     reimplementa el parseo ni el avance de cursor);
  4. responde `2xx` rápido para que Pub/Sub no reintente.
- **Renovación del watch**: el `watch` **expira a los 7 días**; un job de Cloud
  Scheduler **diario** lo vuelve a registrar para todas las casillas conectadas
  (Google recomienda renovar **una vez al día**).
- **Multi-tenant:** un `watch` y una resolución de integración **por casilla**;
  el webhook fija `empresa_id` SIEMPRE desde la integración de la casilla
  notificada (corre con service role, sin JWT → la RLS no aplica), jamás del
  ambiente. La empresa A nunca ingiere correos de la empresa B.
- **Fallback al polling:** el poller de la Spec 002 **se conserva** y sigue
  corriendo (a menor frecuencia si se quiere, p. ej. cada 5–15 min) como red de
  seguridad: si una notificación push se pierde, se retrasa, o el watch caducó,
  el siguiente poll recupera los correos. Push y polling son **idempotentes**
  entre sí (misma ingesta, mismo `cursor`, mismo índice único
  `(empresa_id, gmail_msg_id)`): no se duplican solicitudes.
- **Persistir el estado del watch** (al menos su expiración) por integración,
  para poder renovarlo y diagnosticarlo.

**No incluye (fuera de alcance):**

- **Microsoft Graph `subscriptions`** (push de Outlook). Igual que en la Spec
  002, Outlook queda para otra iteración.
- **Aprovisionar la infraestructura GCP** (crear el topic Pub/Sub, la
  suscripción push, y otorgar el permiso de publicación a la service account de
  Gmail). Eso es **acción humana/devops** (config de GCP), se documenta en un
  `despliegue.md` y se marca como frontera 🧑 en `tasks.md`; el **código**
  (webhook, registrar/renovar watch) es del agente 🤖.
- **La clasificación y el resumen** del correo: ya los hace la ingesta
  reutilizada (Haiku), igual que en el poller. No cambian.
- **UI nueva** más allá de, opcionalmente, un indicador de estado "tiempo real".
  El flujo visible de la bandeja no cambia.
- **Reemplazar el polling.** El push lo **complementa**; el polling sigue como
  respaldo.
- **Eliminar el `watch` al desconectar** vía `users.stop` es deseable (limpieza)
  pero se trata como tarea menor, no como criterio central.

## 4. Criterios de aceptación (de aquí salen los tests)

Escritos en formato Dado / Cuando / Entonces, verificables. Las APIs externas
(Gmail `watch`/`history`, Pub/Sub, el canje OAuth) van **mockeadas** en los tests
(CA8): cero llamadas reales, cero credenciales reales.

- **CA1 — Registrar watch.** Dado una integración `gmail` conectada, Cuando el
  sistema activa el tiempo real para esa casilla, Entonces llama a `users.watch`
  con el `topicName` del topic Pub/Sub configurado y **persiste la expiración**
  devuelta en la integración (estado de watch).
- **CA2 — Webhook dispara ingesta reutilizada.** Dado una notificación push
  legítima de Pub/Sub para la casilla `casilla@empresa.cl`, Cuando llega a
  `POST /interno/gmail/push`, Entonces el backend resuelve la integración de esa
  casilla e invoca **la misma `ingerir_correos_nuevos`** que usa el poller
  (incremental desde el `cursor` por `historyId`), creando **una solicitud por
  correo nuevo** en la bandeja de esa empresa, y responde `2xx`.
- **CA3 — Origen verificado.** Dado una petición a `POST /interno/gmail/push` que
  **no** acredita venir de Pub/Sub (sin el token/JWT válido), Cuando llega,
  Entonces se rechaza con `401/403` y **no** dispara ninguna ingesta. Dado una
  petición con la credencial correcta, Entonces se acepta.
- **CA4 — Idempotencia push ↔ polling.** Dado un correo que ya fue ingerido (por
  push o por un poll previo), Cuando llega una notificación push (o un poll) que
  lo vuelve a ver, Entonces **no** se crea una solicitud duplicada (idempotencia
  por `(empresa_id, gmail_msg_id)` + avance de `cursor`, idéntica a la Spec 002).
- **CA5 — Multi-tenant en el webhook.** Dado notificaciones push para la casilla
  de la empresa A y para la de la empresa B, Cuando se procesan, Entonces cada
  solicitud se crea con el `empresa_id` de **su** integración (jamás se cruzan); y
  una notificación para una casilla **desconocida / no conectada** se ignora con
  `2xx` sin crear nada y sin filtrar datos de otra empresa.
- **CA6 — Renovación del watch.** Dado que el `watch` expira a los ~7 días, Cuando
  corre el job diario de renovación, Entonces se vuelve a llamar `users.watch`
  para **todas** las casillas conectadas y se actualiza la expiración; el fallo de
  renovar **una** empresa (token expirado) no corta la renovación de las demás
  (se marca `reconectar`, igual que el poller — CA7 de la Spec 002).
- **CA7 — Fallback al polling.** Dado que una notificación push se **pierde** o el
  `watch` está caducado para una empresa, Cuando el poller de respaldo corre,
  Entonces igualmente ingiere los correos pendientes desde el `cursor` (no se
  pierde ningún correo); y como push y poll comparten ingesta+cursor, no se
  duplican (CA4).
- **CA8 — Sin servicios reales en los tests.** En los tests, `users.watch`,
  `users.history.list`, la entrega de Pub/Sub y la verificación del JWT/token de
  origen están **mockeadas**. No se hacen llamadas reales ni se usan credenciales
  reales (extiende CA6 de la Spec 002).
- **CA9 — Resiliencia del webhook.** Dado un mensaje push malformado, para una
  casilla sin integración, o cuyo refresh de token falla, Cuando llega al webhook,
  Entonces el endpoint **no se cae** (responde `2xx` o el código adecuado para que
  Pub/Sub no reintente en bucle), registra el caso y, si aplica, marca
  `reconectar` la integración — sin afectar a otras empresas.

## 5. Consideraciones multi-tenant

- El `watch` y el estado de su expiración pertenecen a una `empresa_id`
  (se persisten en la fila `integraciones` de esa empresa, que ya existe).
- El topic Pub/Sub puede ser **único de la empresa-operadora** (Capsulab /
  RukkumansLabs como operador de la plataforma): TODAS las casillas publican al
  mismo topic; el **aislamiento entre tenants lo da el webhook**, que resuelve la
  integración por el `emailAddress` del mensaje y fija `empresa_id` explícito. No
  hace falta un topic por empresa (sería operacionalmente caro); la barrera es la
  resolución por casilla + la RLS de `solicitudes`/`integraciones`.
- El webhook corre con **service role** (Pub/Sub no trae JWT de usuario → la RLS
  no aplica), así que **debe** fijar `empresa_id` desde la integración de la
  casilla notificada y jamás inferirlo del ambiente — idéntico al contrato del
  poller (Spec 002, T11: anti-cruce de tenants).
- **Test de aislamiento:** una notificación para la casilla de A nunca crea
  solicitudes en B; una casilla desconocida no filtra ni crea nada (CA5). La RLS
  de `integraciones`/`solicitudes` (política `int_empresa` y el índice único de
  idempotencia) ya está verificada por la Spec 002 y se reutiliza.

## 6. Decisiones y recomendación (a confirmar antes de planificar a fondo)

> Estas notas guían el plan; la **recomendación formal de hacerlo ahora vs.
> post-piloto** va en `plan.md` (§ recomendación) para que el líder técnico
> decida con la frontera humano/agente y el costo a la vista.

- **El polling NO se elimina.** Push es una optimización de latencia; el polling
  queda como respaldo (red de seguridad ante notificaciones perdidas / watch
  caducado / endpoint caído). Se puede **bajar su frecuencia** (de ~1 min a
  ~5–15 min) para ahorrar cuota una vez que el push esté estable, pero eso es un
  ajuste operacional, no parte del core.
- **Topic único de la operadora**, aislamiento por webhook (ver §5). Decisión por
  costo/operación.
- **Verificación del origen del webhook:** dos opciones (se deciden en el plan):
  (a) **push autenticado de Pub/Sub** con OIDC JWT (verificar `iss`, `aud`,
  `email` de la service account, `email_verified`); o (b) la alternativa simple:
  un **token secreto en la URL** del endpoint (solo Pub/Sub conoce la URL). El
  proyecto ya tiene el patrón de "secreto compartido para el endpoint interno"
  (`X-Poller-Token`, Spec 002 T12), así que (b) es el camino de menor fricción
  para el piloto y (a) el endurecimiento recomendado para producción.
- **Endpoint público:** el webhook **debe** ser alcanzable desde internet (lo
  llama Pub/Sub), a diferencia del poller que es service-to-service interno. Es la
  principal superficie nueva de seguridad → de ahí el énfasis en CA3.
- **Costo/complejidad honestos:** infra nueva (topic + suscripción + permiso de
  publicación de `gmail-api-push@system.gserviceaccount.com`), un endpoint
  público, y un segundo job de Scheduler (renovación diaria). El beneficio es
  latencia de ~80 s → segundos. Para un piloto de **una** agencia, ~80 s suele ser
  tolerable; el valor sube con varias empresas y mayor volumen.

## 7. Aclaraciones pendientes

- [NECESITA ACLARACIÓN: ¿Se implementa **ahora** o se deja la spec documentada
  para **post-piloto**? La latencia actual ~80 s es aceptable; la recomendación
  del plan es **dejarlo documentado** y priorizarlo cuando entre la 2ª/3ª empresa
  o cuando Javier reporte la latencia como molestia real.]
- [NECESITA ACLARACIÓN: ¿El topic Pub/Sub vive en el proyecto GCP de la
  **operadora** (un solo topic compartido) — recomendado — o se quiere un topic
  por empresa? Afecta la config GCP, no el código del webhook.]
- [NECESITA ACLARACIÓN: Verificación del origen del webhook para el piloto:
  ¿**token secreto en la URL** (camino simple, espeja `X-Poller-Token`) o **OIDC
  JWT de Pub/Sub** (endurecido) desde el día uno?]
- [NECESITA ACLARACIÓN: ¿Se quiere bajar la frecuencia del poller (p. ej. de
  ~1 min a ~5–15 min) una vez activo el push, o mantenerlo a ~1 min por máxima
  seguridad mientras se valida?]
- [NECESITA ACLARACIÓN: ¿Llamar `users.stop` al **desconectar** la casilla
  (limpieza del watch) entra en esta entrega o se difiere?]
