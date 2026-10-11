---
name: production-acceptance
description: "生产环境上线后的验收检查。Use when 部署完成需要验收、发布后要核对两套环境、或需要隔离性与防串台证据时。涵盖容器与 schema、公网 smoke、业务 smoke、烧录域名复核、隔离性核对与验收记录格式。"
---

# 生产验收

## 适用场景

- 部署完成后验收。
- 发布后核对两套环境的一致性。
- 留下隔离性与防串台的验证证据。

## 适用对象

| 项 | 生产 A | 生产 B |
|---|---|---|
| 域名 | `https://scrapy.luteos.com` | `https://scrapy.lute-tlz-dddd.top` |
| 分支 | `main` | `deploy/tiktok-cdo-codex` |

## 步骤

### 1. 容器与 schema

```bash
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml ps

docker exec data_achieve_scrapy_db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select version_num from alembic_version"'
```

期望：9 个服务全部 healthy。schema 等于仓库的 `alembic heads`。

### 2. 公网 smoke

```bash
curl -fsSL <域名>/api/health          # ok / connected / current
curl -fsSL <域名>/api/platform-packages   # 70 / 270 / 242
curl -fsSI <域名>/platforms               # 200
curl -sS -L -o /dev/null -w '%{http_code}\n' <域名>/mcp   # 401
```

### 3. 业务 smoke

```bash
set -a; source /opt/data-achieve-scrapy/.env.production; set +a
BASE_URL=<域名> bash scripts/smoke-api-scrapy.sh
```

期望输出：`API smoke passed`。

### 4. 烧录域名复核（防串台）

console 与 web 的产物只应出现本机域名：

```bash
docker exec data_achieve_scrapy_console sh -c \
  "grep -rhoE 'https://scrapy\.[a-z0-9.-]+' /app/.next/static | sort -u"
docker exec data_achieve_scrapy_web sh -c \
  "grep -rhoE 'https://scrapy\.[a-z0-9.-]+' /app/apps/web/.next/static | sort -u"
```

出现另一台的域名即串台。按 `docs/knowledge/生产变更的隔离与串台防线.md` 处理。

### 5. 隔离性核对（仅共享宿主机的变更）

取变更前的快照，对比现在。

```bash
diff <(grep -v data_achieve_scrapy <快照文件> | cut -f1) \
     <(docker ps --format '{{.Names}}' | grep -v data_achieve_scrapy | sort)

docker inspect ai_video_nginx --format '{{.State.StartedAt}} {{.RestartCount}}'
```

通过标准：

1. 非 DIH 容器名集合零差异。
2. `ai_video_nginx` 的 StartedAt 与 RestartCount 与变更前逐位相同。

两侧格式必须先对齐。见知识库文档的假阳性坑点。

### 6. 保存证据

把两份快照存入备份目录：

```bash
/opt/backups/data-achieve-scrapy/<时间戳>/containers-after.txt
/opt/backups/data-achieve-scrapy/<时间戳>/nginx-after.txt
```

## 验收记录格式

每次验收输出一张表：

| 检查项 | 生产 A | 生产 B |
|---|---|---|
| health | status / database / revision | 同 |
| 平台包 | 70 / 270 / 242 | 同 |
| /platforms | 200 | 200 |
| /mcp | 401 | 401 |
| 业务 smoke | 通过 | 通过 |
| 烧录域名 | 本机域名 | 本机域名 |
| 隔离性 | — | 零差异 |

## 坑点

1. 业务 smoke 需要 `.env.production` 里的 demo 账号。先 source 再运行。
2. `grep -c` 计数为 0 时退出码是 1。多条命令用 `;` 分隔，不要用 `&&`。
3. CDO webhook 的存活检查是 GET 返回 405（路由存在）。404 才是路由缺失。
4. 验收失败时按 `docs/workflows/workflow-release-rollback-stable.md` 的回滚条件处理。
