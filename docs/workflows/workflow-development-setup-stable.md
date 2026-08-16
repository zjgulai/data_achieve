---
title: 本地开发环境搭建流程
doc_type: workflow
module: engineering
topic: development-setup
status: stable
created: 2026-06-11
updated: 2026-07-17
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
```

`pnpm test:e2e` 使用 `NEXT_PUBLIC_MOCK_API=true` 在 `3100` 端口启动独立 Next.js dev server，覆盖 Dashboard、Intelligence、Reports、Alerts、Notifications 主路径和移动端横向溢出检查。

`pnpm test:e2e:real` 仅是 Owner-run 工具，不属于当前 V2 CI/release gate。执行前必须获得目标环境、测试范围、预算、保留、cleanup 和 recount 的明确授权，并显式设置 `PLAYWRIGHT_BASE_URL`；不得把 package script 的历史默认 URL 视为授权。必须使用一次性 E2E 用户，不使用 demo 账号，并在执行后按精确 ID 清理与复核。

### Workflow lineage materialization connection-free gate

Revision `202607170034` 的默认本地检查不得设置任何
`WORKFLOW_LINEAGE_*` 授权变量：

```bash
cd apps/api
env -u DATABASE_URL \
  -u WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED \
  -u WORKFLOW_LINEAGE_TEST_DATABASE_URL \
  -u WORKFLOW_LINEAGE_AUTHORIZED_TARGET \
  uv run pytest -q \
    tests/unit/test_workflow_lineage_postgres_guard.py \
    tests/postgres_workflow_lineage
```

预期 PostgreSQL cases 全部 skip；这只证明 source/guard，不是 migration
acceptance。只有用户重新明确授权具体 localhost host、port、database、
create/rebuild 和 `033→034→033→034` 后，才能设置三项独立变量并运行：

```bash
bash scripts/verify-workflow-lineage-migration.sh
```

非 `--check-only` 路径在精确 URL 校验后运行 suite，并在成功、失败或信号退出时
重建同一个授权目标到 head `202607170034`，复核 Dataset/RawRecord/WorkflowRun/
StepRun/materialization ledger 均为 0。不得复用历史 revision-033 授权，也不得把
本 guard 指向共享或生产数据库。

2026-07-17 Task 13 已仅在明确授权的
`127.0.0.1:55367/local_workflow_lineage_test` 执行：guarded
`033→034→033→034`、constraint/rollback/ledger/service-concurrency suite
`13/13` 通过；cleanup 与独立 recount 均为 head `202607170034`，Dataset、
DatasetVersion、RawRecord、WorkflowRun、StepRun 和 materialization ledger
全部 0 行。该授权已消费，不得复用于 Provider、共享/生产数据库或后续迁移。

### YouTube disabled Adapter connection-free gate

该 foundation 不要求 Google SDK、credential、network、PostgreSQL 或 migration：

```bash
cd apps/api
uv run pytest -q \
  tests/unit/test_youtube_read_adapter_foundation.py \
  tests/unit/test_social_provider_runtime.py \
  tests/integration/test_social_provider_routes.py
```

预期只回放包内 Manifest 注册的 YouTube fixture。测试或本地调用不得设置/读取
YouTube API key，不得把 `foundation_ready` 或 `declared_readiness` 解释为
`provider_call_allowed=true`。任何真实 Google request、credential resolution、SDK
安装、WorkflowRun/RawRecord/Dataset 写入均需要新的独立授权与实施计划。

## 7. 远端 CI

`.github/workflows/ci.yml` 在 push / pull request 到 `main` 时运行，也保留不带真实环境输入的普通 `workflow_dispatch`。

API job：

```bash
python3 scripts/verify-ci-no-unscoped-real-e2e.py
cd apps/api
uv sync --locked --dev
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run alembic heads
```

Workflow Planner PostgreSQL 15 job 使用 GitHub service database，并执行：

```bash
bash scripts/verify-workflow-planner-phase2-migration.sh
```

该 job 只验证受保护的一次性 CI database，不是共享或生产 migration 证据。

Web job：

```bash
pnpm install --frozen-lockfile
pnpm -C apps/web lint
pnpm -C apps/web test
pnpm -C apps/web build
pnpm -C apps/web exec playwright install --with-deps chromium
pnpm -C apps/web test:e2e
```

当前 `workflow_dispatch` 只重复运行普通 API、PostgreSQL 15 与 Web mock/static jobs；它没有 `base_url` 输入，不注册真实用户，不创建真实 Project，也不执行 `test:e2e:real`。未来真实 API CI 属于 GOAL-V2-07，必须先具备命名定向测试、一次性身份、创建 ID 账本、`always()` cleanup、recount 与产物保留合同。

真实 API E2E 后清理 fixture：

```bash
SCRAPY_CLEANUP_USE_DOCKER=1 bash scripts/cleanup-e2e-fixtures.sh
SCRAPY_CLEANUP_USE_DOCKER=1 bash scripts/cleanup-e2e-fixtures.sh --execute
```

CI 的 PostgreSQL job 使用一次性 service database；它不替代本地 Docker 全栈验证，也不执行共享或生产 migration。交付前如需本地全栈验证，仍需在 Docker daemon 可用后运行：

```bash
bash scripts/dev-start.sh --migrate
```
