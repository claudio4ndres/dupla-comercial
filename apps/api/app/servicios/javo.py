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
    TareaPropuesta,
)

# Id del modelo Sonnet (chat). Enrutar por costo (regla #4): el chat usa Sonnet.
MODELO_CONVERSACION = "claude-sonnet-4-6"

# Tope de tokens de la respuesta. 4096 (no 1024): una cotización completa (texto +
# varios componentes/tareas vía tool-use) no debe truncarse a mitad de la propuesta.
_MAX_TOKENS = 4096

# Topes del loop de tool-use (robustez + costo): nunca más de N vueltas, ni más de M
# búsquedas en internet por conversación (CA11).
MAX_ITERACIONES = 6
TOPE_INTERNET = 5

# Persona base de Javo, común a ambos tipos. Se cachea (estable entre turnos).
# Javo NO es un asistente pasivo: es una dupla comercial SENIOR que piensa, propone
# y decide con criterio de experto BTL.
_PERSONA = (
    "Eres Javo, una DUPLA COMERCIAL SENIOR de una agencia de marketing/BTL (cliente "
    "piloto: Capsulab): un ejecutivo con años de experiencia armando activaciones, "
    "samplings, lanzamientos y campañas en terreno. Hablas en español de Chile, directo "
    "y con criterio. NO eres un asistente pasivo: piensas y decides como un comercial "
    "experimentado. Tomas la iniciativa — propones ideas, RECOMIENDAS el mejor camino "
    "(no das menús de opciones sin opinión), anticipas lo que la activación va a "
    "necesitar y lo dejas armado. Tu meta: convertir la solicitud en una PROPUESTA "
    "RESUELTA Y EJECUTABLE: componentes valorizados (con valores REALES del Drive, "
    "nunca inventados) y las TAREAS que el equipo necesita para ejecutarla. "
    "Para los valores: BUSCA en el Drive del usuario el tarifario/documento que "
    "necesites con `buscar_en_drive`, ÁBRELO con `leer_documento_drive`, usa el número "
    "REAL que dice el documento y CÍTALO como Fuente (el nombre del archivo). Si no lo "
    "encuentras en el Drive, pide el dato — NUNCA inventes un precio."
)

# Guía del Tipo 1 (cotización concreta).
_GUIA_T1 = (
    "Esta es una COTIZACIÓN CONCRETA (Tipo 1): ya se sabe qué hacer. Como dupla "
    "comercial senior, ATERRIZA tú la cotización con criterio profesional: define los "
    "componentes que la activación realmente necesita (catering, promotores, producto, "
    "uniforme, horas, días, valores) sin esperar a que el gestor te dicte cada cosa. "
    "Para cada valor: BUSCA en el Drive del usuario el tarifario/doc con `buscar_en_drive` "
    "(busca en TODO el Drive por nombre y contenido), ÁBRELO con `leer_documento_drive`, "
    "usa el número REAL del documento y CÍTALO como Fuente. NO inventes: si no está en el "
    "Drive, pídelo o márcalo como estimación. Registra los componentes "
    "con `proponer_componentes` (incluye proveedor, días y origen del Drive). Luego "
    "propón las TAREAS de ejecución con `proponer_tareas`: piensa como quien va a "
    "EJECUTAR (reclutar promotores, comprar insumos, producir material, "
    "permisos/logística, coordinación), cada una con su área y un plazo realista. "
    "Recomienda con seguridad; el gestor confirma."
)

# Guía del Tipo 2 (ideas / propuesta creativa).
_GUIA_T2 = (
    "Esto es un pedido de IDEAS / PROPUESTA CREATIVA (Tipo 2): no hay brief cerrado. "
    "Como comercial senior, LIDERA la co-creación: propón 2-3 conceptos potentes y di "
    "CLARO cuál recomiendas y por qué, en vez de listar opciones neutras. Inspírate en "
    "casos del Drive con `buscar_en_drive` (tipo 'caso'). Ofrece `buscar_en_internet` "
    "SOLO si el usuario lo pide; cita las fuentes. Cuando la idea ganadora se aterrice, "
    "bájala a componentes (`proponer_componentes`, con proveedor/días) y a tareas de "
    "ejecución (`proponer_tareas`)."
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
            "Busca EN VIVO en TODO el Drive del usuario (todas las carpetas), por nombre "
            "Y por contenido: tarifarios, modelos de cotización, casos anteriores. "
            "Devuelve los documentos encontrados (nombre, id y tipo). Úsala SIEMPRE antes "
            "de dar un precio para encontrar el tarifario/doc; luego ÁBRELO con "
            "`leer_documento_drive` para leer el valor real. No inventes valores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {
                    "type": "string",
                    "description": "Qué buscar (ej. 'tarifario promotoras', 'pantalla led').",
                },
                "tipo": {
                    "type": "string",
                    "enum": ["componente", "caso"],
                    "description": "Opcional: filtra por tipo de recurso (sólo aplica al catálogo de respaldo).",
                },
            },
            "required": ["consulta"],
        },
    }


def _tool_leer_documento_drive() -> dict:
    return {
        "name": "leer_documento_drive",
        "description": (
            "Abre un documento del Drive (uno que devolvió `buscar_en_drive`) y devuelve "
            "su CONTENIDO como texto, para que leas el valor REAL y lo cites. Pásale el "
            "`file_id` y el `tipo_mime` del documento."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "El id del documento (tal como lo devolvió buscar_en_drive).",
                },
                "tipo_mime": {
                    "type": "string",
                    "description": "El tipo MIME del documento (tal como lo devolvió buscar_en_drive).",
                },
            },
            "required": ["file_id", "tipo_mime"],
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
                            "dias": {
                                "type": "integer",
                                "description": "Días de la activación (la tarifa es por día). Si no aplica, 1.",
                            },
                            "valor_unitario": {"type": "number"},
                            "proveedor": {
                                "type": "string",
                                "description": "Proveedor del catálogo del Drive (si lo hay).",
                            },
                            "origen": {"type": "string"},
                        },
                        "required": ["nombre"],
                    },
                }
            },
            "required": ["componentes"],
        },
    }


def _tool_proponer_tareas() -> dict:
    return {
        "name": "proponer_tareas",
        "description": (
            "Registra las TAREAS que el equipo necesita para EJECUTAR la activación. "
            "Propónlas con criterio de comercial senior: qué hay que hacer concretamente "
            "para que la propuesta se ejecute (reclutar promotores, comprar insumos, "
            "producir material, permisos/logística, coordinación). Cada tarea con su "
            "área responsable y un plazo realista. No las guarda; el gestor confirma."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tareas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "nombre": {"type": "string"},
                            "area": {
                                "type": "string",
                                "description": "Área responsable (RRHH, Producción, Compras, Diseño, Logística, Comercial, Coordinación).",
                            },
                            "plazo": {
                                "type": "string",
                                "description": "Plazo realista (ej. '3 días', '1 semana').",
                            },
                        },
                        "required": ["nombre", "area"],
                    },
                }
            },
            "required": ["tareas"],
        },
    }


def _herramientas(permitir_internet: bool) -> list[dict]:
    tools = [_tool_buscar_en_drive(), _tool_leer_documento_drive()]
    if permitir_internet:
        tools.append(_tool_buscar_en_internet())
    tools.append(_tool_proponer_componentes())
    tools.append(_tool_proponer_tareas())
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


async def _buscar_en_drive_real(consulta: str, cliente_drive, fuentes: list[Fuente]) -> str:
    """Busca EN VIVO en TODO el Drive del usuario (vía `ClienteDriveReal`) y arma el
    `tool_result`: los documentos encontrados (nombre + id + tipo MIME) para que Javo
    elija cuál abrir con `leer_documento_drive`. Cada doc encontrado queda como Fuente
    citable. Si el Drive falla (token revocado, red), degrada sin romper el loop."""
    try:
        archivos = await cliente_drive.buscar_archivos(consulta)
    except Exception:
        return (
            f"No pude buscar en el Drive ahora mismo («{consulta}»). "
            "No inventes un precio: pide el dato o márcalo como estimación."
        )
    if not archivos:
        return (
            f"Sin resultados en el Drive para «{consulta}». "
            "No inventes un precio: pide el dato o márcalo como estimación."
        )
    lineas = []
    for a in archivos:
        fuentes.append(Fuente(titulo=a.nombre, referencia=f"Drive: {a.nombre}"))
        lineas.append(f"- nombre={a.nombre} | file_id={a.id} | tipo_mime={a.tipo_mime}")
    return (
        "Documentos del Drive (ábrelos con leer_documento_drive para ver el valor "
        "real y cítalos):\n" + "\n".join(lineas)
    )


async def _buscar_en_catalogo(
    entrada: dict, repo_catalogo, empresa_id, fuentes: list[Fuente]
) -> str:
    """Respaldo: si no hay Drive real cableado, busca en la tabla `catalogo` (RLS)."""
    if repo_catalogo is None or empresa_id is None:
        return (
            "Sin acceso a Drive configurado para esta empresa. "
            "No inventes un precio: pide el dato o márcalo como estimación."
        )
    items = await repo_catalogo.buscar(
        entrada.get("consulta", ""), empresa_id, tipo=entrada.get("tipo")
    )
    if not items:
        return (
            f"Sin resultados en el catálogo para «{entrada.get('consulta', '')}». "
            "No inventes un precio: pide el dato o márcalo como estimación."
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
    return "Catálogo (usa estos valores, no inventes):\n" + "\n".join(lineas)


async def _ejecutar_herramienta(
    bloque,
    repo_catalogo,
    proveedor_busqueda,
    empresa_id,
    componentes: list[ComponentePropuesto],
    tareas: list[TareaPropuesta],
    fuentes: list[Fuente],
    usos_internet: int,
    cliente_drive=None,
) -> tuple[str, int]:
    """Ejecuta UNA herramienta (la corre el backend, no el LLM) y devuelve el texto del
    `tool_result` + el contador de búsquedas en internet actualizado. Acumula los
    componentes propuestos, las tareas propuestas y las fuentes citadas."""
    nombre = getattr(bloque, "name", "")
    entrada = getattr(bloque, "input", None) or {}

    if nombre == "buscar_en_drive":
        # Prioriza el DRIVE REAL en vivo (todas las carpetas). Si no hay Drive cableado,
        # cae al catálogo de respaldo (tabla `catalogo`).
        if cliente_drive is not None:
            return (
                await _buscar_en_drive_real(
                    entrada.get("consulta", ""), cliente_drive, fuentes
                ),
                usos_internet,
            )
        return (
            await _buscar_en_catalogo(entrada, repo_catalogo, empresa_id, fuentes),
            usos_internet,
        )

    if nombre == "leer_documento_drive":
        if cliente_drive is None:
            return (
                "Sin acceso a Drive configurado: no puedo abrir el documento. "
                "Pide el dato o márcalo como estimación; no inventes.",
                usos_internet,
            )
        try:
            contenido = await cliente_drive.leer_documento(
                entrada.get("file_id", ""), entrada.get("tipo_mime", "")
            )
        except Exception:
            return (
                "No pude abrir ese documento del Drive ahora mismo. "
                "Pide el dato o márcalo como estimación; no inventes.",
                usos_internet,
            )
        if not contenido:
            return ("El documento vino vacío o no se pudo leer su texto.", usos_internet)
        return ("Contenido del documento (usa el valor real y cítalo):\n" + contenido, usos_internet)

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
                    dias=c.get("dias"),
                    valor_unitario=c.get("valor_unitario"),
                    proveedor=c.get("proveedor"),
                    origen=c.get("origen"),
                )
            )
        return (f"Componentes registrados: {len(nuevos)}. (El gestor los confirmará.)", usos_internet)

    if nombre == "proponer_tareas":
        nuevas = entrada.get("tareas", []) or []
        for t in nuevas:
            tareas.append(
                TareaPropuesta(
                    nombre=t.get("nombre", ""),
                    area=t.get("area", ""),
                    plazo=t.get("plazo"),
                    responsable=t.get("responsable"),
                )
            )
        return (f"Tareas registradas: {len(nuevas)}. (El gestor las confirmará.)", usos_internet)

    return (f"Herramienta desconocida: {nombre}.", usos_internet)


async def responder_javo(
    tipo: str,
    mensajes: list[MensajeConversacion],
    cliente,
    *,
    repo_catalogo=None,
    proveedor_busqueda=None,
    empresa_id=None,
    cliente_drive=None,
) -> RespuestaConversacion:
    """Genera la respuesta de Javo para el historial dado, usando Sonnet con tool-use.

    Si hay `cliente_drive` (Drive real de la empresa) o `repo_catalogo`+`empresa_id`,
    Javo es agente: busca EN VIVO en TODO el Drive del usuario (todas las carpetas) con
    `buscar_en_drive`, abre los documentos con `leer_documento_drive` y usa la tarifa
    REAL citándola; además puede buscar en internet (Tipo 2) y proponer componentes /
    tareas. El Drive real tiene prioridad sobre la tabla `catalogo` (respaldo). Si no hay
    Drive cableado (`cliente_drive=None`) las tools de Drive degradan limpio (avisan "sin
    acceso a Drive", no revientan). Sin ninguna fuente, responde en modo simple (una sola
    llamada). El cliente puede lanzar (LLM caído) → se propaga (el endpoint lo convierte
    en 502).
    """
    permitir_internet = _quiere_internet(tipo, mensajes)
    tiene_tools = cliente_drive is not None or (
        repo_catalogo is not None and empresa_id is not None
    )
    tools = _herramientas(permitir_internet) if tiene_tools else None

    conversacion = _normalizar(mensajes)
    componentes: list[ComponentePropuesto] = []
    tareas: list[TareaPropuesta] = []
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
                texto=ultimo_texto,
                componentes=componentes,
                tareas=tareas,
                fuentes=fuentes,
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
                tareas,
                fuentes,
                usos_internet,
                cliente_drive=cliente_drive,
            )
            resultados.append(
                {"type": "tool_result", "tool_use_id": bloque.id, "content": salida}
            )
        conversacion.append({"role": "user", "content": resultados})

    # Loop acotado: devolvemos lo último que dijo Javo (no nos colgamos).
    return RespuestaConversacion(
        texto=ultimo_texto or "Estoy afinando la propuesta, dame un momento.",
        componentes=componentes,
        tareas=tareas,
        fuentes=fuentes,
    )
