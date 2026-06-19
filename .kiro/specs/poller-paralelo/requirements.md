# Requirements Document

## Introduction

El poller de ingesta de correos (`POST /interno/poller/correo`) procesa las
casillas Gmail de todas las empresas en serie: un bucle `for` secuencial que,
para cada integración, descarga correos nuevos y los clasifica con Haiku. Con N
empresas conectadas, el tiempo total es N × (descarga + clasificación), lo que
puede superar fácilmente el timeout de Cloud Scheduler cuando el número de
tenants crece.

La solución es paralelizar la ingesta usando `asyncio.gather()` con un
`asyncio.Semaphore` que respete el rate-limit de Anthropic (clasificación con
Haiku) y el límite de conexiones simultáneas a Gmail. El fallo de una empresa
no debe cortar a las demás (aislamiento existente preservado).

---

## Requirements

### Requirement 1: Ejecución paralela con semáforo

**User Story:** Como operador del sistema, quiero que el poller procese las
casillas Gmail en paralelo (con concurrencia acotada), para reducir el tiempo
total de ingesta de N × T a max(T) + overhead.

#### Acceptance Criteria

1. THE endpoint `POST /interno/poller/correo` SHALL crear un
   `asyncio.Semaphore(concurrencia_max)` para limitar las ingestas concurrentes.
2. THE valor de `concurrencia_max` SHALL ser configurable vía variable de entorno
   (default: 5).
3. THE endpoint SHALL reemplazar el bucle `for` secuencial por
   `asyncio.gather(*[procesar(i) for i in integraciones], return_exceptions=True)`
   o equivalente con el semáforo.
4. WHEN hay más integraciones que el semáforo permite, THE Sistema SHALL encolarse
   sin cancelar las que esperan.

---

### Requirement 2: Aislamiento de fallos por empresa

**User Story:** Como operador, quiero que si una empresa falla (tokens caídos,
timeout de Gmail, error de BD), las demás sigan procesándose normalmente.

#### Acceptance Criteria

1. WHEN una empresa lanza `ErrorAutenticacionGmail`, THE Sistema SHALL marcarla
   como `reconectar` y continuar con las demás (comportamiento actual preservado).
2. WHEN una empresa lanza cualquier otro error, THE Sistema SHALL logear el error
   sin marcar `reconectar` y continuar con las demás.
3. THE conteo final de `empresas_procesadas` y `solicitudes_creadas` SHALL
   reflejar correctamente los resultados parciales (las que tuvieron éxito suman,
   las que fallaron no).
4. THE `ResumenPoller` devuelto SHALL ser consistente con el procesamiento
   paralelo (mismo esquema de respuesta).

---

### Requirement 3: Respeto del rate-limit de Anthropic

**User Story:** Como desarrollador, quiero que la concurrencia no dispare más
llamadas simultáneas a Haiku de las que el plan de API soporta, para evitar
errores 429.

#### Acceptance Criteria

1. THE semáforo SHALL limitar el número de clasificaciones Haiku ejecutándose
   simultáneamente al valor de `concurrencia_max`.
2. WHEN Anthropic devuelve un 429 (rate limit), THE Sistema SHALL reintentar con
   backoff exponencial (o dejar que la empresa falle y se reintente en el próximo
   ciclo del poller).
3. THE Sistema SHALL NO bloquear indefinidamente: si una empresa no avanza en un
   tiempo razonable (configurable, default 60s), se abandona su procesamiento y
   se sigue con las demás.

---

### Requirement 4: Test de paralelización

**User Story:** Como desarrollador, quiero un test que demuestre que dos empresas
se procesan "a la vez" (no secuencialmente), para tener confianza en la
paralelización.

#### Acceptance Criteria

1. THE Sistema SHALL incluir un test que verifique que dos integraciones se
   procesan concurrentemente (p.ej. midiendo que el tiempo total es menor que la
   suma de los tiempos individuales, o verificando que ambas corren dentro del
   mismo `gather`).
2. THE test SHALL usar mocks (no llamar a Gmail ni Anthropic reales).
3. WHEN `cd apps/api && .venv/bin/python -m pytest -q` se ejecuta, SHALL pasar
   todos los tests sin fallos.

---

## Tasks

- [ ] 1. Agregar setting `POLLER_CONCURRENCIA_MAX` (default 5) en `app/config.py`
- [ ] 2. Agregar `asyncio.Semaphore(concurrencia_max)` en el endpoint del poller
- [ ] 3. Cambiar el `for` serial por `asyncio.gather(*[procesar(i) for i in integraciones])` con el semáforo envolviendo cada tarea
- [ ] 4. Mantener el aislamiento de fallos: `ErrorAutenticacionGmail` → reconectar; otro error → solo logear
- [ ] 5. Agregar test que verifica que dos empresas se procesan concurrentemente (timing o interleaving)
- [ ] 6. Verificar `cd apps/api && .venv/bin/python -m pytest -q` en verde
