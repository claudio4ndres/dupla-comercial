# Plan 012 · Resiliencia del cliente LLM

## Arquitectura

Todo el cambio vive en `apps/api/app/servicios/cliente_anthropic.py`. Ningún
llamador cambia: Javo, el clasificador y los chips comparten
`obtener_cliente_anthropic()` (dependencias.py) y reciben la mejora gratis.

- `ClienteAnthropicHttpx.__init__` y `_Mensajes` ganan parámetros con default:
  `reintentos: int = 2`, `espera_base: float = 1.0`, `dormir = asyncio.sleep`
  (inyectable para tests sin espera real).
- `_Mensajes.create` envuelve el POST en un bucle de hasta `reintentos + 1`
  intentos:
  - **Reintenta** ante status 408/429/500/529 y ante `httpx.TimeoutException` /
    `httpx.ConnectError`.
  - **No reintenta** 400/401/403/404/422 (errores del request, no transitorios).
  - Espera: `Retry-After` del response si viene; si no,
    `espera_base * 2**intento + jitter` (jitter uniforme para desincronizar el
    poller paralelo).
  - Agotados los intentos, relanza la última excepción (`HTTPStatusError` o la de
    red) → las rutas siguen convirtiendo en 502.

## Estrategia de pruebas (TDD)

En `apps/api/tests/test_cliente_anthropic_httpx.py`, con `httpx.MockTransport` y
un `dormir` falso que registra las esperas (cero sleep real):

1. 🔴 CA1: 429 (`Retry-After: 0.5`) → 200: responde ok, 2 POST, esperó 0.5.
2. 🔴 CA2: 529 siempre → `HTTPStatusError` tras `reintentos+1` POST.
3. 🔴 CA3: 400 → 1 solo POST, `HTTPStatusError` inmediato.
4. 🔴 CA4: `ConnectError` → 200: responde ok.
5. 🔴 CA5: 500×2 → 200 sin `Retry-After`: esperas exponenciales crecientes.
6. El test existente de propagación de 500 se ajusta para inyectar `dormir` falso
   (con reintentos, el 500 permanente sigue relanzando — mismo contrato).

## Riesgos

- Peor caso de latencia: timeout 60 s × 3 intentos. Aceptable para el poller;
  el chat rara vez verá más de 1 reintento (429 trae `Retry-After` corto).
- No usar el SDK `anthropic` para esto (arranque en frío de minutos, decisión
  documentada en el propio módulo).
