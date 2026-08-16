# Data Intelligence Hub

Data Intelligence Hub 是一个面向品牌和市场运营人员的全社媒自动化数据采集与洞察平台。系统把监测目标、采集能力、透明工作流、数据资产和证据约束洞察连接为可持续运行的闭环。

核心链路：

```text
RawRecord -> EntitySnapshot -> Signal -> Intelligence -> Evidence -> Report / Alert
```

## 生产状态（2026-08-16）

| 项目 | 状态 |
|---|---|
| 生产域名 | `scrapy.lute-tlz-dddd.top` |
| 服务器 | `101.34.52.232` (VM-0-16-ubuntu, Ubuntu 22.04) |
| 当前分支 | `codex/social-api-private-matrix-20260708` |
| 当前 commit | `8a68afc` |
| API schema | `202607160033` (current) |
| 采集端点 | **137 verified / 0 pending / 11 disabled** |
| 容器状态 | api / web / console / edge / db 全部 healthy |
| 热更新状态 | API 容器已热替换（下次 `docker compose up --build` 会固化） |

### 已上线采集能力

| 采集器组 | 方法 | 端点数 | 代表平台 |
|---|---|---|---|
| TikHub Social | tikhub | 45 | TikTok / Instagram / 小红书 / YouTube / Reddit / X / Threads / LinkedIn / Lemon8 |
| Apify 社交 | apify | 20 | Instagram / Facebook / TikTok / YouTube / X / Reddit / Pinterest / Bluesky / Telegram / Snapchat |
| Apify 电商 & 评价 | apify | 18 | Amazon / Walmart / Temu / SHEIN / AliExpress / TikTok Shop / Trustpilot / App Store / Google Play / eBay / Etsy / Shopify |
| Apify Google 生态 | apify | 9 | Google Search / Maps / Maps Reviews / Trends / News / AI Overviews / Google Play Reviews |
| Apify AI 搜索 | apify | 6 | ChatGPT / Perplexity / Gemini (各含 search + scraper) |
| Apify 广告情报 | apify | 11 | Meta Ads / Google Ads / TikTok Ads / Snap Ads / Pinterest Ads + TikTok Creative Center |
| Apify B2B & LinkedIn | apify | 14 | LinkedIn (帖子/职位/员工/搜索) / Threads / Glassdoor / Product Hunt / Crunchbase / HN / Indeed |
| Apify 社群 & 渠道 | apify | 5 | Facebook Group / TikTok Shop Search / SimilarWeb / Target / Facebook Marketplace |
| Apify 内容分析 | apify | 4 | TikTok字幕 / YouTube字幕 / Website Crawler / RAG Browser |
| Apify PR 媒体 | apify | 11 | Google News + 媒体账号监测（Instagram/TikTok/YouTube/Facebook/X/Pinterest）|
| GitHub | github_api | 2 | GitHub Repo / Topics |
| RSS / 公开网页 | rss + web_crawl | 15 | RSS 订阅源 + Web Snapshot |

**数据类型覆盖（14种）**：post · comment · account · product · review · ad · job · trend · ai_answer · news · web_page · repo · feed · search

**覆盖平台（50个）**：TikTok、Instagram、YouTube、X、Reddit、Facebook、LinkedIn、Threads、Pinterest、Lemon8、Telegram、Bluesky、Snapchat、Amazon、Walmart、Temu、SHEIN、AliExpress、eBay、Etsy、Shopify、Target、Google Search/Maps/Trends/News/Play、ChatGPT、Perplexity、Gemini、Trustpilot、App Store、Tripadvisor、Yelp、Booking、Airbnb、Glassdoor、GitHub、Hacker News、Product Hunt、Crunchbase、Indeed、SimilarWeb 等

> 详细端点说明见 [平台数据采集手册](docs/workflows/workflow-platform-collection-playbook-stable.md)

## 文档入口

| 文档 | 用途 |
|---|---|
| [平台数据采集手册](docs/workflows/workflow-platform-collection-playbook-stable.md) | 所有端点参数、成本、调用示例 |
| [下一步产品方案](docs/product/NEXT-STEPS.md) | 产品演进路线与执行 TODO |
| [产品 PRD V2.0](docs/product/product-prd-social-media-automation-platform-v2.md) | 完整产品需求文档 |
| [技术架构](docs/architecture/architecture-data-intelligence-hub-stable.md) | 系统架构设计 |
| [发布与回滚清单](docs/workflows/workflow-release-rollback-stable.md) | 生产部署 SOP |
| [本地开发流程](docs/workflows/workflow-development-setup-stable.md) | 开发环境搭建 |

## 应用服务

| 服务 | 容器 | 端口 | 说明 |
|---|---|---|---|
| API | `data_achieve_scrapy_api` | 8000 | FastAPI 后端 |
| Web | `data_achieve_scrapy_web` | 3000 | Next.js 主产品（洞察面板）|
| Scraper Console | `data_achieve_scrapy_console` | 3001 | 采集管理台（平台能力中心）|
| Edge Nginx | `data_achieve_scrapy_edge` | 8080 | 反向代理 |
| PostgreSQL | `data_achieve_scrapy_db` | 5432 | postgres:16 |

## 本地开发

```bash
cp .env.example .env
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local

# 启动 PostgreSQL
bash scripts/dev-start.sh --migrate

# 后端
cd apps/api && uv sync
uv run uvicorn data_intelligence_hub.main:app --reload --host 0.0.0.0 --port 8000

# 主 Web
cd apps/web && pnpm install && pnpm dev

# 采集管理台
cd apps/scraper-console && pnpm install && pnpm dev
```

默认端口：API `8000` · OpenAPI `8000/docs` · Web `3000` · Console `3001`

## 环境变量

| 变量 | 用途 | 存放位置 |
|---|---|---|
| `TIKHUB_API_KEY` | TikHub 社媒采集 API | `apps/api/.env` + `.env.production` |
| `APIFY_API_TOKEN` | Apify Actor 调用令牌 | `apps/api/.env` + `.env.production` |
| `SCRAPY_POSTGRES_*` | 数据库连接 | `.env.production` |
| `SCRAPY_JWT_SECRET` | JWT 签名密钥 | `.env.production` |

## 质量检查

```bash
# 后端
cd apps/api
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run alembic heads

# 前端
cd apps/web && pnpm lint && pnpm test && pnpm build
cd apps/scraper-console && pnpm tsc --noEmit
```

## 生产部署

SSH 登录：

```bash
ssh -i DDDD.pem ubuntu@101.34.52.232
```

完整重建（推荐）：

```bash
cd /opt/data-achieve-scrapy/app
git pull origin codex/social-api-private-matrix-20260708
docker compose -f configs/deploy/scrapy/docker-compose.yml \
  --env-file /opt/data-achieve-scrapy/.env.production \
  up --build --no-deps --detach api console
```

热更新（紧急修复用，下次正式构建前必须完整重建）：

```bash
# 本地传文件
cat apps/api/src/data_intelligence_hub/api/routes/collectors.py | \
  ssh -i DDDD.pem ubuntu@101.34.52.232 "cat > /tmp/collectors.py"
ssh -i DDDD.pem ubuntu@101.34.52.232 \
  "docker cp /tmp/collectors.py data_achieve_scrapy_api:/app/src/data_intelligence_hub/api/routes/collectors.py && docker restart data_achieve_scrapy_api"
```

验收：

```bash
curl -fsSL https://scrapy.lute-tlz-dddd.top/api/health
curl -fsSL https://scrapy.lute-tlz-dddd.top/api/collectors/catalog | python3 -c "
import sys, json
d = json.load(sys.stdin)
groups = d.get('collectors', [])
v = sum(1 for g in groups for e in g.get('endpoints', []) if e.get('status') == 'verified')
t = sum(len(g.get('endpoints', [])) for g in groups)
print(f'total={t}  verified={v}')
"
# 期望：total=148  verified=137
```

## 远端 CI

- `.github/workflows/ci.yml` 在 push/PR 到 `main` 时运行
- 当前工作分支 `codex/social-api-private-matrix-20260708` 无 CI dispatch；本地绿色 ≠ CI 绿色


| 项目 | 状态 |
|---|---|
| 生产域名 | `scrapy.lute-tlz-dddd.top` |
| 服务器 | `101.34.52.232` (VM-0-16-ubuntu, Ubuntu 22.04) |
| 当前分支 | `codex/social-api-private-matrix-20260708` |
| 当前 commit | `c7167b17` |
| API schema | `202607160033` (current) |
| 采集端点 | **91 verified / 0 pending / 11 disabled** |
| 容器状态 | api / web / console / edge / db 全部 healthy |

### 已上线采集能力

| 采集器组 | 端点数 | 代表平台 |
|---|---|---|
| TikHub Social | 12 | TikTok / Instagram / 小红书 / YouTube / Reddit / X |
| Apify 社交 | 10 | Instagram / Facebook / TikTok / YouTube / X / Reddit |
| Apify 电商 & 评价 | 15 | Amazon / Walmart / Temu / SHEIN / AliExpress / TikTok Shop 等 |
| Apify Google 生态 | 6 | Google Search / Maps / Trends / News / AI Overviews |
| Apify AI 搜索 | 3 | ChatGPT / Perplexity / Gemini |
| Apify 广告情报 | 5 | Meta Ads / Google Ads / TikTok Ads / Snap Ads / Pinterest Ads |
| Apify B2B & 内容 | 10 | LinkedIn / Threads / Pinterest / Glassdoor / HN 等 |
| Apify PR 媒体 | 11 | Google News + 多平台账号监测 |
| Apify 通用爬取 | 3 | Website Crawler / Web Scraper / RAG Browser |
| GitHub | 5 | GitHub REST API |
| RSS / 公开网页 | 11 | RSS + Web Snapshot |

> 详细端点说明见 [平台数据采集手册](docs/workflows/workflow-platform-collection-playbook-stable.md)

## 文档入口

- 平台采集手册（最新）：[docs/workflows/workflow-platform-collection-playbook-stable.md](docs/workflows/workflow-platform-collection-playbook-stable.md)
- 当前产品 PRD V2.0：[docs/product/product-prd-social-media-automation-platform-v2.md](docs/product/product-prd-social-media-automation-platform-v2.md)
- V2.0 需求追踪账本：[docs/product/product-prd-social-media-automation-platform-v2-traceability.md](docs/product/product-prd-social-media-automation-platform-v2-traceability.md)
- V2.0 总体设计：[docs/superpowers/specs/2026-07-10-social-media-automation-platform-v2-design.md](docs/superpowers/specs/2026-07-10-social-media-automation-platform-v2-design.md)
- 技术架构：[docs/architecture/architecture-data-intelligence-hub-stable.md](docs/architecture/architecture-data-intelligence-hub-stable.md)
- API 合同：[docs/api/api-contract-data-intelligence-hub-stable.md](docs/api/api-contract-data-intelligence-hub-stable.md)
- 本地开发流程：[docs/workflows/workflow-development-setup-stable.md](docs/workflows/workflow-development-setup-stable.md)
- 发布与回滚清单：[docs/workflows/workflow-release-rollback-stable.md](docs/workflows/workflow-release-rollback-stable.md)
- Demo 数据治理：[docs/workflows/workflow-demo-data-governance-stable.md](docs/workflows/workflow-demo-data-governance-stable.md)
- 真实 API E2E 策略：[docs/workflows/workflow-real-e2e-strategy-stable.md](docs/workflows/workflow-real-e2e-strategy-stable.md)

## 应用服务

| 服务 | 容器 | 说明 |
|---|---|---|
| API | `data_achieve_scrapy_api` | FastAPI，端口 8000 |
| Web | `data_achieve_scrapy_web` | Next.js 主产品，端口 3000 |
| Scraper Console | `data_achieve_scrapy_console` | 采集管理台，端口 3001 |
| Edge Nginx | `data_achieve_scrapy_edge` | 反向代理，8080 → api/console |
| PostgreSQL | `data_achieve_scrapy_db` | postgres:16 |

## 本地开发

复制环境变量样例：

```bash
cp .env.example .env
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
```

启动 PostgreSQL：

```bash
bash scripts/dev-start.sh
```

启动 PostgreSQL 并运行迁移：

```bash
bash scripts/dev-start.sh --migrate
```

启动后端：

```bash
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn data_intelligence_hub.main:app --reload --host 0.0.0.0 --port 8000
```

启动前端（主 Web）：

```bash
cd apps/web
pnpm install
pnpm dev
```

启动采集管理台（Scraper Console）：

```bash
cd apps/scraper-console
pnpm install
pnpm dev
```

默认端口：

| 服务 | 地址 |
|---|---|
| API | `http://localhost:8000` |
| OpenAPI | `http://localhost:8000/docs` |
| Web | `http://localhost:3000` |
| Scraper Console | `http://localhost:3001` |
| PostgreSQL | `localhost:5432` |

## 环境变量（关键）

| 变量 | 用途 | 存放位置 |
|---|---|---|
| `TIKHUB_API_KEY` | TikHub 社媒采集 API 密钥 | `apps/api/.env` + `/opt/data-achieve-scrapy/.env.production` |
| `APIFY_API_TOKEN` | Apify Actor 调用令牌 | `apps/api/.env` + `/opt/data-achieve-scrapy/.env.production` |
| `SCRAPY_POSTGRES_*` | 数据库连接 | `/opt/data-achieve-scrapy/.env.production` |
| `SCRAPY_JWT_SECRET` | JWT 签名密钥 | `/opt/data-achieve-scrapy/.env.production` |

## 质量检查

后端：

```bash
cd apps/api
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run alembic heads
```

前端：

```bash
cd apps/web
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
```

## 生产部署

> 详细步骤见 [发布与回滚清单](docs/workflows/workflow-release-rollback-stable.md)

SSH 登录服务器：

```bash
ssh -i DDDD.pem ubuntu@101.34.52.232
```

拉取最新代码并重建 API 容器：

```bash
cd /opt/data-achieve-scrapy/app
git pull origin codex/social-api-private-matrix-20260708
docker compose -f configs/deploy/scrapy/docker-compose.yml \
  --env-file /opt/data-achieve-scrapy/.env.production \
  up --build --no-deps --detach api
```

验收：

```bash
curl -fsSL https://scrapy.lute-tlz-dddd.top/api/health
curl -fsSL https://scrapy.lute-tlz-dddd.top/api/collectors/catalog | python3 -c "
import sys, json
d = json.load(sys.stdin)
groups = d.get('collectors', [])
v = sum(1 for g in groups for e in g.get('endpoints', []) if e.get('status') == 'verified')
print(f'verified={v}')
"
# 期望：verified=91
```

> ⚠️ **热更新注意**：若 Docker build 超时，可用 `docker cp` 热替换文件后 `docker restart`，
> 但必须在下次正式部署时完成完整镜像重建，否则容器重建会回退到旧镜像代码。

## 远端 CI

- `.github/workflows/ci.yml` 在 push / pull request 到 `main` 时运行。
- API job：real-API E2E fail-closed guard → ruff → mypy → pytest → alembic heads。
- Workflow Planner PostgreSQL job：一次性 PostgreSQL 15 service database，migration/constraint/persistence gate。
- Web job：lint → test → build → test:e2e。
- 当前工作分支 `codex/social-api-private-matrix-20260708` 没有 dispatch CI；本地绿色不等于 CI 绿色。
