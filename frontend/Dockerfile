FROM node:20-alpine AS base

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

# --- Production build: compiles Next's standalone output (next.config.mjs
# sets output: 'standalone'). NEXT_PUBLIC_* vars are inlined at build time, so
# this must be supplied as a build arg, not just a runtime env var.
FROM base AS builder
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY . .
RUN npm run build

# --- Production image: only the standalone server + static assets, run as a
# non-root user. Used by docker-compose.prod.yml.
FROM node:20-alpine AS prod
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
USER appuser
EXPOSE 3000
CMD ["node", "server.js"]

# --- Development image (default build target). Application code and the run
# command come from docker-compose.yml's bind mount and command override, not
# from this image, so plain `docker build` / `docker compose up` keep working
# exactly as before.
FROM base AS dev
