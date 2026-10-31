FROM node:22-alpine AS deps

# 生产 B 在国内，直连 npmjs ~220KB/s；允许构建时切换 registry，默认仍是官方源。
# NPM_CONFIG_REGISTRY 给 pnpm 用，COREPACK_NPM_REGISTRY 给 corepack 拉取 pnpm 本体用。
ARG NPM_CONFIG_REGISTRY=https://registry.npmjs.org/
ARG COREPACK_NPM_REGISTRY=https://registry.npmjs.org/
ENV NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY} \
    COREPACK_NPM_REGISTRY=${COREPACK_NPM_REGISTRY}

WORKDIR /app
RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json

RUN pnpm install --frozen-lockfile --filter data-intelligence-hub-web...

FROM node:22-alpine AS builder

# corepack 在 builder 阶段要再拉一次 pnpm 本体，这里同样需要镜像源。
ARG NPM_CONFIG_REGISTRY=https://registry.npmjs.org/
ARG COREPACK_NPM_REGISTRY=https://registry.npmjs.org/
ENV NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY} \
    COREPACK_NPM_REGISTRY=${COREPACK_NPM_REGISTRY}

WORKDIR /app
RUN corepack enable

ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_URL=https://scrapy.lute-tlz-dddd.top
ARG NEXT_PUBLIC_MOCK_API=false
# 部署子路径。生产挂在 https://scrapy.luteos.com/insight，构建期写成常量；
# 空值表示挂在站点根，行为与引入前一致。
ARG NEXT_PUBLIC_BASE_PATH=
# 跨应用入口：采集控制台在站点根。这个地址不参与 basePath 换算。
ARG NEXT_PUBLIC_CONSOLE_URL=/
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_MOCK_API=$NEXT_PUBLIC_MOCK_API
ENV NEXT_PUBLIC_BASE_PATH=$NEXT_PUBLIC_BASE_PATH
ENV NEXT_PUBLIC_CONSOLE_URL=$NEXT_PUBLIC_CONSOLE_URL

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY apps/web ./apps/web
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
# globals.css 用 ../../../../opendesign/... 引这份 token，路径落在 /app 根上。
# 之前没 COPY，构建在 tailwindcss 解析处报 Can't resolve（2026-10-11 首次在
# 生产 B 复现；本地构建因为在仓库根跑所以不报）。CSS 会被打进产物，runner 不需要。
COPY opendesign ./opendesign

RUN pnpm -C apps/web build

FROM node:22-alpine AS runner

WORKDIR /app

ENV HOSTNAME=0.0.0.0
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000

RUN addgroup -S nextjs && adduser -S nextjs -G nextjs

COPY --from=builder --chown=nextjs:nextjs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nextjs /app/apps/web/public ./apps/web/public

USER nextjs

EXPOSE 3000

CMD ["node", "apps/web/server.js"]
