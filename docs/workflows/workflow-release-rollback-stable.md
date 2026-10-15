---
name: production-release-rollback
description: Data Intelligence Hub 生产发布与回滚操作清单，涵盖预检、备份、构建、迁移、demo seed、共享网关、验收和恢复。当向 scrapy.luteos.com 发布或处理发布故障时使用。
---

# 发布与回滚清单

## 适用范围

本文适用于两套生产环境的日常发布和回滚。

| 项目 | 生产 A | 生产 B |
|---|---|---|
| 主机 | `ubuntu@43.163.92.244` | `ubuntu@101.34.52.232` |
| 项目路径 | `/opt/data-achieve-scrapy/app` | 同左 |
| 环境变量 | `/opt/data-achieve-scrapy/.env.production` | 同左 |
| 部署分支 | `main` | `deploy/tiktok-cdo-codex` |
| Compose | `configs/deploy/scrapy/docker-compose.yml` | 同左 |
| 共享网关 | `ai_video_nginx` | 同左 |

生产拓扑和能力数量以 [生产环境基线](../【运维手册】生产环境基线.md) 为准。全量销毁重建使用 [scrapy.luteos.com 全量重建](【运维手册】scrapy-luteos全量重建.md)。

不得把 `.env.production`、Token、Cookie、SSH key 或 TLS 私钥写入仓库、日志和对话输出。

## 发布类型

### Console-only

只修改 `apps/scraper-console` 时，仅构建并替换 Console。不得重启 API、DB 或共享网关容器。

### API-only

只修改 API 代码且无 migration 时，构建 API 并替换 API。完成后检查 scheduler、MCP 和采集器健康。

### 完整应用发布

涉及 migration、Compose、bridge、API 与 Console 协同变更时，按完整流程执行。

## 发布前检查

### Git

```bash
git status --short --branch
git diff --check
git log --oneline -10
```

只发布已推送至生产分支的 commit。生产主机使用 `git pull --ff-only`，不得在生产工作区直接开发或提交。

### 本地质量门禁

后端按变更范围运行：

```bash
cd apps/api
uv run ruff check <changed-paths>
uv run mypy <changed-paths>
uv run pytest <focused-tests>
uv run alembic heads
```

Console：

```bash
pnpm --dir apps/scraper-console test
pnpm --dir apps/scraper-console exec tsc --noEmit
pnpm --dir apps/scraper-console lint
pnpm --dir apps/scraper-console build
```

项目完整测试可能包含历史夹具或专用 PostgreSQL 环境要求。若存在基线失败，发布记录必须区分“本次新增范围通过”和“既有基线失败”，不得删除或弱化失败测试。

### 生产 preflight

```bash
ssh -i zhoujian_pachong.pem ubuntu@43.163.92.244
cd /opt/data-achieve-scrapy/app

bash scripts/deploy-preflight-scrapy.sh \
  --env-file /opt/data-achieve-scrapy/.env.production \
  --compose-file configs/deploy/scrapy/docker-compose.yml \
  --base-url https://scrapy.luteos.com
```

## 备份

涉及数据库、Compose、网关或破坏性操作时，发布前至少备份：

1. PostgreSQL dump。
2. `/opt/data-achieve-scrapy/.env.production`。
3. Export 和 browser data volumes。
4. 当前源码和 Git revision。
5. 当前镜像 ID。
6. `/opt/ai-video/deploy/lighthouse/nginx.conf`。

备份目录建议使用：

```text
/opt/backups/data-achieve-scrapy/<YYYYMMDDTHHMMSS>
```

Console-only 且不修改网关时，可以只记录当前 Console 镜像 ID、revision 和容器启动时间。

## 标准发布

### 1. 同步源码

```bash
ssh -i <密钥> ubuntu@<主机>
cd /opt/data-achieve-scrapy/app

# fetch 带重试参数。生产 B 到 GitHub 常抖动。
ok=0
for i in 1 2 3 4 5; do
  out=$(git -c http.version=HTTP/1.1 -c http.lowSpeedLimit=1000 \
        -c http.lowSpeedTime=20 fetch origin <部署分支> 2>&1); rc=$?
  [ $rc = 0 ] && ok=1 && break
  echo "第 $i 次失败: $(echo "$out" | tail -1)"; sleep 4
done

git merge --ff-only FETCH_HEAD
git status --short --branch
git log -1 --oneline
```

必须用 `merge --ff-only`。不要用 `reset --hard`。工作区不干净时 ff-only 会拒绝，这是期望行为。fetch 重试全部失败时用 bundle 兜底。完整步骤见 `.claude/skills/production/production-sync-revision/`。

### 2. Compose 校验

```bash
docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  config --quiet
```

### 3. 构建镜像

完整构建：

```bash
docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  build api console spiderfoot
```

Console-only：

```bash
docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  build console
```

### 4. 数据库迁移

存在 migration 或新建空库时：

```bash
docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  up --detach db

docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  run --rm --no-deps api alembic upgrade head

docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  run --rm --no-deps api alembic current
```

### 5. 启动服务

完整应用：

```bash
docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  up --detach
```

Console-only：

```bash
docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  up --detach --no-deps console
```

API-only：

```bash
docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  up --detach --no-deps api
```

`proxy_rotator` 默认不启动；仅在已配置有效代理列表并明确需要时使用 `--profile proxy`。

### 6. Demo seed

新建空库或 demo workspace 缺失时执行：

```bash
set -a
source ../.env.production
set +a

docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  run --rm \
  -e SCRAPY_DEMO_EMAIL="$SCRAPY_DEMO_EMAIL" \
  -e SCRAPY_DEMO_PASSWORD="$SCRAPY_DEMO_PASSWORD" \
  api python -m data_intelligence_hub.seed.demo_data
```

Seed 是幂等操作。未执行 seed 时，项目、Dashboard 和 quick-collect 可能返回 `demo_workspace_unavailable`。

### 7. 共享网关

重建 edge 后执行：

```bash
bash scripts/reload-scrapy-gateway.sh --dry-run
bash scripts/reload-scrapy-gateway.sh
```

脚本检查：

- `data_achieve_scrapy_edge` healthy。
- `ai_video_nginx` 可解析 `data_achieve_scrapy_proxy`。
- 共享 Nginx 配置有效。
- 内部和公网 health 可访问。

共享 Nginx 的 `scrapy.luteos.com` 必须代理到 `http://data_achieve_scrapy`，不得恢复旧 SSH 隧道地址。

## 验收

### 容器和 schema

```bash
docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  ps

docker exec data_achieve_scrapy_db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select version_num from alembic_version"'
```

核心服务必须 healthy。当前 schema 期望值见 [生产环境基线](../【运维手册】生产环境基线.md)。

### 公网 smoke

```bash
curl -fsSL https://scrapy.luteos.com/api/health
curl -fsSL https://scrapy.luteos.com/api/platform-packages
curl -fsSL https://scrapy.luteos.com/api/collectors/catalog
curl -fsSI https://scrapy.luteos.com/platforms
curl -sS -L -o /dev/null -w '%{http_code}\n' https://scrapy.luteos.com/mcp
```

期望：

- health 为 `ok / connected / current`。
- 平台包为 `70 / 286 / 258`（2026-10-15 起；此前是 `70 / 270 / 242`）。
- 实测状态见 `/api/platform-packages/providers/status`（`availability` 字段）。
- `/platforms` 返回 `200`。
- 未授权 `/mcp/` 返回 `401`。

### 登录与业务 smoke

```bash
set -a
source /opt/data-achieve-scrapy/.env.production
set +a

BASE_URL=https://scrapy.luteos.com \
SCRAPY_DEMO_EMAIL="$SCRAPY_DEMO_EMAIL" \
SCRAPY_DEMO_PASSWORD="$SCRAPY_DEMO_PASSWORD" \
bash scripts/smoke-api-scrapy.sh
```

### 前端烧录复核

console 与 web 的产物只应出现本机域名：

```bash
docker exec data_achieve_scrapy_console sh -c \
  "grep -rhoE 'https://scrapy\.[a-z0-9.-]+' /app/.next/static | sort -u"
docker exec data_achieve_scrapy_web sh -c \
  "grep -rhoE 'https://scrapy\.[a-z0-9.-]+' /app/apps/web/.next/static | sort -u"
```

出现另一台机器的域名即为串台。必须修源码并重建镜像。

### 隔离性核对

共享宿主机的变更必须核对两项：

1. 非 DIH 容器名集合零差异。
2. `ai_video_nginx` 的 StartedAt 与 RestartCount 与变更前相同。

命令与证据要求见 [生产变更的隔离与串台防线](../knowledge/生产变更的隔离与串台防线.md) 与 `.claude/skills/production/production-acceptance/`。

### 真实采集

只有在已确认 Provider 凭据、预算和目标参数时运行。记录创建的 `task_run_id`、状态、记录数和清理策略。UI 必须将后端 `success` 状态显示为成功，不得误报“未知错误”。

### 命令验收

```bash
curl -fsSL https://scrapy.luteos.com/api/health
docker compose -f configs/deploy/scrapy/docker-compose.yml ps
bash scripts/reload-scrapy-gateway.sh --dry-run
```

- health 为 `ok / connected / current`。
- api、db、edge、console 全部 healthy。
- 外层网关能解析 `data_achieve_scrapy_proxy`。

### 浏览器验收


至少验证：

- `/platforms`
- `/skills`
- `/dashboard`
- `/runs`

覆盖桌面端和移动端，检查控制台错误、API 失败、横向溢出和 CJK 文本裁切。

## 回滚条件

出现以下情况停止发布或回滚：

1. API health 非 200。
2. schema 不在 head。
3. demo seed 失败且影响主要接口。
4. 核心容器 unhealthy 或反复重启。
5. 公网网关无法访问新 edge。
6. 其他 Compose 项目的容器被重启、删除或网络改变。
7. 关键业务 smoke 或已授权真实采集失败。

## 回滚步骤

### Console-only

恢复上一版 Console 镜像或 checkout 上一 commit 后重新构建，只替换 Console：

```bash
docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  up --detach --no-deps console
```

### 应用代码

```bash
git log --oneline -10
git revert <bad-commit>
git push origin main        # 生产 B 用 deploy/tiktok-cdo-codex
```

生产拉取 revert commit 后重建受影响服务。不得在生产分支 force-push。

### 数据库

优先使用已验证的 Alembic downgrade。没有可靠 downgrade 时停止自动操作、保留现场并从备份恢复。不得在未备份情况下删除 PostgreSQL volume 或执行破坏性 SQL。

### 共享网关

恢复发布前的 `/opt/ai-video/deploy/lighthouse/nginx.conf` 备份，然后：

```bash
docker exec ai_video_nginx nginx -t
docker exec ai_video_nginx nginx -s reload
```

不得重启或重建共享 `ai_video_nginx`，除非其自身发布流程明确要求。

## 发布记录

每次发布记录：

1. 发布 commit。
2. 受影响服务。
3. 本地测试、类型检查和构建结果。
4. 基线测试失败及其是否与本次相关。
5. 生产 schema 和容器状态。
6. Demo seed 是否执行。
7. API、浏览器和真实采集验收结果。
8. 备份路径与回滚准备。
9. 未解决问题。
