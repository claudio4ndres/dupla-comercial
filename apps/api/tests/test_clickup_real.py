"""Cliente REAL de ClickUp sobre **httpx** (conector por empresa).

Habla con la API REST de ClickUp (`https://api.clickup.com/api/v2`) vía httpx. El
token personal del usuario viaja en el header `Authorization: <token>` (CRUDO, sin
"Bearer "). Dos capacidades:

  * `listar_listas()` recorre team → space → list (+ folders → lists) y aplana a
    `ListaClickUp{id, nombre, espacio}` para poblar el SELECTOR de la UI.
  * `crear_tarea(list_id, nombre, descripcion)` hace POST y devuelve el id de la
    tarea creada; un status de error propaga como excepción clara.

Cero red y cero llamadas reales: se inyecta un transporte httpx mockeado (igual que
`cliente_anthropic`/`gmail_real`). El live lo prueba el dueño con su token real.
"""
import json

import httpx
import pytest

from app.servicios.clickup_real import ClienteClickUp, ListaClickUp

TOKEN = "pk_test_123"


def _cliente(handler):
    transporte = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transporte)
    return ClienteClickUp(TOKEN, cliente=http)


async def test_listar_listas_aplana_team_space_list_y_folders():
    """Recorre team → space → (listas sueltas + folders→listas) y aplana, anotando
    el nombre del espacio en cada lista."""
    vistos: dict[str, str | None] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        ruta = req.url.path
        # El token va CRUDO en Authorization (sin "Bearer ").
        vistos["auth"] = req.headers.get("Authorization")
        if ruta == "/api/v2/team":
            return httpx.Response(200, json={"teams": [{"id": "team1"}]})
        if ruta == "/api/v2/team/team1/space":
            return httpx.Response(
                200, json={"spaces": [{"id": "sp1", "name": "Marketing"}]}
            )
        if ruta == "/api/v2/space/sp1/list":
            # Listas SIN carpeta dentro del espacio.
            return httpx.Response(
                200, json={"lists": [{"id": "L1", "name": "Backlog"}]}
            )
        if ruta == "/api/v2/space/sp1/folder":
            # Carpetas, cada una con sus listas embebidas.
            return httpx.Response(
                200,
                json={
                    "folders": [
                        {
                            "id": "F1",
                            "name": "Campañas",
                            "lists": [{"id": "L2", "name": "Sampling"}],
                        }
                    ]
                },
            )
        return httpx.Response(404, json={})

    listas = await _cliente(handler).listar_listas()

    assert vistos["auth"] == TOKEN  # token crudo, sin "Bearer "
    # Se aplanan TODAS: la lista suelta y la lista dentro de la carpeta.
    assert ListaClickUp(id="L1", nombre="Backlog", espacio="Marketing") in listas
    assert ListaClickUp(id="L2", nombre="Sampling", espacio="Marketing") in listas
    assert len(listas) == 2


async def test_listar_listas_sin_teams_devuelve_vacio():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"teams": []})

    assert await _cliente(handler).listar_listas() == []


async def test_crear_tarea_postea_y_devuelve_id():
    visto: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["metodo"] = req.method
        visto["ruta"] = req.url.path
        visto["auth"] = req.headers.get("Authorization")
        visto["body"] = json.loads(req.content)
        return httpx.Response(200, json={"id": "tarea_abc", "name": "Reclutar"})

    id_creado = await _cliente(handler).crear_tarea(
        "L1", "Reclutar 6 promotoras", descripcion="RRHH · Coordinación · 3 días"
    )

    assert id_creado == "tarea_abc"
    assert visto["metodo"] == "POST"
    assert visto["ruta"] == "/api/v2/list/L1/task"
    assert visto["auth"] == TOKEN
    assert visto["body"]["name"] == "Reclutar 6 promotoras"
    assert visto["body"]["description"] == "RRHH · Coordinación · 3 días"


async def test_crear_tarea_error_http_lanza_excepcion_clara():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"err": "Token invalid", "ECODE": "OAUTH_019"})

    with pytest.raises(Exception) as exc:
        await _cliente(handler).crear_tarea("L1", "X")
    # El mensaje menciona a ClickUp y el status, para diagnosticar rápido.
    assert "ClickUp" in str(exc.value)
    assert "401" in str(exc.value)
