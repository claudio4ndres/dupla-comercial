"""T18 · Generación del DECK PPTX de la cotización (la **cara comercial**).

Lógica **pura** (sin FastAPI): recibe las líneas de la cotización y devuelve los
BYTES de un `.pptx`. El endpoint (`rutas/solicitudes.py`) mapea la propuesta
persistida (spec 004) a `LineaCotizacion` y sirve estos bytes como descarga.

Es la **versión cliente** de la propuesta (mismo criterio que el Excel cliente):
solo precios de **venta**, NUNCA costos ni margen. `valor_unitario` es el costo
unitario (lo que Javo trae del Drive); el precio de venta de una línea es
`cantidad × días × valor_unitario / (1 − margen)`. Se escribe SOLO el número de
venta calculado — el costo y el margen jamás bajan a un texto del deck.

Theme Capsulab: portada negra con la marca y el título, acento verde `#8ED873`.

Reusa el dataclass `LineaCotizacion` de `exportador_excel.py` para no duplicarlo.
"""
from __future__ import annotations

from io import BytesIO

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from app.servicios.exportador_excel import LineaCotizacion

__all__ = ["LineaCotizacion", "generar_ppt_cotizacion"]

# --- Theme Capsulab (RGB) ----------------------------------------------------
NEGRO = RGBColor(0x00, 0x00, 0x00)
BLANCO = RGBColor(0xFF, 0xFF, 0xFF)
VERDE = RGBColor(0x8E, 0xD8, 0x73)
FUENTE = "Arial"

# Tamaño de diapositiva 16:9.
_ANCHO = Inches(13.333)
_ALTO = Inches(7.5)

# Encabezados de la tabla de la vista CLIENTE (sin costo, margen ni proveedor).
_COLUMNAS = ["Ítem", "Descripción", "Cantidad", "VALOR"]
# Anchos relativos de las columnas (suman ~1) para repartir el ancho útil.
_PESOS_COL = [0.30, 0.42, 0.13, 0.15]


def _fmt_clp(valor: int) -> str:
    """Formatea un entero como pesos chilenos: 9600000 → '$9.600.000'."""
    return "$" + f"{valor:,}".replace(",", ".")


def _venta_linea(linea: LineaCotizacion, margen: float) -> int:
    """Precio de VENTA de una línea (ya con margen aplicado). Mismo cálculo que el
    Excel cliente. Se redondea para escribir un número limpio, sin filtrar el costo."""
    return round(linea.cantidad * linea.dias * linea.valor_unitario / (1 - margen))


def _fondo_negro(slide) -> None:
    fondo = slide.background
    fondo.fill.solid()
    fondo.fill.fore_color.rgb = NEGRO


def _caja_texto(slide, *, izq, arriba, ancho, alto):
    caja = slide.shapes.add_textbox(izq, arriba, ancho, alto)
    caja.text_frame.word_wrap = True
    return caja.text_frame


def _slide_en_blanco(prs: Presentation):
    """Una diapositiva sin placeholders (layout 'blank' = el último del template)."""
    return prs.slides.add_slide(prs.slide_layouts[6])


def _portada(prs: Presentation, titulo: str) -> None:
    """Slide 1: marca 'Capsulab' + el título, sobre fondo negro con acento verde."""
    slide = _slide_en_blanco(prs)
    _fondo_negro(slide)

    # Marca (verde Capsulab).
    tf_marca = _caja_texto(slide, izq=Inches(0.8), arriba=Inches(2.4), ancho=Inches(11.7), alto=Inches(1.2))
    p_marca = tf_marca.paragraphs[0]
    p_marca.text = "Capsulab"
    p_marca.font.name = FUENTE
    p_marca.font.size = Pt(54)
    p_marca.font.bold = True
    p_marca.font.color.rgb = VERDE

    # Título de la cotización (blanco).
    tf_tit = _caja_texto(slide, izq=Inches(0.8), arriba=Inches(3.7), ancho=Inches(11.7), alto=Inches(1.6))
    p_tit = tf_tit.paragraphs[0]
    p_tit.text = titulo
    p_tit.font.name = FUENTE
    p_tit.font.size = Pt(30)
    p_tit.font.color.rgb = BLANCO


def _slide_tabla(prs: Presentation, lineas: list[LineaCotizacion], margen: float) -> None:
    """Slide 2: tabla con los componentes (Ítem · Descripción · Cantidad · VALOR de
    venta). NUNCA escribe el costo ni el margen."""
    slide = _slide_en_blanco(prs)
    _fondo_negro(slide)

    tf = _caja_texto(slide, izq=Inches(0.6), arriba=Inches(0.4), ancho=Inches(12.1), alto=Inches(0.8))
    p = tf.paragraphs[0]
    p.text = "Detalle de la propuesta"
    p.font.name = FUENTE
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = VERDE

    n_filas = len(lineas) + 1  # + encabezado
    n_cols = len(_COLUMNAS)
    izq, arriba = Inches(0.6), Inches(1.4)
    ancho, alto = Inches(12.1), Inches(0.5) * n_filas
    tabla = slide.shapes.add_table(n_filas, n_cols, izq, arriba, ancho, alto).table

    # Anchos de columna repartidos según los pesos.
    ancho_util = 12.1
    for c, peso in enumerate(_PESOS_COL):
        tabla.columns[c].width = Inches(round(ancho_util * peso, 2))

    # Encabezado verde.
    for c, etiqueta in enumerate(_COLUMNAS):
        celda = tabla.cell(0, c)
        celda.fill.solid()
        celda.fill.fore_color.rgb = VERDE
        par = celda.text_frame.paragraphs[0]
        par.text = etiqueta
        par.font.name = FUENTE
        par.font.size = Pt(13)
        par.font.bold = True
        par.font.color.rgb = NEGRO

    # Filas de datos: solo el precio de VENTA (con margen), nunca el costo.
    for r, linea in enumerate(lineas, start=1):
        venta = _venta_linea(linea, margen)
        valores = [linea.item, linea.descripcion, str(linea.cantidad), _fmt_clp(venta)]
        alineaciones = [PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT]
        for c, (valor, alineacion) in enumerate(zip(valores, alineaciones)):
            celda = tabla.cell(r, c)
            celda.fill.solid()
            celda.fill.fore_color.rgb = BLANCO
            par = celda.text_frame.paragraphs[0]
            par.text = valor
            par.alignment = alineacion
            par.font.name = FUENTE
            par.font.size = Pt(12)
            par.font.color.rgb = NEGRO
            par.font.bold = c == n_cols - 1  # la columna VALOR en negrita


def _slide_total(prs: Presentation, lineas: list[LineaCotizacion], margen: float) -> None:
    """Slide 3: el VALOR TOTAL de venta (suma de las líneas)."""
    slide = _slide_en_blanco(prs)
    _fondo_negro(slide)

    total = sum(_venta_linea(linea, margen) for linea in lineas)

    tf_et = _caja_texto(slide, izq=Inches(0.8), arriba=Inches(2.8), ancho=Inches(11.7), alto=Inches(1.0))
    p_et = tf_et.paragraphs[0]
    p_et.text = "VALOR TOTAL"
    p_et.font.name = FUENTE
    p_et.font.size = Pt(28)
    p_et.font.bold = True
    p_et.font.color.rgb = VERDE

    tf_total = _caja_texto(slide, izq=Inches(0.8), arriba=Inches(3.9), ancho=Inches(11.7), alto=Inches(1.4))
    p_total = tf_total.paragraphs[0]
    p_total.text = _fmt_clp(total)
    p_total.font.name = FUENTE
    p_total.font.size = Pt(48)
    p_total.font.bold = True
    p_total.font.color.rgb = BLANCO


def generar_ppt_cotizacion(
    lineas: list[LineaCotizacion],
    *,
    titulo: str,
    margen: float = 0.40,
) -> bytes:
    """Arma el deck PPTX de la cotización (vista cliente) y devuelve sus bytes (.pptx).

    `margen` es la fracción de margen (0.40 = 40 %). El deck SOLO muestra precios de
    venta: en ningún texto aparece el costo unitario ni el margen.
    """
    prs = Presentation()
    prs.slide_width = _ANCHO
    prs.slide_height = _ALTO

    _portada(prs, titulo)
    _slide_tabla(prs, lineas, margen)
    _slide_total(prs, lineas, margen)

    buffer = BytesIO()
    prs.save(buffer)
    return buffer.getvalue()
