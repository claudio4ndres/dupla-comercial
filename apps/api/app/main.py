"""Aplicación FastAPI de Dupla Comercial."""
from fastapi import FastAPI

from app.rutas.catalogo import router as router_catalogo
from app.rutas.clickup import router as router_clickup
from app.rutas.conversaciones import router as router_conversaciones
from app.rutas.integraciones import router as router_integraciones
from app.rutas.interno import router as router_interno
from app.rutas.miembros import router as router_miembros
from app.rutas.propuestas import router as router_propuestas
from app.rutas.solicitudes import router as router_solicitudes
from app.rutas.tareas import router as router_tareas

app = FastAPI(title="Dupla Comercial · API")
app.include_router(router_solicitudes)
app.include_router(router_integraciones)
app.include_router(router_interno)
app.include_router(router_conversaciones)
app.include_router(router_catalogo)
app.include_router(router_propuestas)
app.include_router(router_tareas)
app.include_router(router_clickup)
app.include_router(router_miembros)


@app.get("/salud")
def salud():
    """Comprobación de salud del servicio."""
    return {"estado": "ok"}
