---
name: production-restart-runbook
description: 生产 A（43.163.92.244）的发布重启手册。涵盖前置检查、部署、验收、回滚与 502 处置，并保护 edge 固定 IP。发布只做生产 A。
---

# 生产重启手册（生产 A）

## 结论

1. 只发布生产 A：`ubuntu@43.163.92.244`。
2. 不得重建 `data_achieve_scrapy_edge`。
3. 替换容器只用 `up -d api console`。
4. 发布后必须确认 edge 仍在 `172.20.0.16`。
5. 网关重载失败时，停止并通知。

按 2026-10-21 指示，实际部署只做生产 A。生产 B（`101.34.52.232`）暂缓。本文不覆盖生产 B。

## 固定事实

| 项目 | 值 |
| --- | --- |
| 主机 | `ubuntu@43.163.92.244` |
| 公网域名 | `https://scrapy.luteos.com` |
| 项目路径 | `/opt/data-achieve-scrapy/app` |
| 环境变量 | `/opt/data-achieve-scrapy/.env.production` |
| Compose 文件 | `configs/deploy/scrapy/docker-compose.yml` |
| Compose 项目 | `data_achieve_scrapy` |
| Edge 容器 | `data_achieve_scrapy_edge` |
| 外部网络 | `lighthouse_ai_video_net` |
| 外部固定 IP | `172.20.0.16` |
| 内部网络 | `data_achieve_scrapy_internal` |
| 内部固定 IP | `172.26.0.10` |
| 共享网关 | `ai_video_nginx` |
| 共享上游别名 | `data_achieve_scrapy_proxy` |

`data_achieve_scrapy_proxy` 是 edge 在 `lighthouse_ai_video_net` 上的别名。它不是独立容器。

## 硬性规则

1. 不得运行不带服务名的 `docker compose up -d`。该命令可能重建 edge。
2. 不得运行 `docker compose down`。
3. 不得删除或重建 `lighthouse_ai_video_net`。
4. 不得删除、重启或重建 `ai_video_nginx`。
5. 不得断开 edge 与任一网络的连接。
6. 不得在生产工作区提交。
7. 所有 Compose 命令必须带 `--env-file /opt/data-achieve-scrapy/.env.production`。

## 为什么保护 edge

共享网关 `ai_video_nginx` 在加载配置时解析一次 `data_achieve_scrapy_proxy`。它把结果缓存在内存中。

edge 固定为 `172.20.0.16` 后，网关缓存持续有效。重建 edge 会分配新 IP。网关仍发往旧 IP。公网因此返回 502。

本仓库的 Compose 文件没有声明固定 IP。固定 IP 依赖运行中的网络连接。重建 edge 会丢失固定 IP。

已知网关重载失败原因：无关项目的上游 `ai_video_backend:8001` 解析不到。该问题修复前，不得重建 edge。

`restart edge` 只重启容器内的进程。容器和 IP 不变。`up -d` 或 `--force-recreate` 会重建容器。两者不同。

## 发布前检查

### 1. 本地状态

```bash
git status --short --branch
git log -1 --oneline
git rev-parse HEAD
git ls-remote --heads origin main
```

要求：

1. 工作区干净。
2. 本地 HEAD 等于 `origin/main`。
3. 只发布已推送的 commit。

### 2. 只读预检

在本地仓库运行：

```bash
bash scripts/preflight-production.sh
bash scripts/check-edge-fixed-ip.sh
```

`scripts/preflight-production.sh` 必须输出 `ALL CHECKS PASSED`。它检查以下项目：

| 检查 | 期望值 |
| --- | --- |
| 公网 `/api/health` | 200 |
| edge 固定 IP | `172.20.0.16` |
| API 容器 | healthy |
| schema | `202610220056` |
| vault key | 44 字符 |
| TikTok 工具 | 16 个 |

`scripts/check-edge-fixed-ip.sh` 只读。它通过 SSH 读取 edge 的网络 IP。退出码 0 表示固定 IP 存在。退出码 1 表示检查失败。

脚本默认连接 `ubuntu@43.163.92.244`。默认密钥为 `../data_scrapy/zhoujian_pachong.pem`。可用 `SCRAPY_PROD_HOST` 与 `SCRAPY_PROD_KEY` 覆盖。

### 3. 记录现场

登录生产 A：

```bash
ssh -i zhoujian_pachong.pem ubuntu@43.163.92.244
cd /opt/data-achieve-scrapy/app
```

记录以下值：

```bash
git rev-parse HEAD
docker inspect data_achieve_scrapy_edge \
  --format '{{range $name, $net := .NetworkSettings.Networks}}{{$name}}={{$net.IPAddress}} {{end}}'
docker inspect data_achieve_scrapy_edge \
  --format '{{.State.StartedAt}} {{.RestartCount}}'
docker image inspect --format '{{.RepoTags}} {{.Id}}' \
  data_achieve_scrapy_api:latest data_achieve_scrapy_console:latest
```

要求：

1. edge 有 `lighthouse_ai_video_net=172.20.0.16`。
2. edge 有 `data_achieve_scrapy_internal=172.26.0.10`。
3. 记录 api 与 console 的旧镜像 ID。回滚要用。

### 4. 备份

```bash
stamp=$(date +%Y%m%dT%H%M%S)
backup=/opt/backups/data-achieve-scrapy/$stamp
sudo mkdir -p "$backup"
sudo chown ubuntu:ubuntu "$backup"
docker exec data_achieve_scrapy_db sh -lc \
  'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$backup/postgres.sql.gz"
sudo cp /opt/data-achieve-scrapy/.env.production "$backup/env.production"
docker image inspect data_achieve_scrapy_api:latest data_achieve_scrapy_console:latest \
  > "$backup/images.json"
git rev-parse HEAD > "$backup/head.txt"
```

### 5. 网关只读检查

```bash
bash scripts/reload-scrapy-gateway.sh --dry-run
```

该命令只读。它检查网关容器、edge 健康、别名解析和网关配置。

失败时不要发布。先处理网关问题。

## 部署

以下手工命令在生产 A 的 `/opt/data-achieve-scrapy/app` 目录执行。

```bash
cd /opt/data-achieve-scrapy/app
ENVF=/opt/data-achieve-scrapy/.env.production
COMPOSE_FILE=/opt/data-achieve-scrapy/app/configs/deploy/scrapy/docker-compose.yml
```

### 1. 校验编排

```bash
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" config --quiet
```

### 2. 构建 api 与 console

```bash
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" build api console
```

### 3. 应用迁移

```bash
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" run --rm --no-deps api alembic upgrade head
```

迁移失败时停止。旧容器继续服务。

### 4. 替换容器

```bash
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" up -d api console
```

只允许这一条启动命令。服务列表只有 `api` 和 `console`。edge 不在列表内，因此 edge 不重建。

不得对 edge 使用 `--force-recreate`。

### 5. 重启 edge

```bash
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" restart edge
```

edge 的 nginx 在启动时解析 `api` 与 `console`。替换容器后必须重启 edge。`restart` 不重建容器。固定 IP 保持。

### 6. 使用发布脚本

在本地仓库运行：

```bash
scripts/deploy-p0.sh --host a
```

该脚本执行以下动作：

1. 拉取 `main`。
2. 构建 `api` 与 `console`。
3. 应用迁移。
4. 运行 `up -d --no-deps api console`。
5. 运行 `restart edge`。
6. 等待容器健康。
7. 重载共享网关。

注意：脚本重启 edge，并尝试重载网关。网关重载失败时，脚本只告警。操作者必须停止并通知。不得用重建 edge 的方式绕过网关失败。

## 发布后检查

### 1. 完整预检

在本地运行：

```bash
bash scripts/preflight-production.sh
```

必须输出 `ALL CHECKS PASSED`。

### 2. edge 固定 IP

```bash
bash scripts/check-edge-fixed-ip.sh
echo $?
```

期望输出 `PASS`，退出码 0。

在生产 A 复核两个网络：

```bash
docker inspect data_achieve_scrapy_edge \
  --format '{{range $name, $net := .NetworkSettings.Networks}}{{$name}}={{$net.IPAddress}} {{end}}'
```

输出必须包含以下两项。顺序不限：

```text
data_achieve_scrapy_internal=172.26.0.10
lighthouse_ai_video_net=172.20.0.16
```

### 3. 公网

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://scrapy.luteos.com/api/health
curl -sS -o /dev/null -w '%{http_code}\n' https://scrapy.luteos.com/tools
curl -sS -o /dev/null -w '%{http_code}\n' https://scrapy.luteos.com/api/tools
```

全部期望 200。

### 4. 网关链路

```bash
docker exec ai_video_nginx getent hosts data_achieve_scrapy_proxy
docker exec ai_video_nginx wget -qO- http://data_achieve_scrapy_proxy:8080/api/health
```

第一条必须解析到 `172.20.0.16`。第二条必须返回健康 JSON。

### 5. 容器

```bash
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" ps
```

`api`、`console`、`edge`、`db` 必须为 `healthy` 或 `running`。

### 6. 数据口径

```bash
curl -sS https://scrapy.luteos.com/api/health
docker exec data_achieve_scrapy_api python -c \
  'import os; print(len(os.environ.get("PLATFORM_CREDENTIAL_MASTER_KEY", "")))'
docker exec data_achieve_scrapy_api python -c \
  'from data_intelligence_hub.services.tiktok_tools import TOOL_SPECS; print(len(TOOL_SPECS))'
```

期望：

| 项目 | 期望值 |
| --- | --- |
| `schema_revision` | `202610220056` |
| vault key 长度 | `44` |
| TikTok 工具数 | `16` |

## 回滚

以下命令沿用部署章节的变量。新开 shell 时先设置：

```bash
cd /opt/data-achieve-scrapy/app
ENVF=/opt/data-achieve-scrapy/.env.production
COMPOSE_FILE=/opt/data-achieve-scrapy/app/configs/deploy/scrapy/docker-compose.yml
```

### 触发条件

出现以下任一情况时，停止发布并回滚：

1. 公网 `/api/health` 非 200。
2. schema 不是 `202610220056`。
3. `api` 或 `console` 不健康。
4. edge 不在 `172.20.0.16`。
5. 网关重载失败。
6. 公网 502 持续。

### 代码回滚

在本地仓库运行：

```bash
git revert <bad-commit>
git push origin main
```

生产 A 拉取 revert commit，然后重建：

```bash
cd /opt/data-achieve-scrapy/app
git fetch origin main
git merge --ff-only FETCH_HEAD
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" build api console
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" up -d api console
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" restart edge
```

不得用 `down`。不得用不带服务名的 `up -d` 重建 edge。

### 镜像回滚

发布前记录了旧镜像 ID。需要快速回退时：

```bash
docker tag <old-api-id> data_achieve_scrapy_api:latest
docker tag <old-console-id> data_achieve_scrapy_console:latest
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" up -d api console
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" restart edge
```

### 环境变量回滚

```bash
ls -1t /opt/data-achieve-scrapy/.env.production.bak.* | head -1
cp -p <backup-file> /opt/data-achieve-scrapy/.env.production
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" up -d api console
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" restart edge
```

### 数据库回滚

迁移只向前。没有验证过的 downgrade 时：

1. 停止应用写入。
2. 保留现场。
3. 从 `postgres.sql.gz` 恢复。
4. 通知负责人。

不得删除 PostgreSQL volume。

## 502 处置

以下命令沿用部署章节的 `ENVF` 与 `COMPOSE_FILE`。

### 先收集证据

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://scrapy.luteos.com/api/health
docker inspect data_achieve_scrapy_edge \
  --format '{{range $name, $net := .NetworkSettings.Networks}}{{$name}}={{$net.IPAddress}} {{end}}'
docker exec ai_video_nginx getent hosts data_achieve_scrapy_proxy
docker logs --tail 50 data_achieve_scrapy_edge
```

### 情况 1：edge 被重建

现象：

1. 公网 502。
2. edge 的 `lighthouse_ai_video_net` IP 不是 `172.20.0.16`。

原因：共享网关仍缓存旧 IP。

处理：

```bash
bash scripts/reload-scrapy-gateway.sh --dry-run
bash scripts/reload-scrapy-gateway.sh
```

公网 502 会持续到网关解析新 IP。重载成功后复查公网。

网关重载失败时，停止并通知。不得反复重建 edge。

### 情况 2：网关解析旧 IP

现象：

1. 公网 502。
2. edge IP 是 `172.20.0.16`。
3. 网关解析到其他 IP。

处理：

```bash
docker exec ai_video_nginx getent hosts data_achieve_scrapy_proxy
bash scripts/reload-scrapy-gateway.sh
```

重载失败时，停止并通知。

### 情况 3：edge 到 api/console 的 502

现象：

1. 公网 502。
2. edge 健康。
3. 网关解析正确。
4. 网关到 edge 的 health 请求失败。

检查：

```bash
docker exec ai_video_nginx wget -qO- http://data_achieve_scrapy_proxy:8080/api/health
```

原因：api 或 console 被替换。edge 缓存了旧容器 IP。

处理：

```bash
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" restart edge
```

等待 5 秒，再复查公网。`restart` 不改变 edge 的固定 IP。

### 恢复固定 IP

仅在 edge 已被重建，且网关重载不可用时执行。需负责人批准。

```bash
docker network disconnect lighthouse_ai_video_net data_achieve_scrapy_edge
docker network connect --ip 172.20.0.16 --alias data_achieve_scrapy_proxy \
  lighthouse_ai_video_net data_achieve_scrapy_edge
docker network disconnect data_achieve_scrapy_internal data_achieve_scrapy_edge
docker network connect --ip 172.26.0.10 --alias edge \
  data_achieve_scrapy_internal data_achieve_scrapy_edge
```

连接后复查：

```bash
bash scripts/check-edge-fixed-ip.sh
curl -sS -o /dev/null -w '%{http_code}\n' https://scrapy.luteos.com/api/health
```

注意：重新连接会短暂中断内部网络。不要在业务高峰执行。

## 禁止操作清单

| 操作 | 后果 |
| --- | --- |
| 不带服务名的 `docker compose up -d` | 可能重建 edge，公网 502 |
| `docker compose down` | 删除容器和网络，固定 IP 丢失 |
| `up -d --force-recreate edge` | 重建 edge，固定 IP 丢失 |
| `docker network rm lighthouse_ai_video_net` | 影响同主机 10 个以上域名 |
| `docker restart ai_video_nginx` | 影响共享网关上的其他项目 |
| 在生产工作区 `git commit` | 污染发布源 |

## 相关文档

- [生产环境基线](../【运维手册】生产环境基线.md)
- [发布与回滚清单](../workflows/workflow-release-rollback-stable.md)
- [生产变更的隔离与串台防线](../knowledge/生产变更的隔离与串台防线.md)
- [scrapy.luteos.com 全量重建](../workflows/【运维手册】scrapy-luteos全量重建.md)
