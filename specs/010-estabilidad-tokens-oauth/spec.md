# Spec 010 · Estabilizar los tokens OAuth — fin del "reconectar" recurrente

- **Estado:** borrador
- **Tipo:** integración (OAuth) · operación/infra · backend · frontend (mensajería) · datos (estado del conector)
- **Relacionada con:** multi-tenant · conectores (panel de Configuración) · OAuth de Gmail/Drive (Spec 002) · OAuth de ClickUp por empresa (Spec 009) · cierra la deuda que dejó la Ola 4 (estado por `(empresa,proveedor)` + auto-heal): aquella ola **curó el síntoma**; esta ataca la **raíz**.

---

## 1. Problema y por qué

El conector de ClickUp —y casi con seguridad también el de Gmail/Drive— vuelve a
pedir **"Reconectar"** cada pocos días. El gestor reconecta, funciona un rato, y a
los ~7 días vuelve a caer. Es un goteo de fricción que **erosiona la confianza** en
el producto justo donde más duele: las integraciones que sostienen todo el flujo
(leer correo, leer el Drive, crear tareas). Para vender Dupla a más agencias, una
conexión que se cae sola es inaceptable.

**La Ola 4 ya arregló un síntoma real:** antes, un fallo de Gmail arrastraba la
tarjeta de ClickUp a "reconectar" (el estado era global, no por proveedor); ahora el
estado es por `(empresa, proveedor)` y hay **auto-heal** (un poll/listado exitoso
restaura "conectado" solo). Gracias a eso, una reconexión ya **persiste** y no se
contagia entre conectores. **Pero la causa raíz sigue viva** y se manifiesta así:
la conexión de Gmail/Drive **vuelve a caer sola cada ~7 días**, y el usuario lo
percibe como "esto se desconecta recurrentemente".

**Causa raíz (confirmada contra la documentación oficial):**

- **Google OAuth (Gmail + Drive) — ESTA es la raíz del goteo recurrente.** Las apps
  OAuth de Google cuya pantalla de consentimiento está en **"Testing"** (modo
  desarrollo) con tipo de usuario **"External"** reciben un **refresh token que
  caduca a los 7 días** — *salvo* que los scopes pedidos sean un subconjunto de
  {nombre, email, perfil}. Dupla pide `gmail.readonly` + `drive.readonly`, que
  **NO** están en ese subconjunto exento → **el refresh token caduca a los 7 días**.
  Cuando caduca, el refresh del access token falla (`invalid_grant`), el backend
  marca la integración `gmail` como **"reconectar"**, y el usuario tiene que volver
  a autorizar. Una semana después, otra vez. **Publicar/verificar la app a "In
  production" hace que el refresh token deje de caducar.** Es la solución de raíz, y
  es **acción humana en la consola de Google Cloud** (el agente no la puede hacer).
  - Fuente: Google Identity — *Using OAuth 2.0 to Access Google APIs* → "Refresh
    token expiration": *"A Google Cloud Platform project with an OAuth consent
    screen configured for an external user type and a publishing status of 'Testing'
    is issued a refresh token expiring in 7 days, unless the only OAuth scopes
    requested are a subset of name, email address, and user profile."*

- **ClickUp OAuth — el token NO caduca; "reconectar" en ClickUp es por
  revocación/401, no por expiración.** La documentación oficial de ClickUp dice
  textualmente *"The access token currently does not expire"* y **no entrega refresh
  token**. Esto **confirma la aclaración #4 de la Spec 009**. Conclusión importante:
  el "reconectar" recurrente que el usuario asoció a ClickUp **no era de ClickUp por
  expiración** — era, antes de la Ola 4, el fallo de **Gmail** contagiando la tarjeta
  de ClickUp (estado global). Tras la Ola 4 ese contagio ya no ocurre; lo que queda es
  el goteo **propio de Gmail/Drive** por el modo Testing de la app de Google.
  - Fuente: ClickUp Developer Docs — *Authentication*: *"The access token currently
    does not expire. This is subject to change."*

**En una frase:** la app OAuth de **Google está en modo de desarrollo (Testing)**, y
en ese modo los refresh tokens **caducan a los 7 días**; ese es el motor del
"reconectar" recurrente. El arreglo de raíz es **publicar/verificar la app de Google**
(acción humana). En **paralelo**, el código puede dejar de sufrir en silencio:
**detectar** que una empresa cayó a "reconectar", **avisar mejor** al usuario, y
**alertar al operador** para que ninguna empresa quede días en "reconectar" sin que
nadie se entere. Para ClickUp, publicar/verificar su app es **higiene recomendada**
(reduce fricción del consentimiento y advertencias), aunque no cambia la expiración
del token.

---

## 2. Usuarios y contexto

- **Gestor / admin de empresa (Capsulab, RukkumansLabs, Espiga…):** sufre el
  "reconectar" recurrente desde el **panel de Configuración → Conectores**. Quiere
  conectar **una vez** y olvidarse. Cuando algo sí requiera su atención, quiere un
  mensaje **claro y honesto** ("la conexión con Google expiró, vuelve a conectar"),
  no un "Reconectar" mudo y repetitivo.
- **Operador del producto / responsable técnico (tú):** necesita (a) **ejecutar la
  acción de raíz** en las consolas externas (publicar/verificar las apps OAuth de
  Google y ClickUp) y (b) **enterarse** cuando una empresa cae a "reconectar", para
  no descubrirlo por un reclamo del cliente. Hoy no hay señal: el estado vive en la
  fila de `integraciones` y nadie observa el agregado.
- **Momento del flujo:** la conexión se establece en el **onboarding** y se usa
  **continuamente** (ingesta de correo periódica, lectura del Drive para el catálogo,
  creación de tareas en ClickUp). El fallo aparece **en background** (el poller de
  ingesta es el primero en toparse con el refresh caducado) y se **refleja** en el
  panel como "Reconectar".

---

## 3. Alcance

**Incluye:**

- **(RAÍZ · acción humana) Publicar/verificar la app OAuth de Google** (Gmail + Drive)
  a estado **"In production"** en Google Cloud Console, para que los refresh tokens
  **dejen de caducar a los 7 días**. Esta spec lo **documenta como tarea humana
  explícita** (`🧑`) con su checklist y su criterio de verificación; el agente
  **no** toca consolas externas ni maneja secretos reales.
- **(RAÍZ · acción humana) Revisar/publicar la app OAuth de ClickUp** (higiene del
  consentimiento). Se documenta como tarea humana; su efecto es reducir fricción,
  **no** cambiar la expiración (el token de ClickUp ya no caduca).
- **(CÓDIGO) Detección temprana y observabilidad del "reconectar":** una vista/consulta
  o endpoint **interno** (operador) que liste **qué empresas/proveedores** están en
  `estado='reconectar'` y **desde cuándo**, para no depender de mirar filas a mano.
- **(CÓDIGO) Mejor mensaje al usuario en el panel:** la tarjeta del conector en
  "reconectar" muestra un texto **específico y accionable** por proveedor ("La
  conexión con Google expiró — vuelve a conectar para seguir leyendo tu correo y
  Drive" / "ClickUp se desconectó — vuelve a conectar"), en lugar de un "Reconectar"
  genérico. **No** se inventan estados nuevos si no aportan: se reusa el `estado`
  existente (`conectado | reconectar`) y, *si y solo si* la aclaración #2 lo aprueba,
  se añade un estado **"por expirar"** para el aviso proactivo.
- **(CÓDIGO · sujeto a #2) Aviso proactivo / re-auth temprano:** detectar que un
  refresh token de Google está **por caducar** (o que la app sigue en Testing) y
  avisar **antes** de que se caiga, en vez de esperar al fallo. Alcance mínimo si se
  aprueba; ver aclaración #2.
- **(CÓDIGO) Alerta al operador cuando una empresa cae a "reconectar"** (log
  estructurado con nivel apropiado y/o señal hacia el canal que el operador defina),
  emitida **en el momento** en que el backend marca `reconectar`. Sin exponer tokens.
- **Pruebas** que fijen el comportamiento: detección, mensajería por proveedor,
  alerta al marcar "reconectar", y (si aplica) el estado "por expirar". Todo
  **mockeando** Google/ClickUp/Anthropic (no se llaman servicios reales).

**No incluye (fuera de alcance):**

- **Reescribir el OAuth de Gmail/Drive o de ClickUp.** Se reusan los flujos de las
  Specs 002 y 009 tal cual; esta spec **no** cambia cómo se canjea el `code` ni cómo
  se guardan los tokens.
- **El mecanismo de auto-heal ni el estado por `(empresa,proveedor)`** (ya entregados
  en la Ola 4): esta spec se **apoya** en ellos, no los rehace.
- **Rotar/gestionar los secretos del cliente OAuth** (client_id/secret) ni migrar
  Secret Manager: fuera de alcance salvo lo que la acción humana implique en consola.
- **Refresh token para ClickUp:** ClickUp no lo entrega y su token no caduca; no se
  construye nada al respecto.
- **Un sistema de alerting completo** (PagerDuty/Slack/email con plantillas): se deja
  una **señal mínima** (log estructurado / endpoint interno) y el cableado al canal
  final del operador es un *hook* que se conecta aparte. Ver aclaración #3.
- **Cambiar a un IdP propio, service accounts con domain-wide delegation, u otros
  esquemas de auth.** Posible mejora futura; no aquí.

---

## 4. Criterios de aceptación (de aquí salen los tests)

> Los CA de **código** (CA3–CA7) son verificables con tests automáticos (mockeando
> los servicios). Los CA de **acción humana** (CA1–CA2) se verifican operativamente
> (checklist + observación en producción), no con tests unitarios — se marcan `🧑`.

- **CA1 (🧑 raíz Google — refresh deja de caducar)** — Dado que la app OAuth de Google
  de Dupla está en **"Testing"**, Cuando el operador la publica/verifica a **"In
  production"** en Google Cloud Console, Entonces los refresh tokens emitidos **dejan
  de caducar a los 7 días** y una empresa que conecta Gmail/Drive **permanece
  conectada** sin reconexiones recurrentes. *(Verificación operativa: tras publicar,
  una conexión supera holgadamente 7 días sin caer a "reconectar".)*

- **CA2 (🧑 higiene ClickUp)** — Dado el estado de la app OAuth de ClickUp, Cuando el
  operador la revisa/publica según la consola de ClickUp, Entonces el flujo de
  consentimiento queda en el estado deseado (menos fricción/advertencias). Se deja
  **constancia explícita** de que esto **no** cambia la expiración del token de
  ClickUp (que no caduca), de modo que el "reconectar" de ClickUp sólo puede venir de
  **revocación/401**, nunca de expiración.

- **CA3 (detección/observabilidad para el operador)** — Dado que una o más empresas
  tienen alguna integración en `estado='reconectar'`, Cuando el operador consulta la
  señal interna (endpoint/consulta de operador), Entonces obtiene la **lista de
  `(empresa, proveedor)` en "reconectar"** (y, si está disponible, **desde cuándo**),
  para actuar sin inspeccionar la base a mano. La señal **nunca** incluye tokens
  (regla de oro #3) y respeta el aislamiento (el operador no filtra datos de negocio
  entre empresas más allá del estado del conector).

- **CA4 (mensaje específico por proveedor en el panel)** — Dado un conector en
  "reconectar", Cuando el gestor abre el panel, Entonces la tarjeta muestra un mensaje
  **accionable y específico del proveedor** (Google vs ClickUp) que explica *qué*
  expiró y *qué* hacer ("vuelve a conectar"), no un texto genérico. El estado sigue
  derivándose de la integración de **esa** empresa (no global).

- **CA5 (alerta al marcar "reconectar")** — Dado que el backend detecta credenciales
  rotas y marca una integración como `reconectar` (en la ingesta de correo o en el
  endpoint interno), Cuando ocurre, Entonces se **emite una señal/alerta para el
  operador** (log estructurado con nivel adecuado y/o el hook configurado) que
  identifica `(empresa, proveedor)` y el motivo, **sin** exponer el token. La marca de
  "reconectar" sigue **sin tumbar** el poller de las demás empresas (se preserva el
  comportamiento de la Ola 4).

- **CA6 (aviso proactivo — SÓLO si se aprueba #2)** — Dado un refresh token de Google
  que está **por caducar** (o una app aún en Testing), Cuando el backend lo detecta,
  Entonces lo señala como **"por expirar"** y avisa **antes** del fallo, dándole al
  gestor la opción de reconectar proactivamente. *(Este CA queda **suspendido** hasta
  resolver la aclaración #2; si se descarta, no se implementa y no se añade estado
  nuevo.)*

- **CA7 (la detección no rompe nada ni cruza tenants)** — Dado cualquier estado de los
  conectores, Cuando corre la detección/observabilidad o se renderiza el mensaje,
  Entonces **no** se altera el comportamiento de ingesta/listado existente, **no** se
  exponen tokens, y un usuario/operador **no** ve datos de negocio de una empresa que
  no le corresponde (la RLS de `integraciones` —`int_empresa`— y los flujos de
  service-role ya existentes se respetan).

- **CA8 (tests sin servicios reales — OBLIGATORIO)** — Dado los tests de esta feature,
  Cuando corren, Entonces el **SDK de Anthropic**, la **API de Google** (Gmail/Drive,
  incluido el refresh) y la **API de ClickUp** están **mockeados**: no se hacen
  llamadas reales ni se usan credenciales reales; cualquier prueba de RLS corre contra
  una **DB de Supabase local**.

---

## 5. Consideraciones multi-tenant

- El estado del conector vive en `integraciones (empresa_id, proveedor, estado, …)`
  con la RLS **`int_empresa`** (`empresa_id = empresa_actual()`). El mensaje del panel
  y cualquier consulta de usuario salen **siempre** de la empresa del request (JWT);
  jamás de un estado global. Esta spec **no** debe reintroducir ninguna lectura global
  (precisamente el bug que la Ola 4 corrigió).
- **Observabilidad del operador (CA3):** listar "quién está en reconectar" cruza
  empresas por diseño, así que **no** puede ir por un endpoint de usuario con RLS de
  tenant. Debe ser un **canal de operador** (service-role / endpoint interno protegido,
  como `rutas/interno.py`), que exponga **solo** `(empresa_id, proveedor, estado,
  desde_cuándo)` — **nunca** tokens ni contenido de negocio. Ver aclaración #1 sobre
  el medio exacto (endpoint interno vs vista SQL vs métrica).
- **Tokens (regla de oro #3):** ninguna señal, log, alerta o respuesta de API puede
  incluir tokens (ni refresh ni access). Las alertas identifican la integración por
  `(empresa_id, proveedor)`, no por su secreto.
- **Flujos sin JWT:** la detección que corra en el poller/endpoint interno usa
  **service role** y `empresa_id` explícito, igual que la ingesta y el callback de
  OAuth actuales; no se infiere la empresa.
- **Si se añade el estado "por expirar" (#2):** la columna `estado` de `integraciones`
  tiene hoy un `CHECK (estado in ('conectado','reconectar'))` (migración 0002). Añadir
  un valor **exige una migración nueva** que amplíe el CHECK, en **español**, sin tocar
  la RLS (no agrega acceso). Se documenta como tarea de datos.

---

## 6. Aclaraciones pendientes

- **#1 — Medio de la observabilidad para el operador (CA3/CA5).** ¿Cómo prefiere el
  operador "enterarse"? Opciones: (a) **endpoint interno** `GET /interno/conectores/reconectar`
  (protegido por la credencial de servicio que ya usa `rutas/interno.py`) que liste
  `(empresa, proveedor, estado, desde)`; (b) una **vista SQL** de operador; (c) una
  **métrica/contador** que el operador ya scrapee. **Recomendación del arquitecto:**
  (a) el endpoint interno — es el patrón que ya existe (`interno.py`), es testeable
  end-to-end mockeando, y no añade infraestructura. [NECESITA ACLARACIÓN: ¿confirmas
  el endpoint interno, o prefieres vista/métrica?]

- **#2 — ¿Implementamos el aviso proactivo "por expirar" (CA6) o basta con la acción
  de raíz?** Una vez publicada la app de Google (CA1), los refresh tokens **dejan de
  caducar** y el goteo desaparece: el aviso proactivo pasa a ser **defensa en
  profundidad** (cubre el caso de que alguien revoque el acceso, o un futuro proyecto
  vuelva a quedar en Testing). Tiene costo: nuevo estado en BD (migración) + lógica de
  detección de "por caducar". **Recomendación del arquitecto:** **NO** implementarlo
  en esta spec — la acción humana (CA1) elimina la causa real; dejar CA6 como mejora
  futura y mantener el `estado` en `conectado | reconectar`. [NECESITA ACLARACIÓN:
  ¿de acuerdo con dejar CA6 fuera, o lo quieres dentro como red de seguridad?]

- **#3 — ¿Hasta dónde llega la "alerta" (CA5) en esta spec?** Propuesta: emitir un
  **log estructurado** (nivel `error`/`warning`, con `empresa_id`+`proveedor`+motivo,
  sin token) en el punto donde se marca `reconectar`, y dejar el reenvío a un canal
  final (correo/Slack) como *hook* que se conecta fuera de esta spec. **Recomendación:**
  log estructurado ahora; canal externo después. [NECESITA ACLARACIÓN: ¿basta el log
  estructurado + endpoint interno, o quieres ya un envío a un canal concreto?]

- **#4 — Acceso/propiedad de las consolas externas (bloquea CA1/CA2).** Publicar la app
  de Google requiere ser **propietario/editor** del proyecto de Google Cloud y, según
  scopes, puede gatillar **verificación de Google** (revisión que puede tardar días si
  los scopes se consideran sensibles — `gmail.readonly` suele serlo). [NECESITA
  ACLARACIÓN: ¿quién tiene acceso de propietario a la consola de Google Cloud y a la
  de ClickUp, y asumimos que la verificación de Google puede demorar?]
