"""Servicio de clasificación y resumen de solicitudes con Claude Haiku 4.5.

El cliente de Anthropic se **inyecta** para poder mockearlo en los tests: no se
hacen llamadas reales ni se gastan tokens (Regla #3: el LLM se llama solo desde el
backend; aquí, además, desacoplamos el cliente para testear).
"""
from app.esquemas import ResultadoClasificacion

MODELO_CLASIFICADOR = "claude-haiku-4-5"

_NOMBRE_HERRAMIENTA = "registrar_clasificacion"

SYSTEM_PROMPT = (
    "Eres Javo, asistente comercial de una agencia de marketing/BTL. Lees el correo "
    "de una solicitud y devuelves un resumen breve (4-5 puntos clave) y el tipo de "
    "solicitud.\n"
    "- tipo_1 (cotización concreta): el cliente ya sabe qué quiere; hay que cotizar "
    "componentes (ej: sampling de sopaipillas afuera del Metro).\n"
    "- tipo_2 (ideas / propuesta creativa): el cliente pide conceptos sin brief "
    "cerrado (ej: ideas para una campaña de Fórmula 1).\n"
    "Responde SIEMPRE llamando a la herramienta registrar_clasificacion."
)

HERRAMIENTA_CLASIFICAR = {
    "name": _NOMBRE_HERRAMIENTA,
    "description": "Registra el resumen y el tipo sugerido de la solicitud.",
    "input_schema": {
        "type": "object",
        "properties": {
            "resumen": {
                "type": "string",
                "description": "Resumen breve del correo (4-5 puntos clave).",
            },
            "tipo": {
                "type": "string",
                "enum": ["tipo_1", "tipo_2"],
                "description": "tipo_1 = cotización concreta; tipo_2 = ideas.",
            },
        },
        "required": ["resumen", "tipo"],
    },
}


async def clasificar_solicitud(cuerpo: str, cliente) -> ResultadoClasificacion:
    """Clasifica y resume el cuerpo de un correo usando Haiku 4.5.

    `cliente` es un `AsyncAnthropic` (o un doble de prueba con la misma interfaz).
    """
    if not (cuerpo or "").strip():
        # Sin contenido que clasificar (p. ej. correo sin cuerpo): no gastamos una
        # llamada y evitamos el 400 de la API por mensaje vacío. La ingesta captura
        # esto y deja el correo 'sin_clasificar' sin caerse.
        raise ValueError("cuerpo vacío: nada que clasificar")
    respuesta = await cliente.messages.create(
        model=MODELO_CLASIFICADOR,
        max_tokens=512,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[HERRAMIENTA_CLASIFICAR],
        tool_choice={"type": "tool", "name": _NOMBRE_HERRAMIENTA},
        messages=[{"role": "user", "content": cuerpo}],
    )
    return ResultadoClasificacion(**_extraer_clasificacion(respuesta))


def _extraer_clasificacion(respuesta) -> dict:
    """Devuelve el `input` del bloque tool_use de la respuesta de Anthropic."""
    for bloque in respuesta.content:
        if getattr(bloque, "type", None) == "tool_use":
            return bloque.input
    raise ValueError("La respuesta del modelo no contiene un bloque tool_use.")
