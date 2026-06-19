# Requirements Document

## Introduction

El endpoint `GET /clickup/listas` actualmente hace "auto-heal": si detecta que
la integración ClickUp de la empresa está en un estado inconsistente (p.ej. token
inválido), muta el estado de la integración (la marca como `reconectar` o la
repara). Esto viola la semántica REST: un GET es idempotente y libre de side
effects por definición (RFC 7231 §4.2.1). Un usuario o proxy puede cachear o
reintentar un GET sin esperar que mute estado en el servidor.

La solución es extraer la lógica de auto-heal a una función helper reutilizable y
exponerla en un nuevo endpoint `POST /clickup/verificar`. El GET queda puro:
solo lee y devuelve las listas de ClickUp de la empresa sin mutar nada. Si la
integración está rota, devuelve un error o lista vacía, pero no intenta repararla.

---

## Requirements

### Requirement 1: GET /clickup/listas sin side effects

**User Story:** Como desarrollador frontend, quiero que `GET /clickup/listas`
sea un endpoint puro (sin mutaciones), para poder cachearlo y reintentarlo sin
riesgo de efectos secundarios.

#### Acceptance Criteria

1. WHEN `GET /clickup/listas` es llamado, THE endpoint SHALL únicamente leer las
   listas del workspace ClickUp de la empresa y devolverlas.
2. THE endpoint SHALL NO mutar el estado de la integración ClickUp (no llamar a
   `marcar_estado` ni escribir en la tabla `integraciones`).
3. IF la integración ClickUp no existe o no tiene token válido, THE endpoint SHALL
   devolver una lista vacía `[]` (comportamiento degradado limpio, sin excepción).
4. IF el token de ClickUp falla al listar (401/403 de ClickUp), THE endpoint SHALL
   devolver un error informativo (p.ej. 502 con detalle) SIN mutar el estado de
   la integración.

---

### Requirement 2: POST /clickup/verificar con auto-heal

**User Story:** Como frontend, quiero un endpoint explícito que verifique y repare
la integración ClickUp de mi empresa, para invocarlo solo cuando el usuario lo
pide (no implícitamente en cada carga de listas).

#### Acceptance Criteria

1. THE Sistema SHALL crear un endpoint `POST /clickup/verificar` que ejecute la
   lógica de auto-heal extraída del GET.
2. WHEN la verificación detecta un token inválido, THE endpoint SHALL marcar la
   integración como `reconectar` y devolver el nuevo estado.
3. WHEN la verificación detecta que todo está OK, THE endpoint SHALL devolver un
   estado `conectado` (sin mutar nada si ya estaba conectado).
4. THE endpoint SHALL requerir autenticación (JWT del usuario) y filtrar por su
   empresa (RLS, regla de oro #2).
5. THE response model SHALL incluir al menos: `estado` (str), `mensaje` (str
   opcional con detalle del diagnóstico).

---

### Requirement 3: Extracción del auto-heal a helper

**User Story:** Como desarrollador, quiero que la lógica de auto-heal viva en una
función helper reutilizable, para que el POST la use sin duplicar código.

#### Acceptance Criteria

1. THE Sistema SHALL extraer la lógica de auto-heal de `GET /clickup/listas` a
   una función helper (p.ej. `verificar_integracion_clickup(...)` en un módulo
   de servicios o en el mismo archivo de rutas).
2. THE helper SHALL recibir las dependencias necesarias como parámetros (repo
   integraciones, cliente ClickUp, empresa_id).
3. THE helper SHALL ser testeable de forma aislada (sin montar el endpoint
   completo).

---

### Requirement 4: Actualización del frontend (si aplica)

**User Story:** Como usuario, quiero que la verificación de ClickUp siga
funcionando aunque ahora sea un endpoint separado.

#### Acceptance Criteria

1. IF el frontend invocaba el auto-heal implícitamente al cargar listas, THE spec
   SHALL documentar que el frontend debe llamar a `POST /clickup/verificar`
   explícitamente (p.ej. al presionar un botón "Verificar conexión").
2. THE migración del frontend SHALL ser backward-compatible: si el front no se
   actualiza inmediatamente, solo pierde el auto-heal (las listas siguen
   cargándose normalmente, solo que no reparan la integración solas).
3. THE spec SHALL documentar el cambio de contrato para el frontend en un
   comentario o nota visible.

---

### Requirement 5: Tests

**User Story:** Como desarrollador, quiero tests que verifiquen que el GET ya no
muta estado y que el POST sí lo hace.

#### Acceptance Criteria

1. THE Sistema SHALL incluir un test donde `GET /clickup/listas` se llama con un
   token inválido: verifica que NO se llama a `marcar_estado`.
2. THE Sistema SHALL incluir un test donde `POST /clickup/verificar` se llama con
   un token inválido: verifica que SÍ se marca `reconectar`.
3. THE Sistema SHALL incluir un test donde `POST /clickup/verificar` con token
   válido devuelve `estado: "conectado"` sin mutar.
4. WHEN `cd apps/api && .venv/bin/python -m pytest -q` se ejecuta, SHALL pasar
   sin fallos.

---

## Tasks

- [ ] 1. Extraer la lógica de auto-heal de `GET /clickup/listas` a una función helper `verificar_integracion_clickup()`
- [ ] 2. Crear `POST /clickup/verificar` que ejecuta el auto-heal y devuelve el estado resultante
- [ ] 3. Modificar `GET /clickup/listas` para que solo lea y devuelva listas (sin mutar estado)
- [ ] 4. Agregar test: GET con token inválido NO llama a `marcar_estado`
- [ ] 5. Agregar test: POST /verificar con token inválido SÍ marca `reconectar`
- [ ] 6. Agregar test: POST /verificar con token válido devuelve `"conectado"` sin mutar
- [ ] 7. Documentar el cambio de contrato para el frontend (nota en la spec o comentario en el código)
- [ ] 8. Verificar `cd apps/api && .venv/bin/python -m pytest -q` en verde
