# syntax=docker/dockerfile:1
# Contenedor ÚNICO de Dupla Comercial: un proceso FastAPI sirve la API y el
# front de React ya compilado. "Todo junto" — una imagen, una URL, un deploy.
# Pensado para Google Cloud Run (escucha en $PORT, 8080 por defecto).

# ── Etapa 1 · build del front (React + Vite) ──────────────────────────────────
FROM node:22-slim AS front
WORKDIR /front
# Las VITE_* se incrustan en el bundle AL COMPILAR; por eso llegan como build-args.
# Apuntan al proyecto Supabase Cloud (URL + anon key públicas, no secretas).
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
# VITE_API_URL se deja sin definir: el front usa `/api` (mismo origen que la API).
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

# ── Etapa 2 · backend Python que sirve API + front ────────────────────────────
FROM python:3.12-slim AS run
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080
WORKDIR /app
COPY apps/api/requirements.txt ./
RUN pip install -r requirements.txt
COPY apps/api/app ./app
# El build del front va donde `produccion.py` lo espera (app/web).
COPY --from=front /front/dist ./app/web
# Cloud Run inyecta $PORT. Uvicorn debe escuchar en 0.0.0.0.
CMD ["sh", "-c", "uvicorn app.produccion:raiz --host 0.0.0.0 --port ${PORT}"]
