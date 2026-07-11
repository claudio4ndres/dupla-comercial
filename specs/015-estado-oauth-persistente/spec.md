# Spec 015 · State OAuth persistente + cache de access token

- **Estado:** aprobada
- **Tipo:** backend + datos
- **Relacionada con:** conectores Gmail/Drive/ClickUp (OAuth por empresa), multi-instancia

## 1. Problema y por qué

1. El `state` anti-CSRF de los flujos OAuth vive **en memoria del proceso**: con
   más de una instancia de Cloud Run, el callback puede aterrizar en una instancia
   distinta a la que inició el flujo y el usuario ve "state inválido" al conectar
   Gmail/ClickUp. Además un reinicio pierde los states en vuelo.
2. Gmail y Drive canjean el refresh token por un access token **en cada
   operación**: cada tool-call de Javo al Drive y cada pase del poller paga un
   round-trip OAuth innecesario (el access token dura ~1 hora).

## 2. Usuarios y contexto

Invisible: conectar Gmail/ClickUp se vuelve confiable con múltiples instancias y
Javo/poller ganan latencia.

## 3. Alcance

**Incluye:**
- Tabla `estados_oauth` (state → empresa, con expiración) y
  `AlmacenEstadoOAuthSupabase` con consumo **atómico** (anti-replay entre
  instancias). Selección por `ESTADO_OAUTH_BACKEND` (`supabase` default /
  `memoria` dev-tests), espejo de `SECRETOS_BACKEND`.
- `CacheTokenAcceso` en proceso (token_ref → access token con TTL
  `expires_in - 60s`) compartido por las fábricas de Gmail y Drive.
- Limpieza: eliminar `drive_folder_id` (código muerto con dato del cliente
  piloto) y marcar T3-T8 de la spec 010 (ya implementadas en el código).

**No incluye (fuera de alcance):**
- Gmail push en tiempo real (spec 011, diferida).
- Cache distribuido (el cache de token es best-effort por proceso).

## 4. Criterios de aceptación (de aquí salen los tests)

- **CA1** — Dado `guardar(state, empresa)`, Cuando se mira la petición, Entonces
  es un POST a `estados_oauth` con service role y `expira_en` (~10 min).
- **CA2** — Dado un state vigente, Cuando se `consumir`, Entonces es un DELETE
  con `Prefer: return=representation` filtrando por expiración y devuelve la
  empresa; un state inexistente o expirado devuelve `None`.
- **CA3** — Dado el mismo state consumido dos veces (cualquier backend), Entonces
  la segunda vez devuelve `None` (un solo uso, anti-replay).
- **CA4** — Dado dos operaciones seguidas de Gmail/Drive con cache, Entonces solo
  se canjea UN access token; expirado el TTL (reloj falso) se vuelve a canjear;
  un fallo de auth no se cachea.

## 5. Consideraciones multi-tenant

`estados_oauth` es tabla de **infraestructura del backend**: RLS habilitada SIN
políticas → ningún JWT de usuario puede tocarla; solo la service role. El
aislamiento lo da que el `state` es opaco (token_urlsafe) y el backend fija
`empresa_id` al guardarlo. Excepción documentada a la regla #2 (no hay filas de
usuario que filtrar).

## 6. Aclaraciones pendientes

- Ninguna.
