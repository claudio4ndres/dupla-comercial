# Spec 002 · Conexión de correo y recepción de solicitudes

- **Estado:** aprobada
- **Tipo:** full-stack (integración + backend + datos + frontend)
- **Relacionada con:** bandeja (ingesta de correos) · multi-tenant · es la "ingesta
  de Gmail (spec aparte)" que dejó pendiente la Spec 001.

## 1. Problema y por qué
Hoy la bandeja corre con datos mock. Para que Javo trabaje sobre correos reales,
cada empresa debe poder **conectar su casilla** (Gmail / Outlook / IMAP) y el
sistema debe **detectar correos nuevos sin que nadie los cargue a mano**, para que
entren a la bandeja como solicitudes. Sin esto, no hay producto: la bandeja vive
del correo entrante. Una vez que el correo entra, lo demás (resumen + tipo) ya lo
cubre la Spec 001.

## 2. Usuarios y contexto
Javo (gestor), desde la **Bandeja**. Si la empresa aún no conectó su correo, ve un
llamado "Conecta tu bandeja de entrada" con los proveedores. Tras conectar, la
bandeja queda "escuchando" y los correos nuevos aparecen solos. La conexión es
**por empresa (tenant)**: cada empresa conecta su propia casilla.

## 3. Alcance
**Incluye:**
- UI en la bandeja para elegir proveedor (Gmail / Outlook / IMAP) y ver el estado
  de la conexión: *sin conectar* / *escuchando* / *reconectar*. (El front ya está
  prototipado: botones + estado "Escuchando nuevos correos · <proveedor>".)
- Flujo **OAuth por empresa** para conectar la casilla (Gmail = Google OAuth;
  Outlook = Microsoft Graph). Los tokens se guardan **solo en el backend**
  (Secret Manager o columna cifrada), nunca en el frontend.
- **Recepción de correos nuevos por polling** (intervalo configurable): el backend
  consulta periódicamente la casilla conectada y crea una `solicitud` por cada
  correo nuevo (estado inicial: *sin clasificar*), asociada a la `empresa_id`.
- **Idempotencia**: no se duplican solicitudes ya ingeridas (se usa el id de
  mensaje del proveedor + un cursor de avance).
- Estado de conexión por empresa (conectado / desconectado / token expirado).

**No incluye (fuera de alcance):**
- **Push en tiempo real** (Gmail `watch` + Google Pub/Sub, Microsoft Graph
  `subscriptions`). Se documenta como evolución a producción (ver §6), pero el
  piloto va con polling.
- La **clasificación y el resumen** del correo (Spec 001).
- La **autenticación de usuarios / login** (spec aparte de auth; el login actual es
  un mock de frontend).
- **Enviar o responder** correos desde la app.
- La conversación con Javo y la búsqueda en internet (specs aparte).

## 4. Criterios de aceptación (de aquí salen los tests)
- **CA1** — Dado un usuario cuya empresa no tiene proveedor conectado, Cuando abre
  la Bandeja, Entonces ve la opción de conectar (Gmail / Outlook / IMAP) y la
  bandeja **no** muestra estado "escuchando".
- **CA2** — Dado que el gestor elige un proveedor y completa el OAuth, Cuando vuelve
  a la app, Entonces la empresa queda con ese proveedor conectado y la bandeja
  muestra "Escuchando nuevos correos · <proveedor>".
- **CA3** — Dado un proveedor conectado, Cuando el poller corre y hay correos
  nuevos, Entonces se crea **una solicitud por correo** en la bandeja de esa
  empresa, con estado *sin clasificar*.
- **CA4** — Dado un correo ya ingerido antes, Cuando el poller vuelve a correr,
  Entonces **no** se crea una solicitud duplicada (idempotencia por id de mensaje
  del proveedor).
- **CA5** — Los tokens OAuth **nunca** se exponen al frontend ni viajan en
  respuestas de API; viven solo en el backend.
- **CA6** — En los tests, las APIs de Gmail / Graph / IMAP están **mockeadas**: no
  se hacen llamadas reales ni se usan credenciales reales.
- **CA7** — Dado un token expirado o revocado, Cuando el poller corre, Entonces la
  conexión pasa a estado "reconectar" y la bandeja lo refleja **sin caerse** (no
  rompe la ingesta de otras empresas).

## 5. Consideraciones multi-tenant
- La conexión (proveedor + tokens + cursor de polling) pertenece a una `empresa_id`.
  Tabla nueva sugerida `conexiones_correo` con **RLS por empresa**.
- El poller procesa cada empresa con **sus propias** credenciales; jamás mezcla
  correos entre empresas. Los correos ingeridos (`solicitudes`) llevan `empresa_id`.
- **Test de RLS:** un usuario de la empresa A nunca ve la conexión ni las
  solicitudes de la empresa B (recibe 404/forbidden).

## 6. Decisiones resueltas
- **Polling para el piloto** (intervalo configurable, ~1–2 min). Razón: simplicidad
  y costo — no requiere infraestructura de webhooks ni endpoint público, y encaja
  con la restricción de presupuesto (tiers gratuitos). **Evolución a producción:**
  Gmail `users.watch` + Pub/Sub (push instantáneo) y Microsoft Graph
  `subscriptions`; queda fuera de alcance pero el modelo de datos no debe impedirlo.
- **Tokens solo en backend** (Secret Manager o columna cifrada). Extiende la regla
  de oro #3 (no exponer credenciales en el frontend) a los tokens de Gmail/Graph.
- **Una solicitud por correo entrante**, estado inicial *sin clasificar*; el resumen
  y el tipo los genera la Spec 001 on-demand cuando el gestor abre la solicitud.
- **Gmail primero:** el piloto Capsulab usa Google Workspace, así que esta entrega
  implementa **Gmail** (Google OAuth + Gmail API). Outlook/IMAP quedan para una
  segunda iteración (el modelo de datos los contempla, pero no se implementan ahora).

## 7. Aclaraciones resueltas
- **Proveedor del piloto:** Capsulab usa **Google Workspace** → se implementa
  **Gmail** primero; Outlook/IMAP en una iteración posterior.
- **Casillas por empresa:** **una** casilla por empresa (es piloto 1). Soportar
  varias casillas queda como mejora futura.
- **Ventana inicial al conectar:** se ingieren **solo los correos entrantes desde el
  momento de conectar** (sin importar histórico).
