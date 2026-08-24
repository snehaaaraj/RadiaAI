# ---------------------------------------------------------------------------
# Stage 1 — Build dependencies
# Using slim to keep the image small; install only what's needed to run.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system deps needed by some Python packages (e.g. cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Stage 2 — Install Python dependencies
# Separate stage so Docker caches this layer independently of source code.
# ---------------------------------------------------------------------------
FROM base AS deps

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 3 — Final runtime image
# ---------------------------------------------------------------------------
FROM base AS runtime

# Create a non-root user — never run application code as root
RUN groupadd -r radia && useradd -r -g radia radia

WORKDIR /app

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application source code
COPY app/ ./app/
COPY radia_ai/ ./radia_ai/

# Set correct ownership
RUN chown -R radia:radia /app

USER radia

EXPOSE 8000

# Health check — Docker can restart the container if the API stops responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Use exec form to receive signals correctly (enables graceful shutdown)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
