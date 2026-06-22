# Plan de mejoras · Dupla Comercial

Guía de trabajo para las mejoras priorizadas del proyecto. Cada ítem sigue el flujo
SDD+TDD obligatorio del proyecto: spec → plan → tareas → implementar.

---

## 🔴 Alta prioridad

### 1. Publicar app OAuth de Google a "production"
**Tipo:** operacional (sin código)
**Problema:** La app OAuth está en modo "Testing" → los refresh tokens expiran cada 7 días
→ los usuarios deben reconectar Gmail manualmente cada semana.
**Acción:**
- Ir a Google Cloud Console → OAuth consent screen.
- Cambiar el estado de "Testing" a "In production".
- Completar la verificación de Google si se pide (puede tomar días).
- Validar que los tokens de empresas existentes siguen funcionando tras el cambio.

---

### 2. Ingesta de correos en tiempo real (Spec 011 — Gmail push/watch)
**Tipo:** feature (requiere spec SDD)
**Problema:** El poller actual introduce ~80 segundos de latencia. Para una agencia
comercial, ese retraso puede hacer perder una oportunidad.
**Spec existente:** `specs/011-gmail-push/` (ya redactada, pendiente de implementar)
**Pasos:**
1. Revisar y aprobar la spec 011 existente.
2. Crear topic Pub/Sub en GCP + endpoint webhook en el backend.
3. Registrar el watch de Gmail por empresa al conectar la integración.
4. Procesar los push notifications en el mismo servicio de ingesta actual.
5. Mantener el poller como fallback (si el watch caduca o falla).
**Criterio de éxito:** correo aparece en la bandeja en menos de 5 segundos.

---

## 🟡 Media prioridad

### 3. Refactor de App.tsx — extraer estado por dominio
**Tipo:** deuda técnica (refactor interno, sin cambio de comportamiento)
**Problema:** `App.tsx` tiene ~20 useState y más de 300 líneas. Cualquier feature nueva
agrega más estado ahí, haciéndolo cada vez más difícil de mantener y testear.
**Approach:**
- Crear contextos React por dominio:
  - `SesionContext` — sesión y empresa activa.
  - `SolicitudContext` — solicitud activa, tipo, mensajes, componentes, tareas, fuentes.
  - `BandejaContext` — solicitudes, estados de carga/error, reintento.
- `App.tsx` queda como orquestador de layout (Sidebar + Topbar + pantalla activa).
- Sin cambio de comportamiento observable para el usuario.
**Pasos:**
1. Escribir spec de refactor.
2. Extraer `SesionContext` primero (el más independiente).
3. Extraer `SolicitudContext`.
4. Extraer `BandejaContext`.
5. Verificar que todos los tests existentes siguen en verde tras cada extracción.

---

### 4. Cobertura de tests en el frontend
**Tipo:** calidad (TDD)
**Problema:** El backend tiene pytest configurado, pero el frontend carece de tests
reales. Componentes como `Chat`, `Propuesta` y `Bandeja` tienen lógica relevante sin
cobertura, lo que es riesgo de regresión.
**Stack:** vitest + @testing-library/react (ya declarado en CLAUDE.md)
**Prioridad de componentes a cubrir:**
1. `Bandeja` — estados: cargando, error, vacío, con solicitudes.
2. `Chat` — envío de mensaje, rehidratación del borrador.
3. `Propuesta` — cálculo de total, exportación habilitada/deshabilitada.
4. `Configuracion` — estados del conector (desconectado, cargando, conectado, reconectar).
**Pasos:**
1. Configurar mocks de `fetch` globales en vitest.
2. Escribir tests por componente siguiendo ciclo rojo → verde → refactor.
3. Agregar script `test:coverage` al `package.json` del web.

---

### 5. Navegación con router real
**Tipo:** mejora técnica
**Problema:** La navegación por estado (`pantalla` en App.tsx) no soporta URLs directas
ni el botón "atrás" del navegador. A medida que crecen las pantallas, esto se vuelve
difícil de sostener.
**Approach:** TanStack Router (tipado, compatible con Vite) o React Router v7.
**Pasos:**
1. Evaluar TanStack Router vs React Router v7 y decidir.
2. Escribir spec de migración (mapeo de pantallas actuales a rutas).
3. Migrar una pantalla a la vez, empezando por `inbox`.
4. Asegurar que los tests de componentes no dependan de la lógica de navegación.
**Criterio de éxito:** cada pantalla tiene su URL; el botón "atrás" funciona.

---

### 6. Eliminar datosMock del Sidebar
**Tipo:** deuda técnica menor
**Problema:** `EMPRESAS` del archivo `datosMock` todavía alimenta el `Sidebar`, mezclando
datos hardcodeados con el tenant real. En multi-tenant real, el selector de empresa
debería venir del backend.
**Pasos:**
1. Agregar endpoint `GET /empresas` (o extender `GET /empresa`) para listar las empresas
   accesibles al usuario (según su rol).
2. Reemplazar `EMPRESAS` del mock por una llamada real al backend en `App.tsx`.
3. Eliminar `datosMock.ts` o reducirlo solo a constantes de desarrollo local.

---

## 🟢 Baja prioridad (deuda técnica menor)

### 7. Persistir `dias` y `proveedor` en `componentes_propuesta`
**Problema:** La tabla SQL no tiene columnas `dias` ni `proveedor`, pero el esquema
Pydantic y el frontend sí los manejan. Hay datos que Javo propone y que se pierden al
guardar.
**Acción:** Migración SQL que agrega `dias integer default 1` y `proveedor text` a
`componentes_propuesta`.

---

### 8. Cambiar `vencimiento` de `text` a `date` en tareas
**Problema:** Guardar fechas como texto libre dificulta filtros, ordenamiento y la
integración futura con calendarios o ClickUp.
**Acción:** Migración SQL + ajuste en esquemas Pydantic + frontend.

---

### 9. Mover `introJavo()` al backend
**Problema:** El primer mensaje de Javo está hardcodeado en `App.tsx` (frontend). Eso
mezcla lógica de negocio con UI y puede quedar desincronizado con el system prompt real.
**Acción:** El endpoint `POST /conversaciones/responder` puede devolver el mensaje inicial
cuando el historial está vacío, o bien un nuevo endpoint `POST /conversaciones/iniciar`.

---

## Orden de ejecución sugerido

```
Semana 1:  ítem 1 (OAuth production, sin código) + ítem 6 (mock cleanup)
Semana 2:  ítem 2 (Spec 011 — Gmail push)
Semana 3:  ítem 3 (Refactor App.tsx)
Semana 4:  ítem 4 (Tests frontend)
Semana 5+: ítem 5 (Router), ítems 7-9 (deuda menor)
```

---

## Reglas que aplican a TODAS las mejoras

- Seguir el flujo SDD+TDD del proyecto (spec → plan → tareas → implementar).
- Toda tabla nueva o modificada debe tener RLS y su política correspondiente.
- Sin secretos en el repo ni en el frontend.
- Comentarios y commits en español.
- **Git workflow:** cada cambio nuevo se trabaja en una rama creada desde `main`.
  Formato de rama: `feat/<nombre>`, `fix/<nombre>`, `refactor/<nombre>`.
  Nunca pushear directo a main.
