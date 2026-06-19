# Requirements Document

## Introduction

El endpoint `POST /interno/reprocesar/correo` recorre las integraciones Gmail y
re-clasifica las solicitudes `sin_clasificar`. El bloque `except Exception` del
bucle principal tiene un fallo lógico: ante CUALQUIER error (BD, red, Secret
Manager, timeout), marca la integración como `reconectar`. Esto confunde al
usuario final: le muestra un aviso de "reconectar Gmail" cuando sus tokens están
perfectamente sanos y el error real es un 409 de BD o un fallo transitorio de
red.

En el poller principal (`POST /interno/poller/correo`) este bug ya fue corregido:
se distingue `ErrorAutenticacionGmail` (→ reconectar) de otros errores (→ solo
logear). Pero el endpoint de reproceso todavía tiene el patrón roto.

La solución es aplicar al reproceso la misma lógica discriminada del poller:
solo `ErrorAutenticacionGmail` marca `reconectar`; cualquier otro error se logea
y se sigue con las demás empresas sin tocar el estado de la integración.

---

## Requirements

### Requirement 1: Solo errores de autenticación marcan reconectar

**User Story:** Como usuario de Dupla Comercial, quiero que mi casilla Gmail NO
me pida reconectar cuando el error no es de autenticación, para no tener que
volver a autorizar tokens que están sanos.

#### Acceptance Criteria

1. WHEN el reproceso de una empresa lanza `ErrorAutenticacionGmail`, THE Sistema
   SHALL marcar la integración como `reconectar` vía
   `repo_integraciones.marcar_estado(empresa_id, "reconectar", "gmail")`.
2. WHEN el reproceso de una empresa lanza `ErrorAutenticacionGmail`, THE Sistema
   SHALL logear un warning con el `empresa_id` y continuar con las demás empresas.
3. WHEN el reproceso de una empresa lanza cualquier otro tipo de excepción, THE
   Sistema SHALL logear el error con `logging.exception()` y continuar con las
   demás SIN llamar a `marcar_estado`.
4. THE integración de una empresa que falla por un error NO-auth (BD, red,
   timeout) SHALL mantener su estado previo intacto (no se toca `reconectar`).

---

### Requirement 2: Aislamiento preservado entre empresas

**User Story:** Como operador, quiero que el fallo del reproceso de una empresa
no afecte a las demás, independientemente del tipo de error.

#### Acceptance Criteria

1. WHEN una empresa falla durante el reproceso (por auth o por otro motivo), THE
   Sistema SHALL continuar procesando las empresas restantes sin interrupción.
2. THE `ResumenReproceso` devuelto SHALL reflejar los totales correctos de las
   empresas que sí se procesaron exitosamente.
3. THE aislamiento SHALL funcionar tanto para la primera empresa como para la
   última de la lista (no hay posición privilegiada).

---

### Requirement 3: Consistencia con el poller principal

**User Story:** Como desarrollador, quiero que el reproceso maneje errores con
la misma lógica del poller principal, para evitar inconsistencias de
comportamiento entre endpoints internos.

#### Acceptance Criteria

1. THE patrón de manejo de errores del reproceso SHALL ser idéntico al del poller:
   dos bloques `except` separados, primero `ErrorAutenticacionGmail` luego
   `Exception`.
2. THE log del error NO-auth SHALL incluir un mensaje que indique que NO se marca
   `reconectar` porque las credenciales están sanas (igual que el poller).

---

### Requirement 4: Tests de discriminación de errores

**User Story:** Como desarrollador, quiero tests que verifiquen que solo errores
de auth marcan reconectar y que otros errores no lo hacen.

#### Acceptance Criteria

1. THE Sistema SHALL incluir un test donde el reproceso de una empresa lanza
   `ErrorAutenticacionGmail`: verifica que se llama a `marcar_estado` con
   `"reconectar"`.
2. THE Sistema SHALL incluir un test donde el reproceso de una empresa lanza un
   error genérico (p.ej. `RuntimeError`): verifica que NO se llama a
   `marcar_estado`.
3. WHEN `cd apps/api && .venv/bin/python -m pytest -q` se ejecuta, SHALL pasar
   sin fallos.

---

## Tasks

- [ ] 1. Cambiar el `except Exception` del reproceso para separar `ErrorAutenticacionGmail` (→ reconectar) de otros errores (→ solo logear sin marcar)
- [ ] 2. Agregar log descriptivo para el caso NO-auth: "credenciales sanas, no se marca reconectar"
- [ ] 3. Agregar test: error de auth SÍ marca reconectar
- [ ] 4. Agregar test: error genérico (BD, red) NO marca reconectar
- [ ] 5. Verificar `cd apps/api && .venv/bin/python -m pytest -q` en verde
