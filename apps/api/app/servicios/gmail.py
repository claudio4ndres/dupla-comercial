"""Contrato del cliente de Gmail + tipos de la ingesta de correo.

El cliente REAL (google-api-python-client / OAuth) se cablea en una tarea de
integración aparte (TR1). Aquí definimos SOLO la interfaz, para que el servicio de
ingesta y los tests trabajen contra un doble (CA6: cero llamadas reales, cero
credenciales reales). La Regla de oro #3 (credenciales solo en el backend) se cumple
porque el refresh del token y el secreto viven detrás de esta interfaz.
"""
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.repositorios.integraciones import Integracion


class MensajeCorreo(BaseModel):
    """Un correo entrante ya normalizado, listo para volverse `solicitud`."""

    gmail_msg_id: str
    remitente: str = ""       # nombre del From
    correo_origen: str = ""   # email del From
    asunto: str = ""
    cuerpo: str = ""          # texto plano del mensaje


class ErrorAutenticacionGmail(Exception):
    """El refresh token está expirado o revocado: la empresa debe reconectar (CA7)."""


class ClienteGmail(Protocol):
    """Lee los correos nuevos de UNA casilla. La implementación real resuelve por
    dentro el refresh del access token, el `historyId` y el paginado."""

    async def listar_nuevos(
        self, cursor: str | None
    ) -> tuple[list[MensajeCorreo], str | None]:
        """Devuelve (mensajes nuevos desde `cursor`, nuevo cursor a guardar).

        Si el refresh del token falla, lanza `ErrorAutenticacionGmail`.
        """
        ...

    async def obtener_mensaje(self, gmail_msg_id: str) -> MensajeCorreo | None:
        """Re-baja UN mensaje por su id. Sirve para RE-PROCESAR correos ya ingeridos:
        el cuerpo se re-extrae con el parser actual (incluye el fallback a HTML), así
        un correo que entró con cuerpo vacío recupera su contenido. `None` si el
        mensaje ya no existe; auth fallida → `ErrorAutenticacionGmail`.
        """
        ...


class FabricaClienteGmail(Protocol):
    """Construye el `ClienteGmail` de UNA integración. La implementación real resuelve
    el refresh token (vía `AlmacenSecretos`/OAuth) y arma el cliente; el doble de test
    devuelve un cliente fijo por empresa. Aísla al poller de cómo se obtienen las
    credenciales (regla de oro #3)."""

    def crear(self, integracion: "Integracion") -> ClienteGmail: ...
