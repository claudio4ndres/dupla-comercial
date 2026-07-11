# Tareas 016 · Migración del front a React Router v7

- [ ] **T1** — 🔴 Tests de navegación `src/rutas/router.test.tsx` con
  `createMemoryRouter` + mocks de api/supabase (CA1-CA5). Verificar que fallan.
- [ ] **T2** — 🟢 `router.tsx`: `crearRutas()` con providers dentro del router
  (Raiz), guard de sesión (RutaProtegida → Login) y árbol de rutas real.
- [ ] **T3** — 🟢 `SesionContext`: `irA(p, id?)` sobre `useNavigate`; `pantalla`
  derivada de `useLocation().pathname`; `cerrarSesion` navega a `/`.
- [ ] **T4** — 🟢 `SolicitudContext`/`BandejaContext`: navegación con id
  (`detail`/`chat`/`propuesta`) + `rehidratarChat(solicitudId)`.
- [ ] **T5** — 🟢 `App.tsx` descompuesto: Layout con `<Outlet/>` + contenedor
  por ruta con rehidratación en deep-link/refresh (CA1, CA2, CA4).
- [ ] **T6** — ♻️ Eliminar `useSincronizarRuta`; adaptar tests existentes
  (App.test y tests de contextos envueltos en router). Suite completa verde,
  build y lint sin errores nuevos.
