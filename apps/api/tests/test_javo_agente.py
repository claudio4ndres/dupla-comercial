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

from app.esquemas import MensajeConversacion
from app.repositorios.catalogo import ItemCatalogo, RepositorioCatalogoEnMemoria
from app.servicios.busqueda_internet import ResultadoBusqueda
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
                            "valor_unitario": 240000,
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
