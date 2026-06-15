# Setup de Supabase desde cero — Dupla Comercial (guía de autoayuda)

> Objetivo: montar un proyecto Supabase **limpio** bajo la organización de la empresa
> (RukkumansLabs), aplicar el esquema, conectar el backend (Cloud Run) y reconectar los
> conectores. Pensada para seguirla sola, paso a paso. 🧑 = lo haces tú · 🤖 = lo puede
> hacer el agente.

> ⚠️ **Implicancia de "empezar de cero":** el proyecto nuevo arranca **vacío**. Los datos
> del proyecto viejo (correos ya ingeridos, integraciones) **no se migran solos** → al
> final hay que **reconectar Gmail / Drive / ClickUp**. El esquema sí se reproduce con las
> migraciones. (El app no se cae mientras tanto: sigue apuntando al proyecto viejo hasta
> que cambies las keys en el paso 5.)

---

## 0. Antes de empezar (ten a mano)
- La cuenta de Gmail que **SÍ controlas** (la sesión actual del dashboard).
- El repo clonado, con las migraciones en `supabase/migrations/` (0001 → 0009).
- Acceso a **Cloud Run** (gcloud) del proyecto `dupla-comercial` (región `southamerica-west1`).
- La **Supabase CLI** instalada (`supabase --version`).

---

## 1. 🧑 Crear el proyecto nuevo (dashboard)
1. Dashboard → organización **RukkumansLabs** → botón **"New project"**.
2. **Name:** `dupla-comercial`.
3. **Database Password:** genera una **fuerte** (botón Generate) y **GUÁRDALA** en tu gestor
   de contraseñas — la necesitas para `supabase link` y conexiones directas. No se puede ver
   después.
4. **Region:** la más cercana a Chile → **South America (São Paulo) `sa-east-1`**.
5. **Plan:** Free.
6. **Create new project** → espera ~2 min a que aprovisione.

## 2. 🧑 Copiar las claves (Project Settings → API)
Anota estos 4 valores del proyecto NUEVO (los 3 primeros en *Settings → API*; el JWT en
*Settings → API → JWT Settings*):
- **Project URL** → `https://<ref-nuevo>.supabase.co`
- **anon public** key
- **service_role** key  *(SECRETO — nunca en el frontend)*
- **JWT Secret**  *(el que en prod estaba vacío)*

## 3. 🤖/🧑 Aplicar las migraciones (esquema)
**Opción A — CLI (recomendada):**
```bash
cd <repo>
supabase link --project-ref <ref-nuevo>   # pide la DB password del paso 1
supabase db push                           # aplica las 9 migraciones (0001 → 0009)
```
**Opción B — SQL Editor:** pega el contenido de cada `supabase/migrations/000X_*.sql`
**en orden** (0001 → 0009) y *Run*.

> Verificación: en *Table Editor* deben aparecer `empresas`, `usuarios`, `solicitudes`,
> `conversaciones`, `integraciones`, `propuestas`, etc. con RLS activa.

## 4. 🧑 Crear el/los usuario(s) admin (Auth)
Las migraciones crean el **esquema**, no los usuarios. Por cada admin:
1. Dashboard → **Authentication → Users → Add user** → email + password (ej. tu Gmail).
   Copia el **UID** que genera.
2. En **SQL Editor**, crea su empresa + su fila en `usuarios` ligada a ese UID:
```sql
-- empresa (si es nueva)
insert into empresas (id, nombre, plan, color_marca)
values (gen_random_uuid(), 'RukkumansLabs', 'operador', '#E2502B')
returning id;   -- copia el id

-- usuario admin (reemplaza <UID_AUTH> y <EMPRESA_ID>)
insert into usuarios (id, empresa_id, rol, nombre)
values ('<UID_AUTH>', '<EMPRESA_ID>', 'admin', 'Claudio');
```
   (Repite para cada empresa/usuario que necesites.)

## 5. 🤖 Apuntar el backend al proyecto nuevo (Cloud Run)
Actualiza SOLO las 4 variables de Supabase (las demás —Anthropic, OAuth, poller— no cambian):
```bash
gcloud run services update dupla-comercial \
  --region southamerica-west1 --project dupla-comercial \
  --update-env-vars \
SUPABASE_URL=https://<ref-nuevo>.supabase.co,\
SUPABASE_ANON_KEY=<anon-nuevo>,\
SUPABASE_SERVICE_ROLE_KEY=<service-role-nuevo>,\
SUPABASE_JWT_SECRET=<jwt-secret-nuevo>
```
> El **front** lleva `SUPABASE_URL`/`ANON` horneados en el build → hay que **rebuildear +
> redeploy** (cloudbuild con las nuevas substitutions) para que el front apunte al proyecto
> nuevo. (Te lo hago yo.)

## 6. 🧑 Reconectar los conectores (por empresa)
Entra al app con el admin del paso 4 → **Configuración → Conectores**:
- **Gmail** → Conectar (OAuth de Google) → autoriza.
- **ClickUp** → Conectar (OAuth) → autoriza.
- **Drive** va con la conexión de Google (mismo OAuth que Gmail).

## 7. ✅ Verificar
- Login OK · la bandeja carga · el poller (cada 1 min) ingiere un correo de prueba ·
  el chat de Javo responde · la propuesta se genera.

---

## Limpieza posterior (opcional)
- Cuando el proyecto nuevo esté validado, **pausa/elimina el viejo** (Settings → General →
  Pause/Delete project) para no dejar dos.
- Si publicaste la app OAuth de Google (spec 010), eso vive en **Google Cloud**, no en
  Supabase — no se reconfigura aquí.
