# Plan 009 · ClickUp OAuth por empresa

- **Spec:** [spec.md](./spec.md) (borrador, aclaraciones resueltas)
- **Tipo:** full-stack (OAuth + backend + datos + frontend)
- **Decisión clave:** **espejar el OAuth de Gmail (Spec 002)**. Mismo mecanismo
  ya probado: `state` anti-CSRF ligado a la empresa, canje en el callback, token en
  `AlmacenSecretos` (Secret Manager), fila en `integraciones` por `empresa_id`, RLS
  `int_empresa`. NO se inventa una barrera nueva: se reutiliza la de Gmail. El cambio
  central es que **`obtener_cliente_clickup` deja de usar el token global** y resuelve
  el token **de la empresa del request**.

> Regla #3: el token de ClickUp vive SOLO en el backend (Secret Manager); jamás viaja
> al front (CA5). Esta feature **no** llama al LLM (es OAuth + datos), así que la
> Regla #4 de enrutar modelos no aplica.

---

## 1. Arquitectura (capas que toca)

- **Backend (FastAPI):**
  - Nuevos endpoints del conector ClickUp en `rutas/clickup.py`, **espejo** de los de
    Gmail en `rutas/integraciones.py`: iniciar OAuth, callback, estado por-empresa,
    desconectar.
  - Servicio `servicios/oauth_clickup.py` (espejo de `oauth_gmail.py`):
    `construir_url_consentimiento(config, state)` + `canjear_codigo(code)` → access token.
  - `obtener_cliente_clickup` (en `dependencias.py`): pasa de **token global** a
    **resolver el token de la integración `clickup` de la empresa** (token_ref →
    `AlmacenSecretos`). Sin integración → `ClienteClickUp("")` → `[]` (CA1/CA3).
  - **Reutiliza tal cual:** `AlmacenSecretos` (`secretos.py`), el almacén de estado
    OAuth (`estado_oauth`), el repo de `integraciones` (versión usuario y servicio),
    y `ClienteClickUp` (`clickup_real.py`).
- **Datos (Supabase):** **SIN migración nueva** — `integraciones` ya admite
  `proveedor='clickup'` y la RLS `int_empresa` ya aísla por empresa. Solo **filas nuevas**.
- **Frontend (Vite/React):** la tarjeta "Gestor de tareas · ClickUp" del panel de
  Conectores pasa de *"(OAuth próximamente)"* a flujo real **Conectar / Cambiar / Sin
  conectar**, espejo de la tarjeta de Gmail. El estado sale del endpoint **por-empresa**.
- **LLM:** N/A.

---

## 2. Contratos de API (en `rutas/clickup.py`)

| Método · ruta | Request | Response | Errores |
|---|---|---|---|
| `POST /clickup/iniciar` | — (empresa del JWT) | `200 {url}` (consentimiento ClickUp) | 401 sin auth |
| `GET /clickup/callback` | `?code&state` | `302` redirect al front | `400` state inválido/expirado |
| `GET /clickup/estado` | — | `200 {proveedor, estado}` (por **existencia** de la integración; sin integración → null = "Sin conectar") | 401 |
| `GET /clickup/listas` *(existe)* | — | `200 [{id,nombre,espacio}]` con el token **per-empresa**; sin token → `[]` | `502` ClickUp caído |
| `DELETE /clickup` | — | `204` (borra secreto + fila; idempotente) | 401 |
| `POST /solicitudes/{id}/tareas/clickup` *(existe)* | … | usa el token **per-empresa** | `502` |

- **iniciar:** genera `state` anti-CSRF, `almacen_estado_oauth.guardar(state, empresa_id)`,
  devuelve la URL de consentimiento de ClickUp (con `client_id` + `redirect_uri` + `state`).
- **callback (igual que Gmail):** valida `state` → `empresa_id` (consumir); canjea `code`
  → access token; `secretos.guardar("clickup-token-{empresa_id}", token)`; upsert fila
  `integraciones` (`empresa_id`, `proveedor='clickup'`, `token_ref`, `casilla`=workspace,
  `estado='conectado'`). Es un **redirect del navegador sin JWT** → repo de **service
  role** con `empresa_id` **EXPLÍCITO** del `state` (jamás inferido — no cruzar tenants).
- **estado vs listas (aclaración #5):** "Conectado" = existe la integración (barato);
  el conteo de listas es una llamada viva **aparte** (`/clickup/listas`); si falla → el
  panel muestra **"Reconectar"** (CA6) sin romperse.

---

## 3. Datos

- **Sin migración:** `integraciones (empresa_id, proveedor, token_ref, casilla, estado,
  cursor)` + `unique(empresa_id, proveedor)` + RLS `int_empresa` (`empresa_id =
  empresa_actual()`) ya soportan clickup.
- **Repo `integraciones` — un cambio:** hace falta un getter **por proveedor**
  `obtener_por_empresa_y_proveedor(empresa_id, 'clickup')` (hoy `obtener_por_empresa`
  asume una sola integración; una empresa puede tener **gmail Y clickup**). Igual en el
  repo de servicio. El upsert/eliminar también filtran por proveedor.
- **Token:** `token_ref = clickup-token-{empresa_id}` en `AlmacenSecretos` (Secret
  Manager en prod, archivo en local). El access token (largo, sin refresh) se guarda tal cual.
- **Puente Capsulab (aclaración #2):** snippet de provisión (como el de 008) que crea la
  integración clickup de **Capsulab** a partir del `CLICKUP_API_TOKEN` actual: guarda el
  token como secreto `clickup-token-{capsulab}` + inserta la fila `integraciones`. Así
  Capsulab queda "Conectado" con **su** token y el resto parte "Sin conectar"; el env
  global sale del flujo por-empresa (queda solo como fallback de migración).
- **RLS = la barrera (CA4):** la integración clickup de A no es visible/usable por B. El
  callback (sin JWT) escribe con **service role + `empresa_id` explícito** del `state`.

---

## 4. Servicios

- **`servicios/oauth_clickup.py`** (espejo de `oauth_gmail.py`):
  `ConfigOAuthClickUp(client_id, client_secret, redirect_uri)`;
  `construir_url_consentimiento(config, state)` (consent en `app.clickup.com/api?...`);
  `ClienteOAuthClickUp.canjear_codigo(code)` → `{access_token, workspace?}` (POST a
  `api.clickup.com/api/v2/oauth/token`). **Sin refresh token** (access largo).
- **`ClienteClickUp`** (`clickup_real.py`): ya tiene `tiene_token` / `listar_listas` /
  `crear_tarea`; se construye con el token **per-empresa**.
- **`obtener_cliente_clickup` (async)**: `repo.obtener_por_empresa_y_proveedor(empresa_id,
  'clickup')` → `secretos.obtener(token_ref)` → `ClienteClickUp(token)`. Sin integración →
  `ClienteClickUp("")` (`tiene_token=False`).

---

## 5. Estrategia de pruebas (TDD)

**Todo sin servicios reales (CA8):** el **canje OAuth de ClickUp** y la **API de ClickUp**
se **mockean** (dobles en memoria); cero credenciales reales. RLS contra **Supabase local**.

- **Backend (pytest):**
  - `iniciar`: genera `state`, lo liga a la empresa, devuelve URL (mock estado_oauth).
  - `callback`: valida `state` → empresa; canjea `code` (mock `ClienteOAuthClickUp`);
    guarda secreto + upsert integración con `empresa_id` **del state**; redirige. `state`
    inválido → `400`. (CA2)
  - `estado`: con/sin integración clickup → conectado/"Sin conectar" (CA1). El token
    **nunca** en la respuesta (CA5, garantizado por `response_model`).
  - `obtener_cliente_clickup`: resuelve el token **de la empresa**; sin integración →
    `tiene_token=False` → `listas=[]` (CA3); el token de A **nunca** se usa para B (CA4).
  - `listas` / `crear-tarea`: usan el token per-empresa (doble); token inválido / ClickUp
    caído → `502` y panel "Reconectar" (CA6).
  - `desconectar`: borra secreto + fila; idempotente (CA7).
- **RLS (pgTAP)** — `supabase/tests/rls_clickup_oauth.test.sql` (o extender
  `rls_integraciones`): empresa A con integración clickup, B sin; A ve/usa la suya, B
  **no** ve la de A (CA4). RukkumansLabs sin clickup → "Sin conectar" aunque Capsulab esté
  conectada.
- **Frontend (vitest):** la tarjeta ClickUp muestra **Sin conectar / Conectado /
  Reconectar** según el estado per-empresa (mock fetch); "Conectar" dispara `iniciar`
  (abre la URL); "Cambiar" desconecta. El token **jamás** aparece (CA5).
- **Dobles obligatorios:** `ClienteOAuthClickUp` + `ClienteClickUp` + `AlmacenSecretos`
  en memoria (igual que los de Gmail).

---

## 6. Riesgos / decisiones abiertas

- **Detalles del OAuth de ClickUp** (URL exacta del token, formato de respuesta, si pide
  scopes): **confirmar contra la doc de ClickUp al implementar**. Las aclaraciones #3/#4 se
  resolvieron con el comportamiento esperado (grant por defecto; token largo sin refresh);
  si difiere, se ajusta `oauth_clickup` sin tocar el resto.
- **`obtener_cliente_clickup` pasa de sync a async** (cambia su firma + los endpoints que
  lo inyectan). Los tests existentes que lo sobrescriben por dependencia siguen valiendo;
  hay que adaptar el doble a la nueva firma.
- **Puente de Capsulab:** usa el token global como su token propio. Si ese ClickUp no es
  realmente "de Capsulab", se reconecta por OAuth después (limpio). El puente **no**
  reintroduce el leak (cada empresa su token).
- **Reconectar (CA6):** sin refresh token, "Reconectar" se dispara por **401** de ClickUp
  (revocado); al detectarlo en una operación se marca `estado='reconectar'`.
- **Definición de Terminado (CLAUDE.md §7):** spec+plan+tareas; tests por capa **antes**
  del código; RLS verificada (A no usa el ClickUp de B); sin token al front ni secretos al
  repo; commits en español.

---

Siguiente paso: **`/tareas 009`**.
