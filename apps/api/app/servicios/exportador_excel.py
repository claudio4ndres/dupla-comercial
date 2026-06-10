"""007 · Generación del Excel de la cotización con el theme Capsulab.

Lógica **pura** (sin FastAPI): recibe las líneas de la cotización y devuelve los
BYTES de un `.xlsx`. El endpoint (`rutas/solicitudes.py`) mapea la propuesta
persistida (spec 004) a `LineaCotizacion` y sirve estos bytes como descarga.

El formato replica el archivo modelo de Capsulab `PF - Fuchs cerros.xlsx`:

* Banda de **título** negra con Arial 25 bold blanca, fusionada a lo ancho.
* **Encabezado** verde `FF8ED873` (Arial bold) con las 9 columnas
  `Item · PROVEEDOR · DESCRIPCIÓN · Cantidad · días · valor unitario · COSTO ·
  MARGEN · VALOR FINAL`.
* Datos con **fórmulas** (faithful + editable por el GP):
  `COSTO = Cantidad × días × valor unitario`,
  `VALOR FINAL = COSTO / (1 − margen)`,
  `MARGEN = 1 − COSTO / VALOR FINAL`.
* **Subtotal** amarillo `FFFFFF00` (SUM de COSTO y VALOR FINAL) y **valor venta**
  cian `FF00FFFF` (= subtotal de VALOR FINAL).

`valor_unitario` es el **costo** unitario (lo que Javo trae del Drive); el margen se
aplica en la planilla para llegar al precio de venta.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# --- Theme Capsulab (ARGB) ---------------------------------------------------
NEGRO = "FF000000"
BLANCO = "FFFFFFFF"
VERDE = "FF8ED873"
AMARILLO = "FFFFFF00"
CIAN = "FF00FFFF"
FUENTE = "Arial"

# Formatos de número (extraídos del archivo modelo).
FMT_CLP = '_ "$"* #,##0_ ;_ "$"* \\-#,##0_ ;_ "$"* "-"_ ;_ @_ '
FMT_FINAL = '#,##0_ ;[Red]\\-#,##0\\ '
FMT_PCT = "0%"

# Columnas en el orden del modelo (A..I) y sus anchos.
COLUMNAS = [
    ("Item", 26),
    ("PROVEEDOR", 22),
    ("DESCRIPCIÓN", 52),
    ("Cantidad", 10),
    ("días", 8),
    ("valor unitario", 16),
    ("COSTO", 16),
    ("MARGEN", 11),
    ("VALOR FINAL", 18),
]
N_COLS = len(COLUMNAS)

FILA_TITULO = 1
FILA_ENCABEZADO = 2
FILA_DATOS = 3


@dataclass
class LineaCotizacion:
    """Una línea de la cotización. `valor_unitario` es el COSTO unitario."""

    item: str
    descripcion: str = ""
    proveedor: str = ""
    cantidad: int = 1
    dias: int = 1
    valor_unitario: float = 0.0


def _relleno(color: str) -> PatternFill:
    return PatternFill(start_color=color, end_color=color, fill_type="solid")


def generar_excel_cotizacion(
    lineas: list[LineaCotizacion],
    *,
    titulo: str = "Cotización",
    margen: float = 0.40,
) -> bytes:
    """Arma el libro de la cotización y devuelve sus bytes (.xlsx).

    `margen` es la fracción de margen (0.40 = 40 %); el VALOR FINAL divide el COSTO
    por `1 − margen` (el modelo Capsulab usa `/0.6`). Se trunca a 6 cifras para que
    la fórmula quede limpia (sin ruido de coma flotante).
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Cotización"

    # Anchos de columna.
    for i, (_, ancho) in enumerate(COLUMNAS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho

    # --- Banda de título (negra / Arial 25 blanca, fusionada) ---
    ws.merge_cells(
        start_row=FILA_TITULO, start_column=1, end_row=FILA_TITULO, end_column=N_COLS
    )
    celda_titulo = ws.cell(row=FILA_TITULO, column=1, value=titulo)
    celda_titulo.fill = _relleno(NEGRO)
    celda_titulo.font = Font(name=FUENTE, size=25, bold=True, color=BLANCO)
    celda_titulo.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[FILA_TITULO].height = 34

    # --- Encabezado verde ---
    relleno_verde = _relleno(VERDE)
    for c, (etiqueta, _) in enumerate(COLUMNAS, start=1):
        celda = ws.cell(row=FILA_ENCABEZADO, column=c, value=etiqueta)
        celda.fill = relleno_verde
        celda.font = Font(name=FUENTE, size=11, bold=True)
        celda.alignment = Alignment(vertical="center", wrap_text=True)

    # --- Filas de datos (con fórmulas) ---
    divisor = f"{1 - margen:g}"  # 0.40 → "0.6"; limpia ruido de float
    fila_ini = FILA_DATOS
    fuente = Font(name=FUENTE, size=11)
    for n, linea in enumerate(lineas):
        r = fila_ini + n
        ws.cell(row=r, column=1, value=linea.item).font = fuente
        ws.cell(row=r, column=2, value=linea.proveedor).font = fuente
        celda_desc = ws.cell(row=r, column=3, value=linea.descripcion)
        celda_desc.font = fuente
        celda_desc.alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=r, column=4, value=linea.cantidad).font = fuente
        ws.cell(row=r, column=5, value=linea.dias).font = fuente
        f = ws.cell(row=r, column=6, value=linea.valor_unitario)
        f.number_format = FMT_CLP
        f.font = fuente
        g = ws.cell(row=r, column=7, value=f"=D{r}*E{r}*F{r}")
        g.number_format = FMT_CLP
        g.font = fuente
        h = ws.cell(row=r, column=8, value=f"=1-G{r}/I{r}")
        h.number_format = FMT_PCT
        h.font = fuente
        i = ws.cell(row=r, column=9, value=f"=G{r}/{divisor}")
        i.number_format = FMT_FINAL
        i.font = Font(name=FUENTE, size=11, bold=True)

    fila_fin = fila_ini + len(lineas) - 1 if lineas else fila_ini

    # --- Subtotal (amarillo) ---
    fila_sub = fila_fin + 1
    relleno_amarillo = _relleno(AMARILLO)
    et_sub = ws.cell(row=fila_sub, column=6, value="SUB TOTAL COSTOS")
    et_sub.font = Font(name=FUENTE, size=11, bold=True)
    sub_g = ws.cell(row=fila_sub, column=7, value=f"=SUM(G{fila_ini}:G{fila_fin})")
    sub_g.number_format = FMT_CLP
    sub_g.font = Font(name=FUENTE, size=11, bold=True)
    sub_h = ws.cell(row=fila_sub, column=8, value=f"=1-G{fila_sub}/I{fila_sub}")
    sub_h.number_format = FMT_PCT
    sub_i = ws.cell(row=fila_sub, column=9, value=f"=SUM(I{fila_ini}:I{fila_fin})")
    sub_i.number_format = FMT_FINAL
    sub_i.font = Font(name=FUENTE, size=11, bold=True)
    for c in range(6, N_COLS + 1):
        ws.cell(row=fila_sub, column=c).fill = relleno_amarillo

    # --- Valor venta (cian) ---
    fila_venta = fila_sub + 1
    relleno_cian = _relleno(CIAN)
    et_venta = ws.cell(row=fila_venta, column=8, value="VALOR VENTA")
    et_venta.font = Font(name=FUENTE, size=11, bold=True)
    venta_i = ws.cell(row=fila_venta, column=9, value=f"=I{fila_sub}")
    venta_i.number_format = FMT_CLP
    venta_i.font = Font(name=FUENTE, size=11, bold=True)
    for c in range(8, N_COLS + 1):
        ws.cell(row=fila_venta, column=c).fill = relleno_cian

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
