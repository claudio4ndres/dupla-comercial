"""Implementación real del repositorio de tareas contra Supabase.

Habla con PostgREST (`/rest/v1`) usando el **JWT del usuario**: la RLS de Postgres
filtra por su empresa (regla de oro #2). Se construye **por request** con el token
del usuario; nunca se reutiliza entre usuarios.

Lista TODAS las tareas de la empresa (la RLS hace el filtro), pidiendo sólo los
campos del contrato; NO se pide `empresa_id` (no debe viajar, CA5).

Cero red en los tests: se inyecta un `httpx.AsyncClient` con transporte mockeado
(calca a `propuestas_supabase.py`).
"""
from uuid import UUID

import httpx

from app.repositorios.tareas import TareaResumen

# Sólo los campos del contrato; la RLS ya restringe a la empresa del JWT.
_SELECT = "nombre,grupo,responsable,vencimiento"


class RepositorioTareasSupabase:
    """Repositorio `RepositorioTareas` respaldado por PostgREST de Supabase."""

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

    async def listar(self, empresa_id: UUID) -> list[TareaResumen]:
        # La RLS ya restringe a la empresa del JWT (regla #2): basta con pedir las tareas.
        resp = await self._peticion(
            "GET",
            f"/tareas?select={_SELECT}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        filas = resp.json()
        return [
            TareaResumen(
                empresa_id=empresa_id,
                nombre=fila["nombre"],
                grupo=fila.get("grupo"),
                responsable=fila.get("responsable"),
                vencimiento=fila.get("vencimiento"),
            )
            for fila in filas
        ]
