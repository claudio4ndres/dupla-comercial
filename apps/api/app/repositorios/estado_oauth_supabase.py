"""Spec 015 · Almacén del `state` anti-CSRF respaldado por Supabase.

Mismo contrato que `AlmacenEstadoOAuthEnMemoria` (`guardar`/`consumir`), pero el
state vive en la tabla `estados_oauth`: sobrevive reinicios y funciona con varias
instancias de Cloud Run (el callback puede aterrizar en cualquiera).

El consumo es ATÓMICO: un DELETE con `Prefer: return=representation` filtrando
por vigencia. Si dos instancias intentan consumir el mismo state, solo una
recibe la fila (anti-replay); la otra ve `[]` → None. Corre con la service role
(la tabla tiene RLS sin políticas: los JWT de usuario no la tocan).
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.repositorios.cliente_postgrest import ClientePostgREST

# Cuánto vive un state: suficiente para el redirect de consentimiento, corto
# para no acumular basura ni ampliar la ventana de un ataque.
TTL_MINUTOS = 10


class AlmacenEstadoOAuthSupabase(ClientePostgREST):
    """`AlmacenEstadoOAuth` respaldado por PostgREST (tabla `estados_oauth`)."""

    async def guardar(self, state: str, empresa_id: UUID) -> None:
        expira = datetime.now(timezone.utc) + timedelta(minutes=TTL_MINUTOS)
        resp = await self._peticion(
            "POST",
            "/estados_oauth",
            headers=self._headers(),
            json={
                "state": state,
                "empresa_id": str(empresa_id),
                "expira_en": expira.isoformat(),
            },
        )
        resp.raise_for_status()

    async def consumir(self, state: str) -> UUID | None:
        ahora = datetime.now(timezone.utc).isoformat()
        # DELETE devolviendo la fila = consumo atómico entre instancias. El filtro
        # de vigencia hace que un state vencido no se consuma (devuelve []).
        resp = await self._peticion(
            "DELETE",
            "/estados_oauth",
            headers=self._headers({"Prefer": "return=representation"}),
            params={"state": f"eq.{state}", "expira_en": f"gt.{ahora}"},
        )
        resp.raise_for_status()
        filas = resp.json()
        if not filas:
            return None
        return UUID(filas[0]["empresa_id"])
