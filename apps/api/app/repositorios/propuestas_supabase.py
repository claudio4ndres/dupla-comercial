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
    PropuestaResumen,
    TareaPropuesta,
    _total_de,
)

# `select` con embedding: la propuesta + sus hijos + la conversación (sólo para
# filtrar por la solicitud). NO se pide `empresa_id` (no debe viajar, CA5); el
# repo conoce la empresa por el argumento.
_SELECT = (
    "id,total,estado,"
    "componentes_propuesta(nombre,detalle,proveedor,origen,cantidad,dias,valor_unitario),"
    "tareas(nombre,grupo,responsable,vencimiento),"
    "conversaciones!inner(solicitud_id)"
)

# `select` para la LISTA: sólo la cabecera de cada propuesta + la solicitud ligada
# (vía la conversación) para traer `asunto` y `remitente`. NO se pide `empresa_id`
# (no debe viajar, CA5); la RLS ya restringe a la empresa del JWT.
_SELECT_LISTA = (
    "id,total,estado,"
    "conversaciones!inner(solicitud_id,solicitudes(asunto,remitente))"
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
            f"&conversaciones.solicitud_id=eq.{solicitud_id}"
            # #4 · ordenar por `creado_en.desc` para servir SIEMPRE la última versión:
            # sin `order`, PostgREST puede devolver una propuesta vieja/arbitraria (la
            # descarga Excel/PPT/ClickUp leía una stale).
            "&order=creado_en.desc&limit=1",
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

    async def _id_propuesta_existente(self, conversacion_id: UUID) -> str | None:
        """#4 · ¿ya hay una propuesta para esta conversación? Devuelve su id o None.

        La unicidad real la garantiza el índice UNIQUE `propuestas.conversacion_id`
        (migración 0007); este GET resuelve la idempotencia ANTES de insertar para no
        chocar contra ese UNIQUE y poder REEMPLAZAR los hijos sobre la misma fila."""
        resp = await self._peticion(
            "GET",
            f"/propuestas?select=id&conversacion_id=eq.{conversacion_id}&limit=1",
            headers=self._headers(),
        )
        resp.raise_for_status()
        filas = resp.json()
        return filas[0]["id"] if filas else None

    async def crear(
        self,
        empresa_id: UUID,
        solicitud_id: UUID,
        conversacion_id: UUID,
        componentes: list[ComponentePropuesta],
        tareas: list[TareaPropuesta],
    ) -> Propuesta:
        """Persiste la propuesta que armó Javo: cabecera + componentes + tareas, todo
        ligado a la conversación de la solicitud (propuesta→conversacion→solicitud).
        La RLS exige `empresa_id` = empresa del JWT (regla #2).

        IDEMPOTENTE (#4, Sev ALTA): la conversación se reutiliza por (solicitud, tipo),
        así que un clic doble en "Generar propuesta" caería sobre la MISMA conversación.
        Antes esto INSERTABA una segunda propuesta con componentes/tareas duplicados; ahora,
        si ya existe propuesta para esa conversación, se REEMPLAZA: se borran sus hijos
        (`componentes_propuesta` + `tareas`) y se re-insertan los nuevos sobre la misma fila.
        """
        total = _total_de(componentes)
        # 1. Cabecera: ¿ya existe propuesta para esta conversación? → REEMPLAZAR; si no → INSERT.
        propuesta_id = await self._id_propuesta_existente(conversacion_id)
        if propuesta_id is not None:
            # REEMPLAZAR: actualiza el total/estado y borra los hijos viejos antes de re-insertar.
            patch = await self._peticion(
                "PATCH",
                f"/propuestas?id=eq.{propuesta_id}",
                headers={**self._headers(), "Prefer": "return=representation"},
                json={"total": total, "estado": "borrador"},
            )
            patch.raise_for_status()
            # Borra los hijos de la versión anterior (reemplazo limpio, sin duplicados).
            d1 = await self._peticion(
                "DELETE",
                f"/componentes_propuesta?propuesta_id=eq.{propuesta_id}",
                headers=self._headers(),
            )
            d1.raise_for_status()
            d2 = await self._peticion(
                "DELETE",
                f"/tareas?propuesta_id=eq.{propuesta_id}",
                headers=self._headers(),
            )
            d2.raise_for_status()
        else:
            resp = await self._peticion(
                "POST",
                "/propuestas",
                headers={**self._headers(), "Prefer": "return=representation"},
                json={
                    "empresa_id": str(empresa_id),
                    "conversacion_id": str(conversacion_id),
                    "total": total,
                    "estado": "borrador",
                },
            )
            resp.raise_for_status()
            propuesta_id = resp.json()[0]["id"]
        # 2. Componentes valorizados (un POST con el array).
        if componentes:
            r2 = await self._peticion(
                "POST",
                "/componentes_propuesta",
                headers=self._headers(),
                json=[
                    {
                        "propuesta_id": propuesta_id,
                        "nombre": c.nombre,
                        "detalle": c.detalle,
                        "proveedor": c.proveedor,
                        "origen": c.origen,
                        "cantidad": c.cantidad,
                        "dias": c.dias,
                        "valor_unitario": c.valor_unitario,
                    }
                    for c in componentes
                ],
            )
            r2.raise_for_status()
        # 3. Tareas de ejecución (llevan empresa_id propio + propuesta_id).
        if tareas:
            r3 = await self._peticion(
                "POST",
                "/tareas",
                headers=self._headers(),
                json=[
                    {
                        "empresa_id": str(empresa_id),
                        "propuesta_id": propuesta_id,
                        "nombre": t.nombre,
                        "grupo": t.grupo,
                        "responsable": t.responsable,
                        "vencimiento": t.vencimiento,
                    }
                    for t in tareas
                ],
            )
            r3.raise_for_status()
        return Propuesta(
            id=propuesta_id,
            empresa_id=empresa_id,
            solicitud_id=solicitud_id,
            total=total,
            estado="borrador",
            componentes=componentes,
            tareas=tareas,
        )

    async def actualizar_estado(
        self, propuesta_id: UUID, empresa_id: UUID, nuevo_estado: str
    ) -> Propuesta:
        """#7 · Transiciona el estado de la propuesta (borrador→aprobada→enviada).

        La validación de la transición la hace el endpoint; aquí sólo se persiste el
        nuevo estado. La RLS filtra por la empresa del JWT (regla #2): un usuario sólo
        puede mover propuestas de su empresa. Devuelve la fila actualizada."""
        resp = await self._peticion(
            "PATCH",
            f"/propuestas?id=eq.{propuesta_id}",
            headers={**self._headers(), "Prefer": "return=representation"},
            json={"estado": nuevo_estado},
        )
        resp.raise_for_status()
        filas = resp.json()
        if not filas:
            raise KeyError(propuesta_id)
        fila = filas[0]
        return Propuesta(
            id=fila["id"],
            empresa_id=empresa_id,
            solicitud_id=fila.get("solicitud_id") or UUID(int=0),
            total=fila.get("total", 0) or 0,
            estado=fila.get("estado", nuevo_estado),
        )

    async def listar(self, empresa_id: UUID) -> list[PropuestaResumen]:
        # La RLS ya restringe a la empresa del JWT (regla #2); traemos la cabecera de
        # cada propuesta con la solicitud embebida (asunto/remitente) en UNA llamada.
        resp = await self._peticion(
            "GET",
            f"/propuestas?select={_SELECT_LISTA}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        filas = resp.json()
        resumenes: list[PropuestaResumen] = []
        for fila in filas:
            conv = fila.get("conversaciones") or {}
            sol = conv.get("solicitudes") or {}
            resumenes.append(
                PropuestaResumen(
                    id=fila["id"],
                    empresa_id=empresa_id,
                    solicitud_id=conv.get("solicitud_id"),
                    total=fila.get("total", 0) or 0,
                    estado=fila.get("estado", "borrador"),
                    asunto=sol.get("asunto") or "",
                    remitente=sol.get("remitente") or "",
                )
            )
        return resumenes
