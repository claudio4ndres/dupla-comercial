# Plan 010 · Estabilizar los tokens OAuth — fin del "reconectar" recurrente

- **Spec:** [spec.md](./spec.md) (borrador — tiene `[NECESITA ACLARACIÓN]` #1–#4)
- **Tipo:** integración (OAuth) · operación/infra · backend · frontend (mensajería) ·
  datos (sólo si se aprueba el estado "por expirar", #2)
- **Decisión clave — separar dos planos que NO se mezclan:**
  1. **🧑 Acción HUMANA en consolas externas (la cura de raíz).** Publicar/verificar la
     app OAuth de **Google** (Gmail+Drive) a "In production" → los refresh tokens dejan
     de caducar a los 7 días. Revisar/publicar la de **ClickUp** (higiene). **El agente
     NO entra a consolas, NO registra apps, NO maneja secretos reales.** Esto es lo que
     de verdad termina el goteo; el código **no puede** sustituirlo.
  2. **🤖 Mejoras de CÓDIGO (defensa + diagnóstico), con TDD.** Detección/observabilidad
     del "reconectar", mejor mensaje por proveedor en el panel, y alerta al operador
     cuando una empresa cae. Reduce el daño y el tiempo-a-enterarse **mientras** la
     acción humana se ejecuta, y deja red de seguridad para el futuro.

> **Reglas de oro aplicadas:** los tokens viven SÓLO en el backend / Secret Manager y
> **jamás** salen por ninguna señal/respuesta/log (regla #3, CA5/CA7). Esta feature
> **no llama al LLM** (es OAuth + observabilidad), así que la regla #4 (enrutar modelos)
> no aplica. BD y mensajes en **español** (regla #1/#6).

> **⚠️ Bloqueo de planificación:** la spec tiene aclaraciones abiertas (#1 medio de
> observabilidad, #2 si va el aviso proactivo, #3 alcance de la alerta, #4 acceso a
> consolas). Este plan deja la arquitectura **lista para ambas ramas** y marca qué
> tareas quedan **suspendidas** hasta resolverlas. **No se implementa** hasta tener el
> visto bueno de #1–#3 (el #4 sólo bloquea las tareas humanas CA1/CA2).

---

## 0. Diagnóstico técnico (qué encontré en el código — base del plan)

Recorrido read-only del OAuth actual, para que el plan se ancle en lo que ya existe:

- **Google (Gmail + Drive) SÍ usa refresh token.**
  `servicios/oauth_gmail.py::construir_url_consentimiento` ya pide
  `access_type=offline` + `prompt=consent` (correcto para obtener refresh token), con
  scopes `gmail.readonly` + `drive.readonly`. El refresh→access vive en
  `servicios/gmail_real.py::_access_token` y `servicios/drive_real.py` (grant
  `refresh_token` a `https://oauth2.googleapis.com/token`). Si el refresh falla
  (caducado/revocado) lanzan `ErrorAutenticacionGmail`.
  → **Como la app está en Testing y los scopes NO son el subconjunto exento
  {nombre,email,perfil}, el refresh token caduca a los 7 días.** El código está bien;
  **la configuración de la consola es la raíz.**
- **El "reconectar" se marca en dos sitios (sólo proveedor `gmail`):**
  `servicios/ingesta_correo.py` (al fallar `gmail.listar_nuevos` con
  `ErrorAutenticacionGmail` → `marcar_estado(empresa, "reconectar", "gmail")`) y
  `rutas/interno.py` (mismo patrón en el poll interno). **Aquí van los puntos de
  alerta (CA5).** Ya preservan el aislamiento por proveedor (#5 de la Ola 4) y no
  tumban el poller de las demás empresas.
- **ClickUp NO usa refresh y su token NO caduca** (confirmado vs doc oficial y
  coherente con `servicios/oauth_clickup.py`, que sólo guarda `access_token`). El
  "reconectar" de ClickUp se daría por 401/revocación; hay **auto-heal** en
  `rutas/clickup.py::listar_listas` (un `/listas` OK restaura "conectado").
- **El estado es enum acotado:** `integraciones.estado CHECK (estado in
  ('conectado','reconectar'))` (migración `0002_conexion_correo.sql`), reflejado en
  `repositorios/integraciones.py` y `esquemas.py`. **Añadir "por expirar" exige
  migración** (sólo si se aprueba #2).
- **Ya existe un canal de operador:** `rutas/interno.py` está protegido por una
  **credencial de servicio** (header) y corre con service-role. Es el lugar natural
  para el endpoint de observabilidad (CA3) sin romper la RLS de tenant.

**Conclusión del diagnóstico:** el código de OAuth es correcto; el goteo lo causa el
**modo Testing de la app de Google** (acción humana). El trabajo de código es
**diagnóstico + UX + alerta**, no arreglar el flujo OAuth.

---

## 1. Plano HUMANO (🧑) — la cura de raíz (sin código)

> El agente **documenta y verifica resultados**; **no** ejecuta acciones en consolas.

### 1.1 Google Cloud Console — publicar la app OAuth (resuelve CA1)
1. Google Cloud Console → proyecto de Dupla → **APIs & Services → OAuth consent screen**.
2. Confirmar **User type = External** y **Publishing status = Testing** (estado actual).
3. Pulsar **PUBLISH APP** → pasar a **In production**.
4. Si Google pide **verificación** (probable con `gmail.readonly`, scope sensible):
   completar el formulario (dominio, justificación de scopes, video si lo piden).
   ⚠️ La verificación puede **tardar días/semanas**; mientras tanto la app puede
   funcionar "In production · unverified" con la pantalla de "app no verificada"
   (aceptable para el piloto). [Depende de #4 — acceso/propiedad.]
5. **Verificación de resultado (CA1):** reconectar una empresa de prueba y confirmar
   que la conexión **supera 7 días** sin caer a "reconectar" (antes caía ~día 7).

### 1.2 ClickUp — revisar/publicar la app OAuth (resuelve CA2, higiene)
1. ClickUp → Settings → **Integrations / Apps** (consola de apps OAuth) → app de Dupla.
2. Revisar estado de publicación / visibilidad y dejarla en el estado deseado.
3. **Dejar constancia** (en el propio `tasks.md`) de que esto **no** cambia la
   expiración del token de ClickUp (no caduca); sólo afecta la fricción del consentimiento.

**Frontera dura:** estas dos tareas son **🧑 humanas**. Bloquean CA1/CA2 y dependen de
#4 (acceso a consolas), pero **NO** bloquean el trabajo de código (§2), que se puede
hacer y testear en paralelo.

---

## 2. Plano CÓDIGO (🤖) — arquitectura por capa (con TDD)

> Todo lo de abajo se entrega con tests **mockeando** Google/ClickUp/Anthropic (CA8).
> El alcance final depende de #1–#3; aquí va el diseño de cada pieza.

### 2.1 Backend — alerta al marcar "reconectar" (CA5) · **base, no depende de aclaraciones**
- **Dónde:** los dos puntos que hoy marcan `reconectar`:
  `servicios/ingesta_correo.py` y `rutas/interno.py`.
- **Qué:** al marcar `reconectar`, emitir **una señal estructurada para el operador**:
  un log con nivel adecuado (`warning`/`error`) que incluya `empresa_id`, `proveedor`
  y el **motivo** (`auth_invalida`), **sin token alguno**. Encapsular la emisión en un
  punto único reutilizable (p.ej. una función `avisar_reconectar(empresa_id, proveedor,
  motivo)` en un módulo de observabilidad) para que ambos sitios la llamen y el test la
  verifique en un solo lugar.
- **Invariantes a preservar:** marcar `reconectar` **no** tumba el poller de las demás
  empresas (Ola 4); la alerta es *best-effort* (si el canal falla, no rompe la ingesta).
- **Hook externo (#3):** la función deja un punto de extensión para reenviar a un canal
  (correo/Slack) **sin** que esta spec lo cablee. Por defecto: sólo log.

### 2.2 Backend — observabilidad para el operador (CA3) · **depende de #1**
- **Opción recomendada (a):** endpoint interno
  `GET /interno/conectores/reconectar` en `rutas/interno.py` (mismo guard de credencial
  de servicio que ya usa ese router), que devuelva la lista de integraciones en
  `estado='reconectar'`: `[{empresa_id, proveedor, estado, desde?}]`.
  - **`desde` (desde cuándo está en reconectar):** sólo si lo tenemos barato. Hoy
    `integraciones` no guarda "cuándo cambió el estado". Si se quiere el `desde`,
    **migración** que añada `estado_desde timestamptz` (en español, sin tocar RLS) y
    setearlo al `marcar_estado`. **Recomendación:** entregar primero **sin `desde`**
    (lista de quién está caído) y dejar `estado_desde` como mejora opcional, para no
    arrastrar una migración a la primera versión. [Atado a #1.]
  - **Repo:** nuevo método `listar_por_estado(estado)` en `RepositorioIntegraciones`
    (versión memoria para tests + versión servicio/Supabase). Service-role; no aplica
    RLS de tenant (es canal de operador), pero **sólo** devuelve `(empresa_id,
    proveedor, estado[, estado_desde])` — **nunca** `token_ref` ni datos de negocio.
- **Opción (b) vista SQL / (c) métrica:** si #1 las prefiere, se ajusta sin cambiar el
  resto; el endpoint es lo más testeable end-to-end.

### 2.3 Frontend — mensaje específico por proveedor en el panel (CA4) · **no depende de aclaraciones**
- **Dónde:** la tarjeta del conector en `componentes/Configuracion.tsx` (tarjetas de
  Gmail y de ClickUp), que ya consumen `GET /integraciones/correo` y `GET /clickup/estado`.
- **Qué:** cuando `estado === 'reconectar'`, en vez de un rótulo genérico, mostrar un
  texto **por proveedor**:
  - Google/Gmail: *"La conexión con Google expiró. Vuelve a conectar para seguir
    leyendo tu correo y tu Drive."*
  - ClickUp: *"ClickUp se desconectó. Vuelve a conectar para crear tareas."*
- El estado sigue saliendo de la integración de **esa** empresa (no global). **No** se
  añade ningún campo nuevo en la respuesta (el `estado` ya viaja); el texto es
  responsabilidad del front (i18n/strings en español). Token **jamás** en el front (CA5).

### 2.4 Datos — estado "por expirar" (CA6) · **SUSPENDIDO hasta #2**
- **Sólo si #2 = "sí, implementarlo".** Migración nueva en `supabase/migrations/`
  (siguiente correlativo, p.ej. `0010_estado_conector_por_expirar.sql`) que amplíe el
  CHECK a `('conectado','reconectar','por_expirar')`, en **español**, **sin** tocar la
  RLS (no agrega acceso). Más la lógica que detecte "refresh por caducar / app en
  Testing" y marque `por_expirar`. **Recomendación del plan:** **no** hacerlo (la
  acción humana CA1 elimina la causa). Queda como mejora futura; si se descarta, el
  `estado` se mantiene en `conectado | reconectar` y CA6 no se implementa.

### 2.5 LLM · N/A
- Esta feature no llama a Claude. No hay enrutado de modelos ni prompt caching.

---

## 3. Contratos de API (sólo lo que esta spec añade)

| Método · ruta | Auth | Request | Response | Errores |
|---|---|---|---|---|
| `GET /interno/conectores/reconectar` *(nuevo, #1·CA3)* | credencial de **servicio** (header, como el resto de `/interno`) | — | `200 [{empresa_id, proveedor, estado, estado_desde?}]` — **sin tokens** | `403` credencial inválida |

- **No** se modifican los contratos existentes de `/integraciones/correo`, `/clickup/estado`,
  `/clickup/listas` ni los callbacks OAuth: el mensaje del panel (CA4) usa el `estado`
  que esos endpoints **ya** devuelven.
- Si #1 elige vista SQL o métrica en lugar del endpoint, esta fila se reemplaza por la
  definición de la vista/serie correspondiente.

---

## 4. Datos

- **Por defecto: SIN migración.** CA3 (lista de "quién está en reconectar") se resuelve
  leyendo el `estado` actual de `integraciones` vía `listar_por_estado`. CA4/CA5 no
  tocan el esquema.
- **Migración SÓLO si:** (a) se aprueba el estado "por expirar" (#2) → ampliar el CHECK
  de `estado`; y/o (b) se quiere `estado_desde` para el "desde cuándo" del CA3 → añadir
  `estado_desde timestamptz` y setearlo en `marcar_estado`. Ambas, de hacerse, van en
  **español**, **sin** modificar la RLS `int_empresa`, con su test pgTAP de que no
  cambia el aislamiento.
- **RLS:** intacta. El endpoint de operador (CA3) corre **fuera** de la RLS de tenant
  (service-role, canal interno) y por eso devuelve **sólo** estado del conector, nunca
  datos de negocio ni tokens.

---

## 5. Estrategia de pruebas (TDD)

**Todo sin servicios reales (CA8):** Google (incluido el refresh), ClickUp y Anthropic
**mockeados**; cualquier prueba de RLS contra **Supabase local**.

- **Backend (pytest):**
  - **Alerta al marcar "reconectar" (CA5):** simular `ErrorAutenticacionGmail` en la
    ingesta (doble de `ClienteGmail`) → assert que (1) la integración queda
    `reconectar`, (2) se **emitió la alerta** con `empresa_id`+`proveedor`+motivo y
    **sin token** (capturar logs / espiar el hook), y (3) el poller **no** se cae y
    sigue con las demás empresas. Repetir el assert de alerta para el camino de
    `rutas/interno.py`.
  - **Observabilidad (CA3):** con varias integraciones (algunas `conectado`, otras
    `reconectar`, mezclando proveedores y empresas), `GET /interno/conectores/reconectar`
    con la credencial de servicio → devuelve **sólo** las `reconectar` con
    `(empresa_id, proveedor, estado[, estado_desde])` y **ningún** `token_ref`; sin
    credencial → `403`. Test del repo `listar_por_estado` (memoria) por separado.
  - **No-regresión (CA7):** los tests existentes de ingesta/listas/estado siguen verdes
    (la alerta y el endpoint no cambian su comportamiento observable).
  - **Estado "por expirar" (CA6):** **sólo si #2 lo aprueba** — test de la detección de
    "por caducar" y del nuevo valor de estado; si no, este bloque no existe.
- **Frontend (vitest + Testing Library):**
  - **Mensaje por proveedor (CA4):** render de la tarjeta con `estado='reconectar'`
    (mock `fetch`) → aparece el **texto específico** de Google en la de Gmail y el de
    ClickUp en la de ClickUp; con `estado='conectado'` no aparece. El token **jamás**
    figura en el DOM/props (CA5).
- **RLS / datos:** si se añade `estado_desde` o `por_expirar`, **pgTAP** que confirme
  que la RLS `int_empresa` **no** cambió (A no ve la integración de B) y que el CHECK
  acepta el nuevo valor.
- **Acción humana (CA1/CA2):** **no** tiene test unitario. Verificación operativa:
  checklist de §1 + observar en producción que una conexión supera 7 días tras publicar.
  Se documenta como criterio de aceptación operacional en `tasks.md`.
- **Dobles obligatorios:** `ClienteGmail` (que lanza `ErrorAutenticacionGmail`),
  captura de logs/hook de alerta, repo de `integraciones` en memoria. Cero red, cero
  credenciales reales.

---

## 6. Riesgos / decisiones abiertas

- **(Bloqueante) Aclaraciones #1–#3 sin resolver:** definen *qué* código se construye
  (endpoint vs vista/métrica; con/sin aviso proactivo; alcance de la alerta). **No se
  implementa** hasta cerrarlas. #4 sólo bloquea las tareas humanas.
- **Verificación de Google puede demorar (#4):** publicar a "In production" con
  `gmail.readonly` puede gatillar revisión de Google (días/semanas). Mientras tanto, la
  app puede operar "in production · unverified". Esto **no** bloquea el código, pero sí
  el cierre operativo de CA1. Riesgo de calendario, no técnico.
- **El código NO sustituye la acción humana:** sin publicar la app de Google, el goteo
  de 7 días **persiste** por más alertas/mensajes que pongamos. Hay que ser honesto con
  el usuario: la mejora de código **reduce el daño y avisa**, pero **la cura es la
  consola**. (Por eso CA1 es el criterio primario.)
- **"Desde cuándo" (CA3) cuesta una migración:** entregar primero sin `estado_desde`
  evita arrastrarla; añadirla después es incremental.
- **Falsos positivos de alerta:** el punto de `interno.py` ya distingue
  `ErrorAutenticacionGmail` (credenciales rotas → alerta legítima) de fallos de
  infraestructura (no deben pedir reconexión). La alerta se ata **sólo** al primer caso,
  para no spamear al operador por caídas de red.
- **Definición de Terminado (CLAUDE.md §7):** spec+plan+tareas; tests por capa **antes**
  del código (los de código); RLS verificada si se toca el esquema; **sin** tokens en
  logs/alertas/respuestas/front; commits en español. Las tareas 🧑 se cierran por
  verificación operativa, no por test.

---

Siguiente paso: **resolver las aclaraciones #1–#3** (y #4 para las tareas humanas) y
luego **`/tareas 010`**.
