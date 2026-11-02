# 生产 B 升级 runbook（2026-11-02）

- 目标：把 B 从 `bf7a2815`（schema `202610220056`）升级到 main 当前 HEAD（schema `202610310068`）。
- 前提：`bash scripts/preflight-production-b.sh` PASS；用户确认维护窗口；完成新备份与回滚包。
- 红线：先 push 再发布；服务器只 `fetch + merge --ff-only`；不 `pull`、不 `reset --hard`；重建 api 后必须 `restart edge`；不重建 edge 容器本身。

## 0. 事实

| 项 | 值 |
|---|---|
| 主机 | `ubuntu@101.34.52.232` |
| 密钥 | 仓库根 `DDDD.pem` |
| 代码路径 | `/opt/data-achieve-scrapy/app` |
| env | `/opt/data-achieve-scrapy/.env.production` |
| 分支 | `deploy/tiktok-cdo-codex` |
| 当前 HEAD | `bf7a281584c526888daf11f1aae71920db7cb0b2` |
| 当前 schema | `202610220056` |
| edge 固定 IP | `172.20.0.30` |
| 目标 schema | `202610310068`（用 `alembic heads` 动态确认） |

B 相对 main 是 **217/0 严格祖先**，0 个独有提交。升级是 fast-forward，不是 merge。

## 1. 备份与回滚包

在 B 上执行：

```bash
cd /opt/data-achieve-scrapy/app
STAMP=$(date +%Y%m%d-%H%M)
mkdir -p /opt/backups/data-achieve-scrapy/$STAMP
git rev-parse HEAD > /opt/backups/data-achieve-scrapy/$STAMP/HEAD
docker inspect -f '{{.Image}}' data_achieve_scrapy_api      > /opt/backups/data-achieve-scrapy/$STAMP/api.image
docker inspect -f '{{.Image}}' data_achieve_scrapy_console  > /opt/backups/data-achieve-scrapy/$STAMP/console.image
docker inspect -f '{{.Image}}' data_achieve_scrapy_web      > /opt/backups/data-achieve-scrapy/$STAMP/web.image
cp /opt/data-achieve-scrapy/.env.production /opt/backups/data-achieve-scrapy/$STAMP/env.production
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  exec -T db pg_dump -U "$SCRAPY_POSTGRES_USER" -d "$SCRAPY_POSTGRES_DB" -Fc \
  > /opt/backups/data-achieve-scrapy/$STAMP/db.dump
ls -lh /opt/backups/data-achieve-scrapy/$STAMP/db.dump
```

验收：`db.dump` 大于 1 MB；`HEAD`、三个 image ID、env 备份都存在。

## 2. 同步代码

在 B 上执行。GitHub 抖动时重试，最多 4 次：

```bash
cd /opt/data-achieve-scrapy/app
for i in 1 2 3 4; do
  git -c http.version=HTTP/1.1 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=20 \
    fetch origin main && break
  echo "fetch retry $i"; sleep 5
done
git merge --ff-only FETCH_HEAD
git rev-parse HEAD
```

验收：HEAD 等于本地 `git rev-parse main`；`git status` 干净。

## 3. 构建镜像

```bash
cd /opt/data-achieve-scrapy/app
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  build --progress plain api console web
```

验收：三个镜像构建成功；失败则停止，旧容器仍在服务。

## 4. 迁移

```bash
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  run --rm --no-deps api alembic upgrade head
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  run --rm --no-deps api alembic current
```

验收：`current` 等于仓库 `alembic heads` 的唯一 head。失败则停止；旧容器仍在服务。

## 5. 替换容器与 edge

```bash
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  up -d --no-deps api console web

# ABI 导出 worker 依赖 export-init 完成 chown；先跑 export-init。
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  run --rm --no-deps export-init
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  --profile abi up -d --no-deps abi-export

docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  restart edge
```

验收：`api`、`console`、`web`、`edge`、`abi-export` 都 running；edge IP 仍是 `172.20.0.30`。

## 6. 公网验收

在本地执行：

```bash
curl -s https://scrapy.lute-tlz-dddd.top/api/health
curl -s -o /dev/null -w '%{http_code}\n' https://scrapy.lute-tlz-dddd.top/api/tiktok/tools
curl -s -o /dev/null -w '%{http_code}\n' https://scrapy.lute-tlz-dddd.top/api/abi/datasets
curl -s -o /dev/null -w '%{http_code}\n' https://scrapy.lute-tlz-dddd.top/api/insight/analysis-types
curl -s -I https://scrapy.lute-tlz-dddd.top/insight | head -5
```

通过条件：

- `/api/health`：`status=ok`、`database=connected`、`schema=current`、`schema_revision=schema_head=202610310068`。
- `/api/tiktok/tools`、`/api/abi/datasets`、`/api/insight/analysis-types` 均为 401。
- `/insight` 307 到 `/insight/login?next=...`。
- `bash scripts/check_dual_production_drift.sh` 无 schema drift。

## 7. 记账

在本地执行：

```bash
python3 scripts/record_release.py append \
  --host b --commit <remote_head> --branch deploy/tiktok-cdo-codex \
  --subject "deploy-p0.sh B" --result success
```

## 8. 回滚

### 8.1 容器回滚（最快）

```bash
STAMP=<备份目录>
docker tag "$(cat /opt/backups/data-achieve-scrapy/$STAMP/api.image)"     data_achieve_scrapy_api:latest
docker tag "$(cat /opt/backups/data-achieve-scrapy/$STAMP/console.image)" data_achieve_scrapy_console:latest
docker tag "$(cat /opt/backups/data-achieve-scrapy/$STAMP/web.image)"     data_achieve_scrapy_web:latest
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  up -d --no-deps api console web
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  restart edge
```

### 8.2 代码回滚

```bash
cd /opt/data-achieve-scrapy/app
git switch --detach "$(cat /opt/backups/data-achieve-scrapy/$STAMP/HEAD)"
```

不要 `reset --hard`。回滚代码后重建镜像，再按 8.1 替换容器。

### 8.3 数据库回滚

迁移只应向前。只有在数据损坏且用户明确授权时才恢复：

```bash
docker compose ... exec -T db pg_restore -U "$SCRAPY_POSTGRES_USER" \
  -d "$SCRAPY_POSTGRES_DB" --clean --if-exists \
  < /opt/backups/data-achieve-scrapy/$STAMP/db.dump
```

恢复前先停 api/console；恢复后重跑健康检查。优先向前修复，恢复是最后手段。

## 9. 停止条件

出现任一情况立即停止，不继续下一步：

- 备份文件小于 1 MB 或 `pg_dump` 退出非 0。
- `git merge --ff-only` 失败或 HEAD 不等于目标。
- 镜像构建失败。
- 迁移失败或 `alembic current` 不是唯一 head。
- 公网 `/api/health` 不是 `schema=current`。
- edge IP 不是 `172.20.0.30`。
- 任一 401 探针返回 404 或 200。

## 10. 2026-11-02 执行记录

| 项 | 结果 |
|---|---|
| 备份 | `/opt/backups/data-achieve-scrapy/20261102-0909/`，`db.dump` 3.4 MB，含 HEAD、三个旧镜像 ID、env |
| preflight | PASS：SSH 可达、分支正确、edge `172.20.0.30`、四容器 running、备份存在、45G 空闲 |
| fast-forward | `bf7a2815` → `3f889e7`，0 冲突 |
| 迁移 | `202610220056` → `202610310068`，12 个 revision 全部应用 |
| 镜像 | api/console/web 重建成功 |
| 容器 | api/console/web 已替换；`abi-export` running；edge 仍在 `172.20.0.30` |
| 公网 | `/api/health` 200、schema 068；ABI/insight/tiktok 均 401；`/abi`、`/insight` 307 到登录 |
| 账本 | A/B 均记 `3f889e7`；`record_release.py verify` 通过 |
| 备注 | 升级脚本在迁移后中断，容器替换由第二条命令补齐；`abi-export` 需带依赖启动（`--profile abi up -d abi-export`，不要加 `--no-deps`） |

### 2026-11-02 二次升级（ABI ETL 代码）

- 目标：`09aa288`（与 A `efe6d94` 同一代码；A 多两个文档/账本提交）
- 备份：`/opt/backups/data-achieve-scrapy/20261102-1138/`，`db.dump` 3.6 MB
- 结果：B 健康、schema 068；api/console/web/abi-export 均 running；edge `172.20.0.30`
- 坑：`up -d` 重建 api 后 edge 缓存旧 IP，公网 502；执行 `restart edge` 后恢复。`abi-export` 需 `--profile abi up -d abi-export`（不带 `--no-deps`）。
- 账本：`09aa288`，`record_release.py verify` 通过。

### 2026-11-02 三次升级（ABI scan consumer）

- 目标：`ea9e197`，与 A 同一提交
- 备份：复用 `20261102-1138`（schema 未变，代码增量）
- 结果：B 健康、schema 068；api/abi-export 新镜像 `dd74ea53…` running；edge `172.20.0.30`
- 坑：同上，`up -d` 后必须 `restart edge`；`abi-export` 用 `--profile abi up -d abi-export`
- 账本：`ea9e197`

### 2026-11-02 四次升级（token 表 + scan 队列）

- 目标：`c10ed99`，与 A 同一提交；`ABI_FERNET_KEY` 已在 B `.env.production`
- 结果：B 健康、schema 068；api/abi-export 新镜像 `1001be4f…` running；edge `172.20.0.30`
- 未做：B 未种子化 Apify token、未启动 `abi-ingest`；B 只有 demo workspace
- 账本：`c10ed99`