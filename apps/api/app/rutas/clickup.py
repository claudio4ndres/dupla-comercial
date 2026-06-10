"""Rutas del conector ClickUp.

`GET /clickup/listas` alimenta el SELECTOR de lista destino en la pantalla de Tareas:
devuelve las listas reales del usuario (planas) para que ELIJA dónde crear las tareas
de la propuesta (decisión de producto: la lista NO va hardcodeada, es por-empresa como
un conector). Requiere auth (la empresa sale del JWT).

* Sin token configurado → 200 con `[]` (el front muestra "conecta ClickUp"); NO se
  llama a ClickUp.
* Si ClickUp falla (token inválido, red, 5xx) → 502 (servicio externo caído).

El token vive sólo en el backend (regla de oro #3); jamás viaja al front. El endpoint
que CREA las tareas vive en `rutas/solicitudes.py` (cuelga de una solicitud).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.dependencias import obtener_cliente_clickup, obtener_empresa_actual
from app.esquemas import ListaClickUpSalida

router = APIRouter(prefix="/clickup", tags=["clickup"])


@router.get("/listas", response_model=list[ListaClickUpSalida])
async def listar_listas(
    clickup=Depends(obtener_cliente_clickup),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> list[ListaClickUpSalida]:
    """Listas reales del ClickUp del usuario (planas) para el selector de destino."""
    # Sin token: la empresa aún no conectó ClickUp → [] (el front muestra el aviso).
    if not clickup.tiene_token:
        return []
    try:
        listas = await clickup.listar_listas()
    except Exception as exc:
        # ClickUp es un servicio externo: si cae, es un 502 (no un 500 crudo).
        raise HTTPException(
            status_code=502, detail="El servicio de ClickUp no está disponible"
        ) from exc
    return [
        ListaClickUpSalida(id=l.id, nombre=l.nombre, espacio=l.espacio)
        for l in listas
    ]
