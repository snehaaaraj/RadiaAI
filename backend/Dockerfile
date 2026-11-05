# Radia AI backend (FastAPI) for Azure Container Apps.
# Build context: backend/    docker build -t radia-backend backend

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app
COPY radia_ai ./radia_ai

# Runs as a non-root user: nothing here needs to write outside /tmp.
RUN useradd --create-home --uid 10001 radia
USER radia

EXPOSE 8000

# ENVIRONMENT must be set explicitly (it defaults to production, which requires Entra ID).
# --proxy-headers lets the app see the original scheme/client IP behind the Container Apps ingress.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
