# Data Intelligence Hub

Data Intelligence Hub 是一个以可追溯情报为核心的数据采集与分析平台。

核心链路：

```text
RawRecord -> EntitySnapshot -> Signal -> Intelligence -> Evidence -> Report / Alert
```

## 文档入口

- 产品 PRD：[docs/product/product-prd-data-intelligence-hub-stable.md](docs/product/product-prd-data-intelligence-hub-stable.md)
- 开发计划草案：[drafts/analysis/analysis-development-plan-data-intelligence-hub-draft-20260611.md](drafts/analysis/analysis-development-plan-data-intelligence-hub-draft-20260611.md)
- 本地开发流程：[docs/workflows/workflow-development-setup-stable.md](docs/workflows/workflow-development-setup-stable.md)

## 本地开发

当前 MVP 已覆盖：

- Auth / Workspace / Project
- Source / Task / RawRecord / Entity / Signal
- Intelligence / Evidence / Dashboard
- Report / AlertRule / AlertEvent / Notification
- Playwright E2E 主路径检查

复制环境变量样例：

```bash
cp .env.example .env
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
```

启动 PostgreSQL：

```bash
bash scripts/dev-start.sh
```

启动 PostgreSQL 并运行迁移：

```bash
bash scripts/dev-start.sh --migrate
```

如果 Docker daemon 未运行，脚本会在前置检查阶段失败；先启动 Docker Desktop 或本机 Docker 服务。

启动后端：

```bash
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn data_intelligence_hub.main:app --reload --host 0.0.0.0 --port 8000
```

启动前端：

```bash
cd apps/web
pnpm install
pnpm dev
```

默认端口：

| 服务 | 地址 |
|---|---|
| API | `http://localhost:8000` |
| OpenAPI | `http://localhost:8000/docs` |
| Web | `http://localhost:3000` |
| PostgreSQL | `localhost:5432` |

## 质量检查

一键检查：

```bash
bash scripts/verify-mvp.sh
```

包含 PostgreSQL 实库 migration：

```bash
bash scripts/verify-mvp.sh --with-db
```

重置本地数据库卷：

```bash
CONFIRM_RESET=1 bash scripts/dev-reset-db.sh --migrate
```

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
```
