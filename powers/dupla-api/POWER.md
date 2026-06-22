---
name: "dupla-api"
displayName: "Dupla Comercial API"
description: "Documentación completa de la API FastAPI de Dupla Comercial: endpoints, contratos, autenticación y guías para agregar nuevos endpoints"
keywords: ["api", "fastapi", "endpoints", "backend", "dupla", "solicitudes", "propuestas"]
author: "RukkumansLabs"
---

# Dupla Comercial · API

## Overview

Backend FastAPI del SaaS multi-tenant Dupla Comercial. Sirve el flujo completo:
ingesta de correos → clasificación IA → conversación con Javo → propuesta → tareas → ClickUp.

Multi-tenant por RLS: cada request lleva un JWT de Supabase Auth y la RLS de Postgres
filtra los datos por empresa.

## Autenticación

Todos los endpoints (excepto `/salud` y `/interno/*`) requieren:
```
Authorization: Bearer <JWT de Supabase Auth>
```

Los endpoints `/interno/*` (poller, reproceso) usan:
```
X-Poller-Token: <secreto compartido>
```

## Endpoints

### Solicitudes
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /solicitudes | Lista solicitudes de la empresa (bandeja) |
| POST | /solicitudes/{id}/clasificar | Clasifica con Haiku (resumen + tipo) |
| GET | /solicitudes/{id}/propuesta | Obtiene la cotización resuelta |
| POST | /solicitudes/{id}/propuesta | Persiste la propuesta del chat |
| PATCH | /solicitudes/{id}/propuesta/estado | Transiciona estado (borrador→aprobada→enviada) |
| GET | /solicitudes/{id}/cotizacion.xlsx | Descarga Excel |
| GET | /solicitudes/{id}/propuesta.pptx | Descarga PPT |
| POST | /solicitudes/{id}/tareas/clickup | Envía tareas a ClickUp |

### Conversaciones
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | /conversaciones/responder | Chat con Javo (Sonnet + tool-use) |
| POST | /conversaciones/{id}/iniciar | Saludo inicial de Javo |
| POST | /conversaciones/{id}/sugerencias | Chips dinámicos (Haiku) |
| GET | /conversaciones/{id} | Historial del chat |
| GET | /conversaciones/{id}/cotizacion | Borrador de cotización en curso |

### Integraciones
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /integraciones/correo | Estado de conexión Gmail |
| POST | /gmail/iniciar | URL de consentimiento OAuth |
| GET | /gmail/callback | Callback OAuth de Google |
| DELETE | /integraciones/correo | Desconectar Gmail |

### ClickUp
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /clickup/listas | Listas del workspace |
| GET | /clickup/estado | Estado del conector |
| POST | /clickup/iniciar | URL de consentimiento OAuth |
| GET | /clickup/callback | Callback OAuth |
| POST | /clickup/verificar | Auto-heal de la integración |
| DELETE | /clickup | Desconectar ClickUp |

### Otros
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /empresa | Datos del tenant del usuario |
| GET | /propuestas | Lista de propuestas (menú) |
| GET | /tareas | Lista global de tareas |
| GET | /catalogo/recursos | Recursos del Drive |
| GET | /miembros | Roster del equipo |
| GET | /salud | Health check |

### Internos (service-to-service)
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | /interno/poller/correo | Ingesta de correos (Cloud Scheduler) |
| POST | /interno/reprocesar/correo | Re-clasifica solicitudes sin_clasificar |
| GET | /interno/conectores/reconectar | Lista integraciones caídas |
| POST | /interno/drive/diagnostico | Diagnóstico de Drive |

## Arquitectura

```
rutas/          → Endpoints HTTP (presentación)
servicios/      → Lógica de negocio (dominio)
repositorios/   → Acceso a datos (PostgREST vía httpx)
dependencias.py → Inyección de dependencias (Depends de FastAPI)
esquemas.py     → Modelos Pydantic (contratos)
config.py       → Variables de entorno (pydantic-settings)
```

## Cómo agregar un endpoint nuevo

1. Definir esquemas de entrada/salida en `esquemas.py`
2. Crear la ruta en `rutas/mi_recurso.py` (router con prefijo)
3. Registrar el router en `main.py`
4. Si necesita acceso a datos: crear el repo (Protocol + Supabase) en `repositorios/`
5. Agregar la dependencia en `dependencias.py`
6. Escribir el test en `tests/test_endpoint_mi_recurso.py`

## Reglas de oro

1. Base de datos 100% en español
2. Multi-tenant por RLS (nunca confiar solo en el backend)
3. LLM solo desde el backend (nunca exponer API key)
4. Enrutar modelos por costo: Haiku (clasificar) / Sonnet (conversar)
5. Comentarios en español
