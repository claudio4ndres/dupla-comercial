"""Spec 015 · Cache en proceso del access token OAuth (Gmail/Drive).

Hoy cada operación canjea el refresh por un access token nuevo: cada tool-call
de Javo al Drive y cada pase del poller paga un round-trip OAuth. El access
token dura ~1 hora: se cachea por `token_ref` con TTL `expires_in - 60s`.
Reloj inyectable (cero espera real) y MockTransport (cero red).
"""
import httpx

from app.servicios.cache_token_acceso import CacheTokenAcceso
from app.servicios.drive_real import ClienteDriveReal


class _RelojFake:
    def __init__(self):
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


class _AlmacenFake:
    def __init__(self, refresh="refresh-token"):
        self._refresh = refresh
        self.lecturas = 0

    async def obtener(self, token_ref):
        self.lecturas += 1
        return self._refresh


def test_cache_devuelve_dentro_del_ttl_y_expira_despues():
    reloj = _RelojFake()
    cache = CacheTokenAcceso(reloj=reloj)

    cache.guardar("ref-1", "token-a", expires_in=3600)
    assert cache.obtener("ref-1") == "token-a"

    reloj.ahora += 3600 - 61  # justo dentro del TTL (margen de 60 s)
    assert cache.obtener("ref-1") == "token-a"

    reloj.ahora += 2  # cruzó el TTL
    assert cache.obtener("ref-1") is None


def test_cache_aisla_por_token_ref():
    cache = CacheTokenAcceso(reloj=_RelojFake())
    cache.guardar("ref-a", "token-a", expires_in=3600)
    assert cache.obtener("ref-b") is None  # el token de A jamás sirve para B


async def test_drive_con_cache_canjea_un_solo_token_para_dos_operaciones():
    # CA4: dos listar_recientes seguidos → UN solo POST al endpoint de token.
    canjes = []

    def handler(req: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com" in str(req.url):
            canjes.append(1)
            return httpx.Response(
                200, json={"access_token": "access-efimero", "expires_in": 3600}
            )
        return httpx.Response(200, json={"files": []})

    cliente = ClienteDriveReal(
        almacen=_AlmacenFake(),
        token_ref="ref-1",
        client_id="cid",
        client_secret="csecret",
        cliente=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        cache=CacheTokenAcceso(reloj=_RelojFake()),
    )

    await cliente.listar_recientes()
    await cliente.listar_recientes()

    assert len(canjes) == 1  # el segundo listar usó el token cacheado


async def test_drive_sin_cache_mantiene_el_comportamiento_actual():
    canjes = []

    def handler(req: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com" in str(req.url):
            canjes.append(1)
            return httpx.Response(200, json={"access_token": "a", "expires_in": 3600})
        return httpx.Response(200, json={"files": []})

    cliente = ClienteDriveReal(
        almacen=_AlmacenFake(),
        token_ref="ref-1",
        client_id="cid",
        client_secret="csecret",
        cliente=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    await cliente.listar_recientes()
    await cliente.listar_recientes()

    assert len(canjes) == 2  # sin cache: un canje por operación (como hoy)
