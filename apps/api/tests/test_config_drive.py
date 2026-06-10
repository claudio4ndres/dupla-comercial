"""Test del setting `drive_folder_id` (carpeta del Drive de la empresa).

Bloquea el contrato del default: el id de la carpeta REAL del cliente piloto. Se
puede sobreescribir por entorno (`DRIVE_FOLDER_ID`). Sin red.
"""
from app.config import Settings


def test_drive_folder_id_tiene_default_la_carpeta_real():
    s = Settings()
    assert s.drive_folder_id == "1sPeaZbXVi4q-eXNkwGTTpaZUgKNuhy1i"


def test_drive_folder_id_se_puede_sobreescribir_por_entorno(monkeypatch):
    monkeypatch.setenv("DRIVE_FOLDER_ID", "otra-carpeta-123")
    s = Settings()
    assert s.drive_folder_id == "otra-carpeta-123"
