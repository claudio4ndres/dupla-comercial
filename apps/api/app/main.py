"""Aplicación FastAPI de Dupla Comercial."""
from fastapi import FastAPI

from app.rutas.catalogo import router as router_catalogo
from app.rutas.conversaciones import router as router_conversaciones
from app.rutas.integraciones import router as router_integraciones
from app.rutas.interno import router as router_interno
from app.rutas.solicitudes import router as router_solicitudes

app = FastAPI(title="Dupla Comercial · API")
app.include_router(router_solicitudes)
app.include_router(router_integraciones)
app.include_router(router_interno)
app.include_router(router_conversaciones)
app.include_router(router_catalogo)


@app.get("/salud")
def salud():
    """Comprobación de salud del servicio."""
    return {"estado": "ok"}
