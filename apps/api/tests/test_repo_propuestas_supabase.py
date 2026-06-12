"""004 · `RepositorioPropuestasSupabase` contra PostgREST (sin red).

Usa un transporte httpx **mockeado**: verifica que el repo manda el JWT del
usuario (lo que dispara la RLS que aísla por empresa), pega al endpoint correcto
de PostgREST filtrando por la solicitud, y mapea la respuesta (con componentes y
tareas embebidos) a `Propuesta`. La prueba real de aislamiento corre contra
`supabase start` en integración, no en esta suite unitaria.
"""
from uuid import UUID, uuid4

import httpx

from app.repositorios.propuestas import ComponentePropuesta, TareaPropuesta
from app.repositorios.propuestas_supabase import RepositorioPropuestasSupabase

BASE = "https://proyecto.supabase.co"
ANON = "anon-key-de-prueba"
JWT = "jwt-del-usuario-empresa-a"
EMPRESA = UUID("0000c0de-0000-4000-8000-000000000001")


def _repo(handler):
    transporte = httpx.MockTransport(handler)
    cliente = httpx.AsyncClient(transport=transporte)
    return RepositorioPropuestasSupabase(BASE, ANON, JWT, cliente=cliente)


def _grabador():
    """Handler que GRABA cada (método, url, json) y responde según la tabla golpeada.

    Simula PostgREST: el GET de búsqueda por `conversacion_id` decide si la propuesta
    YA existe (lo controla `existe[...]`); los POST devuelven una fila con id.
    """
    estado = {"existe": None, "prop_id_existente": str(uuid4())}
    llamadas: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        cuerpo = None
        if req.content:
            import json as _json

            cuerpo = _json.loads(req.content)
        llamadas.append({"metodo": req.method, "url": url, "json": cuerpo})

        # GET de la cabecera por conversacion_id: ¿ya hay propuesta para esta conversación?
        if req.method == "GET" and "/propuestas" in url and "conversacion_id" in url:
            if estado["existe"]:
                return httpx.Response(200, json=[{"id": estado["prop_id_existente"]}])
            return httpx.Response(200, json=[])
        # POST de la cabecera nueva.
        if req.method == "POST" and url.endswith("/propuestas"):
            return httpx.Response(201, json=[{"id": str(uuid4())}])
        # PATCH de la cabecera (camino REEMPLAZAR).
        if req.method == "PATCH" and "/propuestas" in url:
            return httpx.Response(200, json=[{"id": estado["prop_id_existente"]}])
        # DELETE / POST de hijos, o cualquier otra cosa: 200/201 vacío.
        if req.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(201, json=[])

    return handler, llamadas, estado


async def test_obtener_por_solicitud_manda_jwt_y_mapea_componentes_y_tareas():
    sol_id = uuid4()
    prop_id = uuid4()
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["auth"] = req.headers.get("authorization")
        visto["apikey"] = req.headers.get("apikey")
        visto["url"] = str(req.url)
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(prop_id),
                    "total": 5190000,
                    "estado": "borrador",
                    "componentes_propuesta": [
                        {
                            "nombre": "Promotoras uniformadas",
                            "detalle": "6h/día × 4 días · 3 tiendas",
                            "cantidad": 6,
                            "valor_unitario": 240000,
                        }
                    ],
                    "tareas": [
                        {
                            "nombre": "Reclutar 6 promotoras",
                            "grupo": "RRHH",
                            "responsable": "Coordinación",
                            "vencimiento": "3 días",
                        }
                    ],
                }
            ],
        )

    prop = await _repo(handler).obtener_por_solicitud(sol_id, EMPRESA)

    # El JWT del usuario en el header es lo que hace que la RLS filtre por SU empresa.
    assert visto["auth"] == f"Bearer {JWT}"
    assert visto["apikey"] == ANON
    assert "/rest/v1/propuestas" in visto["url"]
    # Filtra la propuesta por la conversación de ESA solicitud.
    assert f"solicitud_id=eq.{sol_id}" in visto["url"]

    assert prop is not None
    assert prop.id == prop_id
    assert prop.estado == "borrador"
    assert prop.total == 5190000
    assert len(prop.componentes) == 1
    assert prop.componentes[0].nombre == "Promotoras uniformadas"
    assert prop.componentes[0].valor_unitario == 240000
    assert prop.componentes[0].cantidad == 6
    assert len(prop.tareas) == 1
    assert prop.tareas[0].grupo == "RRHH"
    assert prop.tareas[0].vencimiento == "3 días"


async def test_obtener_por_solicitud_sin_filas_devuelve_none():
    def handler(req):
        return httpx.Response(200, json=[])

    assert await _repo(handler).obtener_por_solicitud(uuid4(), EMPRESA) is None


async def test_obtener_por_solicitud_propuesta_sin_hijos_mapea_listas_vacias():
    prop_id = uuid4()

    def handler(req):
        return httpx.Response(
            200,
            json=[{"id": str(prop_id), "total": 0, "estado": "borrador"}],
        )

    prop = await _repo(handler).obtener_por_solicitud(uuid4(), EMPRESA)
    assert prop is not None
    assert prop.componentes == []
    assert prop.tareas == []


async def test_obtener_por_solicitud_ordena_por_creado_en_desc():
    # #4 · sin `order` PostgREST puede servir una versión vieja/arbitraria: el repo
    # debe pedir explícitamente la ÚLTIMA (creado_en.desc + limit=1).
    visto = {}

    def handler(req):
        visto["url"] = str(req.url)
        return httpx.Response(200, json=[{"id": str(uuid4()), "total": 0, "estado": "borrador"}])

    await _repo(handler).obtener_por_solicitud(uuid4(), EMPRESA)
    assert "order=creado_en.desc" in visto["url"]
    assert "limit=1" in visto["url"]


# ── Write-path: crear() (#4) ────────────────────────────────────────────────
async def test_crear_inserta_cabecera_componentes_y_tareas_con_dias_y_proveedor():
    sol_id = uuid4()
    conv_id = uuid4()
    handler, llamadas, estado = _grabador()
    estado["existe"] = None  # no hay propuesta previa → INSERT

    componentes = [
        ComponentePropuesta(
            nombre="Promotoras",
            detalle="3 tiendas",
            proveedor="Eventos Pro",
            cantidad=6,
            dias=3,
            valor_unitario=240000,
        )
    ]
    tareas = [
        TareaPropuesta(
            nombre="Reclutar 6 promotoras",
            grupo="RRHH",
            responsable="Coordinación",
            vencimiento="3 días",
        )
    ]

    prop = await _repo(handler).crear(EMPRESA, sol_id, conv_id, componentes, tareas)

    # Mandó el JWT del usuario (RLS por su empresa).
    assert all(l_["url"].startswith(BASE) for l_ in llamadas)
    # 1) POST de la cabecera ligada a la conversación.
    post_cab = next(l_ for l_ in llamadas if l_["metodo"] == "POST" and l_["url"].endswith("/propuestas"))
    assert post_cab["json"]["conversacion_id"] == str(conv_id)
    assert post_cab["json"]["estado"] == "borrador"
    assert post_cab["json"]["total"] == 6 * 3 * 240000  # cantidad × días × valor
    # 2) POST de los componentes CON dias y proveedor en el body.
    post_comp = next(l_ for l_ in llamadas if "/componentes_propuesta" in l_["url"] and l_["metodo"] == "POST")
    fila_c = post_comp["json"][0]
    assert fila_c["dias"] == 3
    assert fila_c["proveedor"] == "Eventos Pro"
    assert fila_c["valor_unitario"] == 240000
    assert fila_c["cantidad"] == 6
    # 3) POST de las tareas con su empresa_id propio.
    post_tar = next(l_ for l_ in llamadas if l_["url"].endswith("/tareas") and l_["metodo"] == "POST")
    fila_t = post_tar["json"][0]
    assert fila_t["empresa_id"] == str(EMPRESA)
    assert fila_t["grupo"] == "RRHH"
    assert fila_t["vencimiento"] == "3 días"

    # El total devuelto = Σ cantidad × días × valor.
    assert prop.total == 6 * 3 * 240000
    assert prop.estado == "borrador"


async def test_crear_es_idempotente_no_duplica_reemplaza_la_existente():
    # #4 (Sev ALTA) · clic doble en "Generar propuesta": como ya hay propuesta para esa
    # conversación, NO se inserta otra cabecera; se REEMPLAZAN sus hijos sobre la MISMA fila.
    conv_id = uuid4()
    handler, llamadas, estado = _grabador()
    estado["existe"] = True  # ya existe propuesta para esta conversación

    componentes = [ComponentePropuesta(nombre="Catering", cantidad=1, dias=1, valor_unitario=100000)]
    tareas = [TareaPropuesta(nombre="Comprar insumos", grupo="Compras")]

    prop = await _repo(handler).crear(EMPRESA, uuid4(), conv_id, componentes, tareas)

    # NO hubo POST de cabecera nueva (eso es lo que duplicaba).
    posts_cabecera = [l_ for l_ in llamadas if l_["metodo"] == "POST" and l_["url"].endswith("/propuestas")]
    assert posts_cabecera == [], "re-crear NO debe insertar una segunda propuesta"
    # Sí se borraron los hijos viejos antes de re-insertar (reemplazo limpio).
    borrados = [l_["url"] for l_ in llamadas if l_["metodo"] == "DELETE"]
    assert any("/componentes_propuesta" in u for u in borrados)
    assert any("/tareas" in u for u in borrados)
    # Reusa la MISMA fila existente.
    assert str(prop.id) == estado["prop_id_existente"]


async def test_actualizar_estado_patchea_y_filtra_por_empresa():
    # #7 · transición del estado de la propuesta (borrador→aprobada→enviada).
    prop_id = uuid4()
    visto = {}

    def handler(req):
        visto["metodo"] = req.method
        visto["url"] = str(req.url)
        import json as _json

        visto["json"] = _json.loads(req.content) if req.content else None
        visto["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json=[{"id": str(prop_id), "total": 0, "estado": "aprobada"}])

    prop = await _repo(handler).actualizar_estado(prop_id, EMPRESA, "aprobada")

    assert visto["metodo"] == "PATCH"
    assert f"id=eq.{prop_id}" in visto["url"]
    assert visto["json"] == {"estado": "aprobada"}
    assert visto["auth"] == f"Bearer {JWT}"  # RLS por el JWT del usuario
    assert prop.estado == "aprobada"
