# Tareas 010 · Estabilizar los tokens OAuth — fin del "reconectar" recurrente

Orden TDD: cada tarea de código escribe **el test primero (rojo)**, luego el mínimo
código (verde), luego refactor. Tareas pequeñas, commit por tarea (en español).

## Leyenda

- 🧑 = **acción humana** (consolas externas / verificación operativa). El agente
  **documenta**, NO ejecuta. No tiene test unitario; se cierra por observación.
- 🤖 = **código** (con TDD, mockeando Google/ClickUp/Anthropic — CA8).
- **AHORA** = backend de esta ola.
- **DIFERIDO · Kiro** = frontend (CA4); lo edita Kiro en `apps/web`. **No** se toca aquí.

## Decisiones del Gerente TI (cierran las aclaraciones de la spec)

- **#1 (medio de observabilidad, CA3)** → **endpoint interno** (opción a):
  `GET /interno/conectores/reconectar`, protegido por `verificar_credencial_servicio`.
- **#2 (estado proactivo "por_expirar", CA6)** → **NO se implementa**. El `estado` se
  mantiene en `conectado | reconectar`. **SIN migración.** CA6 queda fuera de esta ola.
- **#3 (alcance de la alerta, CA5)** → **log estructurado** ahora (nivel `warning`, con
  `empresa_id`+`proveedor`+`motivo`, **sin token**). Sin canal externo (correo/Slack).
- **CA4 (mensaje por proveedor en el panel)** → **DIFERIDO · Kiro** (edita
  `Configuracion.tsx`). No se hace en esta ola de backend.

---

## A. Acción humana — la cura de raíz (🧑 · sin código, sin test)

> Bloquean CA1/CA2 y dependen del acceso a consolas (#4). **NO** bloquean el código de
> §B/§C, que se hace y testea en paralelo. El agente sólo deja el checklist; la ejecución
> y la verificación las hace el operador.

- [ ] **T1 · 🧑 Publicar la app OAuth de Google a "In production" (resuelve CA1).**
  Google Cloud Console → proyecto de Dupla → **APIs & Services → OAuth consent screen**:
  1. Confirmar **User type = External** y **Publishing status = Testing** (estado actual).
  2. **PUBLISH APP** → pasar a **In production**.
  3. Si Google pide **verificación** (probable con `gmail.readonly`, scope sensible):
     completar el formulario (dominio, justificación de scopes, video si lo piden).
     ⚠️ Puede tardar días/semanas; mientras tanto la app opera "In production · unverified"
     (aceptable para el piloto).
  - **Verificación de resultado (CA1, operativa):** reconectar una empresa de prueba y
    confirmar que la conexión **supera 7 días** sin caer a "reconectar". (Antes caía ~día 7
    porque en modo Testing el refresh token de Google caduca a los 7 días con scopes fuera
    del subconjunto {nombre, email, perfil}.)
  - **Bloqueado por #4:** requiere ser propietario/editor del proyecto de Google Cloud.

- [ ] **T2 · 🧑 Revisar/publicar la app OAuth de ClickUp (resuelve CA2 — higiene).**
  ClickUp → Settings → **Integrations / Apps** → app de Dupla: revisar estado de
  publicación/visibilidad y dejarla en el estado deseado.
  - **Constancia explícita (CA2):** esto **NO** cambia la expiración del token de ClickUp.
    La doc oficial dice *"The access token currently does not expire"* y ClickUp **no**
    entrega refresh token. Por lo tanto un "reconectar" de ClickUp sólo puede venir de
    **revocación/401**, **nunca** de expiración. Sólo reduce fricción del consentimiento.

---

## B. Backend — CA5: alerta al marcar "reconectar" (🤖 · AHORA · no depende de aclaraciones)

> Un único punto reutilizable que ambos sitios (ingesta + poller) llaman; el test lo
> verifica en un solo lugar. **Best-effort:** si la alerta falla, NO rompe la ingesta.

- [x] **T3 · 🤖 Módulo de observabilidad: `avisar_reconectar(empresa_id, proveedor, motivo)`.**
  Nuevo `app/servicios/observabilidad.py` con la función que emite un **log estructurado**
  (nivel `warning`) con `empresa_id`, `proveedor` y `motivo`, **sin token alguno** (regla de
  oro #3). Best-effort: si el logging revienta, **traga** la excepción (no propaga) para no
  tumbar a quien la llama.
  - **Test (rojo→verde):** `caplog` captura un `warning` que contiene `empresa_id`,
    `proveedor` y `motivo`; el record **no** contiene ningún token/`token_ref`. Si se fuerza
    un fallo del logger, `avisar_reconectar` **no** lanza.

- [x] **T4 · 🤖 Emitir la alerta en la INGESTA (`servicios/ingesta_correo.py`).**
  En el `except ErrorAutenticacionGmail` (donde ya se marca `reconectar`), llamar a
  `avisar_reconectar(empresa_id, "gmail", "auth_invalida")` **antes/después** de
  `marcar_estado`, sin cambiar el comportamiento observable (sigue devolviendo
  `estado="reconectar"`, no lanza, no avanza cursor).
  - **Test (rojo→verde):** simular `ErrorAutenticacionGmail` (doble `ClienteGmailQueFallaAuth`)
    → la integración queda `reconectar`, **se emitió** la alerta con `empresa_id`+`gmail`+
    `motivo` y **sin token**, y la ingesta **no** lanzó.

- [x] **T5 · 🤖 Emitir la alerta en el POLLER (`rutas/interno.py`).**
  En el `except ErrorAutenticacionGmail` del poller (mismo patrón), llamar a
  `avisar_reconectar(integracion.empresa_id, "gmail", "auth_invalida")`. Best-effort:
  envuelto de forma que un fallo de la alerta **no** tumbe el poll de las demás empresas
  (se preserva el comportamiento de la Ola 4).
  - **Test (rojo→verde):** con empresas A (token roto) y B (sana) → el poller responde `200`,
    **emite** la alerta para A con `empresa_id`+`gmail`+`motivo` sin token, A queda
    `reconectar`, B se procesa igual (`conectado`) y crea sus solicitudes.

---

## C. Backend — CA3: observabilidad para el operador (🤖 · AHORA · decisión #1 = endpoint interno)

> Canal de operador (service-role / endpoint interno protegido). Devuelve **sólo**
> `(empresa_id, proveedor, estado)` de las `reconectar` — **nunca** `token_ref` ni datos de
> negocio. **Sin `desde`** (no se arrastra migración; decisión de la spec/plan).

- [x] **T6 · 🤖 `listar_por_estado(estado)` en el repositorio de integraciones.**
  Añadir el método al `Protocol RepositorioIntegraciones` + a la versión **en memoria**
  (`RepositorioIntegracionesEnMemoria`) + a la versión **Supabase**
  (`RepositorioIntegracionesSupabase`, PostgREST `?estado=eq.<estado>`). Devuelve la lista de
  integraciones en ese estado.
  - **Test memoria (rojo→verde):** con integraciones en `conectado` y en `reconectar`
    (varias empresas/proveedores) → `listar_por_estado("reconectar")` devuelve **sólo** las
    `reconectar`; `listar_por_estado("conectado")` devuelve **sólo** las `conectado`.
  - **Test Supabase (rojo→verde, transporte mockeado, sin red):** el GET pega a
    `/rest/v1/integraciones` con `estado=eq.reconectar`, manda apikey + bearer, mapea a
    `Integracion`.

- [x] **T7 · 🤖 Endpoint `GET /interno/conectores/reconectar` (CA3).**
  En `rutas/interno.py`, protegido por `verificar_credencial_servicio`. Usa
  `listar_por_estado("reconectar")` y responde con un **`response_model` Pydantic** nuevo
  (`ConectorReconectar { empresa_id, proveedor, estado }`) — así FastAPI **descarta**
  `token_ref` y cualquier otro campo interno (CA7). Lista vacía si no hay ninguno.
  - **Test (rojo→verde, TestClient):**
    - con integraciones mezcladas (algunas `conectado`, otras `reconectar`, varios
      proveedores/empresas) y la credencial de servicio → `200` con **sólo** las
      `reconectar`, cada una con `{empresa_id, proveedor, estado}` y **ningún** `token_ref`
      (aislamiento: no expone tokens ni datos de negocio);
    - **sin** la credencial de servicio → `403`.

---

## D. No-regresión + cierre (🤖 · AHORA)

- [x] **T8 · 🤖 No-regresión (CA7).** Correr `.venv/bin/python -m pytest -q` y confirmar que
  **toda** la suite existente (ingesta, poller, repos, endpoints) sigue **verde**: la alerta y
  el endpoint nuevo **no** cambian el comportamiento observable previo y **no** exponen tokens.

---

## E. Frontend — CA4: mensaje por proveedor en el panel (🤖 · DIFERIDO · Kiro)

> **NO se hace en esta ola de backend.** Lo edita **Kiro** en `apps/web`
> (`componentes/Configuracion.tsx`). Se deja documentado para trazabilidad.

- [x] **T9 · 🤖 (DIFERIDO · Kiro) Mensaje específico por proveedor cuando `estado === 'reconectar'`.**
  En la tarjeta del conector: Gmail → *"La conexión con Google expiró. Vuelve a conectar para
  seguir leyendo tu correo y tu Drive."*; ClickUp → *"ClickUp se desconectó. Vuelve a conectar
  para crear tareas."* El `estado` ya viaja en `GET /integraciones/correo` y `GET /clickup/estado`
  (no se añade ningún campo nuevo en backend). Token **jamás** en el front (CA5).
  - **Test (vitest + Testing Library, lo escribe Kiro):** render con `estado='reconectar'`
    (mock `fetch`) → aparece el texto de Google en la tarjeta de Gmail y el de ClickUp en la de
    ClickUp; con `estado='conectado'` no aparece; el token nunca figura en el DOM/props.

---

## Notas

- **SIN migración** en esta ola (decisión #2): el `estado` se mantiene en
  `conectado | reconectar`; CA3 lee el `estado` actual vía `listar_por_estado`. CA6
  (estado "por_expirar" + aviso proactivo) queda como **mejora futura**.
- **Sin tokens** en logs/alertas/respuestas (regla de oro #3; CA5/CA7).
- Siguiente paso tras estas tareas de backend: `/implementar 010` (las 🤖 de §B–§D).
