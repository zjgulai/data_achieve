---
name: production-image-build
description: "在两台生产主机构建本项目镜像。Use when 需要构建 api、console、web、spiderfoot 镜像、构建很慢或超时、构建失败需要诊断、或更换包源/升级 Playwright 时。涵盖国内镜像源参数、后台构建方式与构建后验证。"
---

# 生产镜像构建

## 适用场景

- 发布或重建时构建镜像。
- 构建慢、超时、失败。
- 更换包源，或升级 Playwright。

## 命令

在 `/opt/data-achieve-scrapy/app` 执行。必须带 `--env-file`。

```bash
docker compose \
  --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml \
  build --progress plain <服务名>
```

服务名：`api`、`console`、`web`、`spiderfoot`、`tor`。

构建大时放后台。日志写文件。这样 SSH 断开不中断构建。

```bash
nohup docker compose ... build --progress plain api </dev/null >/tmp/build.log 2>&1 &
disown
echo started
```

然后轮询：`pgrep -f "docker [c]ompose.*build"` 与 `tail /tmp/build.log`。

## 环境差异

生产 A 不设镜像源键，走官方源。

生产 B 的 `.env.production` 固定四个 `SCRAPY_*` 键，走国内镜像。命令不变，compose 自动带入。

生产 B 的镜像源值与约束见 `docs/knowledge/国内主机构建加速.md`。

## 构建后验证

### 通用

```bash
docker images data_achieve_scrapy_<服务> --format "{{.ID}} {{.CreatedSince}}"
```

### api

锁文件改写只在国内构建生效。验证镜像内状态：

```bash
docker run --rm --entrypoint sh data_achieve_scrapy_api:latest -c \
  "grep -c mirrors.cloud.tencent.com/pypi/packages /app/uv.lock; \
   grep -c files.pythonhosted.org /app/uv.lock; \
   /app/.venv/bin/python -c 'import fastapi, sqlalchemy, asyncpg, alembic, playwright; print(\"imports ok\")'"
```

期望：生产 B 的第一项大于 0，第二项为 0。

### console 与 web

复核烧录域名。产物只应出现本机域名：

```bash
docker exec <容器> sh -c \
  "grep -rhoE 'https://scrapy\.[a-z0-9.-]+' /app/.next/static | sort -u"
```

出现另一台机器的域名即串台。必须修源码后重建。

## 诊断分支

按现象查表。

| 现象 | 先查 | 动作 |
|---|---|---|
| pip/uv 下载超时 | 索引键是否生效 | 换源前在容器内解析主机、测速 |
| uv 下载流向官方站 | 锁文件改写是否执行 | 核对 `PIP_INDEX_URL` 是否以 `/simple/` 结尾 |
| corepack 报 404 | registry 尾斜杠 | 去掉尾斜杠 |
| corepack/浏览器报 ENOTFOUND | 容器内 DNS | 换容器内可解析的主机 |
| Playwright 下载 400 | CFT 路径 | 按版本核对 `builds/cft/<版本>/linux64/` |
| webpack `Can't resolve ../../../../opendesign/...` | Dockerfile 是否 COPY `opendesign` | 补 COPY |
| 构建参数不生效 | Dockerfile 的 ARG/ENV | ENV 写 `${ARG_NAME}` |

完整方案与实测数据见 `docs/knowledge/国内主机构建加速.md`。

## 坑点

1. 构建可能耗时数分钟。用后台加轮询，不要一次 ssh 长等。
2. `nohup` 后台进程必须接 `/dev/null` 作 stdin。
3. 构建与重建容器是两步。构建完还要 `up -d <服务>`。
4. 重建 console 或 web 后要复核烧录域名。
