"""T13 · Implementación real del repositorio de conversaciones contra Supabase.

Habla con PostgREST (`/rest/v1`) usando el **JWT del usuario**: la RLS de Postgres
filtra por su empresa (regla de oro #2 — la barrera multi-tenant es la RLS, no un
filtro del backend). Se construye **por request** con el token del usuario; nunca se
reutiliza entre usuarios.

Traduce el vocabulario entre el front y la base:
  - rol  `javo` ⇆ `asistente` (la columna `mensajes.rol` sólo admite
    `usuario`/`asistente`/`sistema`).
  - tipo `t1`/`t2` → `tipo_1`/`tipo_2` (CHECK de `conversaciones.tipo`).

`guardar_turnos` hace *find-or-create* de la fila `conversaciones` por (solicitud,
empresa) y luego inserta los mensajes nuevos. Cero red en los tests: se inyecta un
`httpx.AsyncClient` con transporte mockeado.
"""
from uuid import UUID

import httpx

from app.repositorios.conversaciones import MensajeGuardado

# Mapeos front ⇆ base. El front usa `javo`; la columna `rol` admite `asistente`.
_ROL_A_BASE = {"usuario": "usuario", "javo": "asistente", "sistema": "sistema"}
_ROL_DESDE_BASE = {"usuario": "usuario", "asistente": "javo", "sistema": "sistema"}

# El tipo confirmado en el chat (`t1`/`t2`) vs. el CHECK de la tabla (`tipo_1`/`tipo_2`).
_TIPO_A_BASE = {"t1": "tipo_1", "t2": "tipo_2"}


class RepositorioConversacionesSupabase:
    """Repositorio `RepositorioConversaciones` respaldado por PostgREST de Supabase."""

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

    async def obtener_mensajes(
        self, solicitud_id: UUID, empresa_id: UUID
    ) -> list[MensajeGuardado]:
        # La RLS ya restringe a la empresa del JWT (regla #2). Filtramos los mensajes
        # por la conversación de ESTA solicitud (vía el embedding `!inner`) y ordenamos
        # cronológicamente. No pedimos `empresa_id` (no debe viajar): la empresa la fija
        # el argumento; el aislamiento lo garantiza la RLS.
        resp = await self._peticion(
            "GET",
            "/mensajes?select=rol,contenido,creado_en,conversaciones!inner(solicitud_id)"
            f"&conversaciones.solicitud_id=eq.{solicitud_id}&order=creado_en.asc",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return [
            MensajeGuardado(
                rol=_ROL_DESDE_BASE.get(fila["rol"], fila["rol"]),
                contenido=fila["contenido"],
                creado_en=fila["creado_en"],
            )
            for fila in resp.json()
        ]

    async def _id_conversacion(
        self, solicitud_id: UUID, empresa_id: UUID, tipo: str
    ) -> str:
        """Devuelve el id de la conversación de (solicitud, empresa), creándola si no
        existe. La RLS garantiza que sólo se vea/cree dentro de la empresa del JWT."""
        resp = await self._peticion(
            "GET",
            f"/conversaciones?select=id&solicitud_id=eq.{solicitud_id}&limit=1",
            headers=self._headers(),
        )
        resp.raise_for_status()
        filas = resp.json()
        if filas:
            return filas[0]["id"]

        # No existe: la creamos con su empresa, solicitud y el tipo mapeado al CHECK.
        # `empresa_id` viaja explícito (la fila lo exige y el WITH CHECK de la RLS
        # valida que coincida con la empresa del JWT).
        resp = await self._peticion(
            "POST",
            "/conversaciones",
            headers=self._headers({"Prefer": "return=representation"}),
            json={
                "empresa_id": str(empresa_id),
                "solicitud_id": str(solicitud_id),
                "tipo": _TIPO_A_BASE.get(tipo, "tipo_1"),
            },
        )
        resp.raise_for_status()
        return resp.json()[0]["id"]

    async def guardar_turnos(
        self,
        solicitud_id: UUID,
        empresa_id: UUID,
        tipo: str,
        nuevos: list[dict],
    ) -> None:
        if not nuevos:
            return
        conversacion_id = await self._id_conversacion(solicitud_id, empresa_id, tipo)
        filas = [
            {
                "conversacion_id": conversacion_id,
                "rol": _ROL_A_BASE.get(n["rol"], n["rol"]),
                "contenido": n["contenido"],
            }
            for n in nuevos
        ]
        resp = await self._peticion(
            "POST", "/mensajes", headers=self._headers(), json=filas
        )
        resp.raise_for_status()
