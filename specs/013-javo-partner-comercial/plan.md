# Plan 013 · Javo, partner comercial

## Arquitectura

Todo en `apps/api/app/servicios/javo.py` + el prompt de chips en
`apps/api/app/rutas/conversaciones.py`. Sin cambios de contrato HTTP.

1. **Prompt**: nueva constante de módulo `_CONDUCTA_COMERCIAL` (sin NADA dinámico)
   con las 4 conductas; `_system_para(tipo)` = persona + conducta + guía del tipo.
   Sigue siendo determinista por tipo → el caché solo se invalida una vez por
   deploy, jamás por request.
2. **Tool `consultar_tarifario`**: `_tool_consultar_tarifario()` PRIMERA en
   `_herramientas` (description prescriptiva: "úsala PRIMERO para precios
   estándar; si no está, busca en el Drive"). Ejecutor: reutiliza
   `_buscar_en_catalogo` SIEMPRE (aunque haya `cliente_drive`); si no hay
   catálogo, degrada con aviso propio.
3. **Chips**: prompt de Haiku y `_chips_fallback` orientados a partner
   (opciones de presupuesto, upsell, cierre).

## Estrategia de pruebas (TDD)

En `tests/test_javo_agente.py` (dobles guionados, cero red):
1. 🔴 CA1: orden fijo de `_herramientas(False/True)` con `consultar_tarifario`.
2. 🔴 CA2: guion con `tool_use consultar_tarifario` + Drive presente → el valor
   viene del catálogo, Fuente citada, el Drive no recibe consultas.
3. 🔴 CA3: dos `responder_javo` seguidos → `system` y nombres de tools idénticos
   entre `llamadas[0]` y `llamadas[1]`, con `cache_control` ephemeral.
4. 🔴 CA4: marcadores de conducta en `_system_para` (robustos a redacción).

Nuevo `tests/test_endpoint_sugerencias.py`:
5. 🔴 CA5: Haiku que falla → fallback comercial; Haiku ok → 3 chips del modelo.

🧑 Validación humana (no automatizable): sesión de chat T1 real verificando que
Javo pregunta lo que falta, da opción + alternativa, sugiere upsell y ofrece
generar la propuesta.

## Riesgos

- No tocar el orden relativo de las tools existentes salvo la inserción fija.
- El matiz `permitir_internet` ya hace variar el set de tools en t2 (asumido,
  no se empeora).
