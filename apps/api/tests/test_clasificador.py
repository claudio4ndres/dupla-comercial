"""Tests del servicio de clasificación (Haiku 4.5 mockeado).

Cubre CA2 (sopaipillas -> tipo_1), CA3 (F1 -> tipo_2) y CA5 (sin llamadas reales:
el SDK de Anthropic se reemplaza por un doble de prueba que nunca toca la red).
"""
from app.esquemas import ResultadoClasificacion
from app.servicios.clasificador import MODELO_CLASIFICADOR, clasificar_solicitud
from tests.dobles import ClienteAnthropicFake

CUERPO_SOPAIPILLAS = (
    "Hola Javo, queremos cotizar regalar sopaipillas afuera del Metro. "
    "Activación de 5 horas diarias. Necesitamos catering, promotores, "
    "producto y uniformes. ¿Nos pasas valores?"
)
CUERPO_F1 = (
    "Hola Javo, estamos viendo la campaña de la Fórmula 1 y necesitamos "
    "ideas de alto impacto para ver el proyecto."
)


async def test_clasifica_cotizacion_concreta_como_tipo_1():
    # CA2
    cliente = ClienteAnthropicFake(
        {"resumen": "Sampling de sopaipillas afuera del Metro.", "tipo": "tipo_1"}
    )
    resultado = await clasificar_solicitud(CUERPO_SOPAIPILLAS, cliente)
    assert isinstance(resultado, ResultadoClasificacion)
    assert resultado.tipo == "tipo_1"
    assert resultado.resumen.strip() != ""


async def test_clasifica_pedido_de_ideas_como_tipo_2():
    # CA3
    cliente = ClienteAnthropicFake(
        {"resumen": "Pedido de ideas para campaña de Fórmula 1.", "tipo": "tipo_2"}
    )
    resultado = await clasificar_solicitud(CUERPO_F1, cliente)
    assert resultado.tipo == "tipo_2"


async def test_usa_el_cliente_inyectado_y_modelo_haiku_sin_red():
    # CA5: con el SDK mockeado, se usa el cliente inyectado (una sola llamada)
    # con el modelo Haiku. No hay tráfico de red ni gasto de tokens.
    cliente = ClienteAnthropicFake({"resumen": "x", "tipo": "tipo_1"})
    await clasificar_solicitud(CUERPO_SOPAIPILLAS, cliente)
    assert len(cliente.llamadas) == 1
    assert cliente.llamadas[0]["model"] == MODELO_CLASIFICADOR
