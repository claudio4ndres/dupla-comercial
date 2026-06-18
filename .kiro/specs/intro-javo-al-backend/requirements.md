# Documento de Requisitos — Mover introJavo() al backend

## Introduction

La función `introJavo()` en `App.tsx` genera el primer mensaje de Javo al iniciar
la conversación con una solicitud. Esta lógica vive en el frontend, lo que:

1. Mezcla lógica de negocio con UI (violación de la separación de responsabilidades).
2. Puede quedar desincronizada con el system prompt real que usa el backend.
3. Impide cambiar el saludo de Javo sin hacer deploy del frontend.

El objetivo es que el primer mensaje de Javo lo genere el backend, igual que el
resto de los mensajes del chat.

---

## Glossary

- **introJavo**: Función en `App.tsx` que genera el mensaje inicial de Javo según
  el tipo de solicitud (t1 o t2).
- **POST /conversaciones/responder**: Endpoint que responde mensajes del chat. Si el
  historial llega vacío, puede generar el saludo inicial.
- **POST /conversaciones/iniciar**: Endpoint nuevo alternativo que genera el saludo
  inicial de Javo para una solicitud y tipo dados.

---

## Requirements

### Requirement 1: Endpoint para el mensaje inicial de Javo

**User Story:** Como desarrollador, quiero que el mensaje inicial de Javo
venga del backend, para que sea consistente con el system prompt y se pueda
cambiar sin tocar el frontend.

#### Acceptance Criteria

1. THE Sistema SHALL crear el endpoint `POST /conversaciones/:solicitud_id/iniciar`
   que recibe `tipo: TipoConversacion` y devuelve el primer mensaje de Javo
   (`RespuestaConversacion` con solo `texto`).
2. WHEN el historial de la conversación está vacío, THE endpoint SHALL generar el
   saludo inicial usando el resumen y remitente de la solicitud, exactamente como
   hace `introJavo()` hoy.
3. THE Sistema SHALL eliminar la función `introJavo()` de `App.tsx` y reemplazar
   su llamada por una petición al nuevo endpoint.
4. THE Sistema SHALL mantener el comportamiento de rehidratación: si ya hay historial,
   `iniciarChat` sigue usando `obtenerHistorialConversacion` en lugar del saludo.

---

### Requirement 2: Sin cambio de comportamiento para el usuario

**User Story:** Como usuario, quiero que el chat con Javo siga comenzando
con el mismo mensaje de bienvenida de siempre.

#### Acceptance Criteria

1. THE Sistema SHALL mantener el contenido del saludo inicial igual que hoy
   (referencia al remitente, tipo de solicitud, invitación a conversar).
2. THE Sistema SHALL mantener el estado de carga: mientras se obtiene el saludo,
   el chat muestra el indicador `enviando` en lugar de un mensaje vacío.

---

## Tasks

- [ ] 1. Crear endpoint `POST /conversaciones/:solicitud_id/iniciar` en el backend
  - Recibe `{ tipo: TipoConversacion }` en el body
  - Lee la solicitud por `solicitud_id` (remitente + resumen)
  - Genera el saludo usando la misma lógica que `introJavo()` actual
  - Devuelve `{ texto: string }` (sin componentes, tareas ni fuentes)
  - Persiste el saludo como primer mensaje de la conversación
  - _Requirements: 1.1, 1.2_

- [ ] 2. Crear función `iniciarConversacion(solicitudId, tipo)` en `src/api/conversaciones.ts`
  - Llama al nuevo endpoint
  - Devuelve `{ texto: string }`
  - _Requirements: 1.1_

- [ ] 3. Actualizar `iniciarChat` en `App.tsx` (o `SolicitudContext`)
  - En lugar de `introJavo(sol, t)`, llamar `iniciarConversacion(sol.id, t)`
  - Mostrar el indicador de carga mientras resuelve
  - Eliminar la función `introJavo()` de `App.tsx`
  - _Requirements: 1.3, 1.4, 2.2_

- [ ] 4. Tests del backend
  - Test: `POST /conversaciones/s-1/iniciar` con `tipo=t1` → devuelve texto con el remitente
  - Test: `POST /conversaciones/s-1/iniciar` con `tipo=t2` → devuelve texto diferente (propuesta creativa)
  - _Requirements: 1.1, 1.2_

- [ ] 5. Test del frontend
  - Test: al entrar al chat, el primer mensaje de Javo viene del backend (no de `introJavo`)
  - Mock del nuevo endpoint en el test correspondiente de `App.test.tsx`
  - _Requirements: 1.3, 2.1_

- [ ] 6. Checkpoint — `pytest -q` y `npm test` en verde
