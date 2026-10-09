---
name: dih-platform-skill-mcp-test-cases
description: Data Intelligence Hub 平台 Skill 与 MCP 测试用例，覆盖生成契约、API、MCP、网站和生产发布。当验证平台工具包版本时使用。
---

# DIH 平台 Skill 与 MCP 测试用例

关联方案：[【技术方案】平台采集Skill与MCP目录](../architecture/【技术方案】平台采集Skill与MCP目录.md)

## 测试范围

| 用例编号 | 类型 | 标题 | 优先级 |
|---|---|---|---|
| DIH-SM-001 | 功能 | 生成-平台工具包-覆盖全部平台 | P0 |
| DIH-SM-002 | 异常 | 生成-密钥边界-阻止敏感信息 | P0 |
| DIH-SM-003 | 业务 | MCP-发现能力-返回一致目录 | P0 |
| DIH-SM-004 | 异常 | MCP-未知或停用端点-拒绝调用 | P0 |
| DIH-SM-005 | UI | 网站-Skill目录-筛选与导航成功 | P1 |
| DIH-SM-006 | UI | 网站-移动端详情-无横向溢出 | P1 |
| DIH-SM-007 | 功能 | API-Playbook详情-返回对应平台 | P1 |
| DIH-SM-008 | 异常 | 生产-MCP无Token-返回未授权 | P0 |
| DIH-SM-014 | 异常 | 路由-quick-collect-未知 project_id 返回 400 | P0 |
| DIH-SM-015 | 异常 | 归一化-非空响应不得产出零记录 | P0 |
| DIH-SM-016 | 功能 | 路由-Apify 入参装配-只挡采集开关 | P0 |
| DIH-SM-017 | 异常 | 目录-Apify 端点-必须有可运行归属 | P0 |

## DIH-SM-001 生成-平台工具包-覆盖全部平台

前置条件：后端 catalog 可导入，生成目录可写。

测试步骤：

1. 运行 `cd apps/api && uv run python ../../scripts/generate_platform_packages.py`。
2. 运行 `uv run python ../../scripts/test_platform_packages.py`。

预期结果：生成 74 个平台目录、278 个能力视图、250 个唯一 endpoint；每个目录包含 Skill、README、manifest、trigger cases 和 Playbook。

## DIH-SM-002 生成-密钥边界-阻止敏感信息

前置条件：平台包已生成。

测试步骤：运行契约测试脚本并扫描生成目录。

预期结果：不存在 `API_KEY=`、`PASSWORD=` 或私钥头；生成文件只引用 `SCRAPY_BASE_URL`、MCP URL 和占位 Token。

## DIH-SM-003 MCP-发现能力-返回一致目录

前置条件：API 已启动，MCP session manager 正常运行。

测试步骤：使用官方 MCP in-memory Client 调用 `list_platforms` 与 `describe_capability`。

预期结果：平台数量、endpoint 参数和 catalog digest 与 `/api/platform-packages` 一致，不产生采集任务。

## DIH-SM-004 MCP-未知或停用端点-拒绝调用

前置条件：MCP 可用。

测试步骤：调用不存在的 endpoint，并调用 disabled endpoint。

预期结果：分别返回 `capability_not_found` 与 `capability_disabled`，数据库不新增任务。

## DIH-SM-005 网站-Skill目录-筛选与导航成功

前置条件：Console 和 API 已启动。

测试步骤：

1. 打开 `/skills`。
2. 搜索 TikTok。
3. 选择一种 method 和 verified 状态。
4. 打开 TikTok 详情。

预期结果：卡片数量正确，详情包含 Skill、MCP、Playbook、能力清单和参数。

## DIH-SM-006 网站-移动端详情-无横向溢出

前置条件：浏览器宽度 390px。

测试步骤：打开 `/skills/tiktok` 并滚动页面。

预期结果：正文、代码块和能力参数可滚动或换行，页面主体无横向溢出。

## DIH-SM-007 API-Playbook详情-返回对应平台

前置条件：API 已启动。

测试步骤：请求 `/api/platform-packages/tiktok/playbook`。

预期结果：HTTP 200，`platform_id=tiktok`，Markdown 包含能力表、执行步骤、验收和风险边界。

## DIH-SM-008 生产-MCP无Token-返回未授权

前置条件：生产设置 `SCRAPY_MCP_TOKEN`。

测试步骤：不带 Authorization 请求 `/mcp`，再携带正确 Bearer Token 初始化 MCP。

预期结果：无 Token 返回 401；正确 Token 可以 initialize 和 list tools。

## DIH-SM-009 生成-坑点渲染进包与控制台

前置条件：`platform_packages/notes/<platform>.json` 存在至少一条策展坑点。

测试步骤：

1. 运行 `cd apps/api && uv run python ../../scripts/generate_platform_packages.py --update-lock`。
2. 检查 `generated/platform-skills/<platform>/references/playbook.md` 与 `SKILL.md`。
3. 检查 `docs/playbooks/【坑点库】DIH-平台采集坑点汇总.md`。
4. 请求 `GET /api/platform-packages/<platform>/playbook` 与 `GET /api/platform-packages/<platform>`。

预期结果：Playbook 含 `## 坑点与规避` 表；SKILL 含 `## 已知限制与坑点`；坑点库按 failure_class 分组；API 响应含 `notes`/`platform_notes`；控制台 `/skills/<platform>` 显示坑点卡片。

## DIH-SM-010 契约-坑点字段与密钥边界

前置条件：平台包已生成。

测试步骤：运行 `uv run python ../../scripts/test_platform_packages.py`。

预期结果：`note_count` > 0 时无 `note_empty_field` / `note_unknown_target` / `note_bad_severity` / `secret_marker` / `missing:pitfalls_library`。占位符（如 `EXA_API_KEY=...`）不算泄漏。

## DIH-SM-011 状态-无证据不得报 verified

前置条件：可导入 status 模块。

测试步骤：`build_provider_status(catalog, configured={...}, evidence={})`，取一个既无缺失配置也无证据的端点。

预期结果：其 `availability == "untested"`（不是 `verified`）；有 `success` 证据的端点才是 `verified`。

## DIH-SM-012 生产-播种清单与 registry 一致

前置条件：可导入 collector_catalog 与 registry。

测试步骤：比对 `set(COLLECTOR_REGISTRY) - {d.type for d in COLLECTOR_CATALOG}`。

预期结果：差集为空。若不为空，对应端点在生产 `POST /api/quick-collect` 会返回 400 `Collector ... is not available`（曾于 `autoscraper_enhanced_web` / `bestblogs_articles` / `blackbird_*` 出现）。

## DIH-SM-013 配置-空 MCP Token 不得锁死 MCP

前置条件：无（纯配置用例）。

测试步骤：

1. `Settings(SCRAPY_MCP_TOKEN="")`，断言 `mcp_token is None` 且 `accepted_mcp_tokens == ()`。
2. `Settings(SCRAPY_MCP_TOKENS_JSON={"claude": "", "codex": "  "})`，断言 `accepted_mcp_tokens == ()`。
3. 用上述 settings 构造 `BearerTokenMiddleware`，不带 Authorization 请求，应放行（200）。

预期结果：空/空白 token 一律视为未配置。

> **历史坑（2026-10-09 生产事故）**：compose 用 `${SCRAPY_MCP_TOKEN:-}` 注入，未配置时传入**空字符串**，pydantic 解析成 `SecretStr("")` → `accepted_mcp_tokens=("",)` 非空 → 中间件对**所有**请求返回 401，且任何 token 都通不过。生产 `/mcp/` 曾因此 100% 不可用。修复见 `config.py` 的 `_blank_mcp_token_is_unset` 与 `accepted_mcp_tokens` 过滤。

## DIH-SM-014 路由-quick-collect-未知 project_id 返回 400

前置条件：demo workspace 存在。

测试步骤：

1. 用不存在的 UUID 调 `POST /api/quick-collect`。
2. 用真实 project_id + 不存在的 endpoint_type 调一次。

预期结果：前者 400 且 `detail` 含 `Unknown project_id`（不是 500、不泄漏 SQL）；后者 400 且含 `Unknown endpoint_type`（证明 project 校验先于端点查表）。

> **历史坑（2026-10-09 生产实测）**：`quick_collect` 从不校验 `body.project_id`，其值只进 `sources.project_id` / `collection_tasks.project_id` 外键。demo 项目被删后，任何沿用旧 id 的调用（含扫描脚本）都会撞 `ForeignKeyViolation` → **500 + 原始 SQL 栈**。已加显式 `get_project` 校验。回归测试见 `tests/integration/test_quick_collect_routes.py`（此前 quick-collect **零覆盖**）。

## DIH-SM-015 归一化-非空响应不得产出零记录

前置条件：可导入 `tikhub_social` 采集器。

测试步骤：把线上真实响应（YouTube `data.contents` 为 dict、Reddit `data.search` 为 dict）喂给 `_extract_items` / `_normalize_item`。

预期结果：YouTube 取到 `videoRenderer` 条目、Reddit 取到 `SearchPost.post` 条目，且 `text` 非空。

> **历史坑（2026-10-09 生产实测）**：上游把嵌套结构由 list 改成 dict 后，`_extract_items` 按固定路径取值**静默返回空列表**，端点仍报 `status=success`、`records_count=0`；从参数侧排查永远查不出来。修复：`_deep_find_dicts` / `_deep_find_typename` 深度查找兜底 + `_normalize_youtube_video` / `_normalize_reddit_post`。实测 `tikhub_youtube_search` 0→11、`tikhub_reddit_search` 0→7。

## DIH-SM-016 路由-Apify 入参装配-只挡采集开关

前置条件：可导入 `api.routes.quick_collect`。

测试步骤：对 `build_apify_actor_input` 分别传入

1. `{"query": "x"}` / `{"url": ...}` / `{"keyword": ...}` / `{"asin": ...}` 等 Actor 侧键；
2. 采集开关 `maxItems` / `max_items` / `max_total_charge_usd` / `run_timeout_seconds`；
3. 与端点缺省值同名的键。

预期结果：第 1 组原样进入 `actor_input`；第 2 组被剔除；第 3 组覆盖缺省值。

> **历史坑（2026-10-09 生产实测）**：装配逻辑用一个"元键"黑名单把 `query`/`url`/`keyword`/`domain`/`asin`/`location`/`username`/`profile`/`handle` 一起剔除，而 `apify/rag-web-browser` 的必填键恰好是 `query` → 调用方传了也报 `400 invalid-input: Field input.query is required`。修复：`_APIFY_META_KEYS` 只保留 4 个采集开关（`quick_collect.py`），并入参改为覆盖缺省值（此前缺省值胜出，调用方传的值会被静默忽略）。回归见 `tests/unit/test_quick_collect_apify_input.py`。

## DIH-SM-017 目录-Apify 端点-必须有可运行归属

前置条件：可导入 catalog 与 `_APIFY_ENDPOINT_DEFAULTS`。

测试步骤：取 `GET /api/collectors/catalog` 里的全部 `apify_*` endpoint_type，与 `_APIFY_ENDPOINT_DEFAULTS` 的键做差集。

预期结果：差集为空（目录暴露的端点都能跑）；且 `_APIFY_ENDPOINT_DEFAULTS` 的每个键都映射到 `apify_actor`、actor_id 均为 `username/name` 形式。

> **事实（2026-10-09）**：反方向不成立——`_APIFY_ENDPOINT_DEFAULTS` 有 118 个端点，目录只暴露 87 个，多出的 31 个"幽灵端点"能跑、消耗额度，但不出现在 `/platforms`、`/skills`、`/collector-docs` 与 MCP 目录里。同类问题见 `tikhub_youtube_video_search`。是否补进目录待产品决策；测试只钉住"目录 ⊆ 可运行"这个安全方向。
