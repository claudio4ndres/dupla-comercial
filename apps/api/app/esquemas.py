"""Esquemas Pydantic compartidos por la API."""
from typing import Literal

from pydantic import BaseModel

TipoSolicitud = Literal["tipo_1", "tipo_2"]


class ResultadoClasificacion(BaseModel):
    """Resultado de clasificar y resumir una solicitud."""

    resumen: str
    tipo: TipoSolicitud
