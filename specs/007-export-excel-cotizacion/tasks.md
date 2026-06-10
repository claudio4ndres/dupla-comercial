# Tareas 007 · Export Excel de la cotización

Orden con TDD (cada tarea: test que falla → mínimo código → verde).

- [x] **T1 · Generador Excel (lógica pura).**
  - 🔴 `tests/test_exportador_excel.py`: encabezados + fills + fuente + fórmulas
    (COSTO=D*E*F, VALOR FINAL=COSTO/0.6 con margen 0.4) + subtotal amarillo + valor
    venta cian + caso margen custom.
  - 🟢 `app/servicios/exportador_excel.py`: `LineaCotizacion`, `generar_excel_cotizacion`.

- [x] **T2 · Endpoint `GET /solicitudes/{id}/cotizacion.xlsx`.**
  - 🔴 `tests/test_endpoint_cotizacion_excel.py`: 200 + content-type xlsx + reabrible;
    404 sin propuesta; aislamiento multi-tenant.
  - 🟢 Ruta en `app/rutas/solicitudes.py` (deps 004 + mapeo componentes→líneas + margen
    query param).

- [x] **T3 · Cliente front + descarga.**
  - 🔴 `apps/web/src/api/exportaciones.test.ts`.
  - 🟢 `apps/web/src/api/exportaciones.ts` `descargarCotizacionExcel`.

- [x] **T4 · Wiring UI.**
  - 🟢 `Propuesta.tsx` prop `onExportarExcel` en el botón "⤓ Excel"; `App.tsx` lo cablea
    a la solicitud activa.

- [x] **T5 · Verde total.** `pytest -q` (152) + `npm run test` (37) + `tsc` (0). Validado e2e en
  Chrome: login real → propuesta 212CH ($5.190.000) → ⤓ Excel → descarga `.xlsx` con el theme.
