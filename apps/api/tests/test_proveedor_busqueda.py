"""005 · Proveedor de búsqueda en internet (Tipo 2).

Para la demo usamos un proveedor **curado** (determinista, offline-safe) que NO llama
a una API real: devuelve referencias con sus **fuentes** (CA6/CA11). En los tests del
servicio de Javo se inyecta un doble; aquí verificamos el contrato del proveedor.

En PRODUCCIÓN el proveedor real (`ProveedorBusquedaWeb`) usa el **web search nativo**
de Anthropic (server tool `web_search_20260209`): el modelo busca server-side y nosotros
parseamos los bloques `web_search_tool_result` al MISMO contrato `ResultadoBusqueda`.
Aquí lo verificamos MOCKEANDO la respuesta del SDK (cero red, cero tokens).
"""
from types import SimpleNamespace

from app.servicios.busqueda_internet import (
    ProveedorBusquedaCurado,
    ProveedorBusquedaWeb,
)


async def test_curado_devuelve_resultados_con_fuentes():
    prov = ProveedorBusquedaCurado()

    res = await prov.buscar("activación fórmula 1")

    assert len(res) >= 1
    # Cada resultado trae una fuente citable (título + referencia/URL).
    assert all(r.titulo and r.referencia for r in res)


async def test_curado_respeta_limite():
    prov = ProveedorBusquedaCurado()

    res = await prov.buscar("ideas de alto impacto", limite=2)

    assert len(res) <= 2


async def test_curado_es_determinista():
    prov = ProveedorBusquedaCurado()

    a = await prov.buscar("sampling metro")
    b = await prov.buscar("sampling metro")

    assert [r.referencia for r in a] == [r.referencia for r in b]


# ── Proveedor REAL: web search nativo de Anthropic (server tool) ─────────────
def _bloques(*bloques) -> SimpleNamespace:
    """Mapea una lista de dicts a la forma de la respuesta del SDK (bloques con
    atributos), igual que `ClienteAnthropicHttpx` / el SDK real."""
    return SimpleNamespace(
        content=[SimpleNamespace(**b) for b in bloques]
    )


class _ClienteAnthropicWebFake:
    """Doble del cliente Anthropic: registra el payload de `messages.create` (para
    verificar que se habilitó el tool web_search) y devuelve una respuesta fija con
    bloques `server_tool_use` + `web_search_tool_result`. Cero red, cero tokens."""

    def __init__(self, respuesta: SimpleNamespace):
        self.llamadas: list = []
        self._respuesta = respuesta
        self.messages = self

    async def create(self, **kwargs):
        self.llamadas.append(kwargs)
        return self._respuesta


def _respuesta_web_search(*resultados) -> SimpleNamespace:
    """Arma una respuesta del SDK con un bloque `web_search_tool_result` cuyo `content`
    son items `web_search_result` (forma EXACTA de la doc oficial)."""
    return _bloques(
        {"type": "text", "text": "Voy a buscar referencias."},
        {
            "type": "server_tool_use",
            "id": "srvtoolu_1",
            "name": "web_search",
            "input": {"query": "activaciones fórmula 1"},
        },
        {
            "type": "web_search_tool_result",
            "tool_use_id": "srvtoolu_1",
            "content": list(resultados),
        },
        {"type": "text", "text": "Listo."},
    )


async def test_web_parsea_resultados_reales_al_contrato():
    # El proveedor real parsea los bloques `web_search_tool_result` del SDK al tipo del
    # contrato existente (ResultadoBusqueda: titulo / referencia=url / resumen).
    respuesta = _respuesta_web_search(
        {
            "type": "web_search_result",
            "title": "Activación F1 en el GP de Chile",
            "url": "https://ejemplo.cl/f1-activacion",
            "page_age": "March 1, 2026",
            "encrypted_content": "EqgfCi...",
        },
        {
            "type": "web_search_result",
            "title": "Casos de marketing en Fórmula 1",
            "url": "https://ejemplo.cl/casos-f1",
            "page_age": "April 2, 2026",
            "encrypted_content": "FbhgDj...",
        },
    )
    cliente = _ClienteAnthropicWebFake(respuesta)
    prov = ProveedorBusquedaWeb(cliente)

    res = await prov.buscar("referencias de activación F1")

    assert [r.titulo for r in res] == [
        "Activación F1 en el GP de Chile",
        "Casos de marketing en Fórmula 1",
    ]
    assert [r.referencia for r in res] == [
        "https://ejemplo.cl/f1-activacion",
        "https://ejemplo.cl/casos-f1",
    ]
    # Cada resultado trae una fuente citable (título + url).
    assert all(r.titulo and r.referencia for r in res)


async def test_web_habilita_el_server_tool_web_search():
    # El proveedor habilita el tool nativo `web_search` (server-side) en messages.create.
    cliente = _ClienteAnthropicWebFake(_respuesta_web_search())
    prov = ProveedorBusquedaWeb(cliente)

    await prov.buscar("sampling metro")

    assert len(cliente.llamadas) == 1
    payload = cliente.llamadas[0]
    tipos = {t["type"] for t in payload["tools"]}
    nombres = {t["name"] for t in payload["tools"]}
    assert any(t.startswith("web_search") for t in tipos)
    assert "web_search" in nombres
    # La consulta del usuario va como mensaje del usuario.
    contenido = str(payload["messages"]).lower()
    assert "sampling metro" in contenido


async def test_web_respeta_el_limite():
    respuesta = _respuesta_web_search(
        *[
            {
                "type": "web_search_result",
                "title": f"Resultado {i}",
                "url": f"https://ejemplo.cl/r{i}",
            }
            for i in range(6)
        ]
    )
    prov = ProveedorBusquedaWeb(_ClienteAnthropicWebFake(respuesta))

    res = await prov.buscar("ideas alto impacto", limite=2)

    assert len(res) <= 2


async def test_web_sin_resultados_no_revienta():
    # Respuesta sin bloque de resultados (el modelo no buscó / o vino un error): []
    cliente = _ClienteAnthropicWebFake(
        _bloques({"type": "text", "text": "No encontré nada."})
    )
    prov = ProveedorBusquedaWeb(cliente)

    res = await prov.buscar("algo inexistente")

    assert res == []


async def test_web_ignora_bloque_de_error_del_tool():
    # Cuando el server tool falla, el `content` es un dict de error, no una lista.
    cliente = _ClienteAnthropicWebFake(
        _bloques(
            {
                "type": "web_search_tool_result",
                "tool_use_id": "srvtoolu_err",
                "content": {
                    "type": "web_search_tool_result_error",
                    "error_code": "max_uses_exceeded",
                },
            }
        )
    )
    prov = ProveedorBusquedaWeb(cliente)

    res = await prov.buscar("algo")

    assert res == []
