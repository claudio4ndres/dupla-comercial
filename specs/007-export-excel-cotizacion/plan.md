# Plan 007 · Export Excel de la cotización

## Arquitectura

```
Front (Propuesta "⤓ Excel")
  → api/exportaciones.ts  descargarCotizacionExcel(solicitudId)
    → GET /api/solicitudes/{id}/cotizacion.xlsx   (Authorization: Bearer JWT)
      → backend: auth (empresa del JWT) + repo_propuestas (RLS) → Propuesta
        → servicios/exportador_excel.generar_excel_cotizacion(lineas, margen) → bytes
      ← Response(xlsx, attachment)
    ← blob → descarga en el navegador
```

## Backend

### `app/servicios/exportador_excel.py` (lógica pura, sin FastAPI)

```python
@dataclass
class LineaCotizacion:
    item: str
    descripcion: str = ""
    proveedor: str = ""
    cantidad: int = 1
    dias: int = 1
    valor_unitario: float = 0.0   # costo unitario

def generar_excel_cotizacion(
    lineas: list[LineaCotizacion],
    *,
    titulo: str = "Cotización",
    margen: float = 0.40,
) -> bytes: ...
```

- Usa **openpyxl** (ya es dependencia). Construye un `Workbook` en memoria y lo
  serializa a `bytes` con `save(BytesIO())`.
- **Theme** en constantes: `NEGRO`, `BLANCO`, `VERDE='FF8ED873'`, `AMARILLO='FFFFFF00'`,
  `CIAN='FF00FFFF'`, fuente `Arial`. Formato contable CLP y `0%`.
- **Fórmulas** (no valores estáticos): faithful al modelo y editable por el GP.
  `COSTO=Dr*Er*Fr`, `VALOR FINAL=COSTO/(1-margen)`, `MARGEN=1-COSTO/VALORFINAL`,
  subtotal `SUM`, valor venta `=I_subtotal`.

### Endpoint (en `app/rutas/solicitudes.py`)

`GET /solicitudes/{solicitud_id}/cotizacion.xlsx?margen=0.40`
- Deps: `obtener_repositorio_propuestas`, `obtener_empresa_actual` (mismas que la 004).
- 404 si no hay propuesta. Mapea `propuesta.componentes` → `LineaCotizacion`
  (proveedor="" y dias=1, no persistidos hoy). Devuelve `fastapi.Response` con el
  media-type xlsx y `Content-Disposition: attachment`.

## Frontend

### `apps/web/src/api/exportaciones.ts`
`descargarCotizacionExcel(solicitudId): Promise<boolean>` — fetch con `cabecerasAuth()`,
`blob()`, `URL.createObjectURL`, ancla `download`, click, revoke. `false` ante error
(no rompe la UI).

### Wiring
- `Propuesta.tsx`: nueva prop `onExportarExcel?: () => void`; el botón "⤓ Excel" la llama.
- `App.tsx`: pasa `onExportarExcel={() => solicitudActual && descargarCotizacionExcel(solicitudActual.id)}`.

## Estrategia de pruebas

- **`tests/test_exportador_excel.py`** (pytest): abre los bytes con openpyxl y aserta
  encabezados, fills (verde/amarillo/cian/negro), fuente Arial/25, fórmulas COSTO y
  VALOR FINAL (margen 0.4 → `/0.6`), subtotal y valor venta. Caso margen custom.
- **`tests/test_endpoint_cotizacion_excel.py`**: TestClient con dobles en memoria;
  200 + content-type + bytes reabribles por openpyxl; 404 sin propuesta; aislamiento
  multi-tenant.
- **`apps/web/src/api/exportaciones.test.ts`** (vitest): mock fetch + stubs de
  `URL.createObjectURL`/`document.createElement`; aserta URL, header auth, ancla
  `download`, `click`; `false` ante !ok.
```
