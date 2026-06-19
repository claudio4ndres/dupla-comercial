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

from app.repositorios.cliente_postgrest import ClientePostgREST
from app.repositorios.conversaciones import MensajeGuardado

# Mapeos front ⇆ base. El front usa `javo`; la columna `rol` admite `asistente`.
_ROL_A_BASE = {"usuario": "usuario", "javo": "asistente", "sistema": "sistema"}
_ROL_DESDE_BASE = {"usuario": "usuario", "asistente": "javo", "sistema": "sistema"}

# El tipo confirmado en el chat (`t1`/`t2`) vs. el CHECK de la tabla (`tipo_1`/`tipo_2`).
_TIPO_A_BASE = {"t1": "tipo_1", "t2": "tipo_2"}


class RepositorioConversacionesSupabase(ClientePostgREST):
    """Repositorio `RepositorioConversaciones` respaldado por PostgREST de Supabase."""

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

    async def obtener_o_crear_conversacion(
        self, solicitud_id: UUID, empresa_id: UUID, tipo: str
    ) -> UUID:
        """Versión pública de `_id_conversacion`: la usa el write-path de propuestas
        para ligar la propuesta a la conversación de la solicitud."""
        return UUID(await self._id_conversacion(solicitud_id, empresa_id, tipo))

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

    async def guardar_borrador(
        self,
        solicitud_id: UUID,
        empresa_id: UUID,
        tipo: str,
        borrador: dict,
    ) -> None:
        """Guarda el ÚLTIMO estado de la cotización en curso (componentes/tareas/fuentes
        que Javo propuso) en la columna jsonb `cotizacion_borrador` de la conversación.
        Find-or-create de la conversación por (solicitud, empresa) y PATCH de la columna.
        La RLS (WITH CHECK por empresa del JWT) impide tocar conversaciones de otra empresa."""
        conversacion_id = await self._id_conversacion(solicitud_id, empresa_id, tipo)
        resp = await self._peticion(
            "PATCH",
            f"/conversaciones?id=eq.{conversacion_id}",
            headers=self._headers(),
            json={"cotizacion_borrador": borrador},
        )
        resp.raise_for_status()

    async def obtener_borrador(
        self, solicitud_id: UUID, empresa_id: UUID
    ) -> dict | None:
        """Lee el borrador de la cotización de la conversación de ESA solicitud. La RLS
        del JWT restringe a la empresa del usuario; si no hay conversación o la columna
        está vacía, devuelve None (el front parte el panel sin cotización en curso)."""
        resp = await self._peticion(
            "GET",
            f"/conversaciones?select=cotizacion_borrador&solicitud_id=eq.{solicitud_id}&limit=1",
            headers=self._headers(),
        )
        resp.raise_for_status()
        filas = resp.json()
        if not filas:
            return None
        return filas[0].get("cotizacion_borrador")
