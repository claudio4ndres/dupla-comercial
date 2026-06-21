"""Rutas del conector ClickUp (listas + OAuth por empresa, Spec 009).

`GET /clickup/listas` alimenta el SELECTOR de lista destino en la pantalla de Tareas:
devuelve las listas reales del usuario (planas) para que ELIJA dónde crear las tareas
de la propuesta (decisión de producto: la lista NO va hardcodeada, es por-empresa como
un conector). Requiere auth (la empresa sale del JWT).

* Sin token configurado → 200 con `[]` (el front muestra "conecta ClickUp"); NO se
  llama a ClickUp.
* Si ClickUp falla (token inválido, red, 5xx) → 502 (servicio externo caído).

`POST /clickup/verificar` ejecuta la lógica de auto-heal de forma EXPLÍCITA: el front
lo llama solo cuando el usuario quiere verificar/reparar la conexión ClickUp. El GET
queda puro (sin side effects, RFC 7231 §4.2.1).

El OAuth por empresa (iniciar/callback/estado/desconectar) ESPEJA el de Gmail
(`rutas/integraciones.py`): el token se resuelve por-tenant y vive SÓLO en el backend
(Secret Manager); jamás viaja al front (CA5). El endpoint que CREA las tareas vive en
`rutas/solicitudes.py` (cuelga de una solicitud).
"""
import secrets
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.dependencias import (
    obtener_almacen_estado_oauth,
    obtener_almacen_secretos,
    obtener_cliente_clickup,
    obtener_cliente_oauth_clickup,
    obtener_config_oauth_clickup,
    obtener_empresa_actual,
    obtener_repositorio_integraciones,
    obtener_repositorio_integraciones_servicio,
)
from app.esquemas import (
    EstadoClickUp,
    ListaClickUpSalida,
    ResultadoVerificacionClickUp,
    UrlConsentimiento,
)
from app.repositorios.integraciones import Integracion
from app.servicios.oauth_clickup import ConfigOAuthClickUp, construir_url_consentimiento

router = APIRouter(prefix="/clickup", tags=["clickup"])


# ── Helper de auto-heal (extraído del GET, ahora reutilizable) ────────────────

async def verificar_integracion_clickup(
    clickup,
    repo,
    empresa_id: UUID,
) -> ResultadoVerificacionClickUp:
    """Verifica la integración ClickUp de la empresa y repara el estado si es necesario.

    - Sin token → no hay integración, nada que verificar.
    - Llama a ClickUp (/listas) para probar que el token funciona.
    - Si funciona y la integración venía 'reconectar', la repara a 'conectado'.
    - Si ClickUp falla (token inválido), marca 'reconectar'.

    Retorna el estado resultante + un mensaje descriptivo."""
    if not clickup.tiene_token:
        return ResultadoVerificacionClickUp(
            estado="sin_conectar",
            mensaje="La empresa no tiene integración ClickUp configurada.",
        )

    try:
        await clickup.listar_listas()
    except Exception:
        # El token no sirve: marcar 'reconectar' si no estaba ya.
        integracion = await repo.obtener_por_empresa_y_proveedor(empresa_id, "clickup")
        if integracion is not None and integracion.estado != "reconectar":
            await repo.marcar_estado(empresa_id, "reconectar", "clickup")
        return ResultadoVerificacionClickUp(
            estado="reconectar",
            mensaje="El token de ClickUp no es válido. Se requiere reconexión.",
        )

    # Token funciona: restaurar a 'conectado' si venía en otro estado.
    integracion = await repo.obtener_por_empresa_y_proveedor(empresa_id, "clickup")
    if integracion is not None and integracion.estado != "conectado":
        await repo.marcar_estado(empresa_id, "conectado", "clickup")
        return ResultadoVerificacionClickUp(
            estado="conectado",
            mensaje="La integración fue reparada automáticamente (auto-heal).",
        )
    return ResultadoVerificacionClickUp(
        estado="conectado",
        mensaje="La integración ClickUp funciona correctamente.",
    )


@router.get("/listas", response_model=list[ListaClickUpSalida])
async def listar_listas(
    clickup=Depends(obtener_cliente_clickup),
) -> list[ListaClickUpSalida]:
    """Listas reales del ClickUp del usuario (planas) para el selector de destino.

    Endpoint PURO (sin side effects): solo lee y devuelve listas. No muta el estado
    de la integración. Para verificar/reparar la conexión, usar POST /clickup/verificar.
    """
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


@router.post("/verificar", response_model=ResultadoVerificacionClickUp)
async def verificar_clickup(
    clickup=Depends(obtener_cliente_clickup),
    repo=Depends(obtener_repositorio_integraciones),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> ResultadoVerificacionClickUp:
    """Verifica y repara la integración ClickUp de la empresa (auto-heal explícito).

    El front llama a este endpoint cuando el usuario quiere verificar la conexión
    (botón "Verificar conexión"). Es un POST porque PUEDE mutar el estado de la
    integración (cambiar 'reconectar' → 'conectado' o viceversa).

    NOTA para el frontend: este endpoint REEMPLAZA el auto-heal implícito que antes
    vivía en GET /clickup/listas. El GET ahora es puro (sin side effects). Si el front
    detecta un 502 al cargar listas, puede ofrecer al usuario llamar a este endpoint
    para diagnosticar la conexión."""
    return await verificar_integracion_clickup(clickup, repo, empresa_id)


@router.get("/estado", response_model=EstadoClickUp)
async def estado_clickup(
    repo=Depends(obtener_repositorio_integraciones),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> EstadoClickUp:
    """Estado del conector ClickUp de la empresa, por EXISTENCIA de la integración
    (aclaración #5: barato, sin llamar a ClickUp). Sin integración → todo null
    ("Sin conectar", CA1). El conteo de listas es una llamada viva aparte
    (`/clickup/listas`). Nunca incluye tokens (CA5, garantizado por el `response_model`)."""
    integracion = await repo.obtener_por_empresa_y_proveedor(empresa_id, "clickup")
    if integracion is None:
        return EstadoClickUp()
    return EstadoClickUp(
        proveedor=integracion.proveedor, estado=integracion.estado
    )


@router.post("/iniciar", response_model=UrlConsentimiento)
async def iniciar_clickup(
    config: ConfigOAuthClickUp = Depends(obtener_config_oauth_clickup),
    almacen=Depends(obtener_almacen_estado_oauth),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> UrlConsentimiento:
    """Arranca el consentimiento de ClickUp: genera un `state` anti-CSRF ligado a la
    empresa, lo registra y devuelve la URL de ClickUp a la que el front redirige.

    No toca ClickUp: sólo construye la URL (client_id + redirect_uri + state). El canje
    ocurre en el callback (CA2)."""
    state = secrets.token_urlsafe(32)
    await almacen.guardar(state, empresa_id)
    return UrlConsentimiento(url=construir_url_consentimiento(config, state))


@router.get("/callback")
async def callback_clickup(
    code: str,
    state: str,
    config: ConfigOAuthClickUp = Depends(obtener_config_oauth_clickup),
    almacen_estado=Depends(obtener_almacen_estado_oauth),
    oauth=Depends(obtener_cliente_oauth_clickup),
    secretos=Depends(obtener_almacen_secretos),
    repo=Depends(obtener_repositorio_integraciones_servicio),
) -> RedirectResponse:
    """Cierra el consentimiento: valida el `state` (anti-CSRF), canjea el `code` por el
    access token, lo guarda como secreto y persiste la integración clickup conectada;
    luego redirige al front. El token nunca sale en la respuesta (CA5).

    La empresa se toma del `state` validado (no del JWT): es el navegador el que vuelve
    de ClickUp (un redirect, sin header `Authorization`), y el `state` es lo que liga
    ese retorno a su empresa. Por eso el repo es el de SERVICIO (service role): no hay
    JWT que active la RLS, así que escribimos con `empresa_id` EXPLÍCITO del state
    (jamás se infiere → no cruza tenants)."""
    empresa_id = await almacen_estado.consumir(state)
    if empresa_id is None:
        raise HTTPException(status_code=400, detail="state inválido o expirado")

    credenciales = await oauth.canjear_codigo(code)
    token_ref = await secretos.guardar(
        f"clickup-token-{empresa_id}", credenciales.access_token
    )
    await repo.guardar(
        Integracion(
            id=uuid4(),
            empresa_id=empresa_id,  # EXPLÍCITO, del state (no inferido)
            proveedor="clickup",
            token_ref=token_ref,
            casilla=None,
            cursor=None,
            estado="conectado",
        )
    )
    return RedirectResponse(url=config.url_post_conexion, status_code=302)


@router.delete("", status_code=204)
async def desconectar_clickup(
    repo=Depends(obtener_repositorio_integraciones),
    secretos=Depends(obtener_almacen_secretos),
    empresa_id: UUID = Depends(obtener_empresa_actual),
) -> None:
    """Desconecta ClickUp de la empresa (el botón "Cambiar"): borra el secreto (access
    token) y elimina SÓLO la fila clickup de `integraciones` (no toca gmail). Idempotente:
    si no hay integración clickup, responde 204 igual (CA7)."""
    integracion = await repo.obtener_por_empresa_y_proveedor(empresa_id, "clickup")
    if integracion is not None:
        await secretos.borrar(integracion.token_ref)
        await repo.eliminar_por_proveedor(empresa_id, "clickup")
