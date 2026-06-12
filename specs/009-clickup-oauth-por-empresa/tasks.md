# Tareas 009 · ClickUp OAuth por empresa

Orden TDD: cada tarea escribe **el test primero (rojo)**, luego el mínimo (verde),
luego refactor. Pequeñas, commit por tarea (en español).

> **Todo mockea ClickUp + el canje OAuth (CA8):** cero red, cero credenciales reales.
> RLS contra Supabase local. **Frontera humano/agente:** registrar/configurar las
> credenciales de la app OAuth de ClickUp es **paso humano (T11)** y bloquea solo el
> flujo EN VIVO (T13), **no** el código+tests.

---

## Backend (código + tests — todo mockeado)

- [ ] **T1 · Repo: `obtener_por_empresa_y_proveedor(empresa_id, proveedor)`**
  - 🔴 test (memoria + supabase mock): devuelve la integración del proveedor pedido; una
    empresa con **gmail Y clickup** no las confunde; sin esa integración → `None`.
  - 🟢 método en el repo (versión usuario y servicio). No toca RLS.

- [ ] **T2 · Fix del leak: `obtener_cliente_clickup` resuelve el token PER-EMPRESA (CA3/CA4)**
  - 🔴 test: con integración clickup → `ClienteClickUp` con el token (de `AlmacenSecretos`);
    sin integración → `tiene_token=False` → `/clickup/listas` = `[]`; el token de A **jamás**
    se usa para B.
  - 🟢 cambiar la dependencia (async) para resolver el `token_ref` de la integración clickup
    de la empresa, en vez del `CLICKUP_API_TOKEN` global. **Esto ya corta el leak.**

- [ ] **T3 · Servicio `oauth_clickup` (CA2)**
  - 🔴 test: `construir_url_consentimiento` lleva client_id/redirect/state;
    `ClienteOAuthClickUp.canjear_codigo` (doble) → `access_token`. Sin red.
  - 🟢 `servicios/oauth_clickup.py` (espejo de `oauth_gmail.py`) + doble para tests.

- [ ] **T4 · POST /clickup/iniciar (CA2)**
  - 🔴 test: genera `state`, lo liga a la empresa (mock estado_oauth), devuelve `{url}`.
  - 🟢 endpoint en `rutas/clickup.py`.

- [ ] **T5 · GET /clickup/callback (CA2/CA5)**
  - 🔴 test: `state` válido → canjea `code` (mock) → guarda secreto `clickup-token-{empresa}`
    + upsert integración con `empresa_id` **DEL STATE** → 302; `state` inválido → 400; el
    token **NUNCA** en la respuesta.
  - 🟢 endpoint (service role, `empresa_id` explícito del state — no inferir).

- [ ] **T6 · GET /clickup/estado (CA1/CA5)**
  - 🔴 test: con integración clickup → `{proveedor, estado=conectado}`; sin → `estado=null`
    ("Sin conectar"); el token nunca viaja (response_model).
  - 🟢 endpoint.

- [ ] **T7 · DELETE /clickup — desconectar (CA7)**
  - 🔴 test: borra el secreto + la fila clickup de la empresa; idempotente (sin fila → 204).
  - 🟢 endpoint.

- [ ] **T8 · Config: creds OAuth de ClickUp en `Settings`**
  - 🔴 test: `Settings` carga `clickup_client_id` / `clickup_client_secret` /
    `clickup_redirect_uri` (vacíos en test, sin valores reales).
  - 🟢 campos en `config.py` + `ConfigOAuthClickUp` desde `Settings`.

## Datos / RLS

- [ ] **T9 · RLS pgTAP: aislamiento de la integración clickup (CA4)**
  - 🔴 `supabase/tests/rls_clickup_oauth.test.sql`: empresa A con integración clickup, B sin;
    A ve/usa la suya, B **NO** ve la de A (count 0); RukkumansLabs (`…d1`) sin clickup →
    "sin conectar" aunque Capsulab (`…c1`) conectada. Verificar **rojo** primero.
  - 🟢 no se tocan políticas (`int_empresa` ya existe); el test prueba la barrera con clickup.

## Frontend

- [ ] **T10 · Tarjeta ClickUp real — Conectar / Cambiar / Sin conectar (CA1/CA5/CA6)**
  - 🔴 test (vitest): la tarjeta muestra **Sin conectar / Conectado / Reconectar** según el
    estado per-empresa (mock fetch); "Conectar" dispara `iniciar` (abre la URL); "Cambiar"
    desconecta; el token **jamás** aparece.
  - 🟢 cliente `api/clickup` (estado/iniciar/desconectar) + la tarjeta en `Configuracion`
    (espejo de la de Gmail). Más: el backend marca `estado='reconectar'` ante un 401 de
    ClickUp (CA6).

## Provisión a producción (cruza la frontera humano/agente)

- [ ] **T11 · 🧑 PASO HUMANO (bloquea el VIVO) — creds de la app OAuth de ClickUp**
  - El **humano** configura `client_id` / `client_secret` / `redirect_uri` de la app OAuth de
    ClickUp en el env del backend / Secret Manager. `redirect_uri` = `…/api/clickup/callback`
    (se da exacta al implementar). El agente **no** registra apps OAuth ni maneja secretos
    reales. **Bloquea T13.**

- [ ] **T12 · Puente Capsulab — su integración clickup desde el token global (🔒 dep. T2/T5)**
  - snippet de provisión: guardar el `CLICKUP_API_TOKEN` actual como secreto
    `clickup-token-{capsulab}` + insertar fila `integraciones` (capsulab, clickup, token_ref,
    `estado=conectado`). Retirar el global del flujo per-empresa. Así Capsulab no se cae y no
    hay leak (cada empresa su token).

- [ ] **T13 · 🔒 Verde total + deploy + verificación EN VIVO (dep. T11)**
  - suite backend + front + pgTAP verdes; deploy; con las creds del paso humano:
    RukkumansLabs "sin conectar", Capsulab "conectado" con **su** token, y un usuario de A
    **jamás** ve/usa el ClickUp de B. Chequeo operacional (la garantía automatizada ya está
    en T2/T9).

---

Leyenda: 🧑 paso humano · 🔒 bloqueada por el paso humano.

Cobertura de CAs: **CA1**→T6/T10 · **CA2**→T3/T4/T5 · **CA3**→T2 · **CA4**→T2/T9 ·
**CA5**→T5/T6/T10 · **CA6**→T10 (+ detección 401 en backend) · **CA7**→T7 · **CA8**→todos
los tests mockean ClickUp + el canje OAuth.

Siguiente paso: **`/implementar 009`**.
