# Requirements Document

## Introduction

Los 7 repositorios `*_supabase.py` del backend (`solicitudes`, `catalogo`,
`conversaciones`, `integraciones`, `miembros`, `propuestas`, `tareas`) repiten
~20 líneas idénticas: constructor con `base_url`, `anon_key`, `jwt` y `cliente`
opcional, método `_headers()` que arma las cabeceras PostgREST con el JWT del
usuario, y método `_peticion()` que enruta la llamada al `httpx.AsyncClient`
inyectado o crea uno efímero.

Esta duplicación viola DRY, complica el mantenimiento (un cambio en la lógica de
headers obliga a tocar 7 archivos) y diluye la responsabilidad de cada repo
(mezcla infraestructura de transporte con lógica de dominio).

La solución es extraer una clase base `ClientePostgREST` que encapsule la lógica
común de conexión, y hacer que cada repo herede de ella conservando únicamente
sus métodos de dominio. Los tests existentes no deben romperse: la inyección del
`httpx.AsyncClient` para mocks sigue funcionando igual.

---

## Requirements

### Requirement 1: Clase base ClientePostgREST

**User Story:** Como desarrollador, quiero una clase base que encapsule la
conexión y autenticación contra PostgREST de Supabase, para no repetir esa lógica
en cada repositorio.

#### Acceptance Criteria

1. THE Sistema SHALL crear el archivo `app/repositorios/cliente_postgrest.py` con
   una clase `ClientePostgREST` que contenga:
   - Constructor que reciba `base_url: str`, `anon_key: str`, `jwt: str` y
     `cliente: httpx.AsyncClient | None = None`.
   - Método `_headers(extra: dict | None = None) -> dict` que retorne las
     cabeceras `apikey`, `Authorization` (Bearer + JWT) y `Content-Type`.
   - Método `async _peticion(metodo: str, ruta: str, **kw) -> httpx.Response` que
     use el cliente inyectado o cree uno efímero.
2. THE clase base SHALL calcular `self._base` como `base_url.rstrip("/") + "/rest/v1"`.
3. WHEN `cliente` es `None`, `_peticion` SHALL crear un `httpx.AsyncClient` efímero
   con `async with` para la llamada (comportamiento actual).
4. WHEN `cliente` es proporcionado, `_peticion` SHALL usarlo directamente sin
   crear uno nuevo.

---

### Requirement 2: Refactorización de RepositorioSolicitudesSupabase

**User Story:** Como desarrollador, quiero que `RepositorioSolicitudesSupabase`
herede de `ClientePostgREST` y elimine su código duplicado, como prueba de
concepto del refactor.

#### Acceptance Criteria

1. THE `RepositorioSolicitudesSupabase` SHALL heredar de `ClientePostgREST`.
2. THE archivo `solicitudes_supabase.py` SHALL eliminar el constructor duplicado,
   `_headers()` y `_peticion()`, delegando a `super().__init__(...)`.
3. WHEN los tests existentes de solicitudes se ejecutan, THE Sistema SHALL pasar
   todos sin modificación (la interfaz pública no cambia).

---

### Requirement 3: Refactorización de los 6 repositorios restantes

**User Story:** Como desarrollador, quiero que todos los repositorios Supabase
hereden de `ClientePostgREST`, para que la lógica de conexión viva en un solo
lugar.

#### Acceptance Criteria

1. THE Sistema SHALL refactorizar los siguientes repos para heredar de
   `ClientePostgREST`:
   - `catalogo_supabase.py`
   - `conversaciones_supabase.py`
   - `integraciones_supabase.py`
   - `miembros_supabase.py`
   - `propuestas_supabase.py`
   - `tareas_supabase.py`
2. EACH repositorio refactorizado SHALL eliminar su constructor, `_headers()` y
   `_peticion()` duplicados.
3. WHEN `pytest -q` se ejecuta, THE Sistema SHALL reportar todos los tests en verde.

---

### Requirement 4: Sin cambio de comportamiento observable

**User Story:** Como operador del sistema, quiero que el refactor sea transparente
para la aplicación en producción, sin alterar la firma de constructores ni el
comportamiento de los endpoints.

#### Acceptance Criteria

1. THE firma pública de cada repositorio (parámetros del constructor) SHALL
   permanecer idéntica para no romper `dependencias.py`.
2. THE refactor SHALL NO modificar `dependencias.py` (el cableado de repos sigue
   igual).
3. WHEN el backend arranca (`uvicorn`), THE Sistema SHALL importar todos los repos
   sin errores.
4. WHEN `cd apps/api && .venv/bin/python -m pytest -q` se ejecuta, SHALL pasar
   sin fallos.

---

## Tasks

- [ ] 1. Crear `app/repositorios/cliente_postgrest.py` con la clase base `ClientePostgREST` (constructor, `_headers`, `_peticion`)
- [ ] 2. Refactorizar `solicitudes_supabase.py` para heredar de `ClientePostgREST` y eliminar código duplicado
- [ ] 3. Refactorizar `catalogo_supabase.py` para heredar de `ClientePostgREST`
- [ ] 4. Refactorizar `conversaciones_supabase.py` para heredar de `ClientePostgREST`
- [ ] 5. Refactorizar `integraciones_supabase.py` para heredar de `ClientePostgREST`
- [ ] 6. Refactorizar `miembros_supabase.py` para heredar de `ClientePostgREST`
- [ ] 7. Refactorizar `propuestas_supabase.py` para heredar de `ClientePostgREST`
- [ ] 8. Refactorizar `tareas_supabase.py` para heredar de `ClientePostgREST`
- [ ] 9. Verificar `cd apps/api && .venv/bin/python -m pytest -q` en verde
