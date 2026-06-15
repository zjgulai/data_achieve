---
title: 培训内容增量更新执行计划
doc_type: workflow
module: operations
topic: training-content-refresh
status: stable
created: 2026-06-15
updated: 2026-06-15
owner: self
source: human+ai
---

# 培训内容增量更新执行计划

## 目标

把生产站点从“可演示的数据采集工作台”升级为“可用于培训的数据采集情报工作台”：

1. 每个功能页面都有真实可解释的数据，不只展示骨架。
2. 内容聚焦当下主流数据采集方法、平台、工具、skills、agents、爬虫框架和 GitHub 项目。
3. 每条情报都有来源、时间、证据和可行动结论。
4. 内容更新链路可重复执行、可回滚、可验收，不污染 E2E 测试数据。

## 核心判断

本轮不直接抓取高风险平台的用户数据，也不绕过平台限制。培训站点优先沉淀“采集方法、工具能力、适用场景、风险边界、GitHub 趋势和官方文档变化”。

原因：

1. 该网站当前价值是培训和工作台，不是批量生产爬虫集群。
2. GitHub、官方文档和公开工具仓库适合作为低风险、高解释性的情报源。
3. 社媒、电商、竞品等平台先用方法卡和合规边界卡表达，后续再接入具体平台适配器。

## 内容分层

| 数据层 | 用途 | 写入方式 | 说明 |
|---|---|---|---|
| `curated_demo` | 当前演示主链路 | 现有 `demo_data.py` | 保持稳定，不直接混入测试噪音 |
| `curated_training` | 培训内容主链路 | 新增或扩展培训 seed | 本轮主目标 |
| `live_snapshot` | 执行时采集快照 | 采集脚本临时输出 | 进入 `tmp/outputs/`，不作为长期资产 |
| `e2e_fixture` | 测试隔离数据 | E2E 一次性账号 | 不进入 demo/training 工作区 |
| `user_generated` | 用户真实数据 | 用户操作产生 | 不由培训刷新脚本清理 |

## 信息架构

培训内容按六类组织：

1. `crawler_framework`：Scrapy、Crawlee、Playwright、Puppeteer、Selenium、Crawl4AI、Firecrawl。
2. `browser_automation`：浏览器自动化、动态页面采集、反爬检测边界。
3. `ai_agent_collection`：browser-use、OpenAI Agents SDK、CrewAI Tools、MCP server 生态。
4. `github_intelligence`：GitHub topic、仓库星标、更新时间、issue 活跃度、生态热度。
5. `platform_method`：GitHub、Amazon、Shopify、TikTok、Reddit、YouTube、竞品官网的公开采集方法。
6. `compliance_boundary`：robots、登录态、个人信息、频率控制、平台 ToS、数据最小化。

## 推荐数据源

### GitHub topic 源

使用现有 `github_topic` collector 小批量采集：

1. `web-scraping`
2. `crawler`
3. `data-extraction`
4. `browser-automation`
5. `ai-agent`
6. `mcp-server`
7. `agent-framework`

每个 topic 首轮 `max_results=10`。生产无 GitHub token 时要控制频率，避免 rate limit。

### GitHub repo 源

使用现有 `github_repo` collector 采集重点仓库：

1. `scrapy/scrapy`
2. `microsoft/playwright`
3. `puppeteer/puppeteer`
4. `SeleniumHQ/selenium`
5. `apify/crawlee`
6. `apify/crawlee-python`
7. `unclecode/crawl4ai`
8. `firecrawl/firecrawl`
9. `browser-use/browser-use`
10. `openai/openai-agents-python`
11. `openai/openai-agents-js`
12. `crewAIInc/crewAI`
13. `crewAIInc/crewAI-tools`
14. `modelcontextprotocol/servers`

### 官方文档源

使用 `generic_web` 或人工审核后写入 `manual_json`：

1. GitHub REST API 文档：`https://docs.github.com/en/rest`
2. GitHub Repositories API：`https://docs.github.com/rest/repos/repos`
3. Scrapy 文档与 release notes：`https://docs.scrapy.org/en/latest/news.html`
4. Playwright 文档：`https://playwright.dev/`
5. Crawlee 文档：`https://crawlee.dev/`
6. Crawl4AI 文档：`https://docs.crawl4ai.com/`
7. Firecrawl API 文档：`https://docs.firecrawl.dev/api-reference/v2-introduction`
8. OpenAI Agents SDK 文档：`https://developers.openai.com/api/docs/guides/agents`
9. CrewAI Tools 文档：`https://docs.crewai.com/en/concepts/tools`
10. MCP 文档：`https://modelcontextprotocol.io/docs/getting-started/intro`

## 页面落点

| 页面 | 必须呈现的培训内容 |
|---|---|
| `/dashboard` | 今日情报摘要、采集覆盖率、热门工具变化、待处理告警 |
| `/projects` | 四个训练项目：开源采集工具、平台采集方法、Agent 采集生态、合规风险雷达 |
| `/sources` | GitHub topic、GitHub repo、官方文档、人工方法卡四类 source |
| `/tasks` | 每个 source 对应采集任务，显示最近执行状态和证据数量 |
| `/raw-records` | 原始 GitHub/API/docs 快照，保留来源 URL 和采集时间 |
| `/entities` | 工具、框架、平台、方法卡实体 |
| `/signals` | 星标增长、文档更新、生态热度、合规风险变化 |
| `/intelligence` | 可直接用于培训讲解的情报卡，每条必须有结论、证据、建议动作 |
| `/reports` | “数据采集培训情报周报”，覆盖工具趋势、平台方法、风险边界 |
| `/alerts` | 高增长工具、关键文档更新、高风险采集方法提醒 |
| `/notifications` | 报告生成、告警触发、采集失败通知 |

## 执行阶段

### Phase 0：基线确认

执行内容：

1. 确认本地 `main` 与 `origin/main` 同步。
2. 确认生产当前 SHA、容器健康、schema 版本。
3. 备份生产数据库。
4. 记录当前 demo/training 数据计数。

验收标准：

1. 本地工作区干净或仅包含本轮变更。
2. 生产 `api/db/web/edge` 健康。
3. 备份文件存在且可定位。

### Phase 1：内容源清单与字段契约

执行内容：

1. 固化 `curated_training` 字段契约。
2. 明确 source、task、raw record、entity、signal、intelligence、report 的最小字段。
3. 输出候选源清单和风险分级。

验收标准：

1. 每个候选源有 `source_url`、`collector_type`、`risk_level`。
2. 每类培训内容至少有 3 个可解释来源。
3. 不含 `sample`、`placeholder`、`示例`、`样本` 等演示腔文案。

### Phase 2：实时内容快照

执行内容：

1. 调用 GitHub REST API 获取重点仓库状态。
2. 调用 GitHub topic search 获取生态候选项目。
3. 抓取官方文档页面标题、更新时间线索和正文摘要。
4. 生成临时快照文件。

落盘位置：

```text
tmp/outputs/training-content-snapshot-20260615.json
```

验收标准：

1. 快照记录总数不少于 40。
2. 每条记录有 `source_url`、`collected_at`、`collector_type`。
3. GitHub 记录保留 stars、forks、open issues、updated_at。
4. 官方文档记录保留 title 和摘要。

### Phase 3：情报萃取

执行内容：

1. 将快照归类为工具趋势、平台方法、Agent 生态、合规边界。
2. 生成 12 到 16 条培训情报。
3. 每条情报包含：结论、证据、影响、建议动作、适合培训讲解的切入点。
4. 对高风险平台只写方法边界，不写规避限制的操作细节。

验收标准：

1. 每条情报至少关联 1 条 raw record 和 1 个 entity。
2. 每条情报都有 evidence URL。
3. 情报标题能被业务用户理解，不使用内部技术噪音。

### Phase 4：培训 seed / 增量脚本

推荐实现：

1. 新增 `apps/api/src/data_intelligence_hub/seed/training_content.py`。
2. 使用确定性 UUID，dataset 标记为 `curated_training`。
3. 支持 `--dry-run` 和 `--execute`。
4. 支持重复执行不制造重复记录。
5. 不修改 E2E fixture 生成逻辑。

验收标准：

1. 空库可写入完整 training 数据。
2. 重复执行关键记录数量不翻倍。
3. cleanup 不误删 `curated_training`。
4. 现有 demo governance 验收仍通过，或同步更新治理文档中的白名单口径。

### Phase 5：本地验收

执行内容：

1. Python 类型/格式/测试。
2. 前端 lint、typecheck、build。
3. 本地真实 API smoke。
4. 本地桌面与移动 E2E。
5. 页面人工走查，确认每页有实际培训内容。

验收标准：

1. `uv run pytest` 通过。
2. `pnpm lint`、`pnpm build` 通过。
3. E2E 通过或仅跳过已声明非本轮目标的用例。
4. 所有主要页面不再只是空骨架。

### Phase 6：生产增量发布

执行内容：

1. 打包代码并上传到 `/opt/data-achieve-scrapy/app`。
2. 使用生产 env 和 compose 重建需要变化的服务。
3. 执行 Alembic 迁移。
4. 执行 training seed dry-run。
5. 确认 dry-run diff 后执行写入。
6. 重启 web/edge。

生产 compose 命令必须使用：

```bash
docker compose --env-file ../.env.production -f configs/deploy/scrapy/docker-compose.yml
```

验收标准：

1. `https://scrapy.lute-tlz-dddd.top/api/health` 健康。
2. 生产数据计数达到 training 内容阈值。
3. 生产桌面真实 API E2E 通过。
4. 生产移动真实 API E2E 通过。
5. Chrome 直连测试只有在 Chrome 插件 profile 修复后才可声明完成。

### Phase 7：培训验收报告

执行内容：

1. 截图留存每个页面的关键状态。
2. 输出数据计数、来源覆盖、页面覆盖、测试结果。
3. 记录未完成项与下一轮建议。

落盘位置：

```text
docs/workflows/workflow-training-content-refresh-stable.md
tmp/outputs/training-content-acceptance-20260615.json
tmp/screenshots/
```

验收标准：

1. 报告能说明“哪些页面有了哪些真实情报”。
2. 报告能说明“哪些来源支撑这些情报”。
3. 报告能说明“哪些风险被刻意排除”。

## 内容质量门槛

上线前必须满足：

1. 项目数不少于 4。
2. sources 不少于 20。
3. raw records 不少于 40。
4. entities 不少于 30。
5. signals 不少于 12。
6. intelligence items 不少于 12。
7. reports 不少于 1。
8. alerts 不少于 3。
9. notifications 不少于 3。
10. 所有用户可见培训内容均有来源和更新时间。

## 风险边界

1. GitHub API rate limit：首轮小批量采集，后续再接入 token。
2. 平台合规风险：不写绕过登录、破解限制、抓取个人信息的教程。
3. 内容漂移：所有“最新”判断必须来自执行时快照，不硬编码在文档里。
4. demo cleanup 误删：`curated_training` 必须进入治理口径或独立 workspace。
5. 信号类型不足：首轮复用现有 signal 类型表达，新增信号 taxonomy 另起代码变更。

## 完成定义

本轮完成不是“写了一批静态文案”，而是达到以下闭环：

1. 生产站点每个主要页面都有可讲解的培训内容。
2. 内容来自公开来源、GitHub API、官方文档和人工审核方法卡。
3. 采集、萃取、写入、部署、E2E、页面验收全部有记录。
4. 后续可重复执行增量刷新，不依赖手工改库。
