---
name: data-intelligence-hub-readme
description: Data Intelligence Hub 项目入口文档，介绍产品能力、生产状态、本地开发和文档导航。当首次了解、开发或运维本项目时使用。
---

# Data Intelligence Hub

Data Intelligence Hub 是多平台数据采集工作台。系统通过统一 API、平台 Skill 和共享 MCP Runtime 调用采集能力，将结果保存为 `RawRecord`，并提供项目、任务、运行记录和数据集管理界面。

## 当前生产状态

| 项目 | 当前值 |
|---|---|
| 生产地址 | <https://scrapy.luteos.com>（A 主站）· <https://scrapy.lute-tlz-dddd.top>（B） |
| 平台目录 | 70 个平台（生产 catalog、仓库生成物与工作树三处一致，2026-10-20 核对） |
| 能力视图 | 生产 catalog 311 个（2026-10-21 实测，`catalog_digest=e5169ab2…`）。 |
| 唯一 endpoint | 生产 catalog 283 个（按 `endpoint_type` 去重，2026-10-21 实测）。 |
| 实测状态 | 2026-10-21 生产 `providers/status`，283 个唯一端点：200 个 verified / 57 个 config-gated / 12 个 degraded / 10 个 empty / 3 个 untested / 1 个 disabled |
| 工具目录 | 283 个工具，225 个当前可执行（`GET /api/tool-catalog`，2026-10-21）。 |
| MCP | `https://scrapy.luteos.com/mcp/`，要求 Bearer Token；25 个工具。 |
| 数据库 schema | A=`202610210053`（2026-10-21 `/api/health` 实测）。B 暂缓，未纳入本轮。 |
| 部署分支 | A=`main`。B 按 2026-10-21 指示暂缓。 |

服务器、容器、网络和数据卷的当前事实统一维护在 [生产环境基线](docs/【运维手册】生产环境基线.md)，不要在其他文档复制易变的 revision 或容器状态。

## 产品界面

| 页面 | 路径 | 用途 |
|---|---|---|
| 能力目录 | `/tools` | 按平台、数据类型和 Provider 选择采集能力 |
| 平台详情 | `/tools/[toolId]` | 查看平台 Skill、Playbook、安装包与 MCP 能力 |
| TikTok 工具台 | `/tools/tiktok` | 16 个 TikTok 工具与创作者 Cookie 配置入口 |
| 项目 | `/projects` | 管理采集项目 |
| 任务 | `/tasks` | 管理采集任务和手动运行 |
| 运行记录 | `/runs` | 查看运行状态、记录数和原始结果 |
| 运行详情 | `/runs/[runId]` | 查看步骤、成本、证据等级与原始记录 |
| 资产 | `/assets` | 管理数据集、版本和导出 |
| 原始记录 | `/assets/records` | 浏览原始记录 |
| 文档 | `/docs` | 查看采集器验证状态和参数说明 |
| 监控 | `/monitors` | 查看搜索监控 |
| 用量 | `/usage` | 查看用量与成本 |
| 连接 | `/connect` | 配置平台凭证与登录状态 |

旧路径由 Next.js 永久重定向：`/platforms` 与 `/skills` → `/tools`，`/collector-docs` → `/docs`，`/datasets` → `/assets`，`/raw-records` → `/assets/records`，`/collect/[runId]` → `/runs/[runId]`，`/skills/[platformId]` → `/tools/[platformId]`。

公开目录页面可直接访问。项目数据和管理接口使用 demo workspace 与演示账号机制；生产账号和密码只存在于生产环境变量，不写入仓库。

## 系统组成

```text
Browser
  → shared ai_video_nginx / TLS
  → data_achieve_scrapy_edge
  → data_achieve_scrapy_console 或 data_achieve_scrapy_api
  → data_achieve_scrapy_db
```

主要代码目录：

```text
apps/api/                       FastAPI API、采集器、调度器、Skill/MCP Runtime
apps/scraper-console/           Next.js 采集管理台，生产公网主界面
apps/web/                       保留的洞察应用，生产仅内部运行
configs/deploy/scrapy/          当前生产 Docker Compose 与 edge Nginx
configs/bridges/                SpiderFoot、MediaCrawler 等桥接服务
docs/                           API、架构、运维和采集文档
opendesign/design-systems/      前端设计系统
```

## 本地开发

### 外访安全默认值

本地采集默认 `COLLECTION_NETWORK_MODE=offline`，不发送真实采集请求。
快速采集保持一次性手动任务。扫描器、未受控浏览器和 sidecar 不允许直接执行。

如需受控 HTTP，必须由维护者配置精确域名、有效期和请求预算；请求参数不能授予权限。
参见 [采集外访安全边界](docs/standards/collection-outbound-safety.md)。
该变更尚未部署，以上生产快照不代表新策略已在生产启用。

### 后端

```bash
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn data_intelligence_hub.main:app --reload --port 8000
```

### 采集管理台

```bash
pnpm install --frozen-lockfile
pnpm --dir apps/scraper-console dev
```

本地访问：<http://localhost:3001>。

## 质量检查

```bash
# 后端
cd apps/api
uv run ruff check .
uv run mypy src
uv run pytest
uv run alembic heads

# Console
pnpm --dir apps/scraper-console test
pnpm --dir apps/scraper-console exec tsc --noEmit
pnpm --dir apps/scraper-console lint
pnpm --dir apps/scraper-console build

# 生产 Compose 配置
docker compose \
  -f configs/deploy/scrapy/docker-compose.yml \
  --env-file /path/to/.env.production \
  config --quiet
```

完整测试套件可能包含依赖历史夹具或专用 PostgreSQL 环境的测试。发布时必须记录新增范围的测试结果和已知基线失败，不得将基线失败误报为本次回归。

## 新增采集能力

新增 endpoint 至少需要同步以下位置：

1. `apps/api/src/data_intelligence_hub/collectors/`：实现 collector。
2. `apps/api/src/data_intelligence_hub/collectors/registry.py`：注册 collector。
3. `apps/api/src/data_intelligence_hub/api/routes/collectors.py`：添加 catalog 定义。
4. `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py`：添加 quick-collect 映射和默认参数。
5. `apps/api/src/data_intelligence_hub/services/collector_catalog.py`：添加配置校验。
6. `apps/scraper-console/`：仅在需要新平台展示或特殊参数表单时修改。
7. 测试、平台包锁文件和相关 Playbook：按变更范围同步。

所有第三方 Provider 调用必须经过 collector 抽象层，业务路由和 Agent 不得绕过 collector 直接调用 Provider API。

## 部署

日常发布、迁移、demo seed、共享网关 reload 和回滚按 [发布与回滚清单](docs/workflows/workflow-release-rollback-stable.md) 执行。

全量销毁重建按 [scrapy.luteos.com 全量重建](docs/workflows/【运维手册】scrapy-luteos全量重建.md) 执行。

生产安装说明见 [腾讯云生产部署](docs/deployment-new-server.md)。

## 文档导航

| 文档 | 用途 |
|---|---|
| [生产环境基线](docs/【运维手册】生产环境基线.md) | 当前域名、主机、容器、网络、数据卷和能力口径 |
| [API 合同](docs/api/api-contract-data-intelligence-hub-stable.md) | API 路径、认证与请求响应合同 |
| [技术架构](docs/architecture/architecture-data-intelligence-hub-stable.md) | 系统边界、运行拓扑和数据流 |
| [平台采集手册](docs/workflows/workflow-platform-collection-playbook-stable.md) | 采集能力、参数和调用方式 |
| [发布与回滚](docs/workflows/workflow-release-rollback-stable.md) | 日常生产发布和故障回滚 |
| [本地开发](docs/workflows/workflow-development-setup-stable.md) | 开发环境搭建 |
| [设计系统](opendesign/design-systems/data-intelligence-product/DESIGN.md) | Console 视觉和交互规范 |
