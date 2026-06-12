"""005 · Javo como AGENTE (loop de tool-use).

El cliente Anthropic, el catálogo (Drive) y la búsqueda en internet se MOCKEAN (CA4):
cero red, cero tokens. Verificamos que Javo consulta el Drive y usa datos reales
(CA1), no inventa (CA2), busca en internet solo si se lo piden y con tope (CA3/CA11),
captura los componentes propuestos sin persistir (CA10), cita fuentes (CA6) y que el
loop está acotado.
"""
import asyncio
import json
from uuid import uuid4

from types import SimpleNamespace

from app.esquemas import MensajeConversacion
from app.repositorios.catalogo import ItemCatalogo, RepositorioCatalogoEnMemoria
from app.servicios.busqueda_internet import ProveedorBusquedaWeb, ResultadoBusqueda
from app.servicios.javo import MAX_ITERACIONES, TOPE_INTERNET, responder_javo
from tests.dobles import (
    ClienteAnthropicGuionFake,
    respuesta_texto,
    respuesta_tool_use,
)

EMPRESA = uuid4()


def _msg(texto):
    return [MensajeConversacion(rol="usuario", contenido=texto)]


def _item(**kw):
    base = dict(
        id=uuid4(),
        empresa_id=EMPRESA,
        tipo="componente",
        nombre="Promotoras uniformadas",
        detalle="3 tiendas",
        valor_unitario=240000,
        origen="Tarifario_promotores_2026.xlsx",
    )
    base.update(kw)
    return ItemCatalogo(**base)


class _ProveedorFake:
    def __init__(self, resultados=None):
        self.veces = 0
        self._resultados = resultados or [
            ResultadoBusqueda(titulo="Caso F1", referencia="https://ejemplo.cl/f1")
        ]

    async def buscar(self, consulta, *, limite=5):
        self.veces += 1
        return list(self._resultados)


class _ArchivoFake:
    """Imita un `ArchivoDrive` (id/nombre/tipo_mime) para los tests de Javo→Drive."""

    def __init__(self, id, nombre, tipo_mime):
        self.id = id
        self.nombre = nombre
        self.tipo_mime = tipo_mime


class _DriveFake:
    """Doble del `ClienteDriveReal`: busca en una lista fija y devuelve contenido fijo
    por file_id. Registra las consultas y lecturas (cero red, cero credenciales)."""

    def __init__(self, archivos=None, contenidos=None):
        self._archivos = archivos or []
        self._contenidos = contenidos or {}
        self.consultas: list = []
        self.lecturas: list = []

    async def buscar_archivos(self, consulta):
        self.consultas.append(consulta)
        return list(self._archivos)

    async def leer_documento(self, file_id, tipo_mime):
        self.lecturas.append((file_id, tipo_mime))
        return self._contenidos.get(file_id, "")


def _correr(*args, **kw):
    return asyncio.run(responder_javo(*args, **kw))


# ── T6 · CA1 ─────────────────────────────────────────────────────────────────
def test_usa_valor_real_del_drive():
    repo = RepositorioCatalogoEnMemoria([_item()])
    cliente = ClienteAnthropicGuionFake(
        [
            respuesta_tool_use("buscar_en_drive", {"consulta": "promotoras"}),
            respuesta_texto("Las promotoras quedan a $240.000 c/u."),
        ]
    )
    resp = _correr(
        "t1", _msg("cotiza promotoras"), cliente,
        repo_catalogo=repo, proveedor_busqueda=_ProveedorFake(), empresa_id=EMPRESA,
    )
    assert resp.texto == "Las promotoras quedan a $240.000 c/u."
    # El backend ejecutó buscar_en_drive y le pasó el VALOR REAL al modelo (2ª llamada).
    segunda = json.dumps(cliente.llamadas[1]["messages"], ensure_ascii=False).lower()
    assert "240000" in segunda and "promotoras" in segunda


# ── T7 · CA10 ────────────────────────────────────────────────────────────────
def test_captura_componentes_propuestos_sin_persistir():
    cliente = ClienteAnthropicGuionFake(
        [
            respuesta_tool_use(
                "proponer_componentes",
                {
                    "componentes": [
                        {
                            "nombre": "Promotoras",
                            "detalle": "3 tiendas",
                            "cantidad": 6,
                            "dias": 3,
                            "valor_unitario": 240000,
                            "proveedor": "Eventos Pro",
                            "origen": "Tarifario.xlsx",
                        }
                    ]
                },
            ),
            respuesta_texto("Te propongo estos componentes; confírmame."),
        ]
    )
    resp = _correr(
        "t1", _msg("arma la cotización"), cliente,
        repo_catalogo=RepositorioCatalogoEnMemoria([]),
        proveedor_busqueda=_ProveedorFake(), empresa_id=EMPRESA,
    )
    assert len(resp.componentes) == 1
    c = resp.componentes[0]
    assert c.nombre == "Promotoras" and c.cantidad == 6
    assert c.valor_unitario == 240000 and c.origen == "Tarifario.xlsx"
    assert c.proveedor == "Eventos Pro" and c.dias == 3


def test_captura_tareas_propuestas():
    # Javo decide y propone las TAREAS de ejecución (criterio de comercial senior).
    cliente = ClienteAnthropicGuionFake(
        [
            respuesta_tool_use(
                "proponer_tareas",
                {
                    "tareas": [
                        {"nombre": "Reclutar 6 promotoras", "area": "RRHH", "plazo": "3 días"},
                        {"nombre": "Comprar insumos de sampling", "area": "Compras", "plazo": "1 semana"},
                    ]
                },
            ),
            respuesta_texto("Te dejé las tareas de ejecución; confírmame."),
        ]
    )
    resp = _correr(
        "t1", _msg("arma las tareas"), cliente,
        repo_catalogo=RepositorioCatalogoEnMemoria([]),
        proveedor_busqueda=_ProveedorFake(), empresa_id=EMPRESA,
    )
    assert len(resp.tareas) == 2
    t = resp.tareas[0]
    assert t.nombre == "Reclutar 6 promotoras" and t.area == "RRHH" and t.plazo == "3 días"


# ── T8 · CA2 ─────────────────────────────────────────────────────────────────
def test_sin_match_indica_sin_resultados():
    cliente = ClienteAnthropicGuionFake(
        [
            respuesta_tool_use("buscar_en_drive", {"consulta": "dron submarino"}),
            respuesta_texto("No tengo ese valor en el catálogo, ¿me lo confirmas?"),
        ]
    )
    _correr(
        "t1", _msg("cotiza un dron submarino"), cliente,
        repo_catalogo=RepositorioCatalogoEnMemoria([]),
        proveedor_busqueda=_ProveedorFake(), empresa_id=EMPRESA,
    )
    segunda = json.dumps(cliente.llamadas[1]["messages"], ensure_ascii=False).lower()
    assert "sin resultados" in segunda


# ── T9 · CA3 (sin pedir → no se ofrece) ──────────────────────────────────────
def test_internet_no_se_ofrece_sin_pedirlo():
    cliente = ClienteAnthropicGuionFake([respuesta_texto("Te tiro 3 conceptos.")])
    _correr(
        "t2", _msg("dame ideas de alto impacto para la F1"), cliente,
        repo_catalogo=RepositorioCatalogoEnMemoria([]),
        proveedor_busqueda=_ProveedorFake(), empresa_id=EMPRESA,
    )
    nombres = [t["name"] for t in cliente.llamadas[0]["tools"]]
    assert "buscar_en_internet" not in nombres


# ── T9 · CA3 (pidiéndolo → se ofrece y se ejecuta) ───────────────────────────
def test_internet_se_ofrece_y_ejecuta_si_se_pide():
    prov = _ProveedorFake()
    cliente = ClienteAnthropicGuionFake(
        [
            respuesta_tool_use("buscar_en_internet", {"consulta": "activaciones F1"}),
            respuesta_texto("Encontré estas referencias."),
        ]
    )
    resp = _correr(
        "t2", _msg("busca en internet referencias de F1"), cliente,
        repo_catalogo=RepositorioCatalogoEnMemoria([]),
        proveedor_busqueda=prov, empresa_id=EMPRESA,
    )
    nombres = [t["name"] for t in cliente.llamadas[0]["tools"]]
    assert "buscar_en_internet" in nombres
    assert prov.veces == 1
    assert len(resp.fuentes) >= 1


# ── T9 · CA3/CA6 (Tipo 2 con el PROVEEDOR REAL: web search nativo) ────────────
class _ClienteWebSearchFake:
    """Doble del cliente Anthropic que usa el `ProveedorBusquedaWeb` real: devuelve una
    respuesta con bloques `web_search_tool_result` (forma EXACTA del SDK). Cero red."""

    def __init__(self):
        self.messages = self

    async def create(self, **kwargs):
        return SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="server_tool_use",
                    id="srvtoolu_1",
                    name="web_search",
                    input={"query": "activaciones F1"},
                ),
                SimpleNamespace(
                    type="web_search_tool_result",
                    tool_use_id="srvtoolu_1",
                    content=[
                        {
                            "type": "web_search_result",
                            "title": "Activación Red Bull en la F1",
                            "url": "https://ejemplo.cl/redbull-f1",
                            "page_age": "March 1, 2026",
                        }
                    ],
                ),
            ]
        )


def test_internet_usa_resultados_reales_del_proveedor_web_y_los_cita():
    # Tipo 2 + el usuario pide internet → Javo llama `buscar_en_internet`, que ejecuta el
    # PROVEEDOR REAL (web search nativo de Anthropic, mockeado). Los resultados REALES
    # parseados (título/url) llegan al modelo y quedan citados como Fuente (CA6).
    proveedor_real = ProveedorBusquedaWeb(_ClienteWebSearchFake())
    cliente = ClienteAnthropicGuionFake(
        [
            respuesta_tool_use("buscar_en_internet", {"consulta": "activaciones F1"}),
            respuesta_texto("Mira esta referencia de Red Bull en la F1."),
        ]
    )
    resp = _correr(
        "t2", _msg("busca en internet referencias de la F1"), cliente,
        repo_catalogo=RepositorioCatalogoEnMemoria([]),
        proveedor_busqueda=proveedor_real, empresa_id=EMPRESA,
    )
    # El resultado REAL (título + url) se citó como Fuente.
    assert any(
        f.titulo == "Activación Red Bull en la F1"
        and f.referencia == "https://ejemplo.cl/redbull-f1"
        for f in resp.fuentes
    )
    # Y se le pasó al modelo en la 2ª llamada (tool_result con la url real).
    segunda = json.dumps(cliente.llamadas[1]["messages"], ensure_ascii=False)
    assert "https://ejemplo.cl/redbull-f1" in segunda


# ── T9/T11 · CA11 (tope de internet) ─────────────────────────────────────────
def test_tope_de_busquedas_internet():
    prov = _ProveedorFake()
    guion = [
        respuesta_tool_use("buscar_en_internet", {"consulta": f"q{i}"}, id=f"t{i}")
        for i in range(MAX_ITERACIONES + 3)
    ]
    cliente = ClienteAnthropicGuionFake(guion)
    _correr(
        "t2", _msg("busca en internet"), cliente,
        repo_catalogo=RepositorioCatalogoEnMemoria([]),
        proveedor_busqueda=prov, empresa_id=EMPRESA,
    )
    assert prov.veces <= TOPE_INTERNET


# ── T10 · CA6 ────────────────────────────────────────────────────────────────
def test_respuesta_trae_fuentes_del_drive():
    repo = RepositorioCatalogoEnMemoria([_item(origen="Modelo Cotización.xlsx")])
    cliente = ClienteAnthropicGuionFake(
        [
            respuesta_tool_use("buscar_en_drive", {"consulta": "promotoras"}),
            respuesta_texto("Listo."),
        ]
    )
    resp = _correr(
        "t1", _msg("cotiza promotoras"), cliente,
        repo_catalogo=repo, proveedor_busqueda=_ProveedorFake(), empresa_id=EMPRESA,
    )
    assert any(
        "Modelo Cotización" in f.referencia or "Modelo Cotización" in f.titulo
        for f in resp.fuentes
    )


# ── T11 · loop acotado ───────────────────────────────────────────────────────
def test_loop_acotado():
    repo = RepositorioCatalogoEnMemoria([_item()])
    guion = [
        respuesta_tool_use("buscar_en_drive", {"consulta": "x"}, id=f"t{i}")
        for i in range(MAX_ITERACIONES + 50)
    ]
    cliente = ClienteAnthropicGuionFake(guion)
    resp = _correr(
        "t1", _msg("cotiza"), cliente,
        repo_catalogo=repo, proveedor_busqueda=_ProveedorFake(), empresa_id=EMPRESA,
    )
    assert len(cliente.llamadas) <= MAX_ITERACIONES
    assert resp.texto  # devuelve algo, no se cuelga ni revienta


# ── Drive REAL en vivo: buscar → leer → usar el valor real y citarlo ──────────
def test_buscar_en_drive_consulta_el_drive_real_y_lista_los_docs():
    # Con un cliente Drive cableado, `buscar_en_drive` busca en TODO el Drive (no en la
    # tabla `catalogo`): devuelve los docs encontrados (nombre+id+mime) al modelo.
    drive = _DriveFake(
        archivos=[
            _ArchivoFake("doc1", "Tarifario promotores 2026",
                         "application/vnd.google-apps.document"),
        ]
    )
    cliente = ClienteAnthropicGuionFake(
        [
            respuesta_tool_use("buscar_en_drive", {"consulta": "tarifario promotores"}),
            respuesta_texto("Encontré el tarifario."),
        ]
    )
    resp = _correr(
        "t1", _msg("cotiza promotoras"), cliente,
        repo_catalogo=RepositorioCatalogoEnMemoria([]),
        proveedor_busqueda=_ProveedorFake(), empresa_id=EMPRESA, cliente_drive=drive,
    )
    assert drive.consultas == ["tarifario promotores"]
    # El backend le pasó al modelo los docs reales (id+nombre+mime) en la 2ª llamada.
    segunda = json.dumps(cliente.llamadas[1]["messages"], ensure_ascii=False).lower()
    assert "doc1" in segunda and "tarifario promotores 2026" in segunda
    assert "vnd.google-apps.document" in segunda
    # Las tools de Drive están declaradas (buscar + leer documento).
    nombres = [t["name"] for t in cliente.llamadas[0]["tools"]]
    assert "buscar_en_drive" in nombres and "leer_documento_drive" in nombres
    # El doc encontrado quedó como Fuente citable.
    assert any("Tarifario promotores 2026" in f.titulo for f in resp.fuentes)


def test_javo_lee_el_doc_del_drive_usa_el_valor_real_y_lo_cita():
    # Flujo completo: busca → encuentra → LEE el doc → usa el número real y lo cita.
    drive = _DriveFake(
        archivos=[
            _ArchivoFake("doc1", "Tarifario promotores 2026",
                         "application/vnd.google-apps.document"),
        ],
        contenidos={"doc1": "Promotora uniformada: $120.000 por día"},
    )
    cliente = ClienteAnthropicGuionFake(
        [
            respuesta_tool_use("buscar_en_drive", {"consulta": "promotoras"}, id="t1"),
            respuesta_tool_use(
                "leer_documento_drive",
                {"file_id": "doc1", "tipo_mime": "application/vnd.google-apps.document"},
                id="t2",
            ),
            respuesta_texto(
                "La promotora va a $120.000 por día (Fuente: Tarifario promotores 2026)."
            ),
        ]
    )
    resp = _correr(
        "t1", _msg("cotiza promotoras"), cliente,
        repo_catalogo=RepositorioCatalogoEnMemoria([]),
        proveedor_busqueda=_ProveedorFake(), empresa_id=EMPRESA, cliente_drive=drive,
    )
    assert drive.lecturas == [("doc1", "application/vnd.google-apps.document")]
    # El contenido real del doc llegó al modelo (3ª llamada).
    tercera = json.dumps(cliente.llamadas[2]["messages"], ensure_ascii=False)
    assert "120.000" in tercera
    assert "$120.000 por día" in resp.texto


def test_sin_cliente_drive_las_tools_degradan_sin_romper():
    # Empresa sin Drive/token: `cliente_drive=None`. Las tools de Drive NO revientan;
    # avisan "sin acceso a Drive" y el loop sigue (responde con texto, sin colgarse).
    cliente = ClienteAnthropicGuionFake(
        [
            respuesta_tool_use("buscar_en_drive", {"consulta": "promotoras"}, id="t1"),
            respuesta_tool_use(
                "leer_documento_drive",
                {"file_id": "x", "tipo_mime": "application/vnd.google-apps.document"},
                id="t2",
            ),
            respuesta_texto("No tengo el Drive conectado; pásame el valor."),
        ]
    )
    resp = _correr(
        "t1", _msg("cotiza promotoras"), cliente,
        repo_catalogo=RepositorioCatalogoEnMemoria([]),
        proveedor_busqueda=_ProveedorFake(), empresa_id=EMPRESA, cliente_drive=None,
    )
    assert resp.texto  # no se cuelga ni revienta
    segunda = json.dumps(cliente.llamadas[1]["messages"], ensure_ascii=False).lower()
    assert "sin acceso a drive" in segunda
    tercera = json.dumps(cliente.llamadas[2]["messages"], ensure_ascii=False).lower()
    assert "sin acceso a drive" in tercera
