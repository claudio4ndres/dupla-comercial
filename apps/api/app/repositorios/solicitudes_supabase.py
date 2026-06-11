"""T7c · Implementación real del repositorio de solicitudes contra Supabase.

Habla con PostgREST (`/rest/v1`) usando el **JWT del usuario**: así la RLS de
Postgres filtra por su empresa (regla de oro #2 — la barrera multi-tenant es la
RLS, no un filtro del backend). Se construye **por request** con el token del
usuario; nunca se reutiliza entre usuarios.

Cero red en los tests: se inyecta un `httpx.AsyncClient` con transporte mockeado.
"""
from uuid import UUID

import httpx

from app.repositorios.solicitudes import Solicitud
from app.servicios.gmail import MensajeCorreo


class RepositorioSolicitudesSupabase:
    """Repositorio `RepositorioSolicitudes` respaldado por PostgREST de Supabase."""

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

    def _headers(self, extra: dict | None = None) -> dict:
        # `apikey` identifica al proyecto; `Authorization` lleva el JWT del usuario,
        # que es lo que activa la RLS a nombre de SU empresa.
        cabeceras = {
            "apikey": self._anon,
            "Authorization": f"Bearer {self._jwt}",
            "Content-Type": "application/json",
        }
        if extra:
            cabeceras.update(extra)
        return cabeceras

    async def _peticion(self, metodo: str, ruta: str, **kw) -> httpx.Response:
        url = self._base + ruta
        if self._cliente is not None:
            return await self._cliente.request(metodo, url, **kw)
        async with httpx.AsyncClient() as cliente:
            return await cliente.request(metodo, url, **kw)

    async def obtener(self, solicitud_id: UUID, empresa_id: UUID) -> Solicitud | None:
        # La RLS ya restringe a la empresa del JWT; no hace falta filtrar por
        # empresa_id en el backend (regla #2). Filtramos por id y pedimos la fila.
        resp = await self._peticion(
            "GET",
            f"/solicitudes?id=eq.{solicitud_id}&select=*",
            headers=self._headers(),
        )
        resp.raise_for_status()
        filas = resp.json()
        if not filas:
            return None
        return Solicitud(**filas[0])

    async def listar(self, empresa_id: UUID) -> list[Solicitud]:
        # La RLS ya restringe a la empresa del JWT (regla #2): pedimos todas las
        # filas visibles. `empresa_id` viaja por la firma del Protocol pero no se
        # filtra en el backend; la barrera multi-tenant es la RLS, no este código.
        resp = await self._peticion(
            "GET",
            "/solicitudes?select=*",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return [Solicitud(**fila) for fila in resp.json()]

    async def guardar_clasificacion(
        self, solicitud_id: UUID, empresa_id: UUID, resumen: str, tipo: str
    ) -> Solicitud:
        resp = await self._peticion(
            "PATCH",
            f"/solicitudes?id=eq.{solicitud_id}",
            headers=self._headers({"Prefer": "return=representation"}),
            json={"resumen": resumen, "tipo": tipo},
        )
        resp.raise_for_status()
        filas = resp.json()
        if not filas:
            raise KeyError(solicitud_id)
        return Solicitud(**filas[0])

    async def crear_desde_correo(
        self,
        empresa_id: UUID,
        mensaje: MensajeCorreo,
        *,
        resumen: str | None = None,
        tipo: str = "sin_clasificar",
    ) -> bool:
        """Inserta una solicitud desde un correo, idempotente por el índice único
        parcial `(empresa_id, gmail_msg_id)`. `resolution=ignore-duplicates` hace
        que un duplicado no falle y devuelva sin filas → `False`. `resumen`/`tipo`
        vienen del clasificador (si corrió); si no, queda 'sin_clasificar'."""
        resp = await self._peticion(
            "POST",
            "/solicitudes",
            headers=self._headers(
                {"Prefer": "return=representation,resolution=ignore-duplicates"}
            ),
            json={
                "empresa_id": str(empresa_id),
                "gmail_msg_id": mensaje.gmail_msg_id,
                "remitente": mensaje.remitente,
                "correo_origen": mensaje.correo_origen,
                "asunto": mensaje.asunto,
                "cuerpo": mensaje.cuerpo,
                "resumen": resumen,
                "tipo": tipo,
                "estado": "nueva",
            },
        )
        resp.raise_for_status()
        filas = resp.json()
        return bool(filas)
