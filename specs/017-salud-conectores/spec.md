# Spec 017 · Salud de conectores (incluye 010-T9)

- **Estado:** aprobada
- **Tipo:** frontend
- **Relacionada con:** conectores Gmail/Drive/ClickUp (multi-tenant), spec 010 (CA4/T9)

## 1. Problema y por qué

Cuando una conexión OAuth se cae (token expirado o revocado), el usuario no se
entera hasta que algo deja de funcionar. La tarjeta de Gmail ni siquiera
distingue "reconectar" de "sin conectar" y ClickUp no ofrece forma de probar la
conexión. La spec 010 dejó definido (y diferido) el mensaje por proveedor (T9).

## 2. Usuarios y contexto

El gestor en la pantalla Configuración ("Prepara tu espacio"), que ya muestra
las tarjetas de conectores.

## 3. Alcance

**Incluye:**
- Tarjeta Gmail con estado `reconectar`: chip de alerta + mensaje 010-T9
  ("La conexión con Google expiró. Vuelve a conectar para seguir leyendo tu
  correo y tu Drive.") + botón Reconectar.
- Tarjeta ClickUp `reconectar`: mensaje 010-T9 ("ClickUp se desconectó.
  Vuelve a conectar para crear tareas.").
- Botón "Probar conexión" en ClickUp → `POST /clickup/verificar` (auto-heal ya
  implementado en el backend) mostrando el resultado y actualizando el chip.
- Nota de Drive en la tarjeta Gmail (mismo OAuth).

**No incluye:** endpoints nuevos; verificador liviano para Gmail/Drive
(mejora futura); tokens en el DOM (jamás — regla de oro #3).

## 4. Criterios de aceptación

- **CA1** — Dado `estadoCorreo.estado === 'reconectar'`, la tarjeta Gmail
  muestra el mensaje 010-T9 y el botón Reconectar dispara `onConectar('gmail')`.
- **CA2** — Dado ClickUp en `reconectar`, la tarjeta muestra el mensaje 010-T9.
- **CA3** — Dado ClickUp conectado, "Probar conexión" llama a
  `verificarClickup()` y muestra el resultado (mensaje del backend); el chip
  refleja el estado devuelto.
- **CA4** — Ningún token/token_ref aparece en el DOM.

## 5. Consideraciones multi-tenant

Solo consume `GET /integraciones/correo`, `GET /clickup/estado` y
`POST /clickup/verificar`, todos filtrados por la empresa del JWT (RLS).

## 6. Aclaraciones pendientes

- Ninguna.
