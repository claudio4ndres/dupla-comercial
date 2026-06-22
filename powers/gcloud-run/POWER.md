---
name: "gcloud-run"
displayName: "Google Cloud Run"
description: "Guía de deploy y operación de Dupla Comercial en Google Cloud Run: build, deploy, logs y troubleshooting"
keywords: ["gcloud", "cloud-run", "deploy", "docker", "cloudbuild", "google-cloud"]
author: "RukkumansLabs"
---

# Google Cloud Run · Dupla Comercial

## Overview

Dupla Comercial se despliega en Google Cloud Run (backend FastAPI + frontend Vite).
El build usa Cloud Build con el `cloudbuild.yaml` del repo.

## Prerrequisitos

- `gcloud` CLI instalado y autenticado
- Proyecto GCP: el mismo donde vive Supabase y Secret Manager
- Docker configurado (para builds locales)

## Estructura de deploy

```
Dockerfile        → Multi-stage: build del frontend + backend Python
cloudbuild.yaml   → Pipeline de Cloud Build (build + deploy)
```

## Comandos frecuentes

### Deploy manual
```bash
gcloud run deploy dupla-comercial \
  --source . \
  --region us-west1 \
  --allow-unauthenticated \
  --set-env-vars "SUPABASE_URL=...,SUPABASE_ANON_KEY=..."
```

### Ver logs
```bash
gcloud run services logs read dupla-comercial --region us-west1 --limit 50
```

### Ver revisiones activas
```bash
gcloud run revisions list --service dupla-comercial --region us-west1
```

### Rollback a revisión anterior
```bash
gcloud run services update-traffic dupla-comercial \
  --to-revisions REVISION_ID=100 \
  --region us-west1
```

## Variables de entorno requeridas

| Variable | Descripción |
|----------|-------------|
| SUPABASE_URL | URL del proyecto Supabase |
| SUPABASE_ANON_KEY | Anon key de Supabase |
| SUPABASE_SERVICE_ROLE_KEY | Service role key (poller) |
| SUPABASE_JWT_SECRET | Secreto para verificar JWTs |
| ANTHROPIC_API_KEY | API key de Claude |
| GOOGLE_CLIENT_ID | OAuth client ID |
| GOOGLE_CLIENT_SECRET | OAuth client secret |
| GOOGLE_REDIRECT_URI | Callback URL de OAuth |
| GCP_PROJECT_ID | ID del proyecto GCP |
| POLLER_TOKEN | Secreto del poller |
| FRONTEND_URL | URL del frontend (para redirects) |

## Troubleshooting

### Error: "Container failed to start"
- Verificar que el Dockerfile expone el puerto correcto (`PORT` env var)
- Verificar que uvicorn arranca con `--loop asyncio` (uvloop no funciona en Cloud Run)

### Error: "Permission denied" en Secret Manager
- Verificar que la service account tiene el rol `secretmanager.secretAccessor`

### Deploy lento (>5 min)
- Revisar el Dockerfile: ¿se copian `node_modules` sin `.dockerignore`?
- Usar cache de capas de Docker
