"""Tests del servicio `ingerir_correos_nuevos` (Gmail mockeado, CA6).

Cubre CA3 (un correo nuevo → una solicitud `sin_clasificar`/`nueva`, con el mapeo
From/subject/body y el avance del cursor) y CA4 (un correo ya ingerido no se
duplica). La resiliencia ante token expirado (CA7) se prueba en test_ingesta_token.
"""
from uuid import uuid4

from app.repositorios.integraciones import (
    Integracion,
    RepositorioIntegracionesEnMemoria,
)
from app.esquemas import ResultadoClasificacion
from app.repositorios.solicitudes import RepositorioSolicitudesEnMemoria, Solicitud
from app.servicios.gmail import MensajeCorreo
from app.servicios.ingesta_correo import ingerir_correos_nuevos
from tests.dobles import ClienteGmailFake

EMPRESA = uuid4()


def _integracion(cursor: str | None = None) -> Integracion:
    return Integracion(
        id=uuid4(),
        empresa_id=EMPRESA,
        token_ref="secreto://capsulab",
        casilla="javier@capsulab.cl",
        cursor=cursor,
    )


def _mensaje(msg_id: str, **kwargs) -> MensajeCorreo:
    base = dict(
        gmail_msg_id=msg_id,
        remitente="Zona Espiga",
        correo_origen="contacto@zonaespiga.cl",
        asunto="Cotización sopaipillas",
        cuerpo="Hola Javo, cotizar sopaipillas.",
    )
    base.update(kwargs)
    return MensajeCorreo(**base)


async def test_dos_correos_nuevos_crean_dos_solicitudes_y_avanzan_cursor():
    # CA3
    integ = _integracion(cursor="h1")
    repo_sol = RepositorioSolicitudesEnMemoria()
    repo_int = RepositorioIntegracionesEnMemoria([integ])
    gmail = ClienteGmailFake([_mensaje("m1"), _mensaje("m2")], nuevo_cursor="h2")

    resultado = await ingerir_correos_nuevos(integ, gmail, repo_sol, repo_int)

    assert resultado.creadas == 2
    assert resultado.estado == "conectado"
    creadas = list(repo_sol._por_id.values())
    assert len(creadas) == 2
    assert all(s.empresa_id == EMPRESA for s in creadas)
    assert all(s.tipo == "sin_clasificar" and s.estado == "nueva" for s in creadas)
    # Pidió desde el cursor de la integración y lo avanzó al nuevo.
    assert gmail.llamadas == ["h1"]
    actualizada = await repo_int.obtener_por_empresa(EMPRESA)
    assert actualizada.cursor == "h2"


async def test_mapea_los_campos_del_correo_a_la_solicitud():
    # CA3 (mapeo From → remitente/correo_origen, subject → asunto, body → cuerpo)
    integ = _integracion()
    repo_sol = RepositorioSolicitudesEnMemoria()
    repo_int = RepositorioIntegracionesEnMemoria([integ])
    gmail = ClienteGmailFake(
        [
            _mensaje(
                "m1",
                remitente="Fórmula 1 LATAM",
                correo_origen="marketing@f1latam.com",
                asunto="Necesitamos ideas",
                cuerpo="Hola Javo, ideas de alto impacto.",
            )
        ]
    )

    await ingerir_correos_nuevos(integ, gmail, repo_sol, repo_int)

    s = next(iter(repo_sol._por_id.values()))
    assert s.remitente == "Fórmula 1 LATAM"
    assert s.correo_origen == "marketing@f1latam.com"
    assert s.asunto == "Necesitamos ideas"
    assert s.cuerpo == "Hola Javo, ideas de alto impacto."
    assert s.gmail_msg_id == "m1"


async def test_no_duplica_un_correo_ya_ingerido():
    # CA4
    integ = _integracion()
    previa = Solicitud(
        id=uuid4(), empresa_id=EMPRESA, cuerpo="ingerida antes", gmail_msg_id="m1"
    )
    repo_sol = RepositorioSolicitudesEnMemoria([previa])
    repo_int = RepositorioIntegracionesEnMemoria([integ])
    gmail = ClienteGmailFake([_mensaje("m1"), _mensaje("m2")], nuevo_cursor="h9")

    resultado = await ingerir_correos_nuevos(integ, gmail, repo_sol, repo_int)

    assert resultado.creadas == 1  # solo m2 es nuevo; m1 ya estaba
    assert len(repo_sol._por_id) == 2  # la previa + la nueva (m2)


async def test_ingiere_clasificando_resumen_y_tipo():
    # El poller debe clasificar cada correo (Haiku) y guardar `resumen` + `tipo`,
    # para que el detalle muestre una descripción real (no quede vacío). Esta es la
    # brecha que dejaba los correos reales "sin descripción".
    integ = _integracion()
    repo_sol = RepositorioSolicitudesEnMemoria()
    repo_int = RepositorioIntegracionesEnMemoria([integ])
    gmail = ClienteGmailFake([_mensaje("m1")])

    async def clasificar_fake(cuerpo: str) -> ResultadoClasificacion:
        assert "sopaipillas" in cuerpo  # clasifica sobre el CUERPO del correo
        return ResultadoClasificacion(
            resumen="Sampling de sopaipillas afuera del Metro.", tipo="tipo_1"
        )

    await ingerir_correos_nuevos(
        integ, gmail, repo_sol, repo_int, clasificar=clasificar_fake
    )

    s = next(iter(repo_sol._por_id.values()))
    assert s.resumen == "Sampling de sopaipillas afuera del Metro."
    assert s.tipo == "tipo_1"


async def test_si_la_clasificacion_falla_igual_ingiere_sin_resumen():
    # Resiliencia: si el LLM se cae, el correo igual se ingiere ('sin_clasificar',
    # sin resumen) para no PERDER correos por una falla del clasificador.
    integ = _integracion()
    repo_sol = RepositorioSolicitudesEnMemoria()
    repo_int = RepositorioIntegracionesEnMemoria([integ])
    gmail = ClienteGmailFake([_mensaje("m1")])

    async def clasificar_explota(cuerpo: str) -> ResultadoClasificacion:
        raise RuntimeError("LLM caído")

    resultado = await ingerir_correos_nuevos(
        integ, gmail, repo_sol, repo_int, clasificar=clasificar_explota
    )

    assert resultado.creadas == 1
    s = next(iter(repo_sol._por_id.values()))
    assert s.tipo == "sin_clasificar"
    assert not s.resumen  # None o ""
