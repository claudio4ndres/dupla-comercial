# Requirements Document

## Introduction

El paquete `anthropic>=0.40` sigue declarado como dependencia de producción en
`pyproject.toml`, pero el código de producción ya NO usa el SDK oficial: el
`ClienteAnthropicHttpx` habla directo con la Messages API vía httpx (decisión
documentada en `dependencias.py` — el import del SDK tardaba ~1s y arrastraba
~1800 módulos).

Mantener la dependencia declarada tiene costos reales:
- Agranda la imagen Docker (~15 MB de paquetes transitivos).
- Ralentiza `pip install` / `uv sync` en CI.
- Genera confusión: un dev nuevo podría asumir que el SDK se usa y empezar a
  importarlo.

La solución es verificar si algún path de producción (`app/`) importa el SDK. Si
solo se importa para type hints (o no se importa en absoluto), eliminarlo de las
dependencias. Si hay tipos del SDK usados como type hints, reemplazarlos por
Protocol o TypeVar equivalente.

---

## Requirements

### Requirement 1: Auditoría de imports del SDK anthropic

**User Story:** Como desarrollador, quiero saber exactamente qué archivos de
producción importan el paquete `anthropic`, para decidir si es seguro eliminarlo.

#### Acceptance Criteria

1. THE Sistema SHALL buscar todos los `import anthropic` y
   `from anthropic import ...` en `app/` (recursivo).
2. THE resultado SHALL clasificar cada import como:
   - "producción real" (se ejecuta en runtime), o
   - "solo type hint" (dentro de `if TYPE_CHECKING` o en anotaciones que no se
     evalúan en runtime).
3. IF hay imports de producción real, THE Sistema SHALL documentarlos y evaluar si
   pueden reemplazarse por la interfaz httpx existente.

---

### Requirement 2: Reemplazo de type hints del SDK (si aplica)

**User Story:** Como desarrollador, quiero que los type hints no dependan de un
paquete que no se usa en runtime, para que la eliminación sea limpia.

#### Acceptance Criteria

1. IF algún type hint usa tipos del SDK anthropic (p.ej. `anthropic.types.Message`),
   THE Sistema SHALL reemplazarlo por un Protocol o TypeVar equivalente definido
   localmente.
2. THE reemplazo SHALL mantener la misma semántica de tipo (los atributos
   accedidos deben estar declarados en el Protocol).
3. THE cambio SHALL NO romper MyPy/Pyright si se usa un checker de tipos (o al
   menos no romper pytest).

---

### Requirement 3: Eliminación de la dependencia

**User Story:** Como operador, quiero reducir el tamaño de la imagen Docker y el
tiempo de instalación eliminando dependencias que no se usan.

#### Acceptance Criteria

1. AFTER verificar que no hay imports de producción real, THE Sistema SHALL
   eliminar `"anthropic>=0.40"` de la lista `dependencies` en `pyproject.toml`.
2. THE Sistema SHALL regenerar el lockfile (`uv.lock` o `requirements.txt`) si
   corresponde.
3. WHEN el backend arranca (`uvicorn app.main:app`), THE Sistema SHALL importar
   todos los módulos sin `ModuleNotFoundError`.
4. THE `ProveedorBusquedaWeb` SHALL seguir funcionando: usa
   `cliente.messages.create` que es del `ClienteAnthropicHttpx` (no del SDK).

---

### Requirement 4: Tests en verde y arranque limpio

**User Story:** Como desarrollador, quiero certeza de que la eliminación no rompe
nada en el proyecto.

#### Acceptance Criteria

1. WHEN `cd apps/api && .venv/bin/python -m pytest -q` se ejecuta, SHALL pasar
   sin fallos.
2. WHEN el backend arranca sin el SDK instalado, SHALL no haber import errors ni
   warnings relevantes.
3. THE `ProveedorBusquedaWeb` SHALL funcionar correctamente (test existente o
   nuevo que verifica que `messages.create` se llama vía httpx, no vía el SDK).

---

## Tasks

- [ ] 1. Buscar todos los imports de `anthropic` en el código de producción (`app/`) con grep recursivo
- [ ] 2. Clasificar cada import: producción real vs. solo type hint vs. no existe
- [ ] 3. Si hay type hints del SDK, reemplazarlos por Protocol/TypeVar local
- [ ] 4. Eliminar `"anthropic>=0.40"` de `pyproject.toml`
- [ ] 5. Verificar que el backend arranca sin errores (`python -c "from app.main import app"`)
- [ ] 6. Verificar que `ProveedorBusquedaWeb` funciona (test existente o nuevo)
- [ ] 7. Verificar `cd apps/api && .venv/bin/python -m pytest -q` en verde
