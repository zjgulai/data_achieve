---
title: 控制台能力实测与坑点沉淀
doc_type: workflow
module: operations
topic: console-capability-live-verification
status: stable
created: 2026-10-09
updated: 2026-10-09
owner: self
source: human+ai
---

# 控制台能力实测与坑点沉淀

把 `scrapy.luteos.com` 的"声明能力"变成"实测结论"，并把发现的坑点沉淀进 Skill/Playbook/MCP 与控制台。
能力清单见 [能力图谱](../architecture/【能力图谱】DIH-控制台能力地图.md)，通过标准见 [测试计划](../playbooks/【测试计划】DIH-平台采集生产实测.md)。

## 前置

- 工作分支基于生产分支：`git checkout -b <branch> deploy/scrapy-luteos-rebuild`。
- 本地跑单测需要 `apps/api/.venv`（`uv sync`）与一份 Postgres：
  ```
  docker run -d --name dih-test-pg -e POSTGRES_USER=data_intel -e POSTGRES_PASSWORD=dev_password \
    -e POSTGRES_DB=data_intel -p 5432:5432 postgres:16
  cd apps/api && .venv/bin/python -m alembic upgrade head
  ```
- 需要一个 demo 项目的 UUID 作为 quick-collect 的归属：`curl <base>/api/projects | jq '.[0].id'`。

## 步骤

### 1. 枚举页面与端点

- 页面：读 `apps/scraper-console/src/app/**/page.tsx` 与 `components/layout/sidebar.tsx`，对照线上导航（含 `target=_blank` 外链）。
- 端点：`curl <base>/api/collectors/catalog`，按 `collector_type` 分组、按 `endpoint_type` 去重。

### 2. 冒烟

```
curl -fsS <base>/api/health
curl -fsS <base>/api/collectors/catalog | jq '.collectors|length'
curl -fsS <base>/api/collectors/docs | jq '{total_endpoints,tested_endpoints,success_endpoints}'
curl -fsS <base>/api/platform-packages | jq '{platform_count,capability_count,unique_endpoint_count}'
curl -fsS "<base>/api/platform-packages/tiktok/download" -o /tmp/tiktok.zip && unzip -l /tmp/tiktok.zip
```
> `/api/collectors/docs` 的 `tested_endpoints=0` 说明平台还没有任何实测记录——这正是要改的。

### 3. 全量实测

```
python scripts/verify_platform_live.py --base-url <base> --project-id <uuid> \
  --delay 0.3 --concurrency 6 --timeout 180 [--resume]
```
- 先 `--dry-run` 校端点集合与是否缺演示参数。
- 结果在 `reports/live-sweep/latest.{json,md}`；按 `failure_class` 汇总。
- 中断可加 `--resume` 续跑（已 ok 跳过）。

### 4. 分流修复

按 [测试计划 §3](../playbooks/【测试计划】DIH-平台采集生产实测.md) 的分类决定改环境/镜像/代码/文档。
**改任何函数前先评估影响面**（本项目未挂 GitNexus 时用 `grep -rn <symbol> apps/api/src` 手工枚举调用点），改完跑相关单测。

### 5. 沉淀坑点（单一事实源）

1. 在 `apps/api/src/data_intelligence_hub/platform_packages/notes/<platform_id>.json` 增/改一条：
   ```json
   {"scope":"platform|endpoint","target":"<platform_id|endpoint_type>",
    "symptom":"...","cause":"...","workaround":"...",
    "failure_class":"config_gated","severity":"blocker","verified_at":"YYYY-MM-DD",
    "source_ref":"reports/live-sweep/latest.json","tags":["..."]}
   ```
   > `target` 必须是**真实 platform_id**（例如 Exa 端点的 platform 是 `web`，不是 `exa`）。
   > 禁止写入真实密钥；占位符 `XXX_API_KEY=...` 允许。
2. 重新生成并同步 lock：
   ```
   cd apps/api && .venv/bin/python ../../scripts/generate_platform_packages.py --update-lock
   .venv/bin/python ../../scripts/test_platform_packages.py
   ```
   坑点会渲染进 `SKILL.md` / `README.md` / `references/playbook.md` / `docs/playbooks/platforms/*.md`，
   并汇总到 `docs/playbooks/【坑点库】DIH-平台采集坑点汇总.md`。

### 6. 发布

生产实际形态（2026-10-09 实测）：`scrapy.luteos.com` → `43.163.92.244`，仓库在 **`/opt/data-achieve-scrapy/app`**，
env 文件在 **`/opt/data-achieve-scrapy/.env.production`**，compose 项目目录 `configs/deploy/scrapy`。

```bash
# 服务器上
cd /opt/data-achieve-scrapy/app
git fetch origin <branch> && git reset --hard FETCH_HEAD   # 别用 fetch 到当前分支（会 Refusing）
cd configs/deploy/scrapy
ENV=/opt/data-achieve-scrapy/.env.production
docker compose --env-file "$ENV" build api console
docker compose --env-file "$ENV" up -d api console
docker compose --env-file "$ENV" restart edge        # ⚠️ 必须，见下
```

> **坑 1（必踩）**：`edge` 容器启动时把 `api` 的 IP 解析并缓存住。`up -d api` 会重建 api 容器拿到**新 IP**，
> 但 edge 不会自动重解析 → 外部一律 **502 Bad Gateway**，而容器内 `curl http://api:8000/api/health` 是 200。
> 每次重建 api 后**必须 `restart edge`**。可通过 `docker logs edge` 里 `upstream: "http://172.26.0.6:8000/..."` 的旧 IP 确认。
> **坑 2**：`git fetch origin <branch>:refs/heads/<branch>` 在当前分支上会 `fatal: Refusing to fetch into current branch`；
> 用 `git fetch origin <branch> && git reset --hard FETCH_HEAD`。
> **坑 3**：`pgrep -f "docker compose.*build"` 会匹配到你自己的 SSH 命令行本身 → 误判"还在构建"；用镜像 `Created` 时间戳判断更可靠。
> **坑 4**：quick-collect 的 `project_id` 必须属于 demo workspace。传一个**已不存在**的 project id（例如此前扫描用的 demo id 被删掉后）会撞 `sources.project_id` 外键 → 500 + 原始 SQL 栈。
> 2026-10-09 已改为 400 `Unknown project_id`；扫描前先 `curl $B/api/projects | jq '.[].id'` 取一个真实 id，别硬编码。
> **坑 5**：本地 `.venv` 是 **editable 安装**，可能指向另一个检出（`python -c "import data_intelligence_hub as m; print(m.__file__)"` 可确认）。
> 在 worktree 里跑 `python ../scripts/*.py` 时 `sys.path[0]` 是脚本目录而非 `src`，载入的可能是**别的检出的代码** → 生成/契约测试结果全部无效。
> 必须显式 `PYTHONPATH=<worktree>/apps/api/src`。（`pytest` 不受影响：`pyproject.toml` 里有 `pythonpath=["src"]`。）
> **坑 6（Apify）**：Actor 的 `inputSchema` 是 `additionalProperties:false` —— 缺一个必填键或**多一个未知键**都整单 400。
> 扫描脚本的演示参数（`scripts/collector_demo_params.py`）与 `_APIFY_ENDPOINT_DEFAULTS` 是两份，容易各写各的。
> 报 `Field input.X is required` 或 `Property input.X is not allowed` 时，先取 schema 对照，别猜。
> **坑 7（Apify）**：quick-collect 的 Apify 分支只把 `maxItems` / `max_items` / `max_total_charge_usd` / `run_timeout_seconds`
> 当采集开关（`_APIFY_META_KEYS`）；其余入参一律透传。曾把 `query`/`url`/`keyword`/… 也列进黑名单，
> 导致 `apify_rag_web_browser` 收到的 `query` 被静默丢掉，上游报"必填 query 缺失"。
> **坑 8（Apify）**：`http_forbidden` 403 **不等于反爬**。先看 TaskRun 耗时：**<2 秒**的 403 来自
> `POST /acts/<id>/runs`，连 Apify run 都没创建（Actor 已下架或拒绝本账号运行），换参数/加代理都没用；
> 耗时长才是上游站点反爬。

发布后自检：

```bash
B=https://scrapy.luteos.com
curl -s $B/api/health
curl -s $B/api/collectors/docs | python3 -m json.tool | head      # tested_endpoints 应 > 0
curl -s $B/api/platform-packages | python3 -c 'import json,sys;print(json.load(sys.stdin)["catalog_digest"])'
curl -s $B/api/platform-packages/web/playbook | grep -c 坑点与规避
curl -s -o /dev/null -w '%{http_code}\n' $B/mcp/                  # 无 token → 401
```


## Apify Actor 巡检（免额度，必须先跑）

全量实测之前先做一遍 Actor 存活巡检：**不产生 run、不消耗额度**，但能提前过滤掉一大类
必然失败的端点。用 `scripts/verify_platform_live.py` 扫到的失败里，Apify 的 403 有一部分
就是这么来的。

```bash
# 1) Actor 是否存在 / 是否被废弃（免鉴权）
curl -s "https://api.apify.com/v2/acts/<user>~<name>" | python3 -c \
  'import json,sys; d=json.load(sys.stdin)["data"]; print(d["title"], d["isDeprecated"], d["stats"]["totalRuns"])'

# 2) 取真实 inputSchema（必填/可选/枚举/默认值全在里面，同样免鉴权）
curl -s "https://api.apify.com/v2/acts/<user>~<name>/builds/default" | python3 -c \
  'import json,sys; s=json.load(sys.stdin)["data"]["inputSchema"]; print(json.dumps(json.loads(s)["properties"], ensure_ascii=False, indent=1))'

# 3) 找替代 Actor（按关键词搜 Store，返回 totalRuns / 近 30 天活跃用户）
curl -s "https://api.apify.com/v2/store?search=linkedin%20profile%20scraper&limit=5"
```

判据：
- `record-not-found` / `page-not-found` → Actor 已下架，对应的 endpoint_type 必须改指。
- `isDeprecated=true` → 立刻排期替换，不要等它彻底下线。
- `stats.totalUsers30Days == 0` → 高风险（无人维护），降级为备选。
- `exampleRunInput` 常是 `{"helloWorld":123}` 占位，**不能**当作入参示例；入参以 `inputSchema` 为准。

> 更新 endpoint 时三处都要动，否则文档与运行不一致：
> `_APIFY_ENDPOINT_DEFAULTS`（真实 actor_id + 缺省入参）、
> `scripts/collector_demo_params.py`（扫描用演示参数）、
> `api/routes/collectors.py` 的 `provider` / `required_params`（控制台与文档展示）。

## 收尾

- `reports/live-sweep/` 是本地产物，不入库（已在 `.gitignore`）。
- 提交前 `git status` 确认没有 `*.key` / `*.pem` / `.env`。
- 把 §2 的 `tested_endpoints` 与 §3 的 `summary` 回填进 [能力图谱](../architecture/【能力图谱】DIH-控制台能力地图.md)。

## 待配 Provider 密钥清单（2026-10-09）

从采集器读取的环境变量（`grep -rhoE '(getenv|environ)\(\s*"[A-Z0-9_]+"' apps/api/src`）减去服务器
`/opt/data-achieve-scrapy/.env.production` 已配置项，得到的缺口。**配齐前，对应端点只能是
`config_gated`，不是代码缺陷。**

### 需要提供密钥值（写进 `.env.production` 后 `up -d api`）

| 变量 | 影响 | 说明 |
|---|---|---|
| `EXA_API_KEY` | 平台 `web` 的 20 个 Exa 端点 | 缺它时 `exa_*` 全部 config_gated |
| `FIRECRAWL_API_KEY` | `firecrawl_crawl` / `_extract` / `_batch_scrape` | 可选 `FIRECRAWL_BASE_URL` |
| `ANYCRAWL_API_KEY` | AnyCrawl 系列 | 可选 `ANYCRAWL_BASE_URL` |
| `BESTBLOGS_API_KEY` | `bestblogs_articles` | |
| `GITHUB_TOKEN`（或 `GH_TOKEN`） | `github_repo` / `github_topic` | 无 token 也能跑，但会撞限流 |
| `TWITTER_ACCOUNTS_JSON` | `twscrape_*` | 也支持 `TWITTER_ACCOUNTS_FILE` / `TWITTER_DB_PATH` |
| `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY` | `browser_use_task` | 需配 `BROWSER_USE_LLM_PROVIDER` |

### 需要基础设施地址（不是密钥）

| 变量 | 影响 |
|---|---|
| `SPIDERFOOT_BASE_URL` | spiderfoot 各 endpoint（`container_missing` 的来源之一） |
| `MEDIACRAWLER_BASE_URL` | mediacrawler |
| `BLACKBIRD_BASE_URL` | blackbird OSINT |
| `OBSCURA_CDP_URL` | 浏览器 CDP 复用 |
| `HTTP_PROXY` / `HTTPS_PROXY` / `OSINT_PROXY` / `TOR_PROXY_URL` | `network_proxy` 类失败（直连被墙的站点，如 weibo/baidu/bing） |

> 服务器上**已经**配置的：`TIKHUB_API_KEY`、`APIFY_API_TOKEN`、`ANYSEARCH_API_KEY`、`JINA_API_KEY`、
> `MAIGRET_URL`、`PROXY_ROTATOR_*`。`PLATFORM_CREDENTIAL_MASTER_KEY` 是凭据加密主密钥，不要更换
> （换了会解不开 `/settings/credentials` 已存的凭据）。
