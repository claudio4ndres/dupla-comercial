# Tareas 015 · State OAuth persistente + cache de access token

- [x] **T1** — 🔴 Tests `test_almacen_estado_oauth.py` (CA1-CA3, MockTransport +
  memoria) y `test_cache_token_acceso.py` (CA4, reloj falso + Drive con cache).
- [x] **T2** — 🟢 Migración `0012_estados_oauth.sql` (RLS sin políticas) +
  `AlmacenEstadoOAuthSupabase` (DELETE atómico con representación).
- [x] **T3** — 🟢 `ESTADO_OAUTH_BACKEND` en config + selección en
  `obtener_almacen_estado_oauth` (supabase default / memoria dev).
- [x] **T4** — 🟢 `CacheTokenAcceso` + cache en `ClienteGmailReal`/`ClienteDriveReal`
  y sus fábricas (singleton compartido en dependencias).
- [x] **T5** — ♻️ Limpieza: eliminar `drive_folder_id` + `test_config_drive.py`;
  marcar T3-T8 de `specs/010/tasks.md` (ya implementadas).
- [x] **T6** — ♻️ Suite completa verde, commit en español.
