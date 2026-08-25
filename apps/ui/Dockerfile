# Via UI - standalone Next.js build served by the framework's minimal server.
# Build from the repository root:
#   docker build -f apps/ui/Dockerfile .
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-fund --no-audit

FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* tsconfig.base.json ./
COPY apps/ui/package.json ./apps/ui/
RUN cd apps/ui && npm install --no-fund --no-audit
COPY tsconfig.base.json ./
COPY apps/ui ./apps/ui
WORKDIR /app/apps/ui
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
# Next standalone output nests the server under apps/ui in monorepos.
COPY --from=builder --chown=via:via /app/apps/ui/.next/standalone ./
COPY --from=builder --chown=via:via /app/apps/ui/.next/static ./apps/ui/.next/static
COPY --from=builder --chown=via:via /app/apps/ui/public ./apps/ui/public
USER via
EXPOSE 3000
CMD ["node", "apps/ui/server.js"]
