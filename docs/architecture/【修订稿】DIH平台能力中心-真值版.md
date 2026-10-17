---
name: dih-platform-capability-center-truth-revision
description: DIH 平台能力中心（/platforms）设计稿的真值修订稿。把设计稿中无来源的数字与不存在的元素换成实测真值。供产品判断改设计还是改数据。
---

# 【修订稿】DIH 平台能力中心-真值版

本文替换设计稿中无来源的数字与不存在的元素。

**基准仓库**：`/Users/lute/Project/data_scrapy-p0g`，分支 `feat/dih-p0-on-guardrails`。
**复核日期**：2026-10-16。

**标注约定**

- （本机 offline 实测）：进程内实测。未起服务、未连数据库。`app_env=development`，网络模式 offline。
- （本机源码核对）：只读源码与文件。
- （生产实测）：两域名只读 GET（`https://scrapy.luteos.com`、`https://scrapy.lute-tlz-dddd.top`）。无凭证，8 秒超时。
- （需生产实测）：本机不可验证。等生产数据。

生产域名出处：`docs/【运维手册】生产环境基线.md:16-22`、`configs/deploy/scrapy/docker-compose.yml:68`、`configs/deploy/scrapy-new/docker-compose.yml:68`、`docs/deployment-new-server.md:18`。

## 1. 结论

设计稿有 7 处数字或元素必须改为真值。另有 3 处口径必须由产品先定。

**必须改的 7 处**

1. 页头副标题。「286 视图」改「286 能力视图」。「258 个工具」先部署 `/api/tools`。
2. 统计块「已核验 226 / 待测试 60 / 禁用 11」。三数相加 297，不等于 286。改实测口径（§3.3）。
3. 「核验率 79%」。只能等于 226/286。改 99.7% 与 86.7%（生产实测）。
4. 横幅。「切换执行环境即可放行」对 57 个端点不成立。改分态文案（§3.2）。
5. 门控芯片。补第三枚「永久拒绝」。前两枚计数随模式翻转，第三枚模式无关（§3.5）。
6. 开关「11」改 12（口径见 §3.6）。侧栏徽标「26」改 70。
7. 四个不存在的元素。两行示例名、一行 `web_search`、一处「参数 —」。逐个替换（§2、§4、§5）。

**必须由产品先定的 3 处**

1. 分类芯片用哪套：方案 A（现有 12 类）或方案 B（新立 8 类）。建议 A（§3.4）。
2. 「已核验」口径用哪套：测试证据、可用性、静态声明。三选一（§3.3、§3.7、§6）。
3. 「系统设置」导航项去留：删除或新建页面（§6）。

**部署前置（工程项。不属产品决策）**

- `policy_block_reason` 字段未部署到生产（生产实测）。横幅与门控芯片依赖它。
- `/api/tools` 未部署到生产，返回 404（生产实测）。「258 个工具」与工具级可用性依赖它。

## 2. 逐元素对照表

处置栏用四值：改为真值 / 删除 / 需产品决策 / 保留。

| 元素 | 设计稿值 | 真值 | 依据 | 处置 |
|---|---|---|---|---|
| 页头标题 | 「平台能力中心」 | 与 `apps/scraper-console/src/app/platforms/page.tsx:508` 现值一致 | 本机源码核对 | 保留 |
| 页头副标题 | 「共 286 视图 / 258 唯一端点 · 258 个工具」 | 286 能力视图 / 258 唯一端点 / 258 个工具。前两数已成立 | 286 与 258：本机 offline 实测；「258 个工具」依赖未部署的 `/api/tools`：生产实测（404） | 改为真值 |
| 横幅 | 「当前网络模式阻止全部目录端点。切换执行环境即可放行。」 | 分态文案（§3.2）。57 个端点换环境不放行 | 本机 offline 实测；字段未部署生产：生产实测 | 改为真值 |
| 统计块 | 「已核验 226 / 待测试 60 / 禁用 11」 | 285/1（合计 286）；或 209/21/17/10/1（合计 258） | 生产实测 | 改为真值 |
| 核验率 | 「79%」 | 99.7%（285/286）；成功率 86.7%（248/286） | 生产实测 | 改为真值 |
| 分类芯片（8 个） | 全部 286 / 搜索与提取 136 / 社交与内容 49 / 电商与商品 29 / 情报与风控 24 / 代码与仓库 15 / 边缘与逆向 13 / 沙箱与拟人 13 | 7 个标签全仓 0 命中。7 数合计 279。真值见 §3.4 两方案 | 本机 offline 实测；生产实测 | 需产品决策 |
| 门控芯片「环境门控 by 环境」 | 计数缺失 | 229 能力视图 / 201 唯一端点（offline）；0（restricted） | 本机 offline 实测 | 改为真值 |
| 门控芯片「环境门控 by 授权」 | 计数缺失 | 0（offline）；32 能力视图 / 4 唯一端点（restricted、无批准） | 本机 offline 实测 | 改为真值 |
| （设计缺）第三枚门控芯片 | 无 | 「永久拒绝」57 能力视图 / 57 唯一端点。模式无关 | 本机 offline 实测 | 改为真值（新增） |
| 开关 | 「不展示 11 个禁用端点」 | 12 能力视图 / 3 唯一端点（`public_feed`、`generic_web`、`pypi_search`） | 本机 offline 实测；生产实测 | 改为真值 |
| 侧栏徽标 | 「26 平台包」 | 70。现侧栏无徽标代码 | 计数：本机 offline 实测 + 生产实测；无代码：本机源码核对 | 改为真值 |
| 侧栏 9 项导航 | 平台能力 / 采集文档 / Skill 目录 / 项目 / 采集任务 / 运行记录 / 数据集 / 凭证设置 / 系统设置 | 8 项已有路由。4 项须改名。「系统设置」无页面 | 本机源码核对 | 改为真值 + 需产品决策 |
| 表格 7 列 | 端点 / 平台 / 参数 / 方法 / 内容 / 状态 / 测试记录 | 7/7 有数据源（§3.7）。「状态」列口径未定 | 本机 offline 实测 | 保留 + 需产品决策 |
| 示例行 `apify_1688_product_search` | 参数显示「—」 | 存在。1 必需 `keyword` / 1 可选 | 本机 offline 实测；生产实测 | 改为真值 |
| 示例行 `apify_alibaba_product_search` | （示例） | 存在。0 必需 / 4 可选 | 本机 offline 实测；生产实测 | 保留 |
| 示例行 `apify_shein_product_detail` | （示例） | 不存在。替换为 `apify_shein_product_scraper` | 全仓 0 命中；两处 API 响应 0 命中：本机 offline 实测；生产实测 | 改为真值 |
| 示例行 `apify_tiktok_ads_library_scraper` | （示例） | 不在采集目录。仅两处硬编码：`quick-collect-drawer.tsx:636`、`scripts/collector_demo_params.py:77`。替换为 `apify_tiktok_ads_scraper` | 本机 offline 实测 | 改为真值 |
| 「参数」列「—」空态 | 「—」 | 真实状态：两者皆空 5 行；必填为空 16 行 | 本机 offline 实测 | 保留（写清规则） |
| 底部固定行 | `web_search`（AnySearch / web-search / 2 必需 / 1 可选） | 端点不存在。(2,1) 组合为空集。替换为 `anysearch_brand_media`（§5） | 本机 offline 实测 | 改为真值 |

## 3. 修订后的页面规格

按屏幕从上到下。

### 3.1 页头

- 显示什么：标题 + 副标题。
- 文案原文：标题「平台能力中心」。副标题「共 286 能力视图 / 258 唯一端点」。`/api/tools` 部署后追加「· 258 个工具」。
- 数据源：`GET /api/collectors/catalog` → `collectors[].endpoints[]` 行数与 `endpoint_type` 去重；`GET /api/tools` → `tool_count`。
- 计数口径：286 = 能力视图（行口径）。258 = 唯一端点。258 = 工具（`tool_id` 与 `endpoint_type` 1:1）。
- 依据：286/258（本机 offline 实测）；双域名同值（生产实测）。

### 3.2 横幅

- 显示什么：阻断状态。分态渲染。
- 数据源：`GET /api/collectors/catalog` → `endpoints[].policy_block_reason`。模式来自 `COLLECTION_NETWORK_MODE`（`core/config.py:79-87`）。
- 计数口径：能力视图（286 行）。与门控芯片同口径。
- 文案原文（四态）：

| 状态 | 文案原文 |
|---|---|
| 环境 offline | 「当前执行环境为离线模式。286 个能力视图全部被阻断。229 个换执行环境即可放行。57 个为永久阻断，换执行环境也不放行。」 |
| restricted，无域名批准 | 「当前执行环境为受限模式。197 个能力视图可放行。89 个被阻断。其中 32 个缺服务端域名批准。57 个为永久阻断，换执行环境也不放行。」 |
| restricted，批准齐全 | 「当前执行环境为受限模式。229 个能力视图可放行。57 个为永久阻断，换执行环境也不放行。」 |
| 生产现状 | 不显示。`policy_block_reason` 未部署（生产实测）。 |

- 必须：删除两处全量断言。「阻止全部目录端点」与「切换执行环境即可放行」都不成立。

### 3.3 统计块

必须给出可相加的口径。两套如下。分数字段的总数必须写明分母。

**口径 A（推荐）：测试证据。分母 = 286 能力视图。**

| 项 | 值 |
|---|---|
| 已实测 | 285 |
| 未实测 | 1（`pypi_search`） |
| 合计 | 286 |
| 实测成功 | 248 |
| 实测失败 | 37 |
| 实测合计 | 285 |
| 实测覆盖率 | 99.7%（285/286） |
| 实测成功率 | 86.7%（248/286） |

- 文案原文（口径 A）：第一行「已实测 285 · 未实测 1」。第二行「实测成功 248 · 实测失败 37」。第三行「覆盖率 99.7% · 成功率 86.7%」。

- 数据源：`GET /api/collectors/docs` → 顶层 `total_endpoints` / `tested_endpoints` / `success_endpoints`；逐行 `test_result.last_run_status`。
- 依据：生产实测（248 成功 / 37 失败 / 1 无记录）。
- 本机：需生产实测。本机无 Postgres 时该路由 500。
- 优点：满足设计规范「已验证必须来自真实测试证据」（`【设计规范】DIH首页与目录视觉规范.md:192`）。

**口径 B（备选）：可用性。分母 = 258 唯一端点。**

| availability | 值 |
|---|---|
| verified | 209 |
| config-gated | 21 |
| degraded | 17 |
| empty | 10 |
| disabled | 1 |
| 合计 | 258 |

- 数据源：`GET /api/platform-packages/providers/status` → `endpoints[].availability`。派生规则见 `platform_packages/status.py`（成功且有记录才记 verified）。
- 依据：生产实测。
- 本机（空证据库）：config-gated 257 / disabled 1（本机 offline 实测，`/api/tools` availability 口径）。
- 注意：静态 `status=verified`（274 能力视图）是声明值。不得标「已验证」。

### 3.4 分类芯片

设计稿 8 类的标签与数字都无来源（7 个标签全仓 0 命中；7 数合计 279）。两套方案如下。

**方案 A（建议）：沿用现有 12 类。**

- 规则：`matchCategory` 子串匹配（`apps/scraper-console/src/lib/platforms/catalog.ts:264-268`）。
- 计数口径：286 能力视图全量。不含运行态门控。
- 真值（本机 offline 实测；生产同值）：

| 芯片 | 计数 |
|---|---|
| 全部 | 286 |
| 国际社媒 | 94 |
| 中文社媒 | 27 |
| 电商 | 31 |
| 评价 | 9 |
| 搜索 & AI | 6 |
| 中文搜索 | 3 |
| 广告情报 | 6 |
| B2B & 开源 | 22 |
| 监管公告 | 4 |
| 开放网络 | 86 |
| OSINT 情报 | 0 |

- 必须随页注明两个偏差。11 个非全部芯片合计 288。其中 19 个能力视图未命中，21 个重复命中。校验：286 − 19 + 21 = 288。
- 重复命中的两类来源：`linkedin` 11 行同时命中「国际社媒」与「B2B & 开源」；其余 10 行是子串误配（`aliexpress`×2、`tiktok_shop`×2、`facebook_ads`×2、`tiktok_ads`、`snapchat_ads`、`pinterest_ads`、`perplexity`），都同时命中「国际社媒」。
- 文案原文：标签沿用 `catalog.ts` 现值；数字紧跟标签（如「国际社媒 94」）。
- 运行态差异（必须写进验收）。页面叠加 `canStartCollection` 门控后，本机 offline 全部芯片计 0。生产上「全部」= 274、「开放网络」= 75。其余 10 项不变（生产实测）。

**方案 B（备选）：新立 8 类。** 逐行瀑布，首个命中即归属。

| 芯片 | 匹配规则 | 计数 |
|---|---|---|
| 全部 | 无 | 286 |
| 沙箱与拟人 | `method == "browser"` | 4 |
| 边缘与逆向 | `endpoint_type` 含 `attack_surface` 或 `provider` 含「指纹」 | 2 |
| 情报与风控 | `content_type == "osint_report"` 或 `provider` 含 SpiderFoot/Blackbird/Aliens Eye/Robin/sherlock/maigret 或 `platform == "regulatory"` | 26 |
| 代码与仓库 | `platform` ∈ {github, npm, pypi, crates, rubygems, golang, packagist, nuget, pubdev} 或 `content_type == "repo"` | 18 |
| 电商与商品 | `platform` ∈ {amazon, walmart, temu, shein, aliexpress, tiktok_shop, ebay, etsy, shopify, target, ecommerce, alibaba} 或 `content_type` ∈ {product, review} | 43 |
| 社交与内容 | `platform` ∈ 20 个社媒值（`catalog.ts` 两社媒表并集）或 `method` ∈ {tikhub, twscrape} 或 `provider` 含 MediaCrawler | 109 |
| 搜索与提取 | 以上未命中的余项 | 84 |

- 匹配顺序 = 表格自上而下。7 类合计 286（本机 offline 实测；双域名核对同值。生产实测）。
- 弱项（必须先解决）：「边缘与逆向」无忠实定义。代理规则只覆盖 2 个端点。「电商与商品」含 12 个临时归属行。「搜索与提取」是未命中余项。
- 建议：首期用方案 A。计数直接可用。规则已在库中。无新概念。如果要保留 8 芯片的信息架构，用方案 B。先给「边缘与逆向」定名或合并。

### 3.5 门控芯片

原因族到芯片的映射如下。计数口径 = 能力视图 + 唯一端点（本机 offline 实测）。

| 芯片 | `policy_block_reason` 原文含 | offline | restricted（无批准） | restricted（批准齐全） |
|---|---|---|---|---|
| 环境门控 by 环境 | `当前执行环境为离线模式` | 229 / 201 | 0 | 0 |
| 环境门控 by 授权 | `缺少唯一的服务端域名批准配置` 或 `服务端域名批准无效或已过期` | 0（被环境检查短路） | 32 / 4 | 0 |
| 永久拒绝（必须新增） | `未具备受控出口` | 57 / 57 | 57 / 57 | 57 / 57 |

- 加和关系：offline 229+0+57=286。restricted 0+32+57=89 阻断，197 放行（197+89=286）。两枚芯片不能单独加和（229+32+57=318）。
- 文案原文：芯片标签「by 环境」「by 授权」「永久拒绝」。数字随模式实时取值（如「by 环境 229」）。
- 数据源：`GET /api/collectors/catalog` → `policy_block_reason`（本工作分支字段，`collectors.py:4489-4497` 逐行注入）。值含前缀 `collection_policy_denied: `（本机 offline 实测原文：`collection_policy_denied: 当前执行环境为离线模式`）。
- 前置：生产未部署该字段（生产实测）。部署前两枚芯片与横幅都不可用。
- 「永久拒绝」与 `/api/tools` 的 `permanently_blocked=true` 同值（57 个）。该路由生产未部署。

### 3.6 开关

- 显示什么：「不展示 12 个禁用端点」。计数取实时值，不写死。
- 数据源：`GET /api/collectors/catalog` → `status == "disabled"`。
- 计数口径：能力视图（286 行口径）= 12。按 `endpoint_type` 去重 = 3（`public_feed`、`generic_web`、`pypi_search`）。`/api/tools` 可用性口径 = 1（`pypi_search`），数据源不同，不得混用。选一个口径，写进文案。
- 依据：12 与 3 为本机 offline 实测。12 为生产实测。`/api/tools` 口径 1 为本机实测（该路由生产未部署）。

### 3.7 表格

7 列的数据源与口径：

| 列 | 数据源（精确到字段） | 口径 |
|---|---|---|
| 端点 | `GET /api/collectors/docs` → `endpoints[].endpoint_type`；`GET /api/tools` → `tools[].tool_id` | 258 个唯一值 |
| 平台 | `platform` | 69 个取值（tools 侧） |
| 参数 | `required_params` 与 `optional_params` 数组长度 | 渲染「N 必需 / M 可选」 |
| 方法 | `method`（仅 catalog / docs 有；`/api/tools` 无此字段） | 12 种取值 |
| 内容 | `content_type` | 18 种取值 |
| 状态 | 建议用 `availability`（providers/status）。备选静态 `status` | 需产品决策（§6） |
| 测试记录 | `test_result`：`last_run_status` / `last_run_at` / `last_records_count` / `last_error_message` | 数据来自数据库（`[quick] [test]` 运行）。生产 285 有记录，1 无记录 |

- 「—」空态规则：两者皆空 → 5 行；必填为空 → 16 行。建议用「两者皆空」。
- 文案原文：列标题沿用设计稿。列序：端点 / 平台 / 参数 / 方法 / 内容 / 状态 / 测试记录。
- 测试记录的生产实测值：成功 248 / 失败 37 / 无记录 1。
- 本机：需生产实测。本机无 Postgres 时这两个路由 500。

### 3.8 底部行

- 显示什么：固定示例行（见 §5）。
- 数据源：同表格 7 列。
- 计数口径：能力视图 / 唯一端点，随行显示。
- 文案原文：见 §5。`web_search` 与「2 必需 / 1 可选」都必须删除。

## 4. 示例行

8 行真实端点。覆盖多种状态与参数形态。

字段来源（逐项标注）：

- 声明状态 = catalog `status`（本机 + 生产实测）。
- 可用性 = providers/status `availability`（生产实测）。
- 最近实测 = docs `test_result`（生产实测）。
- 参数 = `required_params` / `optional_params`（本机 offline 实测）。

| 端点（label） | 平台 | 方法 | 内容 | 参数 | 声明状态 | 可用性 | 最近实测 | 备注 |
|---|---|---|---|---|---|---|---|---|
| `apify_1688_product_search`（1688 商品搜索） | alibaba | apify | product | 1 必需 `keyword` / 1 可选 `max_items_per_url` | verified | degraded | failed：`http_forbidden: upstream returned 403`，0 条，2026-10-09 | 设计稿误标「参数 —」 |
| `apify_alibaba_product_search`（阿里巴巴国际站商品搜索（含规格/证书）） | alibaba | apify | product | 0 必需 / 4 可选（`maxItems`、`includeSpecSheet`、`includeCertificates`、`includePackagingAndWeight`） | verified | verified | success，5 条，2026-10-09 | 「必填为空」形态 |
| `apify_shein_product_scraper`（SHEIN Product Scraper） | shein | apify | product | 1 必需 `startUrl` / 1 可选 `maxItems` | verified | verified | success，3 条，2026-10-09 | 替换 `apify_shein_product_detail` |
| `apify_tiktok_ads_scraper`（TikTok Ads Scraper） | tiktok_ads | apify | ad | 1 必需 `searchTerms` / 1 可选 `maxItems` | verified | verified | success，3 条，2026-10-09 | 替换 `apify_tiktok_ads_library_scraper` |
| `tikhub_douyin_hot_search`（抖音热搜榜） | douyin | tikhub | trend | 0 必需 / 0 可选（「—」） | verified | verified | success，5 条，2026-10-09 | 真「参数 —」示例 |
| `pypi_search`（PyPI 包搜索） | pypi | api | product | 1 必需 `query` / 1 可选 `max_items` | disabled | disabled | 无记录（唯一未实测） | 唯一 disabled 工具 |
| `weibo_keyword_search`（微博关键词搜索） | weibo | web_crawl | post | 1 必需 `keyword` / 1 可选 `max_items` | verified | config-gated（缺 `MEDIACRAWLER_BASE_URL`） | failed：`http_connection_failed`，0 条，2026-10-09 | 永久阻断：本机 `/api/tools` 记 `permanently_blocked=true` |
| `github_repo`（GitHub 仓库监测） | github | github_api | repo | 2 必需 `owner`、`repo` / 0 可选 | verified | verified | success，1 条，2026-10-09 | 「两个必填」形态 |

供应商字段（供卡片副标题）：`apify_1688_product_search` = `Apify Actor (ecomscrape/1688-product-search-scraper)`；`apify_shein_product_scraper` = `Apify Actor (shahidirfan/shein-product-scraper)`；`apify_tiktok_ads_scraper` = `Apify Actor (lexis-solutions/tiktok-ads-scraper)`（本机 offline 实测）。

## 5. 底部固定行

真值行：`anysearch_brand_media`。

| 字段 | 值 |
|---|---|
| 端点 | `anysearch_brand_media` |
| label | AnySearch 品牌×媒体覆盖查询 |
| 平台 / 方法 / 内容 | web / anysearch / search_result |
| 参数 | 1 必需（`query`）/ 2 可选（`site`、`num_results`） |
| 供应商 | AnySearch API |
| 费用 | `$0.001/query`（上游估算） |
| 声明状态 | verified |
| 可用性 | verified（生产实测） |
| 最近实测 | success，10 条，2026-10-09（生产实测） |

- 若版面必须出现「2 必需」，用 `anysearch_tag_search`（2 必需 `query`、`tag` / 3 可选）。
- 但 258 个端点中不存在「2 必需 / 1 可选」组合（本机 offline 实测）。设计稿该分组必须删。
- `web_search` 名不存在。全仓库无此端点与工具。

## 6. 待产品决策项

按重要性排序。

**决策 1：分类芯片用哪套**

- 问题：设计稿 8 类无规则、无数字来源（7 数合计 279，不等于 286）。
- 可选方案：A 用现有 12 类（计数见 §3.4，立即可用）。B 新立 8 类（规则与计数见 §3.4，需先解决「边缘与逆向」定义）。
- 我的建议：方案 A 首期。保留 8 芯片 IA 时用 B，并把「边缘与逆向」定名或合并。

**决策 2：「已核验」口径用哪套**

- 问题：同一时刻三套口径并存。274（静态声明）、209+17 等（可用性，258 端点）、248（测试记录，286 能力视图）。设计稿数字与三者都不符。
- 可选方案：统计块用测试证据（§3.3 口径 A）。表格「状态」列用可用性（§3.3 口径 B）。静态声明只作目录定位，不进状态 UI。
- 我的建议：按上一行的分工执行。理由：设计规范要求「已验证」来自真实测试证据（`:192`）。

**决策 3：「系统设置」导航项**

- 问题：设计稿 9 项导航中，「系统设置」在控制台无对应页面。`settings/` 下只有 `account` 与 `credentials`。`account` 页是占位空页。
- 可选方案：删除该项。或新建页面（整合方案 §4.3 只列 `/settings/providers` 与 `/settings/members`）。
- 我的建议：首期删除。要保留就先建页。

其余导航改名不算决策（本机源码核对）：

- 平台能力（现「采集平台」）。
- Skill 目录（现「Skill 与 MCP」）。
- 项目（现「我的项目」）。
- 凭证设置（现「凭证配置」）。

## 7. 附录：数据来源与复现命令

以下命令均已实测运行。目录 `/Users/lute/Project/data_scrapy-p0g`。

**命令 1：本机目录 + 策略族（offline）**

```bash
cd /Users/lute/Project/data_scrapy-p0g/apps/api
.venv/bin/python -I - <<'PY'
import asyncio, sys, collections
sys.path.insert(0, "src")
from data_intelligence_hub.api.routes.collectors import get_collector_catalog
rows = [e for g in asyncio.run(get_collector_catalog()).collectors for e in g.endpoints]
print("rows", len(rows), "unique", len({e.endpoint_type for e in rows}), "status", dict(collections.Counter(e.status for e in rows)))
fam = collections.Counter(
    "none" if not e.policy_block_reason else
    "env-offline" if "当前执行环境为离线模式" in e.policy_block_reason else
    "permanent" if "未具备受控出口" in e.policy_block_reason else "grant"
    for e in rows)
print("families", dict(fam))
PY
```

输出：`rows 286 unique 258 status {'verified': 274, 'disabled': 12}`；`families {'env-offline': 229, 'permanent': 57}`。

restricted 模拟：命令前加 `COLLECTION_NETWORK_MODE=restricted`。输出：`families {'none': 197, 'grant': 32, 'permanent': 57}`。

**命令 2：本机 `/api/tools`（sqlite 覆盖 session，种子 demo workspace。同仓库测试夹具做法）**

```bash
cd /Users/lute/Project/data_scrapy-p0g/apps/api
.venv/bin/python -I - <<'PY'
import asyncio, sys, uuid, collections
sys.path.insert(0, "src")
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workspaces import DEMO_WORKSPACE_SLUG

async def main():
    engine = create_async_engine("sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async def dep():
        async with sf() as s:
            yield s
    app.dependency_overrides[get_session] = dep
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cl:
        async with sf() as s:
            u = User(email="owner@example.com", password_hash="x", name="O"); s.add(u); await s.flush()
            wid = uuid.uuid4()
            s.add(Workspace(id=wid, name="D", slug=DEMO_WORKSPACE_SLUG, owner_id=u.id)); await s.flush()
            s.add(Project(workspace_id=wid, name="p", domain="osint", owner_id=u.id))
            await s.commit()
        p = (await cl.get("/api/tools")).json()
    params = [x for t in p["tools"] for x in t["parameters"]]
    print("counts", p["tool_count"], p["canonical_tool_count"], p["executable_count"])
    print("availability", dict(collections.Counter(t["availability"]["availability"] for t in p["tools"])))
    print("params", len(params), "typed", sum(1 for x in params if x["typed"]), "not_enforced", sum(1 for x in params if not x["type_enforced"]))
    app.dependency_overrides.clear(); await engine.dispose()

asyncio.run(main())
PY
```

输出：`counts 258 258 0`；`availability {'config-gated': 257, 'disabled': 1}`；`params 650 typed 294 not_enforced 34`。

**命令 3：生产只读 GET（六条。A = scrapy.luteos.com，B = scrapy.lute-tlz-dddd.top）**

```bash
curl -sS -m 8 -o a-catalog.json          -w 'HTTP %{http_code} | %{size_download}B\n' https://scrapy.luteos.com/api/collectors/catalog
curl -sS -m 8 -o a-providers-status.json -w 'HTTP %{http_code} | %{size_download}B\n' https://scrapy.luteos.com/api/platform-packages/providers/status
curl -sS -m 8 -o a-packages.json         -w 'HTTP %{http_code} | %{size_download}B\n' https://scrapy.luteos.com/api/platform-packages
curl -sS -m 8 -o a-docs.json             -w 'HTTP %{http_code} | %{size_download}B\n' https://scrapy.luteos.com/api/collectors/docs
curl -sS -m 8 -o a-tools.json            -w 'HTTP %{http_code} | %{size_download}B\n' https://scrapy.luteos.com/api/tools
curl -sS -m 8 -o b-catalog.json          -w 'HTTP %{http_code} | %{size_download}B\n' https://scrapy.lute-tlz-dddd.top/api/collectors/catalog
```

输出（2026-10-16）：五条 200（126092B / 61221B / 284113B / 197194B / 126092B）；`a-tools` 404（22B）。A、B 两份 catalog 字节一致，`sha256 = c241b8dfd563d8dcda7c8ec71ceca3cd2d5cf1917fbe593c3d620929bfab52ea`。

**命令 4：生产统计派生**

```bash
python3 -I - <<'PY'
import json, collections
cat = json.load(open("a-catalog.json"))
rows = [e for g in cat["collectors"] for e in g["endpoints"]]
print("catalog:", len(cat["collectors"]), len(rows), len({e["endpoint_type"] for e in rows}), dict(collections.Counter(e["status"] for e in rows)))
pk = json.load(open("a-packages.json"))
print("packages:", pk["platform_count"], pk["capability_count"], pk["unique_endpoint_count"])
st = json.load(open("a-providers-status.json"))
print("availability:", dict(collections.Counter(e["availability"] for e in st["endpoints"])))
dc = json.load(open("a-docs.json"))
print("docs:", dc["total_endpoints"], dc["tested_endpoints"], dc["success_endpoints"])
PY
```

输出：`catalog: 36 286 258 {'verified': 274, 'disabled': 12}`；`packages: 70 286 258`；`availability: {'verified': 209, 'degraded': 17, 'empty': 10, 'config-gated': 21, 'disabled': 1}`；`docs: 286 285 248`。

**数字对照表**

| 数字 | 值 | 环境 | 复现 |
|---|---|---|---|
| 能力视图 / 唯一端点 / 分组 | 286 / 258 / 36 | 本机 + 生产 | 命令 1、4 |
| 静态状态分布 | verified 274 / pending 0 / disabled 12 | 本机 + 生产 | 命令 1、4 |
| disabled 分解 | public_feed 9 + generic_web 2 + pypi_search 1 | 本机 + 生产 | 命令 1、4 |
| 12 条 disabled 源码行 | `collectors.py:2290,2303,2316,2409,2422,2435,2448,2461,2474,2499,2551,3713` | 本机 | `grep -n 'status="disabled"'` |
| offline 策略族 | 环境 229 + 永久 57（视图）；201 + 57（唯一端点） | 本机 | 命令 1 |
| restricted 策略族 | 放行 197 / 授权 32 / 永久 57 | 本机（模拟） | 命令 1 加环境变量 |
| 平台包计数 | 70 / 286 / 258 / 286 | 本机 + 生产 | 命令 4；`configs/platform-packages.lock.json` |
| 工具计数 | tool_count 258 / canonical 258；executable_count 0（路由口径；锁文件口径 257） | 本机 | 命令 2；`configs/tool-catalog.lock.json` |
| 参数与类型 | 650 = 294 + 356；必填 118；`type_enforced=false` 34 | 本机 | 命令 2 |
| 可用性分布 | 209 / 21 / 17 / 10 / 1 | 生产 | 命令 4 |
| 测试记录 | 285 实测 / 248 成功 / 37 失败 / 1 无记录 | 生产 | 命令 4 |
| 生产策略字段 | `policy_block_reason` 0/286 行存在 | 生产 | 命令 4（键集合） |
| 生产 `/api/tools` | HTTP 404 | 生产 | 命令 3 |

## 8. 附录：被证伪元素清单

| 元素 | 设计稿值 | 证伪依据 |
|---|---|---|
| 统计块「已核验 226」 | 226 | 任何字段与聚合都无此值。static 274 / availability 209 / tested 285 / success 248。三套口径均非 226（本机 offline 实测 + 生产实测）。 |
| 统计块「待测试 60」 | 60 | `status="pending"` 在当前源码 0 处。本机各组合下「待测试」为 0、20、81、196、200，无一为 60。生产待测试 = 1（本机 offline 实测 + 生产实测）。 |
| 统计块「禁用 11」 | 11 | 真值 12 能力视图 / 3 个唯一端点（`public_feed`、`generic_web`、`pypi_search`）。「11」只存在于旧版本目录（总行数 ≤229）（本机 offline 实测）。 |
| 核验率 79% | 79% | 79% 只能等于 226/286。226 不可得。候选比值：95.8%（静态）、81.0% / 86.7% / 99.7%（生产）。无候选落在 78.5–79.5（本机 offline 实测 + 生产实测）。 |
| 分类芯片 7 个标签 | 搜索与提取 / 社交与内容 / 电商与商品 / 情报与风控 / 代码与仓库 / 边缘与逆向 / 沙箱与拟人 | 7 个标签在 `apps/api` 与 `apps/scraper-console` 源码中 0 命中。标签与代码 12 类标签无逐字一致项（本机 offline 实测）。 |
| 分类芯片 7 个数字 | 136 / 49 / 29 / 24 / 15 / 13 / 13 | 合计 279，不等于 286。按 method / content_type / platform / collector_type 四维扫描，仅 1 处巧合相等（`content_type="news"` = 15）。无任何单一维度能供出这 7 个数（本机 offline 实测）。 |
| 横幅「阻止全部目录端点」 | 全量断言 | 只在 offline 模式成立。restricted 无批准时阻断 89/286（本机 offline 实测）。 |
| 横幅「切换执行环境即可放行」 | 换环境全放行 | 57 个端点换环境也不放行（unsupported 族）。原文：`{collector_type} 未具备受控出口，禁止执行`（本机 offline 实测）。 |
| 开关「11 个禁用端点」 | 11 | 见上一组「禁用 11」行。开关逻辑本身可做（过滤字段存在）（本机 offline 实测）。 |
| 侧栏徽标「26 平台包」 | 26 | `platform_count` = 70（本机与生产实测）。目录、工具与生产响应的数值字段中，无字段值等于 26（本机 offline 实测 + 生产实测）。 |
| 示例行 `apify_shein_product_detail` | 该行名 | 八个工作树与两处 API 响应全 0 命中。真名 `apify_shein_product_scraper`（本机 offline 实测）。 |
| 示例行 `apify_tiktok_ads_library_scraper` | 该行名 | 不在采集目录（258 端点无此类型）。仅在两处硬编码：`quick-collect-drawer.tsx:636`、`scripts/collector_demo_params.py:77`。真名 `apify_tiktok_ads_scraper`（本机 offline 实测）。 |
| 底部行 `web_search` | 该工具 | 在 catalog、tools、MCP 工具表、前端硬编码表中全 0 命中。全库无精确 `web_search` 标识（本机 offline 实测）。 |
| 底部行「2 必需 / 1 可选」 | (2,1) | 258 个端点中该组合为空集。含 2 个必填的端点只有 5 个：`github_repo`(2/0)、`autoscraper_enhanced_web`(2/3)、`anysearch_tag_search`(2/3)、`exa_deep_research`(2/5)、`exa_domain_search`(2/5)（本机 offline 实测）。 |
| `apify_1688_product_search`「参数 —」 | 「—」 | 该端点有必填 `keyword`（本机 offline 实测 + 生产实测）。 |
| 「系统设置」导航项 | 该项 | 控制台无对应页面。`settings/` 下只有 `account`（占位）与 `credentials`。全仓唯一「系统设置」在 `apps/web`（第二套前端，另一个应用）（本机源码核对）。 |
| 「共 286 视图」措辞 | 「视图」 | 术语表规定写「能力视图」。数字 286 本身成立（本机 offline 实测）。 |
