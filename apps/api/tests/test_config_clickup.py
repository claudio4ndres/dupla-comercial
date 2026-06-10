"""Test de los settings de ClickUp (`clickup_api_token` / `clickup_list_id`).

Bloquea el contrato: ambos son credenciales/config que la app lee del entorno (o
de un `.env` en desarrollo) y su default es la cadena vacía, para poder levantar
la app en tests/CI sin configurar ClickUp (regla de oro #3 — el token vive sólo en
el backend). Sin red.

Se construye `Settings(_env_file=None)` para NO leer el `.env` local (que en una
máquina de desarrollo SÍ trae el token real): así el test del default vacío es
determinista en cualquier entorno.
"""
from app.config import Settings


def test_clickup_tiene_defaults_vacios():
    s = Settings(_env_file=None)
    assert s.clickup_api_token == ""
    assert s.clickup_list_id == ""


def test_clickup_se_puede_configurar_por_entorno(monkeypatch):
    monkeypatch.setenv("CLICKUP_API_TOKEN", "pk_token_de_prueba")
    monkeypatch.setenv("CLICKUP_LIST_ID", "123456")
    s = Settings(_env_file=None)
    assert s.clickup_api_token == "pk_token_de_prueba"
    assert s.clickup_list_id == "123456"
