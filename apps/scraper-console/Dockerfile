FROM node:22-alpine AS deps

# 生产 B 在国内，直连 npmjs ~220KB/s；允许构建时切换 registry，默认仍是官方源。
ARG NPM_CONFIG_REGISTRY=https://registry.npmjs.org/
ENV NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY}

WORKDIR /app/apps/scraper-console
RUN corepack enable

COPY apps/scraper-console/package.json ./
COPY apps/scraper-console/package-lock.json* ./

# Fallback: if no package-lock.json, use npm install
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:22-alpine AS builder

WORKDIR /app/apps/scraper-console

ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_URL=https://scrapy.lute-tlz-dddd.top
ARG NEXT_PUBLIC_INSIGHT_URL=/insight
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_INSIGHT_URL=$NEXT_PUBLIC_INSIGHT_URL

COPY --from=deps /app/apps/scraper-console/node_modules ./node_modules
COPY apps/scraper-console ./

RUN npm run build

FROM node:22-alpine AS runner

WORKDIR /app

ENV HOSTNAME=0.0.0.0
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3001

RUN addgroup -S nextjs && adduser -S nextjs -G nextjs

COPY --from=builder --chown=nextjs:nextjs /app/apps/scraper-console/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/apps/scraper-console/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nextjs /app/apps/scraper-console/public ./public

USER nextjs

EXPOSE 3001

CMD ["node", "server.js"]
