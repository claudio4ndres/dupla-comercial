"""Aplicación FastAPI de Dupla Comercial."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.http_pool import cerrar_cliente_http
from app.rutas.catalogo import router as router_catalogo
from app.rutas.clickup import router as router_clickup
from app.rutas.conversaciones import router as router_conversaciones
from app.rutas.empresa import router as router_empresa
from app.rutas.integraciones import router as router_integraciones
from app.rutas.interno import router as router_interno
from app.rutas.miembros import router as router_miembros
from app.rutas.propuestas import router as router_propuestas
from app.rutas.solicitudes import router as router_solicitudes
from app.rutas.tareas import router as router_tareas
from app.rutas.usuario import router as router_usuario


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: cierra el cliente HTTP compartido al apagar."""
    yield
    await cerrar_cliente_http()


app = FastAPI(title="Dupla Comercial · API", lifespan=lifespan)
app.include_router(router_solicitudes)
app.include_router(router_integraciones)
app.include_router(router_interno)
app.include_router(router_conversaciones)
app.include_router(router_empresa)
app.include_router(router_catalogo)
app.include_router(router_propuestas)
app.include_router(router_tareas)
app.include_router(router_clickup)
app.include_router(router_miembros)
app.include_router(router_usuario)


@app.get("/salud")
def salud():
    """Comprobación de salud del servicio."""
    return {"estado": "ok"}
