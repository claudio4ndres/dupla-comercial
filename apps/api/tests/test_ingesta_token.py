"""Test de resiliencia de la ingesta ante token expirado/revocado (CA7).

Si el refresh del token de Gmail falla, la integración debe pasar a
`estado='reconectar'` y el servicio NO debe lanzar excepción (para que el poller
siga con las demás empresas). Tampoco debe crear solicitudes ni avanzar el cursor.
"""
from uuid import uuid4

from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.repositorios.solicitudes import RepositorioSolicitudesEnMemoria
from app.servicios.ingesta_correo import ingerir_correos_nuevos
from tests.dobles import ClienteGmailQueFallaAuth

EMPRESA = uuid4()


def _integracion(cursor: str | None = None) -> Integracion:
    return Integracion(
        id=uuid4(),
        empresa_id=EMPRESA,
        token_ref="secreto://capsulab",
        casilla="javier@capsulab.cl",
        cursor=cursor,
        estado="conectado",
    )


async def test_token_expirado_marca_reconectar_y_no_lanza():
    # CA7
    integ = _integracion(cursor="h1")
    repo_sol = RepositorioSolicitudesEnMemoria()
    repo_int = RepositorioIntegracionesEnMemoria([integ])
    gmail = ClienteGmailQueFallaAuth()

    # No debe lanzar excepción aunque el token esté revocado.
    resultado = await ingerir_correos_nuevos(integ, gmail, repo_sol, repo_int)

    assert resultado.estado == "reconectar"
    assert resultado.creadas == 0
    assert len(repo_sol._por_id) == 0  # no creó solicitudes
    actualizada = await repo_int.obtener_por_empresa(EMPRESA)
    assert actualizada.estado == "reconectar"
    assert actualizada.cursor == "h1"  # no avanzó el cursor
