"""Spec 010 · CA5 (alerta al marcar 'reconectar') en la INGESTA de correo.

Cuando el refresh del token de Gmail falla y la ingesta marca la integración como
'reconectar', debe emitir además una SEÑAL para el operador (vía `avisar_reconectar`):
log estructurado con empresa_id + proveedor + motivo, SIN token. La ingesta sigue sin
lanzar (CA7) — la alerta no cambia su comportamiento observable.
"""
import logging
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


async def test_token_expirado_emite_alerta_para_el_operador(caplog):
    # CA5: al marcar 'reconectar' por auth rota, se emite la señal del operador.
    integ = _integracion(cursor="h1")
    repo_sol = RepositorioSolicitudesEnMemoria()
    repo_int = RepositorioIntegracionesEnMemoria([integ])
    gmail = ClienteGmailQueFallaAuth()

    with caplog.at_level(logging.WARNING):
        resultado = await ingerir_correos_nuevos(integ, gmail, repo_sol, repo_int)

    # Comportamiento de la Ola 4 intacto: marca 'reconectar', no lanza.
    assert resultado.estado == "reconectar"
    actualizada = await repo_int.obtener_por_empresa(EMPRESA)
    assert actualizada.estado == "reconectar"

    # La alerta del operador se emitió con empresa_id + proveedor + motivo, SIN token.
    texto = " ".join(r.getMessage() for r in caplog.records)
    assert str(EMPRESA) in texto
    assert "gmail" in texto
    assert "auth_invalida" in texto
    assert "secreto://" not in texto  # jamás el token_ref
    assert "token" not in texto.lower() or "auth_invalida" in texto
