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
