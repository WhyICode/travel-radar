# ─── Build stage ───
FROM node:22-alpine AS build
WORKDIR /app
COPY app/package*.json ./
RUN npm ci
COPY app/ .
RUN npm run build

# ─── Production stage ───
FROM nginx:alpine
LABEL org.opencontainers.image.title="travel-radar"
LABEL org.opencontainers.image.description="GPS Photo Intelligence Dashboard"

# Custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built app
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 3210

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -qO- http://localhost:3210/ || exit 1
