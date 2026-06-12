# Spec 009 · ClickUp OAuth por empresa

- **Estado:** borrador
- **Tipo:** full-stack (integración + backend + datos + frontend)
- **Relacionada con:** multi-tenant · conectores (panel de Configuración) · onboarding ·
  análoga al OAuth de Gmail de la Spec 002 · cierra el pendiente de la tarea #23
  ("conector OAuth próximamente") · habilita las tareas de la Spec 004 (propuesta → ClickUp)

---

## 1. Problema y por qué

Hoy ClickUp NO está por-empresa: el backend usa un **token global compartido**
(`CLICKUP_API_TOKEN`, una sola variable de entorno) para **todos** los tenants. Es la
deuda que dejó la tarea #23: como no había credenciales OAuth reales, se cableó un
token único y se marcó el conector como "OAuth próximamente".

La consecuencia es un **fallo de aislamiento visible en producción**: el panel de
conectores muestra **"Conectado · 3 listas" para CUALQUIER empresa**, porque el estado
se deriva de consultar ese token global —no de si la empresa conectó algo—. Una empresa
recién creada como **RukkumansLabs**, que **jamás** conectó ClickUp, aparece "Conectada"
y vería listas que **no son suyas**. Esto rompe la promesa central del producto: cada
empresa tiene su **espacio aislado** (regla de oro #2). Además, si alguna empresa creara
tareas, irían al ClickUp de quien sea dueño del token global, **filtrando trabajo entre
clientes**.

Para onboardear más clientes (Espiga, etc.) cada empresa debe conectar **su propio**
ClickUp por **OAuth**, con su token guardado **por-tenant** —exactamente como Gmail: una
fila en `integraciones` con `empresa_id` y el token referenciado en Secret Manager,
aislado por **RLS**—. El panel debe reflejar el estado **real por empresa**: conectada
solo si *esa* empresa autorizó.

---

## 2. Usuarios y contexto

- **Gestor / admin de empresa:** la persona que opera la app. Conecta ClickUp desde el
  **panel de Configuración → Conectores** (tarjeta "Gestor de tareas · ClickUp"), durante
  el **onboarding** o cuando quiera cambiar la conexión. Hoy esa tarjeta solo dice
  "Conecta ClickUp… (conector OAuth próximamente)"; con esta spec pasa a tener un flujo
  real de **Conectar / Cambiar / Sin conectar**, igual que la tarjeta de Gmail.
- **Contexto de uso:** la conexión es **por empresa (tenant)**. Cada empresa autoriza su
  propia cuenta de ClickUp; el resultado habilita el **selector de lista destino** (pantalla
  de Tareas / propuesta) y el envío de tareas a *su* ClickUp.
- **RukkumansLabs** (operador, recién creado en la Spec 008) es el caso que destapó el bug:
  debe aparecer **"Sin conectar"** mientras no autorice su propio ClickUp.

---

## 3. Alcance

**Incluye:**
- **Flujo OAuth de ClickUp por empresa** desde el panel de conectores: iniciar la
  autorización (redirección a ClickUp), volver con el consentimiento y dejar la cuenta de
  *esa* empresa conectada. Reemplaza la nota "conector OAuth próximamente".
- **Persistir el token por-tenant:** una fila en `integraciones` con `empresa_id` +
  `proveedor='clickup'` y el token referenciado en **Secret Manager** (`token_ref`), nunca
  en texto plano en la tabla ni en el frontend. Reutiliza el mecanismo ya usado por Gmail.
- **Estado real por empresa en el panel:** la tarjeta de ClickUp muestra *Sin conectar* /
  *Conectado* / *Reconectar* **según la integración de la empresa autenticada**, no según
  un token global. "Conectado" solo si *esa* empresa autorizó.
- **Uso del token por-empresa en las operaciones existentes de ClickUp:** listar listas
  (selector de destino) y crear tareas pasan a usar el token **de la empresa del request**,
  resuelto desde `integraciones` (vía Secret Manager), en lugar del token global.
- **Desconectar / cambiar:** el gestor puede desconectar ClickUp de su empresa (igual que
  "Cambiar" en Gmail); la integración de esa empresa queda eliminada/inactiva y el panel
  vuelve a "Sin conectar".
- **Aislamiento por RLS** verificado: la integración de ClickUp pertenece a una `empresa_id`
  y la política `int_empresa` impide que una empresa lea/use la de otra.

**No incluye (fuera de alcance):**
- **Migrar el token global existente** más allá de lo mínimo necesario para que deje de
  filtrar entre tenants. No se hace una migración de datos de credenciales viejas; el
  `CLICKUP_API_TOKEN` global deja de gobernar el estado/uso por empresa. [Ver aclaración
  sobre qué hacer con el token global y la empresa que hoy lo usa "de facto".]
- **Rehacer Gmail / Drive ni su OAuth.** Se reutiliza su patrón, pero no se modifican sus
  flujos.
- **Jira u otros gestores de tareas** (la tarjeta "Jira · Próximamente" sigue deshabilitada).
- **Soportar varias cuentas de ClickUp por empresa** (una conexión por empresa; varias es
  mejora futura, como en Gmail).
- **Cambios en la lógica de Tareas/propuesta** salvo que consuman el token por-empresa
  (qué se sincroniza y cómo se arma la tarea es la Spec 004).
- **Selección de workspace/team específico** dentro de ClickUp más allá de lo que ya hace el
  listado plano de listas. [Ver aclaración sobre alcance del scope OAuth.]

---

## 4. Criterios de aceptación (de aquí salen los tests)

- **CA1 (empresa nueva = sin conectar)** — Dado un usuario de una empresa que **nunca**
  conectó ClickUp (p.ej. RukkumansLabs), Cuando abre el panel de conectores, Entonces la
  tarjeta de ClickUp muestra **"Sin conectar"** y **no** lista ni cuenta listas de nadie
  (no aparece "Conectado · N listas").

- **CA2 (conectar por empresa)** — Dado que el gestor inicia el OAuth de ClickUp y completa
  el consentimiento, Cuando vuelve a la app, Entonces su empresa queda con ClickUp
  **conectado**, se crea **una fila en `integraciones`** con `empresa_id` de *esa* empresa,
  `proveedor='clickup'` y un `token_ref` (no el token en claro), y el panel muestra
  **"Conectado"**.

- **CA3 (token por-tenant en uso)** — Dado dos empresas A y B, A con ClickUp conectado y B
  no, Cuando un usuario de A pide el selector de listas o crea una tarea, Entonces se usa el
  token **de A** (resuelto desde su integración); y cuando un usuario de B hace lo mismo,
  Entonces **no** se usa ningún token (cae a `[]` / aviso "conecta ClickUp"), **sin** tocar
  el ClickUp de A.

- **CA4 (aislamiento: A nunca usa el ClickUp de B)** — Dado un usuario de la empresa A,
  Cuando opera ClickUp, Entonces **jamás** se resuelve ni se usa el `token_ref` de la
  empresa B (RLS `int_empresa`): A solo puede leer/usar su propia integración; un intento de
  alcanzar la de B responde vacío/forbidden, nunca datos de B.

- **CA5 (el token nunca llega al frontend)** — Dado cualquier estado de conexión, Cuando el
  frontend consulta el estado del conector o cualquier endpoint, Entonces el token de ClickUp
  **nunca** viaja al frontend ni aparece en respuestas de API (vive solo en el backend /
  Secret Manager, regla de oro #3).

- **CA6 (reconectar sin caerse)** — Dado un token de ClickUp **inválido o revocado** para una
  empresa, Cuando el panel consulta el estado o se intenta usar ClickUp, Entonces el conector
  pasa a **"Reconectar"** y la app **no se rompe** (no rompe el panel ni las operaciones de
  otras empresas).

- **CA7 (desconectar)** — Dado un usuario con ClickUp conectado, Cuando desconecta/"cambia" el
  conector, Entonces la integración de **su** empresa se elimina/inactiva y el panel vuelve a
  **"Sin conectar"**, sin afectar a otras empresas.

- **CA8 (tests sin servicios reales — OBLIGATORIO)** — Dado los tests de esta feature, Cuando
  corren, Entonces el **SDK de Anthropic** y la **API de ClickUp** (y el canje OAuth de
  ClickUp) están **mockeados**: no se hacen llamadas reales ni se usan credenciales reales; la
  RLS se prueba contra una **DB de Supabase local**.

---

## 5. Consideraciones multi-tenant

- La integración de ClickUp (proveedor + `token_ref` al secreto) pertenece a una `empresa_id`
  en la tabla `integraciones`, con la política RLS **`int_empresa`** ya existente
  (`empresa_id = empresa_actual()`). No se introduce un almacén de credenciales paralelo ni
  global por empresa.
- El estado del conector y la resolución del token salen **siempre** de la empresa del
  request (derivada del JWT), nunca de una variable de entorno compartida. El bug actual es,
  literalmente, que el estado/uso **no** dependía de `empresa_id`; esta spec lo corrige.
- **Test de RLS (la prueba de la barrera):** un usuario de la empresa A **no** ve ni usa la
  integración de ClickUp de la empresa B (recibe vacío/forbidden), y empresa A **jamás** crea
  tareas en el ClickUp de B. RukkumansLabs sin conexión aparece "Sin conectar" aunque Capsulab
  (u otra) sí esté conectada.
- Igual que en Gmail, los flujos sin JWT (p.ej. el **callback** del OAuth, que es un redirect
  del navegador) deben fijar `empresa_id` **explícito** al persistir la integración —nunca
  inferirlo— para no cruzar tenants.

---

## 6. Aclaraciones pendientes

- [NECESITA ACLARACIÓN: ¿ClickUp ofrece un app OAuth con `client_id`/`client_secret` y
  `redirect_uri` que podamos registrar para Dupla Comercial? La tarea #23 se bloqueó por
  "falta de credenciales reales": ¿ya existe la app OAuth de ClickUp registrada (y sus
  secretos en Secret Manager / config), o ese registro es un paso manual del humano previo a
  implementar?]
- [NECESITA ACLARACIÓN: ¿Qué hacemos con el `CLICKUP_API_TOKEN` global actual y con la empresa
  que hoy lo usa "de facto" (Capsulab)? Opciones: (a) eliminarlo y exigir que cada empresa
  reconecte por OAuth; (b) sembrar la integración de Capsulab a partir de ese token como
  puente temporal. ¿Cuál se prefiere para no dejar a Capsulab sin ClickUp el día del corte?]
- [NECESITA ACLARACIÓN: ¿Qué **scopes/permisos** de ClickUp pedimos en el consentimiento?
  Mínimo necesario para listar listas (team→space→folder→list) y crear tareas. ¿Alcanza con el
  scope por defecto del token OAuth de ClickUp o hay que pedir algo explícito?]
- [NECESITA ACLARACIÓN: ClickUp OAuth, ¿entrega **refresh token** (como Google) o un access
  token de **larga duración / sin expiración**? Esto define si "Reconectar" (CA6) se dispara
  solo por revocación o también por expiración, y qué se guarda en Secret Manager.]
- [NECESITA ACLARACIÓN: El estado "Conectado" del panel, ¿se determina por la **existencia de
  la integración** de la empresa (barato, sin llamar a ClickUp) o por una **verificación viva**
  (pedir listas y ver que responde)? Hoy se infiere de "hay listas"; conviene separar "conectado"
  (hay token de la empresa) de "tiene N listas disponibles".]
