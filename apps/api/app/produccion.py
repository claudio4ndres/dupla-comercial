"""Servidor de producción: un solo proceso sirve la API y el front compilado.

En Cloud Run corre como `uvicorn app.produccion:raiz`. Monta la API real
(`app.main:app`) bajo `/api` —el front pide rutas relativas `/api/...`, igual que
en dev con el proxy de Vite— y sirve el build de React (Vite `dist`, que el
Dockerfile copia a `app/web`) como estáticos en `/`. Así queda "todo junto": un
contenedor, una URL, un deploy.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.main import app as api

# Carpeta con el build del front. El Dockerfile copia `apps/web/dist` aquí.
# En local (sin build), si no existe, se sirve sólo la API.
ESTATICOS = Path(__file__).resolve().parent / "web"

raiz = FastAPI(title="Dupla Comercial · Producción")

# La API PRIMERO, bajo /api. El backend define sus rutas sin ese prefijo
# (`/solicitudes`, ...); el mount las reubica. Debe registrarse antes que el
# estático de la raíz para que `/api/...` no lo capture el SPA.
raiz.mount("/api", api)

# El front compilado en `/`. html=True sirve index.html en la raíz y como
# fallback. La app navega por estado (no por URL): no hay deep-links que resolver.
# El `if` permite importar este módulo en local sin haber compilado el front.
if ESTATICOS.is_dir():
    raiz.mount("/", StaticFiles(directory=str(ESTATICOS), html=True), name="spa")
