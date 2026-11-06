# Radia AI frontend (static SPA served by nginx) for Azure Container Apps.
# Build context: the REPOSITORY ROOT (vite.config.ts reads ../backend/app/VERSION).
#
# VITE_* values are baked into the JavaScript bundle at build time, so pass them as
# build args (public values only - never secrets):
#   docker build -f frontend/Dockerfile -t radia-frontend \
#     --build-arg VITE_API_BASE_URL=https://<backend-fqdn>/api/v1 \
#     --build-arg VITE_ENTRA_CLIENT_ID=<spa-client-id> \
#     --build-arg VITE_ENTRA_TENANT_ID=<tenant-id> \
#     --build-arg VITE_ENTRA_API_SCOPE=api://<api-client-id>/access_as_user \
#     --build-arg VITE_ENTRA_REDIRECT_URI=https://<frontend-fqdn> .

FROM node:24-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
# The Vite config resolves ../backend/app/VERSION relative to /app.
COPY backend/app/VERSION /backend/app/VERSION

ARG VITE_API_BASE_URL
ARG VITE_ENTRA_CLIENT_ID
ARG VITE_ENTRA_TENANT_ID
ARG VITE_ENTRA_API_SCOPE
ARG VITE_ENTRA_REDIRECT_URI
ARG VITE_APP_NAME="Radia AI"
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_ENTRA_CLIENT_ID=$VITE_ENTRA_CLIENT_ID \
    VITE_ENTRA_TENANT_ID=$VITE_ENTRA_TENANT_ID \
    VITE_ENTRA_API_SCOPE=$VITE_ENTRA_API_SCOPE \
    VITE_ENTRA_REDIRECT_URI=$VITE_ENTRA_REDIRECT_URI \
    VITE_APP_NAME=$VITE_APP_NAME

RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/security-headers.inc /etc/nginx/security-headers.inc
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
