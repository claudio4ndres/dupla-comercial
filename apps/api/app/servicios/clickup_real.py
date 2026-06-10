"""Conector REAL de ClickUp sobre **httpx** (por empresa).

ClickUp es la herramienta de tareas del equipo. Este cliente habla con su API REST
(`https://api.clickup.com/api/v2`) para dos cosas:

  * `listar_listas()` → arma una lista PLANA de las listas reales del usuario
    (recorriendo team → space → list, y también space → folder → list), para que
    la UI ofrezca un SELECTOR de destino (decisión de producto: la lista NO va
    hardcodeada, el usuario la elige como en un conector).
  * `crear_tarea(list_id, nombre, descripcion)` → crea una tarea real en la lista
    elegida y devuelve su id.

Auth: el token PERSONAL del usuario viaja en el header `Authorization: <token>`
CRUDO — ClickUp NO usa el esquema "Bearer ". El token vive sólo en el backend
(regla de oro #3); jamás se expone al front.

Sin red al construir (como `cliente_anthropic`/`gmail_real`): el `AsyncClient` se
inyecta en los tests con transporte mockeado; en prod se crea uno por llamada. Un
status de error propaga como `ErrorClickUp` con el código HTTP, para diagnosticar.
"""
from dataclasses import dataclass

import httpx

BASE_CLICKUP = "https://api.clickup.com/api/v2"
TIMEOUT_SEGUNDOS = 30.0


@dataclass(frozen=True)
class ListaClickUp:
    """Una lista de ClickUp ya aplanada para el selector de la UI.

    `espacio` es el nombre del *space* al que pertenece (para agrupar/orientar al
    usuario cuando tiene muchas listas). No viaja ningún dato sensible.
    """

    id: str
    nombre: str
    espacio: str


class ErrorClickUp(Exception):
    """Falla al hablar con ClickUp (status de error o respuesta inesperada)."""


class ClienteClickUp:
    """Cliente mínimo de ClickUp. `cliente` (httpx.AsyncClient) es opcional: se
    inyecta en tests con transporte mockeado; en prod se omite y cada llamada abre
    su propio cliente (y lo cierra)."""

    def __init__(
        self,
        token: str,
        *,
        cliente: httpx.AsyncClient | None = None,
        base_url: str = BASE_CLICKUP,
        timeout: float = TIMEOUT_SEGUNDOS,
    ) -> None:
        self._token = token
        self._cliente = cliente
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def tiene_token(self) -> bool:
        """Si hay token configurado. Los endpoints lo usan para NO llamar a ClickUp
        cuando la empresa aún no conectó el conector (cae a [] / 400)."""
        return bool(self._token)

    def _headers(self) -> dict[str, str]:
        # ClickUp espera el token CRUDO en Authorization (NO "Bearer ").
        return {"Authorization": self._token, "Content-Type": "application/json"}

    async def _get(self, http: httpx.AsyncClient, ruta: str) -> dict:
        resp = await http.get(self._base + ruta, headers=self._headers())
        if resp.status_code >= 400:
            raise ErrorClickUp(
                f"ClickUp respondió {resp.status_code} al pedir {ruta}"
            )
        return resp.json()

    async def listar_listas(self) -> list[ListaClickUp]:
        """Recorre team → space → (listas sueltas + folders→listas) y las aplana."""
        http = self._cliente or httpx.AsyncClient(timeout=self._timeout)
        try:
            listas: list[ListaClickUp] = []
            teams = (await self._get(http, "/team")).get("teams", []) or []
            for team in teams:
                team_id = team.get("id")
                if not team_id:
                    continue
                spaces = (
                    await self._get(http, f"/team/{team_id}/space")
                ).get("spaces", []) or []
                for space in spaces:
                    space_id = space.get("id")
                    espacio = space.get("name", "")
                    if not space_id:
                        continue
                    # Listas SIN carpeta directamente en el espacio.
                    sueltas = (
                        await self._get(http, f"/space/{space_id}/list")
                    ).get("lists", []) or []
                    for lista in sueltas:
                        listas.append(self._a_lista(lista, espacio))
                    # Listas DENTRO de carpetas del espacio.
                    folders = (
                        await self._get(http, f"/space/{space_id}/folder")
                    ).get("folders", []) or []
                    for folder in folders:
                        for lista in folder.get("lists", []) or []:
                            listas.append(self._a_lista(lista, espacio))
            return listas
        finally:
            if self._cliente is None:
                await http.aclose()

    @staticmethod
    def _a_lista(lista: dict, espacio: str) -> ListaClickUp:
        return ListaClickUp(
            id=str(lista.get("id", "")),
            nombre=lista.get("name", ""),
            espacio=espacio,
        )

    async def crear_tarea(
        self, list_id: str, nombre: str, descripcion: str = ""
    ) -> str:
        """Crea una tarea en `list_id` y devuelve su id. Error HTTP → `ErrorClickUp`."""
        http = self._cliente or httpx.AsyncClient(timeout=self._timeout)
        try:
            resp = await http.post(
                f"{self._base}/list/{list_id}/task",
                headers=self._headers(),
                json={"name": nombre, "description": descripcion},
            )
            if resp.status_code >= 400:
                raise ErrorClickUp(
                    f"ClickUp respondió {resp.status_code} al crear la tarea "
                    f"en la lista {list_id}"
                )
            return str(resp.json().get("id", ""))
        finally:
            if self._cliente is None:
                await http.aclose()
