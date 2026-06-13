---
title: 本地开发环境搭建流程
doc_type: workflow
module: engineering
topic: development-setup
status: stable
created: 2026-06-11
updated: 2026-06-12
owner: self
source: human+ai
---

# 本地开发环境搭建流程

## 1. 前置工具

| 工具 | 用途 |
|---|---|
| `uv` | Python 包管理和虚拟环境 |
| `pnpm` | 前端包管理 |
| Docker | PostgreSQL 本地服务 |
| Node.js 22+ | Next.js 开发运行时 |
| Playwright browsers | 前端 E2E 浏览器运行时 |

## 2. 环境变量

从样例复制本地环境文件：

```bash
cp .env.example .env
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
```

本地 `.env`、`apps/api/.env`、`apps/web/.env.local` 不提交。

## 3. 数据库

启动 PostgreSQL：

```bash
bash scripts/dev-start.sh
```

启动 PostgreSQL 并运行迁移：

```bash
bash scripts/dev-start.sh --migrate
```

如果该命令返回 Docker daemon 不可用，先启动 Docker Desktop 或本机 Docker 服务，再继续 migration。

运行迁移：

```bash
cd apps/api
uv run alembic upgrade head
```

回滚最近一条迁移：

```bash
cd apps/api
uv run alembic downgrade -1
```

重置本地数据库卷：

```bash
CONFIRM_RESET=1 bash scripts/dev-reset-db.sh --migrate
```

`scripts/dev-reset-db.sh` 默认拒绝执行，必须显式设置 `CONFIRM_RESET=1`。

## 4. 后端

安装依赖：

```bash
cd apps/api
uv sync
```

启动 API：

```bash
uv run uvicorn data_intelligence_hub.main:app --reload --host 0.0.0.0 --port 8000
```

检查：

- `GET http://localhost:8000/health`
- `http://localhost:8000/docs`

## 5. 前端

安装依赖：

```bash
cd apps/web
pnpm install
```

启动 Web：

```bash
pnpm dev
```

访问：

- `http://localhost:3000/login`
- `http://localhost:3000/dashboard`

## 6. 质量检查

一键执行当前 MVP 质量门：

```bash
bash scripts/verify-mvp.sh
```

如需把 PostgreSQL migration 纳入检查：

```bash
bash scripts/verify-mvp.sh --with-db
```

`--with-db` 会先检查 Docker daemon，再启动 `db` 服务并执行 `uv run alembic upgrade head`。

后端：

```bash
cd apps/api
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run alembic heads
```

前端：

```bash
cd apps/web
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
SCRAPY_DEMO_PASSWORD=... pnpm test:e2e:real
```

`pnpm test:e2e` 使用 `NEXT_PUBLIC_MOCK_API=true` 在 `3100` 端口启动独立 Next.js dev server，覆盖 Dashboard、Intelligence、Reports、Alerts、Notifications 主路径和移动端横向溢出检查。

`pnpm test:e2e:real` 使用 `PLAYWRIGHT_BASE_URL`（默认 `https://scrapy.lute-tlz-dddd.top`）和 `PLAYWRIGHT_REAL_API=true`，执行同一套 E2E 场景但走真实 API。至少需要设置 `SCRAPY_DEMO_PASSWORD`（例如：`SCRAPY_DEMO_PASSWORD=... pnpm test:e2e:real`）。

## 7. 远端 CI

`.github/workflows/ci.yml` 在 push / pull request 到 `main` 时运行。

API job：

```bash
cd apps/api
uv sync --locked --dev
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run alembic heads
```

Web job：

```bash
pnpm install --frozen-lockfile
pnpm -C apps/web lint
pnpm -C apps/web test
pnpm -C apps/web build
pnpm -C apps/web exec playwright install --with-deps chromium
pnpm -C apps/web test:e2e
```

可选（手动部署验收）：触发 `.github/workflows/ci.yml` 的 `workflow_dispatch`，并可传入 `base_url`（默认 `https://scrapy.lute-tlz-dddd.top`）。GitHub Secrets 需配置 `SCRAPY_DEMO_PASSWORD`（可选 `SCRAPY_DEMO_EMAIL`），执行 `apps/web test:e2e:real` 完成真实 API 回归。

CI 不启动 Docker，不执行 PostgreSQL 实库 migration。交付前仍需在 Docker daemon 可用后运行：

```bash
bash scripts/dev-start.sh --migrate
```
