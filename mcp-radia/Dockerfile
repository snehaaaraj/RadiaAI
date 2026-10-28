# mcp-radia — RadiaAI digital-thread MCP server (Streamable HTTP transport).
#
# Built for Azure Container Apps with internal-only ingress: this image never
# terminates TLS and never authenticates browser traffic. It is reachable only
# from the RadiaAI backend, over the Container Apps environment's private
# network, and only when MCP_RADIA_SERVICE_TOKEN is presented on every request.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY mcp_radia ./mcp_radia

RUN pip install --no-cache-dir .

# Runs as a non-root user: nothing in this image needs to write outside /tmp.
RUN useradd --create-home --uid 10001 mcpradia
USER mcpradia

# Bind address is internal: the real network boundary is the platform's
# ingress configuration (internal-only Container Apps ingress), not this host.
ENV MCP_RADIA_HOST=0.0.0.0
ENV MCP_RADIA_PORT=8081

EXPOSE 8081

CMD ["mcp-radia", "http"]
