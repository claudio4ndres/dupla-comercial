# Requirements Document

## Introduction

Actualmente, cada petición a Supabase (PostgREST) abre y cierra una conexión TCP
nueva: el método `_peticion()` usa `async with httpx.AsyncClient()` cuando no se
inyecta un cliente externo. En producción esto significa que cada request del
usuario dispara al menos 1–3 conexiones TCP independientes a Supabase (DNS lookup
+ TLS handshake + HTTP/2 negotiation por cada una), agregando latencia innecesaria.

La solución es reutilizar un `httpx.AsyncClient` compartido con connection pooling
(HTTP/2, keep-alive), inyectado como dependencia de FastAPI desde `dependencias.py`.
El cliente se crea al arrancar la app y se cierra limpiamente al apagar (lifespan).

Esto es compatible con el patrón existente: los repos ya aceptan un parámetro
`cliente` en el constructor; en los tests se sigue inyectando un mock de
transporte.

---

## Requirements

### Requirement 1: Singleton de httpx.AsyncClient con connection pooling

**User Story:** Como operador del sistema, quiero que las peticiones a Supabase
reutilicen conexiones TCP, para reducir la latencia de red y el consumo de
sockets.

#### Acceptance Criteria

1. THE Sistema SHALL crear un `httpx.AsyncClient` compartido con connection
   pooling en `dependencias.py` (o un módulo auxiliar importado desde ahí).
2. THE cliente SHALL configurarse con `http2=True` y límites de conexión
   razonables (p.ej. `httpx.Limits(max_connections=100, max_keepalive_connections=20)`).
3. THE cliente SHALL ser un singleton a nivel de proceso (no se crea uno nuevo por
   request).
4. THE Sistema SHALL exponer una función/dependencia `obtener_cliente_http()` que
   retorne el cliente compartido.

---

### Requirement 2: Inyección del cliente en los repositorios

**User Story:** Como desarrollador, quiero que los repos Supabase reciban el
cliente compartido vía el constructor, para aprovechar el pooling sin cambiar la
interfaz pública.

#### Acceptance Criteria

1. WHEN se construye un repositorio Supabase en `dependencias.py`, THE Sistema
   SHALL pasar el `httpx.AsyncClient` compartido como parámetro `cliente`.
2. THE `_peticion()` del repo SHALL usar el cliente inyectado directamente (sin
   `async with`) cuando `self._cliente` no es `None`.
3. WHEN `self._cliente` es `None` (edge case o tests sin inyección), THE
   `_peticion()` SHALL crear un cliente efímero como fallback.
4. THE Sistema SHALL NO cambiar la firma del constructor de los repos (el
   parámetro `cliente` ya existe como opcional).

---

### Requirement 3: Cleanup del cliente al shutdown de la app

**User Story:** Como operador, quiero que el cliente HTTP se cierre limpiamente
al apagar el servicio, para evitar warnings de conexiones no cerradas y leaks de
recursos.

#### Acceptance Criteria

1. THE Sistema SHALL registrar el cierre del `httpx.AsyncClient` en el lifespan
   de la app FastAPI (`@asynccontextmanager` en `main.py` o similar).
2. WHEN la app se apaga (SIGTERM / shutdown), THE Sistema SHALL llamar
   `await cliente.aclose()` sobre el cliente compartido.
3. AFTER el cierre, THE Sistema SHALL NO intentar usar el cliente para nuevas
   peticiones.

---

### Requirement 4: Compatibilidad con tests existentes

**User Story:** Como desarrollador, quiero que los tests sigan funcionando con
mocks de transporte sin depender del cliente compartido de producción.

#### Acceptance Criteria

1. WHEN los tests sobrescriben las dependencias con `app.dependency_overrides`,
   THE Sistema SHALL seguir recibiendo el mock de transporte inyectado (el pooling
   de producción no interfiere).
2. WHEN `cd apps/api && .venv/bin/python -m pytest -q` se ejecuta, SHALL pasar
   todos los tests sin fallos.
3. THE refactor SHALL NO romper los tests que inyectan un `httpx.AsyncClient` con
   `MockTransport`.

---

## Tasks

- [ ] 1. Crear el singleton de `httpx.AsyncClient` con connection pooling en `dependencias.py` (o módulo `app/http_pool.py`)
- [ ] 2. Exponer dependencia `obtener_cliente_http()` para inyección en FastAPI
- [ ] 3. Modificar los providers de repositorios en `dependencias.py` para pasar `cliente=obtener_cliente_http()` al construir cada repo
- [ ] 4. Agregar el lifespan (startup/shutdown) en `main.py` para abrir y cerrar el cliente compartido
- [ ] 5. Verificar `cd apps/api && .venv/bin/python -m pytest -q` en verde
