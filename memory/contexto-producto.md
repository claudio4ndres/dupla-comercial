# Contexto de producto · Dupla Comercial

Memoria de referencia para Claude. Complementa `CLAUDE.md`.

## Flujo completo (validado con el cliente)

1. **Llega correo / solicitud** (vía Gmail).
2. **Leer el correo** — el sistema muestra un **resumen** + botón "Ver correo
   completo". El humano siempre puede leer el original (no perder oportunidades).
3. **¿Qué tipo de solicitud es?** — el sistema sugiere, el humano confirma:
   - **Tipo 1 · Cotización concreta** → definir qué cotizar.
   - **Tipo 2 · Ideas / propuesta creativa** → proponer conceptos.
4. **Conversación con Javo (SIEMPRE, ambos tipos).**
   - En Tipo 2, si el usuario lo pide, Javo **busca ideas en internet** y devuelve
     resultados a la conversación.
5. **Definir componentes** — se **consulta el Drive** (tarifarios, costos,
   casos anteriores). Componentes típicos: catering, promotores, producto,
   uniforme, horas, valores.
6. **Se arman las tareas.**
7. **ClickUp / API** — crear reportes y tareas.
8. **Enviar** — exportar a PPT / Excel y mandar la propuesta.

Soporte transversal: **Drive** (biblioteca de recursos) y la **App** que usa el
GP (gestor de proyecto).

## Decisiones técnicas tomadas
- **Sin WhatsApp:** la conversación vive en la app web, para controlar costos.
- **Enrutar modelos:** Haiku 4.5 (clasificar/resumir, barato), Sonnet 4.6
  (conversar). Prompt caching del system prompt + contexto del correo.
- **Multi-tenant:** una sola base con `empresa_id` + RLS de Supabase. Cada empresa
  (Capsulab, Espiga, …) tiene su espacio aislado. White-label por `color_marca`.
- **Despliegue:** Cloud Run (front y back) en Google Cloud; Supabase gestionado;
  tokens de integraciones en Secret Manager.

## Tablas (todas en español)
empresas · usuarios · solicitudes · conversaciones · mensajes · propuestas ·
componentes_propuesta · tareas · integraciones.
Ver `supabase/migrations/0001_esquema_inicial.sql`.

## Glosario
- **Javo:** el asistente conversacional (LLM de Claude) y nombre con el que los
  clientes saludan en los correos.
- **GP:** gestor de proyecto (la persona que opera la app).
- **Tipo 1 / Tipo 2:** los dos modos de solicitud (cotización vs ideas).
