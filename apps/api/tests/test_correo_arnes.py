"""T3 (Spec 002) · Arnés de la capa de correo: interfaces + dobles.

Verifica que las piezas base existen y cumplen su contrato, todo mockeado
(CA6, cero llamadas reales a Gmail):
- el doble `ClienteGmailFake` devuelve los mensajes fijados, un cursor nuevo y
  registra con qué cursor se le llamó (para verificar el avance en T4),
- el repositorio en memoria de integraciones guarda/lee por empresa,
- `crear_desde_correo` es idempotente por (empresa_id, gmail_msg_id) (CA4).
"""
from uuid import uuid4

from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.repositorios.solicitudes import RepositorioSolicitudesEnMemoria
from app.servicios.gmail import MensajeCorreo
from tests.dobles import ClienteGmailFake

EMPRESA = uuid4()


def _mensaje(msg_id: str) -> MensajeCorreo:
    return MensajeCorreo(
        gmail_msg_id=msg_id,
        remitente="Zona Espiga",
        correo_origen="contacto@zonaespiga.cl",
        asunto="Cotización sopaipillas",
        cuerpo="Hola Javo, cotizar sopaipillas afuera del Metro.",
    )


async def test_doble_gmail_devuelve_mensajes_y_registra_llamadas():
    gmail = ClienteGmailFake([_mensaje("m1"), _mensaje("m2")], nuevo_cursor="h2")

    mensajes, cursor = await gmail.listar_nuevos(None)

    assert [m.gmail_msg_id for m in mensajes] == ["m1", "m2"]
    assert cursor == "h2"
    assert gmail.llamadas == [None]  # se pidió desde el cursor None (recién conectado)


async def test_repo_integraciones_guarda_y_obtiene_por_empresa():
    repo = RepositorioIntegracionesEnMemoria()
    integ = Integracion(
        id=uuid4(), empresa_id=EMPRESA, token_ref="secreto://x", casilla="a@a.cl"
    )

    await repo.guardar(integ)
    obtenida = await repo.obtener_por_empresa(EMPRESA)

    assert obtenida is not None
    assert obtenida.casilla == "a@a.cl"
    assert obtenida.estado == "conectado"  # arranca conectado por defecto


async def test_crear_desde_correo_es_idempotente():
    repo = RepositorioSolicitudesEnMemoria()
    m = _mensaje("m1")

    assert await repo.crear_desde_correo(EMPRESA, m) is True
    # mismo gmail_msg_id en la misma empresa: NO duplica (idempotencia).
    assert await repo.crear_desde_correo(EMPRESA, m) is False
