# Via UI - standalone Next.js build served by the framework's minimal server.
# Build from the repository root:
#   docker build -f frontend/ui/Dockerfile .
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-fund --no-audit

FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* tsconfig.base.json ./
COPY frontend/ui/package.json ./frontend/ui/
RUN cd frontend/ui && npm install --no-fund --no-audit
COPY tsconfig.base.json ./
COPY frontend/ui ./frontend/ui
WORKDIR /app/frontend/ui
ARG NEXT_PUBLIC_API_URL=http://localhost:8080
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000
RUN addgroup -S via && adduser -S via -G via
# Next standalone output nests the server under frontend/ui in monorepos.
COPY --from=builder --chown=via:via /app/frontend/ui/.next/standalone ./
COPY --from=builder --chown=via:via /app/frontend/ui/.next/static ./frontend/ui/.next/static
COPY --from=builder --chown=via:via /app/frontend/ui/public ./frontend/ui/public
USER via
EXPOSE 3000
CMD ["node", "frontend/ui/server.js"]
