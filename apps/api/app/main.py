"""Aplicación FastAPI de Dupla Comercial."""
from fastapi import FastAPI

from app.rutas.integraciones import router as router_integraciones
from app.rutas.interno import router as router_interno
from app.rutas.solicitudes import router as router_solicitudes

app = FastAPI(title="Dupla Comercial · API")
app.include_router(router_solicitudes)
app.include_router(router_integraciones)
app.include_router(router_interno)


@app.get("/salud")
def salud():
    """Comprobación de salud del servicio."""
    return {"estado": "ok"}
