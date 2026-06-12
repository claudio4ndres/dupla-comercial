"""Tests del reproceso (servicio): re-baja + re-clasifica las solicitudes
'sin_clasificar'. Cero red, cero LLM (todo inyectado)."""
from uuid import uuid4

from app.esquemas import ResultadoClasificacion
from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.repositorios.solicitudes import RepositorioSolicitudesEnMemoria, Solicitud
from app.servicios.reprocesar import reprocesar_correos
from tests.dobles import ClienteGmailFake, ClienteGmailQueFallaAuth

EMPRESA = uuid4()


def _integracion():
    return Integracion(
        id=uuid4(),
        empresa_id=EMPRESA,
        proveedor="gmail",
        token_ref="secreto://x",
        casilla="x@x.cl",
        cursor=None,
        estado="conectado",
    )


async def _clasif_ok(texto: str) -> ResultadoClasificacion:
    return ResultadoClasificacion(resumen="Resumen recuperado", tipo="tipo_1")


async def _clasif_falla(texto: str) -> ResultadoClasificacion:
    raise ValueError("LLM caído")


def _pendiente(cuerpo: str = "") -> Solicitud:
    return Solicitud(
        id=uuid4(),
        empresa_id=EMPRESA,
        asunto="Cotización pendiente",
        cuerpo=cuerpo,
        tipo="sin_clasificar",
        gmail_msg_id="m-1",
    )


async def test_reprocesa_recupera_cuerpo_y_clasifica():
    # Correo que entró con cuerpo vacío (solo-HTML): al re-bajar recupera el cuerpo y
    # se clasifica → deja de estar 'sin_clasificar'.
    sol = _pendiente(cuerpo="")
    repo_sol = RepositorioSolicitudesEnMemoria([sol])
    repo_int = RepositorioIntegracionesEnMemoria([_integracion()])

    res = await reprocesar_correos(
        _integracion(), ClienteGmailFake([]), repo_sol, repo_int, _clasif_ok
    )

    assert res.revisadas == 1 and res.reclasificadas == 1
    actualizada = repo_sol.por_id(sol.id)
    assert actualizada.tipo == "tipo_1"
    assert actualizada.resumen == "Resumen recuperado"
    assert actualizada.cuerpo != ""  # se recuperó el cuerpo al re-bajar


async def test_reprocesa_no_toca_si_la_clasificacion_falla():
    # Si la clasificación falla (LLM caído / correo realmente vacío), la solicitud
    # queda igual ('sin_clasificar') para reintentar otra vez.
    sol = _pendiente()
    repo_sol = RepositorioSolicitudesEnMemoria([sol])
    repo_int = RepositorioIntegracionesEnMemoria([_integracion()])

    res = await reprocesar_correos(
        _integracion(), ClienteGmailFake([]), repo_sol, repo_int, _clasif_falla
    )

    assert res.revisadas == 1 and res.reclasificadas == 0
    assert repo_sol.por_id(sol.id).tipo == "sin_clasificar"


async def test_reprocesa_marca_reconectar_si_falla_auth():
    # Token expirado al re-bajar → marca 'reconectar' (CA7) y no rompe.
    sol = _pendiente()
    repo_sol = RepositorioSolicitudesEnMemoria([sol])
    repo_int = RepositorioIntegracionesEnMemoria([_integracion()])

    res = await reprocesar_correos(
        _integracion(), ClienteGmailQueFallaAuth(), repo_sol, repo_int, _clasif_ok
    )

    assert res.reclasificadas == 0
    integ = await repo_int.obtener_por_empresa(EMPRESA)
    assert integ.estado == "reconectar"
