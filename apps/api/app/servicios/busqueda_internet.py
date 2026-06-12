"""005 · Búsqueda en internet para Tipo 2 (referencias/ideas).

Regla #3: el LLM y las integraciones viven en el backend. Esta herramienta la
ejecuta el backend (no Sonnet directamente) y devuelve resultados **con fuentes**
(CA6/CA11). El proveedor es **pluggable**:

- Demo: `ProveedorBusquedaCurado` — determinista y offline-safe (no llama a ninguna
  API real), suficiente para la presentación.
- Producción: un proveedor real (web_search de Anthropic, o una API de búsqueda) con
  el MISMO contrato; no cambia el resto del agente.
"""
from typing import Protocol
from urllib.parse import quote_plus

from pydantic import BaseModel


class ResultadoBusqueda(BaseModel):
    """Un resultado de búsqueda con su fuente citable."""

    titulo: str
    referencia: str  # URL / fuente que el GP puede revisar
    resumen: str | None = None


class ProveedorBusqueda(Protocol):
    async def buscar(
        self, consulta: str, *, limite: int = 5
    ) -> list[ResultadoBusqueda]: ...


class ProveedorBusquedaCurado:
    """Proveedor para la demo: referencias derivadas de la consulta, con fuentes.
    Determinista y sin red (no gasta nada). Reemplazable por uno real sin tocar el
    agente."""

    _PLANTILLAS = [
        (
            "Casos y referencias: {b}",
            "https://www.google.com/search?q={q}",
            "Casos y campañas relacionadas con «{b}».",
        ),
        (
            "Inspiración visual: {b}",
            "https://www.pinterest.com/search/pins/?q={q}",
            "Tableros con ideas visuales para «{b}».",
        ),
        (
            "Activaciones BTL: {b}",
            "https://www.behance.net/search/projects?search={q}",
            "Proyectos creativos y activaciones sobre «{b}».",
        ),
    ]

    async def buscar(
        self, consulta: str, *, limite: int = 5
    ) -> list[ResultadoBusqueda]:
        base = (consulta or "").strip() or "referencias de activación"
        q = quote_plus(base)
        resultados = [
            ResultadoBusqueda(
                titulo=titulo.format(b=base),
                referencia=url.format(q=q),
                resumen=resumen.format(b=base),
            )
            for (titulo, url, resumen) in self._PLANTILLAS
        ]
        return resultados[:limite]


# Modelo para la búsqueda (mismo Sonnet del chat: enrutar por costo, regla #4). El
# web search es un *server tool*: Sonnet 4.6 lo soporta y filtra resultados antes de
# meterlos al contexto.
_MODELO_BUSQUEDA = "claude-sonnet-4-6"

# `type`/`name` EXACTOS del web search NATIVO de Anthropic (server tool). Fuente: doc
# oficial https://platform.claude.com/docs/.../web-search-tool y la skill claude-api.
# El `type` es versionado (`web_search_20260209`, el más reciente, con filtrado
# dinámico en Sonnet 4.6); el `name` es fijo (`web_search`).
_TIPO_TOOL_WEB_SEARCH = "web_search_20260209"
_NOMBRE_TOOL_WEB_SEARCH = "web_search"

_MAX_TOKENS_BUSQUEDA = 1024


class ProveedorBusquedaWeb:
    """Proveedor REAL: usa el **web search nativo** de Anthropic (server tool) para traer
    referencias de internet de VERDAD (Tipo 2). Implementa el mismo Protocol
    `ProveedorBusqueda`, así que el agente (javo.py) no cambia.

    Cómo funciona: hace UNA llamada a `messages.create` habilitando el tool
    `web_search_20260209`. El modelo ejecuta la búsqueda SERVER-SIDE (no la corremos
    nosotros) y la respuesta trae bloques `web_search_tool_result` cuyo `content` son
    items `web_search_result` (título / url / page_age / encrypted_content). Los
    parseamos al contrato `ResultadoBusqueda` (titulo, referencia=url, resumen=page_age).

    El cliente Anthropic se INYECTA (regla #3: el LLM vive sólo en el backend; en tests
    se mockea, cero red, cero tokens)."""

    def __init__(self, cliente):
        self._cliente = cliente

    async def buscar(
        self, consulta: str, *, limite: int = 5
    ) -> list[ResultadoBusqueda]:
        base = (consulta or "").strip() or "referencias de activación"
        instruccion = (
            "Busca en internet referencias, casos y ejemplos visuales para esta "
            f"activación de marketing/BTL: «{base}». Devuelve fuentes citables."
        )
        respuesta = await self._cliente.messages.create(
            model=_MODELO_BUSQUEDA,
            max_tokens=_MAX_TOKENS_BUSQUEDA,
            messages=[{"role": "user", "content": instruccion}],
            tools=[
                {"type": _TIPO_TOOL_WEB_SEARCH, "name": _NOMBRE_TOOL_WEB_SEARCH}
            ],
        )
        resultados = _parsear_resultados(respuesta)
        return resultados[:limite]


def _parsear_resultados(respuesta) -> list[ResultadoBusqueda]:
    """Recorre los bloques de la respuesta del SDK y extrae los `web_search_result` de
    cada `web_search_tool_result`, mapeándolos al contrato. Tolera: ausencia de bloques
    de resultado (el modelo no buscó), y el `content` de error (un dict, no una lista)."""
    salida: list[ResultadoBusqueda] = []
    for bloque in getattr(respuesta, "content", []) or []:
        if getattr(bloque, "type", None) != "web_search_tool_result":
            continue
        contenido = getattr(bloque, "content", None)
        if not isinstance(contenido, list):  # bloque de error: {type: ..._error}
            continue
        for item in contenido:
            url = _campo(item, "url")
            titulo = _campo(item, "title") or url
            if not (url or titulo):
                continue
            salida.append(
                ResultadoBusqueda(
                    titulo=titulo or "",
                    referencia=url or "",
                    resumen=_campo(item, "page_age"),
                )
            )
    return salida


def _campo(item, clave: str):
    """Lee `clave` de un item que puede venir como dict o como objeto con atributos
    (según sea el SDK real o el doble de tests)."""
    if isinstance(item, dict):
        return item.get(clave)
    return getattr(item, clave, None)
