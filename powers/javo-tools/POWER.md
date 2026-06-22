---
name: "javo-tools"
displayName: "Javo · Agente y Herramientas"
description: "Guía para entender y extender el agente conversacional Javo: cómo funciona el loop de tool-use, cómo agregar herramientas nuevas y buenas prácticas"
keywords: ["javo", "agente", "tool-use", "claude", "sonnet", "herramientas", "drive", "conversacion"]
author: "RukkumansLabs"
---

# Javo · Agente Conversacional con Herramientas

## Overview

Javo es el asistente conversacional de Dupla Comercial. Usa Claude Sonnet 4.6 con
un loop manual de tool-use para buscar datos reales, proponer componentes y tareas.

NO es un wrapper de LLM: es un AGENTE que ejecuta herramientas en el backend.

## Arquitectura del agente

```
Usuario → POST /conversaciones/responder
          → responder_javo() en servicios/javo.py
              → Claude Sonnet (system prompt + historial)
              → Si stop_reason == "tool_use":
                  → Ejecutar herramientas en el backend
                  → Devolver tool_result a Claude
                  → Repetir (max 6 iteraciones)
              → Devolver texto + componentes + tareas + fuentes
```

## Herramientas disponibles

| Tool | Qué hace | Cuándo se usa |
|------|----------|---------------|
| `buscar_en_drive` | Busca en TODO el Drive (nombre + contenido) | Siempre que necesita un precio/dato |
| `leer_documento_drive` | Abre un doc y devuelve su texto | Después de buscar, para leer el tarifario |
| `buscar_en_internet` | Web search de Anthropic (server tool) | Solo Tipo 2, solo si el usuario lo pide |
| `proponer_componentes` | Registra componentes de la cotización | Cuando Javo decide qué cotizar |
| `proponer_tareas` | Registra tareas de ejecución | Cuando Javo define el plan de trabajo |

## Cómo agregar una herramienta nueva

### 1. Definir la tool en `servicios/javo.py`

```python
def _tool_mi_herramienta() -> dict:
    return {
        "name": "mi_herramienta",
        "description": "Qué hace y cuándo usarla (Javo lee esto para decidir)",
        "input_schema": {
            "type": "object",
            "properties": {
                "parametro": {"type": "string", "description": "..."},
            },
            "required": ["parametro"],
        },
    }
```

### 2. Agregarla al array de herramientas

En `_herramientas(permitir_internet)`:
```python
tools.append(_tool_mi_herramienta())
```

### 3. Implementar la ejecución

En `_ejecutar_herramienta(bloque, ...)`:
```python
if nombre == "mi_herramienta":
    resultado = await mi_servicio.hacer_algo(entrada.get("parametro", ""))
    return (resultado, usos_internet)
```

### 4. Inyectar dependencias

Si la herramienta necesita un servicio externo:
- Agregarlo como parámetro de `responder_javo(..., mi_servicio=None)`
- Inyectarlo desde `rutas/conversaciones.py` vía `Depends`

## System prompt

El system prompt tiene 3 partes:
1. **Persona** (`_PERSONA`): quién es Javo (comercial senior, no pasivo)
2. **Guía del tipo** (`_GUIA_T1` / `_GUIA_T2`): cómo actuar según el tipo de solicitud
3. **Cache control**: `"cache_control": {"type": "ephemeral"}` (regla #4)

## Reglas del agente

1. **Nunca inventar precios** — si no está en el Drive, pedir el dato
2. **Citar fuentes** — todo dato usado se registra como `Fuente`
3. **Buscar antes de proponer** — primero `buscar_en_drive`, luego `proponer_componentes`
4. **Loop acotado** — máximo 6 iteraciones, máximo 5 búsquedas internet
5. **Degradación limpia** — si una tool falla, no rompe el loop
6. **LLM solo en el backend** — el frontend nunca habla con Claude

## Costos y optimización

| Modelo | Uso | Costo aprox. |
|--------|-----|--------------|
| Haiku 4.5 | Clasificar (1 llamada/correo) | ~$0.001/correo |
| Haiku 4.5 | Chips dinámicos (1 llamada/chat) | ~$0.001/chat |
| Sonnet 4.6 | Conversar (1-6 llamadas/turno) | ~$0.02-0.08/turno |
| Web Search | Buscar internet (server tool) | ~$0.01/búsqueda |

**Optimizaciones aplicadas:**
- Prompt caching (`cache_control: ephemeral`) en el system prompt
- Enrutamiento por costo (Haiku para tareas baratas, Sonnet para el chat)
- Tope de iteraciones y búsquedas por conversación
