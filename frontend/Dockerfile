# ─────────────────────────────────────────────────────────────────────────────
# Black House storefront — multi-stage production image
#
#   docker build -t blackhouse-frontend ./frontend
#   docker run -p 8080:80 blackhouse-frontend
#
# Build-time config is baked in (Vite inlines VITE_* into the bundle), so pass
# the environment as build args:
#   docker build --build-arg VITE_API_BASE_URL=/api/v1 -t blackhouse-frontend ./frontend
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: dependencies (cached separately from source) ───────────────────
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── Stage 2: build ──────────────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app

# Any VITE_* value can be overridden at build time.
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_BRAND_NAME="Black House"
ARG VITE_BRAND_TAGLINE="Small-batch outerwear"
ARG VITE_CONTACT_EMAIL="hello@blackhouse.example"
ARG VITE_WHATSAPP_NUMBER="910000000000"
ARG VITE_APP_ENV=production
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_BRAND_NAME=$VITE_BRAND_NAME \
    VITE_BRAND_TAGLINE=$VITE_BRAND_TAGLINE \
    VITE_CONTACT_EMAIL=$VITE_CONTACT_EMAIL \
    VITE_WHATSAPP_NUMBER=$VITE_WHATSAPP_NUMBER \
    VITE_APP_ENV=$VITE_APP_ENV

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build && npm prune --omit=dev

# ── Stage 3: serve (nginx) ──────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

# The nginx image expands ${VAR} in /etc/nginx/templates/*.template at startup,
# so the API origin can be set per-environment *without* rebuilding the image.
ENV BACKEND_ORIGIN=http://api:8000 \
    NGINX_PORT=80

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD wget -qO- http://127.0.0.1:${NGINX_PORT}/healthz >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
