"""Servicio de conversación con Javo usando Claude Sonnet (chat).

El cliente de Anthropic se **inyecta** para mockearlo en los tests (regla #3: el LLM
solo se llama desde el backend; aquí, además, lo desacoplamos para no gastar tokens
ni tocar la red). Se enruta a **Sonnet** (chat) con el *system prompt* cacheado
(regla #4) y guía/persona según el tipo de solicitud.
"""
from app.esquemas import MensajeConversacion

# Id del modelo Sonnet (chat). Ajustable según el plan de la cuenta (spec 003 · §6).
MODELO_CONVERSACION = "claude-sonnet-4-5"

_MAX_TOKENS = 1024

# Persona base de Javo, común a ambos tipos. Se cachea (prompt caching) porque es
# estable entre turnos y entre conversaciones.
_PERSONA = (
    "Eres Javo, el asistente comercial de una agencia de marketing/BTL (cliente "
    "piloto: Capsulab). Hablas en español de Chile, cercano y profesional. Tu meta "
    "es dejar la solicitud RESUELTA conversando con el gestor."
)

# Guía específica del Tipo 1 (cotización concreta).
_GUIA_T1 = (
    "Esta es una COTIZACIÓN CONCRETA (Tipo 1): ya se sabe qué hacer. Tu trabajo es "
    "aterrizar los componentes (catering, promotores, producto, uniforme, horas, "
    "valores) y armar una cotización clara. Haz preguntas puntuales solo si falta un "
    "dato clave; no inventes precios, propón rangos o pide confirmarlos. Sé concreto "
    "y accionable."
)

# Guía específica del Tipo 2 (ideas / propuesta creativa).
_GUIA_T2 = (
    "Esto es un pedido de IDEAS / PROPUESTA CREATIVA (Tipo 2): no hay brief cerrado. "
    "Propón conceptos creativos y haz preguntas para co-crear con el gestor. Ofrece "
    "buscar referencias en internet SOLO si el usuario lo pide explícitamente; no "
    "asumas que ya buscaste. Itera sobre la idea ganadora hasta aterrizarla."
)

_GUIA_POR_TIPO = {"t1": _GUIA_T1, "t2": _GUIA_T2}

# Mapeo de roles del front al formato de Anthropic. `sistema` no se envía como turno
# (Anthropic solo acepta user/assistant en `messages`); el rol de sistema va aparte.
_ROL_ANTHROPIC = {"usuario": "user", "javo": "assistant"}


def _system_para(tipo: str) -> str:
    """Arma el system prompt (persona + guía del tipo)."""
    guia = _GUIA_POR_TIPO.get(tipo, _GUIA_T1)
    return f"{_PERSONA}\n\n{guia}"


def _normalizar(mensajes: list[MensajeConversacion]) -> list[dict]:
    """Convierte el historial del front al formato `messages` de Anthropic.

    Anthropic exige: solo roles `user`/`assistant`, **empezar en `user`** y alternar
    (sin dos turnos seguidos del mismo rol). El historial real parte con el intro de
    Javo (`assistant`), así que:
    - descartamos los turnos `sistema`,
    - mapeamos `usuario`→user, `javo`→assistant,
    - fusionamos turnos consecutivos del mismo rol (uniéndolos con saltos de línea),
    - si el primer turno no es `user`, anteponemos un `user` mínimo para no romper la API.
    """
    crudos: list[dict] = []
    for m in mensajes:
        rol = _ROL_ANTHROPIC.get(m.rol)
        if rol is None:  # 'sistema' u otros: no son turnos de la conversación
            continue
        crudos.append({"role": rol, "content": m.contenido})

    # Fusiona consecutivos del mismo rol para garantizar alternancia.
    fusionados: list[dict] = []
    for turno in crudos:
        if fusionados and fusionados[-1]["role"] == turno["role"]:
            fusionados[-1]["content"] += "\n\n" + turno["content"]
        else:
            fusionados.append(dict(turno))

    # Anthropic exige empezar en `user`.
    if not fusionados or fusionados[0]["role"] != "user":
        fusionados.insert(0, {"role": "user", "content": "(inicio de la conversación)"})
    return fusionados


async def responder_javo(
    tipo: str, mensajes: list[MensajeConversacion], cliente
) -> str:
    """Genera la respuesta de Javo para el historial dado usando Sonnet.

    `cliente` es un `AsyncAnthropic` (o un doble de prueba con la misma interfaz).
    Devuelve el texto del bloque de respuesta. Si el cliente lanza, se propaga (el
    endpoint lo convierte en 502).
    """
    respuesta = await cliente.messages.create(
        model=MODELO_CONVERSACION,
        max_tokens=_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": _system_para(tipo),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=_normalizar(mensajes),
    )
    return _extraer_texto(respuesta)


def _extraer_texto(respuesta) -> str:
    """Concatena el texto de los bloques `text` de la respuesta de Anthropic."""
    partes = [
        bloque.text
        for bloque in respuesta.content
        if getattr(bloque, "type", None) == "text"
    ]
    if not partes:
        raise ValueError("La respuesta del modelo no contiene un bloque de texto.")
    return "".join(partes)
