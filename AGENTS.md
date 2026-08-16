# Data Intelligence Hub — Agent 工作指南

> 最后更新：2026-08-16 · commit `b339f45` · 分支 `codex/social-api-private-matrix-20260708`

## 项目一句话定位

**纯数据采集平台**。后端 FastAPI 提供 162 种采集能力（tikhub/apify/rss/browser/anysearch/jina），前端 Next.js scraper-console 提供无需登录的采集管理台，生产部署在 `scrapy.lute-tlz-dddd.top`。

---

## 生产环境

| 项目 | 值 |
|---|---|
| 域名 | `scrapy.lute-tlz-dddd.top` |
| 服务器 IP | `101.34.52.232` |
| SSH key | `DDDD.pem`（项目根目录，**不得 commit**）|
| 部署分支 | `codex/social-api-private-matrix-20260708` |
| 当前 commit | `b339f45` |
| API health | `GET /api/health` → `{"status":"ok"}` |
| 采集端点 | 151 verified / 11 disabled（总 162）|
| 认证模式 | **无需登录**，全路由使用 demo workspace `bf51c6a8-fba5-5528-ac91-89ffd84f85c2` |

### 容器

| 容器名 | 镜像 | 端口 |
|---|---|---|
| `data_achieve_scrapy_api` | `data_achieve_scrapy_api:latest` | 8000 |
| `data_achieve_scrapy_console` | `data_achieve_scrapy_console:latest` | 3001 |
| `data_achieve_scrapy_edge` | `nginx:1.27-alpine` | 8080 |
| `data_achieve_scrapy_db` | `postgres:16` | 5432 |

> `apps/web`（洞察面板）代码存在但**未在生产部署**，nginx 路由已移除（commit `241910c`）。

---

## 代码结构（只需关注这几个文件）

```
apps/api/src/data_intelligence_hub/
├── collectors/                   ★ 采集器实现
│   ├── base.py                   — BaseCollector 基类
│   ├── registry.py               ★ COLLECTOR_REGISTRY 注册表
│   ├── tikhub_social.py          — TikHub 45 端点
│   ├── apify_actor.py            — Apify 75 端点
│   ├── public_feed.py            — RSS + Web crawl
│   ├── github_repo.py / github_topic.py
│   ├── playwright_browser.py     — 浏览器采集（text/html/screenshot）
│   ├── ecommerce_product_page.py / ecommerce_product_discovery.py
│   ├── anysearch_collector.py    — AnySearch API
│   └── jina_reader.py            — Jina Reader（需代理）
├── api/routes/
│   ├── collectors.py             ★ catalog 端点 + CollectorEndpoint 定义
│   └── quick_collect.py          ★ _ENDPOINT_TO_COLLECTOR 映射
└── services/
    └── collector_catalog.py      ★ CollectorDefinition + _validate_* 函数

apps/scraper-console/src/app/
├── platforms/page.tsx            ★ 前端卡片渲染（PLATFORM_LOGOS / 分类 / 方法）
├── dashboard/                    — 采集概览
├── projects/                     — 项目管理
├── tasks/                        — 任务列表
├── runs/                         — 采集记录
├── raw-records/                  — 原始数据
└── datasets/                     — 数据集

configs/deploy/scrapy/
├── docker-compose.yml            ★ 生产容器编排（含 API keys env）
└── edge-nginx.conf               — Nginx 路由
```

---

## 当前任务状态

### 已完成（生产可用）

| 任务 | commit | 状态 |
|---|---|---|
| D4 监管 RSS（FDA/NHS/OPSS/PR Newswire）| `8d462e8` | ✅ verified×4 |
| D5 AnySearch 采集器 | `7e8468a` | ✅ verified×2，records=10 |
| D1 Jina Reader 采集器 | `ca8b647` | ✅ verified×3，本地 OK，生产需代理 |
| 平台能力中心 UI 重设计 | `e59cbcc` | ✅ 去 emoji，PlatformLogo，工业质感行布局 |
| 项目减负 | `b339f45` | ✅ git 干净，分支精简，文档更新 |

### 未完成 / 待处理

| 任务 | 说明 | 优先级 |
|---|---|---|
| Jina Reader 生产网络 | 服务器 IP 直连 `r.jina.ai` 超时，需配代理或中转 | 中 |
| D2 Shopee | 生产 IP 被封（HTTP 403），暂不可行 | 取消 |
| B1 Reddit collector | **永久取消**（用户明确要求）| 取消 |
| B2 YouTube collector | **永久取消**（用户明确要求）| 取消 |

### 下一步可做的事

- 新增更多平台采集卡片（参考「新增采集卡片流程」）
- 配置 Jina Reader 代理（在 docker-compose.yml 加 `HTTP_PROXY` 环境变量）
- 生产完整重建（当前是热更新状态，下次正式发布需 `docker compose up --build`）

---

## 新增采集卡片流程（5 步）

### Step 1：新建 collector

```python
# apps/api/src/data_intelligence_hub/collectors/your_collector.py
from .base import BaseCollector, CollectionResult, RawRecord

class YourCollector(BaseCollector):
    async def collect(self) -> CollectionResult:
        # self.config 包含前端传入的参数
        url = self.config.get("url", "")
        # ... 实现采集逻辑
        record = RawRecord(content={"key": "value"}, metadata={})
        return CollectionResult(raw_records=[record], errors=[])
```

### Step 2：注册

```python
# collectors/registry.py
from .your_collector import YourCollector
COLLECTOR_REGISTRY["your_collector"] = YourCollector
```

### Step 3：加 catalog 端点

```python
# api/routes/collectors.py — 在对应 group 的 endpoints 列表里加：
CollectorEndpoint(
    endpoint_type="your_endpoint_name",
    label="端点显示名称",
    platform="platform_key",      # 对应 PLATFORM_LOGOS 的 key
    description="采集内容说明",
    method="your_method",          # 对应 METHOD_META 的 key
    content_type="web_page",       # 对应 CONTENT_TYPE_META 的 key
    status="verified",
    required_params=["url"],
    optional_params=[],
    cost_hint=None,
    provider="your_provider",
)
```

### Step 4：加 quick_collect 映射

```python
# api/routes/quick_collect.py — 在 _ENDPOINT_TO_COLLECTOR 加：
"your_endpoint_name": ("your_collector", {"url": "url"}),
```

### Step 5：加 validate 函数

```python
# services/collector_catalog.py
def _validate_your_config(params: dict) -> dict:
    url = params.get("url", "").strip()
    if not url:
        raise ValueError("url is required")
    return {"url": url}
```

### Step 6（可选）：前端加平台 Logo

```typescript
// apps/scraper-console/src/app/platforms/page.tsx
// 在 PLATFORM_LOGOS 加：
your_platform: { bg: "#XXXXXX", fg: "#fff", letter: "XX" },

// 在 PLATFORM_GROUP_META 对应分组的 platforms[] 加平台名：
open_web: { ..., platforms: [..., "your_platform"] },
```

### Step 7：热推部署

```bash
# API 热推
scp -i DDDD.pem apps/api/src/data_intelligence_hub/collectors/your_collector.py \
  ubuntu@101.34.52.232:/tmp/your_collector.py
ssh -i DDDD.pem ubuntu@101.34.52.232 \
  "docker cp /tmp/your_collector.py \
   data_achieve_scrapy_api:/app/src/data_intelligence_hub/collectors/your_collector.py \
   && docker restart data_achieve_scrapy_api"

# 验收
curl https://scrapy.lute-tlz-dddd.top/api/collectors/catalog | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  [print(e['endpoint_type'],e['status']) for g in d['collectors'] \
  for e in g['endpoints'] if 'your_endpoint' in e['endpoint_type']]"
```

---

## 关键约束（不可违反）

- `provider_call=false` — 不得直接调用第三方 Provider API，只通过 collector 抽象层
- B1(Reddit) / B2(YouTube) collector **永远不做**
- D2(Shopee) **取消**，服务器 IP 被封
- 热更新后必须在下次正式发布时完整重建镜像，否则 `docker compose up --build` 会回退
- 不得 commit `DDDD.pem`、`.env.production`、API keys

---

## 部署操作

### SSH 登录

```bash
ssh -i DDDD.pem ubuntu@101.34.52.232
```

### 完整重建（code 已 push 后）

```bash
cd /opt/data-achieve-scrapy/app
git pull origin codex/social-api-private-matrix-20260708
docker compose -f configs/deploy/scrapy/docker-compose.yml \
  --env-file /opt/data-achieve-scrapy/.env.production \
  up --build --no-deps --detach api console
```

### 健康检查

```bash
curl -fsSL https://scrapy.lute-tlz-dddd.top/api/health
curl -fsSL https://scrapy.lute-tlz-dddd.top/api/collectors/catalog | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  v=sum(1 for g in d['collectors'] for e in g['endpoints'] if e.get('status')=='verified'); \
  print('verified:', v)"
# 期望：verified: 151
```

---

## 设计规范（改 UI 前必读）

- 设计 token：`opendesign/design-systems/data-intelligence-product/tokens/colors_and_type.css`
- 设计规范：`opendesign/design-systems/data-intelligence-product/DESIGN.md`
- **禁止** emoji 出现在 UI 中（DESIGN.md §10）
- **禁止** 彩色渐变卡片、glassmorphism（DESIGN.md §12）
- 平台图标用 `PlatformLogo` 组件（letter badge），方法/内容类型用 Lucide 图标
- 所有颜色使用 `var(--token-name)`，不得写 raw hex

---

<!-- gitnexus:start -->
## GitNexus — 代码图谱（可选）

项目已被 GitNexus 索引为 **data_achieve**。改动前可用以下工具评估影响：

- `impact({target: "symbolName", direction: "upstream"})` — 评估改动影响范围
- `context({name: "symbolName"})` — 查看符号的调用者/被调用者
- `query({search_query: "concept"})` — 按语义搜索执行流

> GitNexus 索引可能已过时。运行 `node .gitnexus/run.cjs analyze` 刷新。
<!-- gitnexus:end -->
