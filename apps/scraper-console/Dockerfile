FROM node:22-alpine AS deps

WORKDIR /app
RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/scraper-console/package.json apps/scraper-console/package.json

RUN pnpm install --frozen-lockfile --filter scraper-console...

FROM node:22-alpine AS builder

WORKDIR /app
RUN corepack enable

ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_URL=https://scrapy.lute-tlz-dddd.top
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/scraper-console/node_modules ./apps/scraper-console/node_modules
COPY apps/scraper-console ./apps/scraper-console
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

RUN pnpm -C apps/scraper-console build

FROM node:22-alpine AS runner

WORKDIR /app

ENV HOSTNAME=0.0.0.0
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3001

RUN addgroup -S nextjs && adduser -S nextjs -G nextjs

COPY --from=builder --chown=nextjs:nextjs /app/apps/scraper-console/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/apps/scraper-console/.next/static ./apps/scraper-console/.next/static
COPY --from=builder --chown=nextjs:nextjs /app/apps/scraper-console/public ./apps/scraper-console/public

USER nextjs

EXPOSE 3001

CMD ["node", "apps/scraper-console/server.js"]
