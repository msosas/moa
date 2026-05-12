# syntax=docker/dockerfile:1.6

FROM node:20-alpine AS base
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

# Dev target: source bind-mounted, vite dev server.
FROM base AS dev
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# Build stage: compile static assets.
FROM base AS build
# Leave empty so the client falls back to same-origin relative ``/api/*`` paths
# at runtime. Nginx (or whichever proxy fronts the prod stack) then routes them
# to the backend. Override only when calling a cross-origin backend at build time.
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
COPY . .
RUN npm run build

# Prod target: nginx serves built assets and proxies /api to the backend service.
FROM nginx:1.27-alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
