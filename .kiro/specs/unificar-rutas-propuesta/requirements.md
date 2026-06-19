# Requirements Document

## Introduction

El CRUD de propuestas/cotización está disperso en múltiples prefijos de ruta:

- **Crear/obtener/transicionar:** `POST|GET|PATCH /solicitudes/{id}/propuesta`
- **Listar propuestas:** `GET /propuestas`
- **Exportar (Excel/PPTX):** `GET /solicitudes/{id}/propuesta/exportar/{formato}`
- **Sincronizar ClickUp:** `POST /solicitudes/{id}/propuesta/clickup`

Esta dispersión no es un bug funcional — todo opera correctamente — pero genera
confusión para desarrolladores nuevos y para el frontend al mapear rutas. Además,
violar un estilo REST consistente dificulta la documentación de la API.

Sin embargo, **cambiar las URLs es un breaking change para el frontend**. Esta
spec tiene como objetivo principal **documentar el contrato actual** y evaluar si
existe una migración no-breaking (aliases con deprecation header). La
recomendación por defecto es diferir el cambio real (es cosmético) y solo
documentar.

---

## Requirements

### Requirement 1: Documentación del contrato actual

**User Story:** Como desarrollador nuevo en el proyecto, quiero un documento
claro de todos los endpoints de propuestas/cotización con su ruta, método,
cuerpo y respuesta, para entender el contrato sin leer el código.

#### Acceptance Criteria

1. THE spec SHALL documentar TODOS los endpoints que tocan propuestas/cotización:
   - `POST /solicitudes/{id}/propuesta` (crear)
   - `GET /solicitudes/{id}/propuesta` (obtener detalle)
   - `PATCH /solicitudes/{id}/propuesta` (transicionar estado)
   - `GET /propuestas` (listar resúmenes)
   - `GET /solicitudes/{id}/propuesta/exportar/{formato}` (Excel/PPTX)
   - `POST /solicitudes/{id}/propuesta/clickup` (sincronizar)
2. EACH endpoint documentado SHALL incluir: método HTTP, ruta completa, body
   esperado (si aplica), response model, y autenticación requerida.
3. THE documentación SHALL vivir en un archivo Markdown dentro de esta spec
   (p.ej. `contrato-propuestas.md`).

---

### Requirement 2: Análisis de migración no-breaking

**User Story:** Como arquitecto del backend, quiero saber si existe una forma de
unificar las rutas sin romper el frontend, para tomar una decisión informada.

#### Acceptance Criteria

1. THE análisis SHALL evaluar la opción de aliases (rutas nuevas que coexisten con
   las viejas) con un header `Deprecation` en las rutas viejas.
2. THE análisis SHALL evaluar el costo: ¿cuántos endpoints del frontend habría que
   actualizar si se migra?
3. THE análisis SHALL concluir con una recomendación: migrar ahora, migrar después,
   o no migrar (con justificación).
4. IF la recomendación es diferir, THE spec SHALL documentar claramente que esto
   es deuda cosmética sin impacto funcional.

---

### Requirement 3: Decisión documentada

**User Story:** Como product owner, quiero que la decisión (migrar o diferir)
quede explícitamente registrada en la spec, para que futuros desarrolladores
no reabran el debate.

#### Acceptance Criteria

1. THE spec SHALL incluir una sección "Decisión" con la conclusión: migrar,
   diferir, o no hacer nada.
2. IF se decide diferir, THE Sistema SHALL NO crear tareas de implementación
   (solo las tareas de documentación).
3. IF se decide migrar, THE spec SHALL incluir tareas ordenadas con el frontend
   como última migración (primero aliases backend, luego frontend, luego borrar
   aliases).

---

## Tasks

- [ ] 1. Documentar el contrato actual de todos los endpoints de propuestas/cotización (método, ruta, body, response, auth)
- [ ] 2. Identificar si hay una migración no-breaking viable (aliases + deprecation header)
- [ ] 3. Evaluar el costo de la migración en el frontend (cuántas llamadas habría que cambiar)
- [ ] 4. Escribir la sección "Decisión" con la recomendación final (recomendación: diferir, es cosmético y no tiene impacto funcional)
