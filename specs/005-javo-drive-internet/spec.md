# Spec 005 · Javo agente: consulta el Drive (Tipo 1) y busca en internet (Tipo 2)

- **Estado:** borrador
- **Tipo:** full-stack (backend tool-use · datos/catálogo · integración Drive/web · frontend estado)
- **Relacionada con:** Tipo 1 (cotización · Drive) · Tipo 2 (ideas · internet) · multi-tenant · spec 003 (conversación con Javo) · spec 004 (propuesta)

## 1. Problema y por qué

Hoy Javo **conversa** (spec 003) pero **no consulta datos reales**: los componentes y
valores de la cotización salen de datos sembrados, no del conocimiento de la empresa.

El gestor (GP) necesita que Javo, **durante la conversación**, defina y **valorice los
componentes con los precios REALES de la empresa** — que viven en su **Drive**
(tarifarios, cotizaciones modelo, proveedores, productos). Y en **Tipo 2**, cuando no
hay brief cerrado, a veces necesita que Javo traiga **referencias/opciones de internet**
para co-crear la idea.

Sin esto, Javo inventa o usa datos genéricos y la propuesta **no sirve para cotizar de
verdad**. Esta es la pieza que convierte a Javo en un **asistente comercial real**: es
el corazón del producto ("el mejor chat de Dupla Comercial"). Importa porque es lo que
diferencia a Dupla de un chatbot genérico: responde con los números y los recursos de
**esa** agencia.

## 2. Usuarios y contexto

- **Usuario:** el **GP** (gestor de proyecto) conversando con Javo en la **pantalla de
  chat**, en ambos tipos de solicitud.
- **Agente:** **Javo** (LLM Sonnet, ejecutado **solo desde el backend** — regla de oro
  #3) decide cuándo consultar el Drive o internet según la conversación.
- **Momento del flujo** (ver `memory/contexto-producto.md`):
  - Paso 4–5: conversación → **definir componentes consultando el Drive** (Tipo 1).
  - Paso 4: en **Tipo 2**, **buscar ideas en internet** si el usuario lo pide.

## 3. Alcance

**Incluye:**
- Javo como **agente con herramientas** (tool-use) ejecutadas por el backend:
  - **Consultar el catálogo del Drive** de la empresa (componentes y valores reales).
  - **Buscar en internet** referencias/opciones.
- **Tipo 1:** Javo usa el catálogo para **definir y valorizar** los componentes, **cita
  el origen** del dato y **no inventa precios**.
- **Tipo 2:** Javo se inspira en **casos anteriores del Drive** (trabajos pasados de la
  agencia) y, además, **busca en internet solo cuando el GP lo pide explícitamente**;
  **muestra las fuentes** y se acota a **~3–5 búsquedas por conversación**.
- Javo **propone** los componentes (con sus valores reales y su origen) en el **panel del
  chat**; el GP los **confirma/ajusta** y, al "Generar propuesta", pasan a la cotización
  (spec 004). Es decir, **005 termina en "propuesto en el chat"**.
- **Catálogo de la empresa** (datos consultables): representación **compacta** de los
  precios/recursos del Drive. Para la demo, **pre-extraída** de archivos reales del Drive
  de Capsulab (tarifarios, "Modelo Cotización", "Presupuesto", PROVEEDORES, PRODUCTOS LAB).
- **Estado en la UI** mientras Javo consulta ("Javo está buscando en el Drive…" / "…en
  internet…"), reutilizando el patrón de mensaje de sistema que ya existe.
- **Tests** con el cliente de Anthropic, la API de Drive y la de búsqueda **mockeados**.

**No incluye (fuera de alcance):**
- **Conexión OAuth de Drive en vivo** y **sincronización automática** del catálogo
  (poller/índice): **decidido — fase 2**, spec aparte (análoga a la 002 de Gmail). La 005
  corre sobre el **catálogo pre-extraído** del Drive real de Capsulab.
- **Persistir / editar la propuesta y las tareas**: lo cubre la **spec 004**. **Decidido:**
  Javo **propone** en el chat y el GP confirma; aquí **no** se auto-puebla la propuesta.
- ClickUp, exportar a PPT/Excel, enviar la propuesta.
- Cambios al login/autenticación.

## 4. Criterios de aceptación (de aquí salen los tests)

- **CA1 — Tipo 1 usa datos reales del Drive.** Dado una conversación **Tipo 1** donde el
  GP pide cotizar un componente que **sí está** en el catálogo (ej. "promotoras"), Cuando
  Javo necesita el valor, Entonces **consulta el catálogo del Drive de la empresa** y
  responde con un **valor real del catálogo** (no inventado), **indicando de qué recurso**
  salió.
- **CA2 — Javo no inventa precios.** Dado que el componente pedido **no está** en el
  catálogo, Cuando Javo responde, Entonces **no inventa un precio**: pide el dato o propone
  un **rango marcado como estimación**, dejando claro que no proviene del catálogo.
- **CA3 — Internet solo si el GP lo pide (Tipo 2).** Dado una conversación **Tipo 2**,
  Cuando el GP **no** ha pedido buscar en internet, Entonces Javo propone conceptos **sin
  buscar** (no asume). Y Dado el mismo contexto, Cuando el GP pide explícitamente "busca en
  internet / referencias / opciones", Entonces Javo **ejecuta la búsqueda** y trae los
  resultados/opciones a la conversación.
- **CA4 — El LLM y las APIs externas se mockean en los tests (regla #3).** Dado los tests
  de la feature, Cuando se prueba la conversación con herramientas, Entonces el cliente de
  **Anthropic**, la **API de Drive** y la de **búsqueda en internet** están **mockeados**:
  cero llamadas reales, cero tokens, cero red.
- **CA5 — Aislamiento multi-tenant del Drive.** Dado el GP de la **empresa A**, Cuando Javo
  consulta el catálogo/Drive, Entonces accede **solo** al catálogo de la empresa A; **jamás**
  a recursos de la empresa B.
- **CA6 — Trazabilidad / no perder criterio.** Dado que Javo usó un dato del Drive o un
  resultado de internet, Cuando responde, Entonces el GP **puede ver el origen** (qué recurso
  del Drive / qué fuente web), para mantener el criterio comercial.
- **CA7 — Estado visible mientras consulta.** Dado que Javo está consultando el Drive o
  internet, Cuando ocurre, Entonces la UI muestra un **estado** ("Javo está buscando…").
- **CA8 — Respuestas acotadas (costo/relevancia).** Dado que Javo consulta el Drive, Cuando
  arma la respuesta, Entonces **no vuelca documentos completos** a la conversación: usa solo
  las líneas/recursos **relevantes** (el catálogo entrega extractos, no archivos enteros).
- **CA9 — Tipo 2 usa casos del Drive.** Dado una conversación **Tipo 2**, Cuando Javo propone
  conceptos, Entonces **puede referenciar casos anteriores del Drive** de la empresa (citando
  el recurso), además de —si el GP lo pide— resultados de internet con sus fuentes.
- **CA10 — Los hallazgos quedan propuestos, no auto-guardados.** Dado que Javo definió
  componentes desde el catálogo, Cuando los presenta, Entonces quedan **propuestos en el
  chat** para que el GP confirme; **no se persisten** en la propuesta automáticamente (esa
  persistencia es de la spec 004).
- **CA11 — Internet acotado.** Dado una conversación, Cuando el GP pide buscar en internet,
  Entonces Javo realiza **a lo más ~3–5 búsquedas** por conversación y **muestra las fuentes**
  de los resultados.

## 5. Consideraciones multi-tenant

- El **catálogo** (datos nuevos) lleva `empresa_id` y queda protegido por **RLS**: el GP
  solo ve/consulta el catálogo de **su** empresa (empresa A nunca ve el de B).
- La **integración de Drive** es **por empresa**; los tokens/credenciales del Drive viven
  **solo en el backend** (Secret Manager), nunca en el front (regla #3) y nunca se exponen
  por la API (igual que Gmail en spec 002).
- La herramienta `buscar_en_drive` resuelve la empresa del **JWT del usuario** y **jamás**
  recibe un `empresa_id` desde el front: la barrera es la RLS, no un filtro del backend.

## 6. Decisiones tomadas y aclaraciones pendientes

**Decididas (confirmadas con el cliente):**
- **Drive en Tipo 2:** ✅ Sí — Javo se inspira en **casos anteriores del Drive** además de
  buscar en internet cuando se lo piden.
- **Hallazgos de Javo:** ✅ Se **proponen en el chat**; el GP confirma. La persistencia en
  la propuesta es de la **spec 004** (005 no auto-puebla).
- **Drive en vivo (OAuth):** ✅ **Fase 2** (spec aparte). La 005 corre sobre el **catálogo
  pre-extraído**.
- **Internet:** ✅ Mostrar **fuentes** y topear a **~3–5 búsquedas** por conversación; gating
  "solo si el GP lo pide".

**Pendiente (no bloquea la demo):**
- [NECESITA ACLARACIÓN: **Modelo de producción del catálogo.** ¿Cómo se construye/mantiene
  el catálogo por empresa cuando entre el Drive en vivo (fase 2)? Opciones: (a) el GP
  marca/sube los archivos-fuente; (b) se indexa una carpeta; (c) poller que re-sincroniza.
  Para la demo basta el **catálogo pre-extraído**; esto se resuelve junto con el OAuth de
  Drive en su spec.]
