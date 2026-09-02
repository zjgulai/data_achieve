# Data Intelligence Hub — 新服务器部署方案

> 目标服务器：192.168.204.230（内网）· 8 vCPU · 62GB RAM · 1TB /data
> 最后更新：2026-09-01

---

## 服务器基本信息

| 项目 | 值 |
|---|---|
| 内网 IP | `192.168.204.230` |
| 系统 | Ubuntu 24.04.4 LTS |
| 规格 | 8 vCPU · 62 GB RAM · 200 GB 系统盘 + 1 TB `/data` 数据盘 |
| 访问方式 | 堡垒机 `jumpserver.luteos.site:2222` → lute@192.168.204.230 |
| 登录用户 | `lute`（sudo） |

---

## 与当前生产环境（101.34.52.232）的差异

| 项目 | 旧服务器（腾讯云） | 新服务器（内网） |
|---|---|---|
| IP 性质 | 公网 IP | 内网 IP，需端口映射/反代才能公网访问 |
| 数据盘 | 无独立数据盘 | 1 TB `/data`，所有持久化数据应挂载于此 |
| SSH 入口 | 直连 + DDDD.pem | 堡垒机跳转 |
| 内核参数 | 默认 | 已调优（open files 65535 / somaxconn） |
| Docker | 已安装 | **待安装**（见下方步骤） |

---

## 第一步：安装 Docker

```bash
# 连接服务器
ssh lute@192.168.204.230
# 或通过堡垒机：ssh -p 2222 zhoujian@jumpserver.luteos.site

# 安装 Docker Engine
curl -fsSL https://get.docker.com | sudo sh

# 将 lute 加入 docker 组（免 sudo）
sudo usermod -aG docker lute
newgrp docker

# 启动并设开机自启
sudo systemctl enable --now docker

# 验证
docker version
docker compose version   # 需 >= 2.x
```

---

## 第二步：准备目录结构

```bash
# 在数据盘创建所有持久化目录（关键：使用 /data 而非系统盘）
sudo mkdir -p /data/scrapy/{postgres,exports/datasets,browser_data,configs}
sudo chown -R lute:lute /data/scrapy

# 克隆/拉取项目代码
mkdir -p ~/apps
cd ~/apps
git clone https://github.com/zjgulai/data_achieve.git data_scrapy
cd data_scrapy
git checkout codex/social-api-private-matrix-20260708
```

---

## 第三步：创建环境变量文件

```bash
# 复制模板并填写真实值
cp .env.example /data/scrapy/configs/.env.production
# 然后编辑：
nano /data/scrapy/configs/.env.production
```

**必填变量**（参考旧服务器 /opt/data-achieve-scrapy/.env.production）：

```dotenv
# 数据库
SCRAPY_POSTGRES_DB=data_intelligence_hub
SCRAPY_POSTGRES_USER=scrapy_user
SCRAPY_POSTGRES_PASSWORD=<强密码>
SCRAPY_JWT_SECRET=<随机64字符>
SCRAPY_AUTH_COOKIE_SECURE=true

# API Keys（从旧服务器迁移）
TIKHUB_API_KEY=<from old server>
APIFY_API_TOKEN=<from old server>
ANYSEARCH_API_KEY=<from old server>
JINA_API_KEY=<from old server>
GITHUB_TOKEN=<from old server>

# 调度器
SCRAPY_SCHEDULER_ENABLED=true
SCRAPY_SCHEDULER_POLL_INTERVAL_SECONDS=60

# 域名（改为新域名或内网访问）
# 如果对外：将 scrapy.lute-tlz-dddd.top 替换为新域名
# 如果内网：可填 http://192.168.204.230

# 数据导出目录（使用数据盘）
SCRAPY_DATASET_EXPORT_DIR=/app/exports/datasets

# 代理（可选）
PROXY_ROTATOR_ENABLED=false
HTTP_PROXY=
HTTPS_PROXY=

# OSINT 服务
MAIGRET_URL=http://maigret:5000
SPIDERFOOT_BASE_URL=http://spiderfoot:5001
SPIDERFOOT_TIMEOUT=300
```

---

## 第四步：部署容器

```bash
cd ~/apps/data_scrapy

# 首次完整构建（约 10-20 分钟，依网速）
docker compose \
  -f configs/deploy/scrapy-new/docker-compose.yml \
  --env-file /data/scrapy/configs/.env.production \
  up --build -d

# 等待所有容器健康
watch docker ps
```

---

## 第五步：配置宿主机 Nginx（对外暴露）

```bash
# 安装宿主机 Nginx
sudo apt install -y nginx

# 将配置写入 Nginx
sudo cp ~/apps/data_scrapy/configs/deploy/scrapy-new/nginx.conf \
  /etc/nginx/sites-available/scrapy

sudo ln -sf /etc/nginx/sites-available/scrapy \
  /etc/nginx/sites-enabled/scrapy

sudo nginx -t && sudo systemctl reload nginx
```

如果有公网域名，同步配置 SSL：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.com
```

---

## 第六步：健康验收

```bash
# API 健康检查
curl http://192.168.204.230/api/health
# 期望：{"status":"ok","database":"connected",...}

# catalog 验收
curl http://192.168.204.230/api/collectors/catalog | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  v=sum(1 for g in d['collectors'] for e in g['endpoints'] if e.get('status')=='verified'); \
  print('verified:', v)"
# 期望：verified: 207
```

---

## 容器资源规划（62 GB RAM）

| 容器 | 内存估算 | CPU 估算 |
|---|---|---|
| api (FastAPI) | 512 MB ~ 1 GB | 0.5 core |
| console (Next.js) | 256 MB | 0.2 core |
| db (Postgres) | 512 MB ~ 2 GB | 0.5 core |
| maigret | 256 MB | 0.2 core |
| spiderfoot | 512 MB | 0.3 core |
| nginx (edge) | 64 MB | 微量 |
| **合计** | **~5 GB** | **~2 core** |
| **剩余可用** | **~57 GB** | **~6 core** |

新服务器资源远超当前负载，可在同一台服务器上额外部署其他项目。

---

## 从旧服务器迁移数据（可选）

如需迁移 Postgres 数据：

```bash
# 旧服务器上导出
ssh -i DDDD.pem ubuntu@101.34.52.232 \
  "docker exec data_achieve_scrapy_db pg_dump -U scrapy_user data_intelligence_hub" \
  > /tmp/scrapy_dump.sql

# 传到新服务器
scp /tmp/scrapy_dump.sql lute@192.168.204.230:/tmp/

# 新服务器上导入（容器启动后）
ssh lute@192.168.204.230
docker exec -i data_achieve_scrapy_db \
  psql -U scrapy_user data_intelligence_hub < /tmp/scrapy_dump.sql
```

---

## 防火墙配置

```bash
# 开放 HTTP/HTTPS（给 Nginx 用）
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
# SSH 已开放（22/tcp）

# 验证
sudo ufw status
```

---

## 路径对照表

| 资产 | 旧服务器路径 | 新服务器路径 |
|---|---|---|
| 项目代码 | `/opt/data-achieve-scrapy/app` | `~/apps/data_scrapy` |
| 环境变量 | `/opt/data-achieve-scrapy/.env.production` | `/data/scrapy/configs/.env.production` |
| Postgres 数据 | Docker volume | `/data/scrapy/postgres`（bind mount） |
| 导出文件 | Docker volume | `/data/scrapy/exports`（bind mount） |
| docker-compose | `configs/deploy/scrapy/docker-compose.yml` | `configs/deploy/scrapy-new/docker-compose.yml` |

---

*最后更新：2026-09-01*
