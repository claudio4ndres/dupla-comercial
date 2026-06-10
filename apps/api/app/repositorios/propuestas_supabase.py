"""004 · Implementación real del repositorio de propuestas contra Supabase.

Habla con PostgREST (`/rest/v1`) usando el **JWT del usuario**: la RLS de Postgres
filtra por su empresa (regla de oro #2). Se construye **por request** con el token
del usuario; nunca se reutiliza entre usuarios.

Usa el *resource embedding* de PostgREST para traer en UNA llamada la propuesta con
sus `componentes_propuesta` y `tareas`, filtrando por la conversación de la
solicitud (`conversaciones!inner(solicitud_id)`).

Cero red en los tests: se inyecta un `httpx.AsyncClient` con transporte mockeado.
"""
from uuid import UUID

import httpx

from app.repositorios.propuestas import (
    ComponentePropuesta,
    Propuesta,
    TareaPropuesta,
)

# `select` con embedding: la propuesta + sus hijos + la conversación (sólo para
# filtrar por la solicitud). NO se pide `empresa_id` (no debe viajar, CA5); el
# repo conoce la empresa por el argumento.
_SELECT = (
    "id,total,estado,"
    "componentes_propuesta(nombre,detalle,cantidad,valor_unitario),"
    "tareas(nombre,grupo,responsable,vencimiento),"
    "conversaciones!inner(solicitud_id)"
)


class RepositorioPropuestasSupabase:
    """Repositorio `RepositorioPropuestas` respaldado por PostgREST de Supabase."""

    def __init__(
        self,
        base_url: str,
        anon_key: str,
        jwt: str,
        *,
        cliente: httpx.AsyncClient | None = None,
    ):
        self._base = base_url.rstrip("/") + "/rest/v1"
        self._anon = anon_key
        self._jwt = jwt
        self._cliente = cliente  # inyectable para tests; en prod se crea por llamada

    def _headers(self) -> dict:
        # `apikey` identifica al proyecto; `Authorization` lleva el JWT del usuario,
        # que es lo que activa la RLS a nombre de SU empresa.
        return {
            "apikey": self._anon,
            "Authorization": f"Bearer {self._jwt}",
            "Content-Type": "application/json",
        }

    async def _peticion(self, metodo: str, ruta: str, **kw) -> httpx.Response:
        url = self._base + ruta
        if self._cliente is not None:
            return await self._cliente.request(metodo, url, **kw)
        async with httpx.AsyncClient() as cliente:
            return await cliente.request(metodo, url, **kw)

    async def obtener_por_solicitud(
        self, solicitud_id: UUID, empresa_id: UUID
    ) -> Propuesta | None:
        # La RLS ya restringe a la empresa del JWT (regla #2); filtramos la propuesta
        # por la conversación de ESTA solicitud y traemos sus hijos embebidos.
        resp = await self._peticion(
            "GET",
            f"/propuestas?select={_SELECT}"
            f"&conversaciones.solicitud_id=eq.{solicitud_id}&limit=1",
            headers=self._headers(),
        )
        resp.raise_for_status()
        filas = resp.json()
        if not filas:
            return None
        fila = filas[0]
        return Propuesta(
            id=fila["id"],
            empresa_id=empresa_id,
            solicitud_id=solicitud_id,
            total=fila.get("total", 0) or 0,
            estado=fila.get("estado", "borrador"),
            componentes=[
                ComponentePropuesta(**c) for c in (fila.get("componentes_propuesta") or [])
            ],
            tareas=[TareaPropuesta(**t) for t in (fila.get("tareas") or [])],
        )
