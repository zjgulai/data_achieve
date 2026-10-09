---
name: scrapy-luteos-clean-rebuild
description: scrapy.luteos.com 生产实例全量重建运维手册，涵盖离线备份、旧实例销毁、空库部署、验收和回滚。当腾讯云主机上的同名 Compose 项目需要覆盖重建时使用。
---

# scrapy.luteos.com 全量重建

## 边界

- 仅操作 `/opt/data-achieve-scrapy` 和 Compose 项目 `data_achieve_scrapy`。
- 保留共享容器 `ai_video_nginx`、网络 `lighthouse_ai_video_net` 及其他项目。
- 旧 PostgreSQL 数据不恢复到新实例。

## 备份

```bash
stamp=$(date +%Y%m%dT%H%M%S)
backup=/opt/backups/data-achieve-scrapy/$stamp
sudo mkdir -p "$backup"
sudo chown ubuntu:ubuntu "$backup"
docker exec data_achieve_scrapy_db sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$backup/postgres.sql.gz"
docker run --rm -v data_achieve_scrapy_export_data:/source:ro -v "$backup":/backup alpine tar czf /backup/exports.tgz -C /source .
docker run --rm -v data_achieve_scrapy_browser_data:/source:ro -v "$backup":/backup alpine tar czf /backup/browser-data.tgz -C /source .
sudo cp /opt/data-achieve-scrapy/.env.production "$backup/env.production"
docker image inspect data_achieve_scrapy_api:latest data_achieve_scrapy_console:latest > "$backup/images.json"
```

## 销毁旧实例

```bash
cd /opt/data-achieve-scrapy/app
docker compose -f configs/deploy/scrapy/docker-compose.yml --env-file ../.env.production down --remove-orphans
docker volume rm data_achieve_scrapy_postgres_data data_achieve_scrapy_export_data data_achieve_scrapy_browser_data
docker network rm data_achieve_scrapy_internal 2>/dev/null || true
sudo rm -rf /opt/data-achieve-scrapy
```

不得删除 `lighthouse_ai_video_net`，不得重启 `ai_video_nginx`。

## 空库部署

```bash
sudo mkdir -p /opt/data-achieve-scrapy
sudo chown ubuntu:ubuntu /opt/data-achieve-scrapy
git clone --branch codex/social-api-private-matrix-20260708 https://github.com/zjgulai/data_achieve.git /opt/data-achieve-scrapy/app
install -m 600 /dev/null /opt/data-achieve-scrapy/.env.production
```

生产环境变量至少配置 `SCRAPY_POSTGRES_DB`、`SCRAPY_POSTGRES_USER`、`SCRAPY_POSTGRES_PASSWORD`、`SCRAPY_JWT_SECRET`、`SCRAPY_PUBLIC_URL=https://scrapy.luteos.com` 和所需 Provider Token。CDO、MCP、Cookie 与代理变量按实际启用能力配置。

```bash
cd /opt/data-achieve-scrapy/app
docker compose -f configs/deploy/scrapy/docker-compose.yml --env-file ../.env.production up --detach db
docker compose -f configs/deploy/scrapy/docker-compose.yml --env-file ../.env.production build api console spiderfoot
docker compose -f configs/deploy/scrapy/docker-compose.yml --env-file ../.env.production run --rm --no-deps api alembic upgrade head
docker compose -f configs/deploy/scrapy/docker-compose.yml --env-file ../.env.production up --detach
```

空库迁移后必须执行标准 demo seed，否则工作台项目接口和 quick-collect 会返回 `demo_workspace_unavailable`：

```bash
cd /opt/data-achieve-scrapy/app
set -a
source ../.env.production
set +a
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml \
  run --rm \
  -e SCRAPY_DEMO_EMAIL="$SCRAPY_DEMO_EMAIL" \
  -e SCRAPY_DEMO_PASSWORD="$SCRAPY_DEMO_PASSWORD" \
  api python -m data_intelligence_hub.seed.demo_data
```

共享 `ai_video_nginx` 必须把 `scrapy.luteos.com` 转发到同网络 upstream `data_achieve_scrapy`，不得继续指向旧 SSH 隧道。修改前备份 `/opt/ai-video/deploy/lighthouse/nginx.conf`，修改后只执行热重载：

```nginx
location / {
    proxy_pass http://data_achieve_scrapy;
}
```

```bash
docker exec ai_video_nginx nginx -t
docker exec ai_video_nginx nginx -s reload
```

## 验收

```bash
docker compose -f /opt/data-achieve-scrapy/app/configs/deploy/scrapy/docker-compose.yml --env-file /opt/data-achieve-scrapy/.env.production ps
curl -fsSL https://scrapy.luteos.com/api/health
curl -fsSL https://scrapy.luteos.com/api/platform-packages
curl -fsSL -X POST https://scrapy.luteos.com/api/agents/tiktok-cdo/webhook -H 'content-type: application/json' -d '{"type":"url_verification","challenge":"acceptance"}'
curl -fsSI https://scrapy.luteos.com/platforms
set -a && source /opt/data-achieve-scrapy/.env.production && set +a
BASE_URL=https://scrapy.luteos.com SCRAPY_DEMO_EMAIL="$SCRAPY_DEMO_EMAIL" SCRAPY_DEMO_PASSWORD="$SCRAPY_DEMO_PASSWORD" bash scripts/smoke-api-scrapy.sh
```

确认 `ai_video_nginx` 和其他 Compose 项目的启动时间未变化，且 `data_achieve_scrapy_edge` 已接入 `lighthouse_ai_video_net` 并持有别名 `data_achieve_scrapy_proxy`。

## 回滚

新实例失败时先执行 Compose `down --remove-orphans`，删除新建的三个 volumes，再从备份恢复旧源码、环境变量和 PostgreSQL dump。恢复后以备份记录的镜像摘要启动旧 Compose；共享 Nginx 路由无需修改。
