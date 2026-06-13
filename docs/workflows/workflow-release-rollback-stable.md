---
title: 发布与回滚清单
doc_type: workflow
module: operations
topic: release-rollback
status: stable
created: 2026-06-14
updated: 2026-06-14
owner: self
source: human+ai
---

# 发布与回滚清单

## 适用范围

本文适用于 `https://scrapy.lute-tlz-dddd.top` 的生产发布。服务器路径固定为：

```text
/opt/data-achieve-scrapy/app
```

生产 env 文件固定为：

```text
/opt/data-achieve-scrapy/.env.production
```

不得把生产 env 内容写入仓库、日志或对话输出。

## 发布前检查

本地必须通过：

```bash
bash scripts/verify-mvp.sh
```

后端分项：

```bash
cd apps/api
uv run ruff check .
uv run mypy src tests
uv run pytest
```

前端分项：

```bash
pnpm -C apps/web lint
pnpm -C apps/web test
pnpm -C apps/web build
```

生产 preflight：

```bash
ssh -i /Users/pray/project/data_scrapy/ai_video.pem ubuntu@101.34.52.232 \
  'cd /opt/data-achieve-scrapy/app && \
   bash scripts/deploy-preflight-scrapy.sh \
     --env-file /opt/data-achieve-scrapy/.env.production \
     --compose-file configs/deploy/scrapy/docker-compose.yml'
```

## 发布步骤

1. 确认 git 工作区只包含本次发布相关改动。
2. 本地提交并 push 到 `origin/main`。
3. 同步代码到服务器 `/opt/data-achieve-scrapy/app`。
4. 在服务器运行 compose config 或 preflight。
5. 构建镜像。
6. 启动服务。
7. 执行 Alembic 迁移。
8. 必要时执行 demo seed。
9. 运行 API smoke。
10. 运行生产真实 API E2E。
11. 检查容器健康。

生产 compose 命令必须显式加载 env：

```bash
cd /opt/data-achieve-scrapy/app
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml build
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml up -d
```

迁移：

```bash
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml \
  run --rm api alembic upgrade head
```

demo seed：

```bash
set -a
source ../.env.production
set +a
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml \
  run --rm \
  -e SCRAPY_DEMO_EMAIL="$SCRAPY_DEMO_EMAIL" \
  -e SCRAPY_DEMO_PASSWORD="$SCRAPY_DEMO_PASSWORD" \
  api python -m data_intelligence_hub.seed.demo_data
```

API smoke：

```bash
set -a
source ../.env.production
set +a
BASE_URL=https://scrapy.lute-tlz-dddd.top \
SCRAPY_DEMO_EMAIL="${SCRAPY_DEMO_EMAIL:-owner@example.com}" \
SCRAPY_DEMO_PASSWORD="$SCRAPY_DEMO_PASSWORD" \
bash scripts/smoke-api-scrapy.sh
```

## 验收标准

发布完成必须满足：

1. `curl -ks https://scrapy.lute-tlz-dddd.top/api/health` 返回 `status=ok`。
2. `docker compose ps` 显示 api、db、edge、web healthy。
3. 主要页面返回 200：`/dashboard`、`/intelligence`、`/reports`、`/tasks`、`/sources`、`/alerts`、`/notifications`、`/projects`、`/signals`、`/raw-records`、`/entities`。
4. 演示账号数据域覆盖 `competitor`、`ecommerce`、`osint`、`social`。
5. 最新高价值情报不是 placeholder，至少包含开源、 电商、社媒、竞品四类。
6. 生产真实 API E2E 通过。

## 回滚触发条件

出现任一情况必须回滚或停止发布：

1. API health 非 200。
2. 数据库迁移失败。
3. seed 失败且影响 demo 账号登录或主要页面数据。
4. 生产 E2E 主流程失败。
5. 其他站点被网关配置影响。
6. 容器反复重启或 healthcheck 持续 unhealthy。

## 回滚步骤

代码回滚：

```bash
cd /opt/data-achieve-scrapy/app
git log --oneline -5
git revert <bad_commit>
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml build
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml up -d
```

如果服务器目录不是 git 工作区，使用上一版 rsync 备份目录恢复，再重建容器。

数据库回滚：

1. 优先使用 Alembic downgrade。
2. 没有 downgrade 时，停止发布并保留现场。
3. 不直接删除 PostgreSQL volume。
4. 不在未备份情况下执行破坏性 SQL。

网关回滚：

1. 先恢复项目 edge compose。
2. 如果宿主机 nginx 被影响，恢复发布前备份。
3. 执行 `nginx -t`。
4. reload nginx。

## 发布记录要求

每次发布必须记录：

1. git commit。
2. 本地 gate 结果。
3. 生产 API health 结果。
4. 生产 E2E 结果。
5. seed 是否执行。
6. 是否触发回滚。
7. 遗留问题。
