# ---------------------------------------------------------------------------
# Stage 1 — Build the React application
# ---------------------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first — cached as long as package.json doesn't change
COPY package.json package-lock.json* ./
RUN npm ci --frozen-lockfile

# Copy source and build
COPY . .
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 — Serve with nginx
# The build output is ~5MB; the nginx image adds ~25MB. Total: ~30MB.
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Remove default nginx site config
RUN rm -rf /etc/nginx/conf.d/default.conf

# Copy our custom nginx config
COPY --from=build /app/dist /usr/share/nginx/html
COPY ../docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
