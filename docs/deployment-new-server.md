---
name: tencent-production-deployment
description: Data Intelligence Hub 腾讯云生产部署说明，涵盖主机准备、代码、环境变量、空库迁移、共享网关和验收。当新建或恢复当前生产实例时使用。
---

# 腾讯云生产部署

本文描述当前生产环境 `43.163.92.244` 的安装与恢复流程。日常增量发布优先使用 [发布与回滚清单](workflows/workflow-release-rollback-stable.md)；破坏性全量重建使用 [scrapy.luteos.com 全量重建](workflows/【运维手册】scrapy-luteos全量重建.md)。

## 生产边界

| 项目 | 当前值 |
|---|---|
| 公网 IP | `43.163.92.244` |
| SSH 用户 | `ubuntu` |
| 项目路径 | `/opt/data-achieve-scrapy/app` |
| 环境变量 | `/opt/data-achieve-scrapy/.env.production` |
| 生产域名 | `https://scrapy.luteos.com` |
| Compose | `configs/deploy/scrapy/docker-compose.yml` |
| Compose 项目 | `data_achieve_scrapy` |
| 共享网关 | `ai_video_nginx` |

最新能力数量和容器清单以 [生产环境基线](【运维手册】生产环境基线.md) 为准。

## 前置条件

- Ubuntu 主机已安装 Docker Engine 和 Docker Compose v2。
- `ubuntu` 用户可执行 Docker 命令。
- 外部网络 `lighthouse_ai_video_net` 已存在。
- 共享 `ai_video_nginx` 已连接该网络。
- GitHub 仓库和生产分支可访问。
- 生产 secrets 已准备，但未写入仓库。

检查：

```bash
docker version
docker compose version
docker network inspect lighthouse_ai_video_net
docker inspect ai_video_nginx --format '{{.State.Status}} {{.State.Health.Status}}'
```

## 准备目录和代码

```bash
sudo mkdir -p /opt/data-achieve-scrapy
sudo chown ubuntu:ubuntu /opt/data-achieve-scrapy

git clone \
  --branch feat/live-capability-verification-sink-notes \
  --single-branch \
  https://github.com/zjgulai/data_achieve.git \
  /opt/data-achieve-scrapy/app

install -m 600 /dev/null /opt/data-achieve-scrapy/.env.production
```

## 配置环境变量

必须配置：

```dotenv
SCRAPY_POSTGRES_DB=<数据库名>
SCRAPY_POSTGRES_USER=<数据库用户>
SCRAPY_POSTGRES_PASSWORD=<强密码>
SCRAPY_JWT_SECRET=<随机高强度值>
SCRAPY_AUTH_COOKIE_SECURE=true
SCRAPY_PUBLIC_URL=https://scrapy.luteos.com
SCRAPY_DEMO_EMAIL=owner@example.com
SCRAPY_DEMO_PASSWORD=<演示账号强密码>
```

按启用能力配置：

```dotenv
TIKHUB_API_KEY=
APIFY_API_TOKEN=
EXA_API_KEY=
ANYSEARCH_API_KEY=
JINA_API_KEY=
GITHUB_TOKEN=
PLATFORM_CREDENTIAL_MASTER_KEY=
SCRAPY_MCP_TOKEN=
SCRAPY_MCP_TOKENS_JSON={}
```

Cookie、Twitter 账号、代理、SMTP、CDO 和其他 Provider 变量按实际需要配置。不得在终端输出完整 env 文件或原始 Token。

## Preflight

```bash
cd /opt/data-achieve-scrapy/app
bash scripts/deploy-preflight-scrapy.sh \
  --env-file /opt/data-achieve-scrapy/.env.production \
  --compose-file configs/deploy/scrapy/docker-compose.yml \
  --base-url https://scrapy.luteos.com
```

## 空库部署顺序

先启动数据库，再构建镜像和执行迁移，最后启动完整栈：

```bash
cd /opt/data-achieve-scrapy/app

docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  up --detach db

docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  build api console spiderfoot

docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  run --rm --no-deps api alembic upgrade head

docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  up --detach
```

## Demo seed

空库必须执行标准 demo seed，否则项目、Dashboard 和 quick-collect 会返回 `demo_workspace_unavailable`：

```bash
cd /opt/data-achieve-scrapy/app
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

Seed 是幂等操作，创建一个 demo workspace 和四个业务域项目。

## 共享网关

`data_achieve_scrapy_edge` 必须连接 `lighthouse_ai_video_net`，并持有别名 `data_achieve_scrapy_proxy`。共享 Nginx upstream：

```nginx
upstream data_achieve_scrapy {
    server data_achieve_scrapy_proxy:8080;
}
```

`scrapy.luteos.com` 的 `location /` 必须代理到 `http://data_achieve_scrapy`。修改共享配置前先备份，只执行配置检查和热重载：

```bash
docker exec ai_video_nginx nginx -t
bash scripts/reload-scrapy-gateway.sh
```

不得删除 `lighthouse_ai_video_net`，不得为本项目单独占用宿主机 80/443。

## 验收

```bash
cd /opt/data-achieve-scrapy/app
docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file ../.env.production \
  ps

curl -fsSL https://scrapy.luteos.com/api/health
curl -fsSL https://scrapy.luteos.com/api/platform-packages
curl -fsSI https://scrapy.luteos.com/platforms
curl -sS -L -o /dev/null -w '%{http_code}\n' https://scrapy.luteos.com/mcp
```

加载演示账号执行标准 API smoke：

```bash
set -a
source /opt/data-achieve-scrapy/.env.production
set +a

BASE_URL=https://scrapy.luteos.com \
SCRAPY_DEMO_EMAIL="$SCRAPY_DEMO_EMAIL" \
SCRAPY_DEMO_PASSWORD="$SCRAPY_DEMO_PASSWORD" \
bash scripts/smoke-api-scrapy.sh
```

预期：核心容器 healthy、schema 为 head、平台包为 `70 / 270 / 242`、未授权 MCP 返回 `401`。

## 数据和回滚

持久化数据使用以下 Docker volumes：

- `data_achieve_scrapy_postgres_data`
- `data_achieve_scrapy_export_data`
- `data_achieve_scrapy_browser_data`

升级前必须备份数据库、环境变量、导出文件、旧源码和共享网关配置。恢复步骤见 [发布与回滚清单](workflows/workflow-release-rollback-stable.md)。
