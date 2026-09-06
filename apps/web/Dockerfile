FROM node:22.22.0-alpine@sha256:e4bf2a82ad0a4037d28035ae71529873c069b13eb0455466ae0bc13363826e34 AS base
ENV PNPM_HOME="/pnpm" \
    PATH="/pnpm:${PATH}"
RUN corepack enable && corepack prepare pnpm@10.33.2 --activate

FROM base AS dependencies
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY contracts/ts/package.json contracts/ts/package.json
RUN --mount=type=cache,target=/pnpm/store \
    pnpm install --filter @flash-trips/web... --frozen-lockfile

FROM dependencies AS builder
COPY apps/web apps/web
COPY contracts/ts contracts/ts
RUN pnpm --dir apps/web build

FROM node:22.22.0-alpine@sha256:e4bf2a82ad0a4037d28035ae71529873c069b13eb0455466ae0bc13363826e34 AS runtime
ENV HOSTNAME="0.0.0.0" \
    NODE_ENV="production" \
    PORT=3000
RUN addgroup --system --gid 10001 flashtrips \
    && adduser --system --uid 10001 --ingroup flashtrips flashtrips

WORKDIR /app
COPY --from=builder --chown=flashtrips:flashtrips /app/apps/web/.next/standalone ./
COPY --from=builder --chown=flashtrips:flashtrips /app/apps/web/.next/static ./apps/web/.next/static

USER 10001:10001
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"]

CMD ["node", "apps/web/server.js"]
