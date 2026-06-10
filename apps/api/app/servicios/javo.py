"""Servicio de conversación con Javo: AGENTE con herramientas (003 + 005).

Javo (Claude **Sonnet**, SOLO desde el backend — regla #3) conversa y, cuando hace
falta, usa herramientas que ejecuta el BACKEND en un loop de tool-use manual:

  - `buscar_en_drive`: consulta el catálogo del Drive de la empresa (precios reales /
    casos anteriores). Javo NO inventa precios.
  - `buscar_en_internet`: referencias/ideas (Tipo 2), SOLO si el usuario lo pide.
  - `proponer_componentes`: registra los componentes propuestos (no los persiste; el
    GP confirma y la propuesta la toma la spec 004).

El cliente Anthropic se INYECTA (cero red, cero tokens en tests). El loop está ACOTADO
(tope de iteraciones y de búsquedas en internet) para controlar el costo. El system
prompt se cachea (regla #4) y las herramientas van en orden fijo (estable para la caché).
"""
import re

from app.esquemas import (
    ComponentePropuesto,
    Fuente,
    MensajeConversacion,
    RespuestaConversacion,
)

# Id del modelo Sonnet (chat). Enrutar por costo (regla #4): el chat usa Sonnet.
MODELO_CONVERSACION = "claude-sonnet-4-6"

_MAX_TOKENS = 1024

# Topes del loop de tool-use (robustez + costo): nunca más de N vueltas, ni más de M
# búsquedas en internet por conversación (CA11).
MAX_ITERACIONES = 6
TOPE_INTERNET = 5

# Persona base de Javo, común a ambos tipos. Se cachea (estable entre turnos).
_PERSONA = (
    "Eres Javo, el asistente comercial de una agencia de marketing/BTL (cliente "
    "piloto: Capsulab). Hablas en español de Chile, cercano y profesional. Tu meta "
    "es dejar la solicitud RESUELTA conversando con el gestor."
)

# Guía del Tipo 1 (cotización concreta).
_GUIA_T1 = (
    "Esta es una COTIZACIÓN CONCRETA (Tipo 1): ya se sabe qué hacer. Tu trabajo es "
    "aterrizar los componentes (catering, promotores, producto, uniforme, horas, "
    "valores) y armar una cotización clara. Usa la herramienta `buscar_en_drive` para "
    "obtener los valores REALES del catálogo de la empresa ANTES de dar un precio: NO "
    "inventes valores (si no está en el catálogo, pídelo o márcalo como estimación). "
    "Cuando tengas los componentes con su valor, regístralos con `proponer_componentes` "
    "(incluye el origen del Drive) para que el gestor los confirme."
)

# Guía del Tipo 2 (ideas / propuesta creativa).
_GUIA_T2 = (
    "Esto es un pedido de IDEAS / PROPUESTA CREATIVA (Tipo 2): no hay brief cerrado. "
    "Propón conceptos creativos y co-crea con el gestor. Puedes inspirarte en casos "
    "anteriores del Drive con `buscar_en_drive` (tipo 'caso'). Ofrece buscar en internet "
    "con `buscar_en_internet` SOLO si el usuario lo pide explícitamente; cuando uses "
    "internet, cita las fuentes. Itera sobre la idea ganadora hasta aterrizarla."
)

_GUIA_POR_TIPO = {"t1": _GUIA_T1, "t2": _GUIA_T2}

# Mapeo de roles del front al formato de Anthropic. `sistema` no se envía como turno.
_ROL_ANTHROPIC = {"usuario": "user", "javo": "assistant"}

# El usuario pidió buscar en internet (gating de Tipo 2).
_PATRON_INTERNET = re.compile(r"internet|busca|referencia|opcion|inspiraci", re.IGNORECASE)


def _system_para(tipo: str) -> str:
    """Arma el system prompt (persona + guía del tipo)."""
    guia = _GUIA_POR_TIPO.get(tipo, _GUIA_T1)
    return f"{_PERSONA}\n\n{guia}"


def _normalizar(mensajes: list[MensajeConversacion]) -> list[dict]:
    """Convierte el historial del front al formato `messages` de Anthropic.

    Anthropic exige solo roles `user`/`assistant`, empezar en `user` y alternar. El
    historial parte con el intro de Javo (`assistant`), así que descartamos `sistema`,
    mapeamos roles, fusionamos consecutivos del mismo rol y, si el primero no es `user`,
    anteponemos uno mínimo.
    """
    crudos: list[dict] = []
    for m in mensajes:
        rol = _ROL_ANTHROPIC.get(m.rol)
        if rol is None:  # 'sistema' u otros: no son turnos de la conversación
            continue
        crudos.append({"role": rol, "content": m.contenido})

    fusionados: list[dict] = []
    for turno in crudos:
        if fusionados and fusionados[-1]["role"] == turno["role"]:
            fusionados[-1]["content"] += "\n\n" + turno["content"]
        else:
            fusionados.append(dict(turno))

    if not fusionados or fusionados[0]["role"] != "user":
        fusionados.insert(0, {"role": "user", "content": "(inicio de la conversación)"})
    return fusionados


# ── Definición de herramientas (orden fijo: estable para la caché) ───────────
def _tool_buscar_en_drive() -> dict:
    return {
        "name": "buscar_en_drive",
        "description": (
            "Busca en el catálogo del Drive de la empresa: componentes con su valor "
            "real (para cotizar) o casos anteriores (para inspirar ideas). Úsala SIEMPRE "
            "antes de dar un precio; no inventes valores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {
                    "type": "string",
                    "description": "Qué buscar (ej. 'promotoras', 'pantalla led').",
                },
                "tipo": {
                    "type": "string",
                    "enum": ["componente", "caso"],
                    "description": "Opcional: filtra por tipo de recurso.",
                },
            },
            "required": ["consulta"],
        },
    }


def _tool_buscar_en_internet() -> dict:
    return {
        "name": "buscar_en_internet",
        "description": (
            "Busca referencias/ideas en internet. Úsala SOLO si el usuario lo pidió "
            "explícitamente. Devuelve resultados con sus fuentes para citar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"consulta": {"type": "string"}},
            "required": ["consulta"],
        },
    }


def _tool_proponer_componentes() -> dict:
    return {
        "name": "proponer_componentes",
        "description": (
            "Registra los componentes propuestos para la cotización (no los guarda; el "
            "gestor los confirma). Inclúyelos con su valor del catálogo y su origen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "componentes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "nombre": {"type": "string"},
                            "detalle": {"type": "string"},
                            "cantidad": {"type": "integer"},
                            "valor_unitario": {"type": "number"},
                            "origen": {"type": "string"},
                        },
                        "required": ["nombre"],
                    },
                }
            },
            "required": ["componentes"],
        },
    }


def _herramientas(permitir_internet: bool) -> list[dict]:
    tools = [_tool_buscar_en_drive()]
    if permitir_internet:
        tools.append(_tool_buscar_en_internet())
    tools.append(_tool_proponer_componentes())
    return tools


def _quiere_internet(tipo: str, mensajes: list[MensajeConversacion]) -> bool:
    """En Tipo 2, ¿el último turno del usuario pidió buscar en internet? (gating CA3)."""
    if tipo != "t2":
        return False
    for m in reversed(mensajes):
        if m.rol == "usuario":
            return bool(_PATRON_INTERNET.search(m.contenido or ""))
    return False


def _texto_seguro(respuesta) -> str:
    """Concatena los bloques de texto de la respuesta (vacío si no hay)."""
    return "".join(
        b.text for b in respuesta.content if getattr(b, "type", None) == "text"
    )


def _contenido_assistant(respuesta) -> list[dict]:
    """Reconstruye el turno `assistant` (texto + tool_use) para reanexarlo a la API."""
    bloques: list[dict] = []
    for b in respuesta.content:
        tipo = getattr(b, "type", None)
        if tipo == "text":
            bloques.append({"type": "text", "text": b.text})
        elif tipo == "tool_use":
            bloques.append(
                {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
            )
    return bloques


async def _ejecutar_herramienta(
    bloque,
    repo_catalogo,
    proveedor_busqueda,
    empresa_id,
    componentes: list[ComponentePropuesto],
    fuentes: list[Fuente],
    usos_internet: int,
) -> tuple[str, int]:
    """Ejecuta UNA herramienta (la corre el backend, no el LLM) y devuelve el texto del
    `tool_result` + el contador de búsquedas en internet actualizado. Acumula los
    componentes propuestos y las fuentes citadas."""
    nombre = getattr(bloque, "name", "")
    entrada = getattr(bloque, "input", None) or {}

    if nombre == "buscar_en_drive":
        items = await repo_catalogo.buscar(
            entrada.get("consulta", ""), empresa_id, tipo=entrada.get("tipo")
        )
        if not items:
            return (
                f"Sin resultados en el catálogo para «{entrada.get('consulta', '')}». "
                "No inventes un precio: pide el dato o márcalo como estimación.",
                usos_internet,
            )
        lineas = []
        for it in items:
            fuentes.append(
                Fuente(
                    titulo=it.nombre,
                    referencia=f"Drive: {it.origen}" if it.origen else "Drive (catálogo)",
                )
            )
            lineas.append(
                f"- {it.nombre} | detalle={it.detalle or ''} | "
                f"valor_unitario={it.valor_unitario} | unidad={it.unidad or ''} | "
                f"proveedor={it.proveedor or ''} | origen={it.origen or ''}"
            )
        return ("Catálogo (usa estos valores, no inventes):\n" + "\n".join(lineas), usos_internet)

    if nombre == "buscar_en_internet":
        if proveedor_busqueda is None or usos_internet >= TOPE_INTERNET:
            return ("Límite de búsquedas en internet alcanzado en esta conversación.", usos_internet)
        resultados = await proveedor_busqueda.buscar(entrada.get("consulta", ""))
        for r in resultados:
            fuentes.append(Fuente(titulo=r.titulo, referencia=r.referencia))
        lineas = [f"- {r.titulo}: {r.referencia}" for r in resultados]
        return ("Resultados de internet (cita las fuentes):\n" + "\n".join(lineas), usos_internet + 1)

    if nombre == "proponer_componentes":
        nuevos = entrada.get("componentes", []) or []
        for c in nuevos:
            componentes.append(
                ComponentePropuesto(
                    nombre=c.get("nombre", ""),
                    detalle=c.get("detalle"),
                    cantidad=int(c.get("cantidad", 1) or 1),
                    valor_unitario=c.get("valor_unitario"),
                    origen=c.get("origen"),
                )
            )
        return (f"Componentes registrados: {len(nuevos)}. (El gestor los confirmará.)", usos_internet)

    return (f"Herramienta desconocida: {nombre}.", usos_internet)


async def responder_javo(
    tipo: str,
    mensajes: list[MensajeConversacion],
    cliente,
    *,
    repo_catalogo=None,
    proveedor_busqueda=None,
    empresa_id=None,
) -> RespuestaConversacion:
    """Genera la respuesta de Javo para el historial dado, usando Sonnet con tool-use.

    Si `repo_catalogo` y `empresa_id` están presentes, Javo es agente (puede consultar
    el Drive, internet y proponer componentes). Sin ellos, responde en modo simple (una
    sola llamada). El cliente puede lanzar (LLM caído) → se propaga (el endpoint lo
    convierte en 502).
    """
    permitir_internet = _quiere_internet(tipo, mensajes)
    tiene_tools = repo_catalogo is not None and empresa_id is not None
    tools = _herramientas(permitir_internet) if tiene_tools else None

    conversacion = _normalizar(mensajes)
    componentes: list[ComponentePropuesto] = []
    fuentes: list[Fuente] = []
    usos_internet = 0
    ultimo_texto = ""

    for _ in range(MAX_ITERACIONES):
        kwargs = {
            "model": MODELO_CONVERSACION,
            "max_tokens": _MAX_TOKENS,
            "system": [
                {
                    "type": "text",
                    "text": _system_para(tipo),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": conversacion,
        }
        if tools:
            kwargs["tools"] = tools

        respuesta = await cliente.messages.create(**kwargs)

        texto = _texto_seguro(respuesta)
        if texto:
            ultimo_texto = texto

        if getattr(respuesta, "stop_reason", None) != "tool_use":
            return RespuestaConversacion(
                texto=ultimo_texto, componentes=componentes, fuentes=fuentes
            )

        # Hay tool_use: ejecutar las herramientas y reanexar el resultado.
        conversacion.append({"role": "assistant", "content": _contenido_assistant(respuesta)})
        resultados: list[dict] = []
        for bloque in respuesta.content:
            if getattr(bloque, "type", None) != "tool_use":
                continue
            salida, usos_internet = await _ejecutar_herramienta(
                bloque,
                repo_catalogo,
                proveedor_busqueda,
                empresa_id,
                componentes,
                fuentes,
                usos_internet,
            )
            resultados.append(
                {"type": "tool_result", "tool_use_id": bloque.id, "content": salida}
            )
        conversacion.append({"role": "user", "content": resultados})

    # Loop acotado: devolvemos lo último que dijo Javo (no nos colgamos).
    return RespuestaConversacion(
        texto=ultimo_texto or "Estoy afinando la propuesta, dame un momento.",
        componentes=componentes,
        fuentes=fuentes,
    )
