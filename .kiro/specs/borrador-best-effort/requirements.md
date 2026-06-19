# Requirements Document

## Introduction

En el endpoint `POST /conversaciones/responder`, después de que Javo genera su
respuesta exitosamente, el backend persiste el turno de conversación
(`guardar_turnos`) y el borrador de cotización (`guardar_borrador`) en Supabase.
Si la persistencia falla (p.ej. un timeout de BD, error 409, o constraint
violation), toda la respuesta del endpoint revienta con un 500 — aunque Javo ya
respondió correctamente y el usuario podría haber visto su respuesta.

Esto es un anti-patrón: la persistencia del borrador es un efecto secundario
best-effort (conveniencia para rehidratar al refrescar), no la operación primaria.
El usuario prefiere ver la respuesta de Javo inmediatamente y perder la
rehidratación del borrador, a quedarse sin respuesta por un error de BD.

La solución es envolver `guardar_turnos` y `guardar_borrador` en bloques
try/except que logeen el error sin propagarlo al cliente. La respuesta de Javo
siempre llega al frontend.

---

## Requirements

### Requirement 1: Persistencia best-effort de turnos

**User Story:** Como usuario de Dupla Comercial, quiero recibir siempre la
respuesta de Javo aunque la persistencia del historial falle, para no perder la
respuesta que el asistente ya generó.

#### Acceptance Criteria

1. WHEN `guardar_turnos` lanza una excepción, THE endpoint SHALL logear el error
   con `logging.exception()` y continuar sin propagarlo al cliente.
2. THE respuesta HTTP del endpoint SHALL ser 200 con la `RespuestaConversacion`
   completa, incluso si la persistencia falló.
3. THE log SHALL incluir `solicitud_id` y `empresa_id` para facilitar la
   depuración.
4. WHEN `guardar_turnos` tiene éxito, THE Sistema SHALL comportarse exactamente
   igual que antes (sin cambio funcional).

---

### Requirement 2: Persistencia best-effort del borrador

**User Story:** Como usuario de Dupla Comercial, quiero recibir siempre los
componentes y tareas propuestos por Javo aunque guardar el borrador en BD falle,
para no bloquear el flujo de trabajo.

#### Acceptance Criteria

1. WHEN `guardar_borrador` lanza una excepción, THE endpoint SHALL logear el
   error con `logging.exception()` y continuar sin propagarlo.
2. THE respuesta HTTP del endpoint SHALL ser 200 con componentes, tareas y fuentes
   intactos.
3. THE log SHALL incluir `solicitud_id`, `empresa_id` y un indicador de que fue
   `guardar_borrador` el que falló (distinguir del fallo de `guardar_turnos`).
4. WHEN `guardar_borrador` tiene éxito, THE Sistema SHALL comportarse exactamente
   igual que antes.

---

### Requirement 3: El error de Javo (LLM) sigue siendo 502

**User Story:** Como desarrollador, quiero distinguir claramente que el try/except
best-effort aplica SOLO a la persistencia, no al core de la respuesta de Javo.

#### Acceptance Criteria

1. WHEN Javo (el LLM) falla al generar la respuesta, THE endpoint SHALL seguir
   lanzando HTTPException con status_code=502 (comportamiento actual, no se toca).
2. THE try/except best-effort SHALL aplicarse únicamente a `guardar_turnos` y
   `guardar_borrador`, NUNCA a `responder_javo`.
3. THE refactor SHALL NO modificar el bloque try/except existente de
   `responder_javo`.

---

### Requirement 4: Test de resiliencia

**User Story:** Como desarrollador, quiero un test que verifique que la respuesta
llega OK aunque la persistencia reviente, para prevenir regresiones.

#### Acceptance Criteria

1. THE Sistema SHALL incluir un test donde `guardar_turnos` lanza una excepción y
   el endpoint responde 200 con la respuesta de Javo intacta.
2. THE Sistema SHALL incluir un test donde `guardar_borrador` lanza una excepción
   y el endpoint responde 200 con componentes/tareas/fuentes intactos.
3. WHEN `cd apps/api && .venv/bin/python -m pytest -q` se ejecuta, SHALL pasar
   sin fallos.

---

## Tasks

- [ ] 1. Agregar try/except alrededor de `guardar_turnos` en `rutas/conversaciones.py` con `logging.exception()`
- [ ] 2. Agregar try/except alrededor de `guardar_borrador` en `rutas/conversaciones.py` con `logging.exception()`
- [ ] 3. Agregar test: Javo responde 200 OK incluso si `guardar_turnos` lanza excepción
- [ ] 4. Agregar test: Javo responde 200 OK incluso si `guardar_borrador` lanza excepción
- [ ] 5. Verificar `cd apps/api && .venv/bin/python -m pytest -q` en verde
