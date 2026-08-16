---
title: 发布与回滚清单
doc_type: workflow
module: operations
topic: release-rollback
status: stable
created: 2026-06-14
updated: 2026-08-15
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

## V2 真实 API 验收边界（2026-07-14）

当前 CI 已移除通用 `web-real-e2e` job 和真实环境 `base_url` 输入。普通 CI、一次性 PostgreSQL 15 gate 与 mock E2E 不等于生产验收。发布流程中的真实 API E2E 只能在 Owner 对目标环境、命名测试、预算、保留、精确 cleanup/recount 和回滚作出单独授权后执行；GOAL-V2-07 建立该闭环前，不得用 generic CI 结果关闭 V2 release gate。

## 生产环境变量要求（2026-08-15）

`/opt/data-achieve-scrapy/.env.production` 必须包含以下键，否则 API 容器内 TikHub/Apify 采集调用将静默返回空结果：

```
TIKHUB_API_KEY=<值>
APIFY_API_TOKEN=<值>
```

写入方式（幂等，从运行中容器读取）：

```bash
TIKHUB=$(docker inspect data_achieve_scrapy_api \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | grep TIKHUB_API_KEY | cut -d= -f2-)
APIFY=$(docker inspect data_achieve_scrapy_api \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | grep APIFY_API_TOKEN | cut -d= -f2-)
sed -i '/^TIKHUB_API_KEY/d;/^APIFY_API_TOKEN/d' /opt/data-achieve-scrapy/.env.production
echo "TIKHUB_API_KEY=${TIKHUB}" >> /opt/data-achieve-scrapy/.env.production
echo "APIFY_API_TOKEN=${APIFY}" >> /opt/data-achieve-scrapy/.env.production
```

## 热更新注意事项（⚠️ 临时措施，非标准流程）

当 Docker build 因依赖下载超时时，可用以下方式热替换代码文件：

```bash
# 仅用于紧急修复 Python 路由/逻辑文件，不涉及依赖变更
docker cp <本地文件路径> data_achieve_scrapy_api:/app/src/data_intelligence_hub/...
docker restart data_achieve_scrapy_api
```

**风险**：热更新只改变运行中容器的文件系统，不改变镜像。下次任何触发容器重建的操作（`up --build`、服务器重启、手动 `docker rm` 后重建）都会回退到旧镜像中的代码。

**必须跟进**：热更新后，下一次正式部署必须完整执行 `--no-cache build`，确保镜像与代码一致。当前服务器镜像 `71f098dd57c4` 仍为旧版本，**下次部署必须重建**。

验证镜像与容器代码是否一致：

```bash
# 若容器内行数与仓库不同，说明是热更新状态
docker exec data_achieve_scrapy_api wc -l /app/src/data_intelligence_hub/api/routes/collectors.py
wc -l apps/api/src/data_intelligence_hub/api/routes/collectors.py
# 两者应相同（目前正确值：1264 行）
```

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
ssh -i ~/.ssh/data_scrapy_ai_video.pem ubuntu@101.34.52.232 \
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
6. 启动数据库。
7. 执行 Alembic 迁移。
8. 必要时执行 demo seed。
9. 启动 API/Web/Edge 后刷新外层共享网关。
10. 运行 API smoke。
11. 如已取得独立精确授权，运行命名定向生产真实 API E2E，并执行精确 cleanup/recount；否则停止在生产验收门前。
12. 检查容器健康。

生产 compose 命令必须显式加载 env：

```bash
cd /opt/data-achieve-scrapy/app
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml build
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml up -d db
```

迁移：

```bash
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml \
  run --rm api alembic upgrade head
```

启动 API/Web/Edge：

```bash
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml up -d api web edge
```

刷新外层共享网关：

```bash
bash scripts/reload-scrapy-gateway.sh
```

说明：`data_achieve_scrapy_edge` 重建后，外层 `ai_video_nginx` 可能继续使用旧的 Docker DNS 解析结果，公网会短暂返回 502。该脚本会先确认 edge healthy、`data_achieve_scrapy_proxy` 可解析、外层 Nginx 配置有效，再 reload 外层网关并执行内部与公网 health smoke。只读预检可使用：

```bash
bash scripts/reload-scrapy-gateway.sh --dry-run
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

1. `curl -ks https://scrapy.lute-tlz-dddd.top/api/health` 返回 `status=ok`、`database=connected`、`schema=current`。
2. `docker compose ps` 显示 api、db、edge、web、console 全部 healthy。
3. `bash scripts/reload-scrapy-gateway.sh --dry-run` 通过，外层网关可解析 `data_achieve_scrapy_proxy`。
4. Collector catalog 验收：`curl -fsSL https://scrapy.lute-tlz-dddd.top/api/collectors/catalog` 返回 `verified=91, pending=0`。
5. 主要页面返回 200：`/dashboard`、`/intelligence`、`/reports`、`/tasks`、`/sources`、`/alerts`、`/notifications`、`/projects`、`/signals`、`/raw-records`、`/entities`；Console `/platforms` 返回 200。
6. 演示账号数据域覆盖 `competitor`、`ecommerce`、`osint`、`social`。
7. 最新高价值情报不是 placeholder，至少包含开源、 电商、社媒、竞品四类。
8. 已授权的命名定向生产真实 API E2E 通过，且创建 ID、cleanup、recount 和保留策略证据完整。

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
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml up -d db
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml \
  run --rm api alembic upgrade head
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml up -d api web edge
```

如果服务器目录不是 git 工作区，使用上一版 rsync 备份目录恢复，再重建容器。

数据库回滚：

1. 优先使用 Alembic downgrade。
2. 没有 downgrade 时，停止发布并保留现场。
3. 不直接删除 PostgreSQL volume。
4. 不在未备份情况下执行破坏性 SQL。

Revision `202607170034` 额外规则：其 downgrade 在
`workflow_lineage_materialization_requests` 非空时主动拒绝。Exact disposable
PostgreSQL acceptance 已通过 guarded `033→034→033→034`、rollback/concurrency
`13/13` 和最终 cleanup；这仍不是发布或生产迁移授权。生产回滚若
存在 materialization ledger，必须停止自动 downgrade、保留现场并按 Dataset/
DatasetVersion/RawRecord/ledger lineage 制定显式数据恢复方案，禁止直接删表绕过。

网关回滚：

1. 先恢复项目 edge compose。
2. 执行 `bash scripts/reload-scrapy-gateway.sh --dry-run`，确认外层网关可解析当前 edge。
3. 如果宿主机 nginx 被影响，恢复发布前备份。
4. 执行 `nginx -t`。
5. reload nginx。

## 发布记录要求

每次发布必须记录：

1. git commit。
2. 本地 gate 结果。
3. 生产 API health 结果。
4. 生产 E2E 结果。
5. seed 是否执行。
6. 是否触发回滚。
7. 遗留问题。
