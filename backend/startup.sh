#!/bin/bash
# Azure App Service startup script for Radia AI FastAPI backend.
# Azure sets PORT via the WEBSITES_PORT app setting; default to 8000.
gunicorn app.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${PORT:-8000}" \
  --timeout 300 \
  --keep-alive 75 \
  --access-logfile "-" \
  --error-logfile "-"
