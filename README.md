# Data Intelligence Hub — 数据采集平台

面向品牌和市场运营团队的多平台数据采集管理台。通过统一 API、平台 Skill 和共享 MCP Runtime 调用 278 个能力视图（250 个唯一 endpoint），结果落库为 RawRecord。

## 生产状态（2026-10-09）

| 项目 | 状态 |
|---|---|
| 生产域名 | `https://scrapy.luteos.com` |
| 应用服务器 | `192.168.204.230`（内网）|
| 公网入口 | `43.163.92.244` → 受限 SSH 反向隧道 |
| 当前分支 | `codex/social-api-private-matrix-20260708` |
| 采集目录 | **74 平台 / 278 能力视图 / 250 唯一 endpoint** |
| Skill/MCP | `/skills`、`/mcp/`、平台 ZIP 下载 |
| 容器状态 | api / console / edge / db / maigret healthy |
| 认证 | 全路由无需登录，使用 demo workspace fallback |

## 应用服务

| 服务 | 容器 | 端口 | 说明 |
|---|---|---|---|
| API | `data_achieve_scrapy_api` | 8000 | FastAPI 后端，所有采集逻辑 |
| Scraper Console | `data_achieve_scrapy_console` | 3001 | 采集管理台（平台能力中心）|
| Edge Nginx | `data_achieve_scrapy_edge` | 8080 | 反向代理 |
| PostgreSQL | `data_achieve_scrapy_db` | 5432 | postgres:16 |

> `apps/web`（洞察面板）已从生产路由移除（commit `241910c`），代码保留但容器不部署。

## 采集能力总览（162 端点）

| 采集器组 | 方法 | verified | 代表平台 |
|---|---|---|---|
| TikHub Social | tikhub | 45 | TikTok / Instagram / 小红书 / YouTube / Reddit / X / Threads / LinkedIn / Lemon8 |
| Apify Actor | apify | 75 | 社交/电商/评价/广告/B2B/AI搜索/通用爬取 |
| GitHub | github_api | 2 | GitHub Repo / Topics |
| RSS / Web | rss + web_crawl | 15 | RSS 订阅源 + Web 快照 |
| 浏览器采集 | browser | 3 | Playwright text/html/screenshot |
| 电商独立站 | web_crawl | 2 | 通用电商商品页 |
| 监管公告 | rss | 4 | FDA / UK OPSS / UK NHS / PR Newswire |
| AnySearch | anysearch | 2 | 品牌媒体搜索 / 竞品搜索 |
| Jina Reader | jina_reader | 3 | 页面转 Markdown（需代理） |

**数据类型（17种）**：post · comment · account · product · review · ad · job · trend · ai_answer · news · web_page · repo · feed · search · search_result · web_page_markdown · recall_notice

## 项目结构

```
data_scrapy/
├── apps/
│   ├── api/                          # FastAPI 后端
│   │   └── src/data_intelligence_hub/
│   │       ├── collectors/           # ★ 采集器实现（新增采集卡片从这里开始）
│   │       ├── api/routes/
│   │       │   ├── collectors.py     # ★ catalog 端点定义
│   │       │   └── quick_collect.py  # ★ quick_collect 端点映射
│   │       └── services/
│   │           └── collector_catalog.py  # ★ CollectorDefinition + validate
│   ├── scraper-console/              # Next.js 采集管理台
│   │   └── src/app/platforms/page.tsx  # ★ 前端卡片渲染（平台 Logo / 分类）
│   └── web/                          # 洞察面板（未在生产部署）
├── configs/deploy/scrapy/
│   ├── docker-compose.yml            # 生产容器编排
│   └── edge-nginx.conf               # Nginx 路由
├── docs/
│   ├── api/                          # API 合同
│   ├── architecture/                 # 架构设计
│   └── workflows/                    # 开发/部署/采集 SOP
└── opendesign/design-systems/        # 设计 token + DESIGN.md
```

## 新增采集卡片流程（5步）

1. **新建 collector**：`apps/api/src/data_intelligence_hub/collectors/<name>.py`
   - 继承 `BaseCollector`，实现 `async collect() -> CollectionResult`
   - 返回 `CollectionResult(raw_records=[...], errors=[])`

2. **注册 collector**：`collectors/registry.py`
   ```python
   from .your_collector import YourCollector
   COLLECTOR_REGISTRY["your_collector"] = YourCollector
   ```

3. **加 catalog 定义**：`api/routes/collectors.py`
   ```python
   CollectorEndpoint(
       endpoint_type="your_endpoint",
       label="...", platform="...", method="your_method",
       content_type="...", status="verified",
       required_params=["param1"], ...
   )
   ```

4. **加 quick_collect 映射**：`api/routes/quick_collect.py`
   ```python
   "your_endpoint": ("your_collector", {"key": "params_key"}),
   ```

5. **加 validate 函数**：`services/collector_catalog.py`
   ```python
   def _validate_your_config(params): ...
   ```

6. **前端加平台 Logo**（如有新平台）：`apps/scraper-console/src/app/platforms/page.tsx`
   - 在 `PLATFORM_LOGOS` 加 `{ bg: "#...", fg: "#fff", letter: "XX" }`
   - 在 `PLATFORM_GROUP_META` 的对应分组 `platforms[]` 加平台名

7. **部署**：热推或完整重建（见下方）

## 部署

当前标准部署目标为内网服务器 `192.168.204.230`，公网通过
`scrapy.luteos.com` 的受限反向隧道访问。旧域名仅保留兼容。

### 正式发布（当前生产）

```bash
ssh lute@192.168.204.230
cd ~/apps/data_scrapy
git pull origin codex/social-api-private-matrix-20260708
docker compose -f configs/deploy/scrapy-new/docker-compose.yml \
  --env-file /data/scrapy/configs/.env.production \
  up --build --no-deps --detach api console
```

### 验收

```bash
curl -fsSL https://scrapy.luteos.com/api/health
curl -fsSL https://scrapy.luteos.com/api/platform-packages | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d['platform_count'], d['capability_count'], d['unique_endpoint_count'])
"
# 期望：74 278 250
```

## 本地开发

```bash
# 环境变量
cp .env.example .env
cp apps/api/.env.example apps/api/.env

# 后端
cd apps/api && uv sync
uv run uvicorn data_intelligence_hub.main:app --reload --port 8000

# 采集管理台
cd apps/scraper-console && pnpm install && pnpm dev
# → http://localhost:3001
```

**关键环境变量**

| 变量 | 用途 |
|---|---|
| `TIKHUB_API_KEY` | TikHub 社媒采集 |
| `APIFY_API_TOKEN` | Apify Actor 调用 |
| `ANYSEARCH_API_KEY` | AnySearch 搜索 API |
| `JINA_API_KEY` | Jina Reader（国内需代理）|
| `SCRAPY_POSTGRES_*` | 数据库连接 |

## 文档

| 文档 | 用途 |
|---|---|
| [API 合同](docs/api/api-contract-data-intelligence-hub-stable.md) | 所有 API 端点规范 |
| [架构设计](docs/architecture/architecture-data-intelligence-hub-stable.md) | 系统架构 |
| [平台采集手册](docs/workflows/workflow-platform-collection-playbook-stable.md) | 所有端点参数与示例 |
| [发布与回滚](docs/workflows/workflow-release-rollback-stable.md) | 生产部署 SOP |
| [本地开发](docs/workflows/workflow-development-setup-stable.md) | 开发环境搭建 |
| [设计系统](opendesign/design-systems/data-intelligence-product/DESIGN.md) | UI token + 规范 |

## 质量检查

```bash
# 后端
cd apps/api && uv run ruff check . && uv run mypy src && uv run pytest && uv run alembic heads

# 前端
cd apps/scraper-console && pnpm tsc --noEmit && pnpm build
```
