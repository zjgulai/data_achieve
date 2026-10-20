---
name: prd-insight-workbench
description: 母婴跨境出海数据洞察 Agent 工作台的完整产品需求文档。定义问题判据、能力层规格、页面验收、报告规格与行业模板。做产品规划、排期、验收时先读这份。
---

# PRD：DIH 洞察工作台

> 版本：v1.0 · 2026-10-20
> 依据：[Monid 逆向报告 v2](../architecture/【逆向报告】Monid源码-站点-产物-v2.md)
> 相邻文档：[Playbook](./【Playbook】母婴出海洞察交付.md) · [能力图谱](../architecture/【能力图谱】DIH-控制台能力地图.md)
> 交付形态：企业内部工作台 + 对外可演示的洞察报告

## 0. 一句话定位

**把一次母婴出海业务问题，变成一份带证据、可复现、可执行的洞察报告。**

输入是一句业务问题。输出是一份结论先行的交互式报告。
报告里的每个结论都挂证据。每个证据都能回到一次显式采集。
每条建议都能转成实验，并在下一周期复测。

## 1. 问题与目标

### 1.1 现状判据

你说“各个模块都不满意”。
本轮逆向把“不满意”拆成 7 条可验证的根因。
每条根因给一个判据。判据可以复跑。

每条根因给一个可执行的判据。
判据写成测试，不写成描述。

| # | 根因 | 判据（可执行测试） | 当前值 | 目标值 |
|---|---|---|---|---|
| R1 | 能力不可发现 | 对账测试：`set(_APIFY_ENDPOINT_DEFAULTS)` 减去 `set(catalog.endpoint_type)`，断言为空集 | 差集 31 条 | 差集 0，且加回归守卫 |
| R2 | 有采集无洞察 | 黄金报告检查：固定问题 × 固定种子数据，报告满足 4 项：①有决策句 ②有分群 ③每条 claim 有证据 ④有实验卡。四项全中记通过 | 0 / 4 | 4 / 4 |
| R3 | 有报告无证据链 | 引用测试：随机抽 10 条 claim，统计能点到 `raw_record` 或原文 URL 的比例 | 0% | 100% |
| R4 | UI 是控制台不是工作台 | 路径测试：新账号 → 输入问题 → 批准计划 → 出报告，统计路由数与人工动作数 | 路由 ≥ 5 | 路由 ≤ 2，人工动作 = 1 次批准 |
| R5 | 编排锁在 fixture 边界 | 回执断言：一次 T1 真实 run 的 `evidence_grade` 必须为 `L4_authorized_live`；全量报告里 `L2` 出现次数为 0 | 只有 `L2_fixture_local` | 至少 1 次 `L4`；报告 `L2` 计数 0 |
| R6 | 计量停在后台契约 | 字段断言：打开任一次 `TaskRun`，必须读到 `unit_price`、`total_cost_usd`、`remaining_budget` 三个字段且非空 | 0 个字段 | 3 个字段 |
| R7 | 没有行业模板 | 注册表计数：`ReportTemplate` 注册的模板数，且每个都能通过 2 品牌 × 2 市场的运行 | 0 | ≥ 5 |

R1 与 R7 的判据可以立刻跑。
R2 到 R6 需要先落能力层。

当前值的口径说明：

- R1 的 31 条按端点计，不按 collector 类计。
- R5 的基线来自 `schemas/workflow_executor_evidence.py` 的 `Literal["L2_fixture_local"]`。
- R7 在 `ReportTemplate` 注册表落地前，以 `report_contract` 的 `template_id` 取值为准。

这些判据必须在固定分支与固定数据种子上复跑。
命令与种子写进 M0 的验收记录。

### 1.2 为什么不能只改界面

问题在四层缺失，不在视觉。

现有控制台 16 个页面，13 个接真实查询。
后端注册 26 个路由模块，前端只调用约 10 个。
报告、情报、信号、实体、告警、通知、TikTok CDO 都没有 UI。

四层缺失：

1. 契约层。采集器只有 `required_params`。没有输入 schema、输出 schema、成本、风险、版本。
2. 编排层。planner 有骨架。候选来自 fixture，执行固定 `provider_call=False`。
3. 证据层。`Evidence` 表有 `url` / `excerpt` / `raw_record_id`。报告渲染器只打印证据数与情报 ID。
4. 渲染层。报告是 Markdown 模板拼接。`LLMService` 只有 `MockLLMAdapter`。

所以本 PRD 的重心是补这四层。
不是加页面。

### 1.3 产品目标

三个目标，按顺序达成。

| 目标 | 内容 | 达成标志 |
|---|---|---|
| G1 可发现 | 一个目录，一个事实源，自然语言可检索 | 幽灵端点 0；目录与执行层同一份数据 |
| G2 可交付 | 一句话到一份报告，报告有证据链 | R2 与 R3 达标 |
| G3 可复用 | 五个行业模板，报告与 SOP 同源 | 任一模板换品牌后可直接跑 |

## 2. 用户与场景

### 2.1 三类角色

企业是跨境电商母婴品牌出海。
报告要给三类人看。三类人的判据不同。

| 角色 | 关心 | 看报告的哪一段 | 判据 |
|---|---|---|---|
| 品牌负责人 | 要不要投、投多少、先做哪个市场 | 首屏决策句、行动实验卡、证据边界 | 30 秒内能复述一句决策 |
| 品类与选品 | 哪个 SKU 有缺口、价格带在哪、竞品怎么打 | 市场与价格、竞品定位、变体矩阵 | 能指出 1 个可验证的机会 |
| 内容与投放 | 说什么、对谁说、达人怎么选 | VOC、人群、叙事、达人内容 | 能写出 3 条 brief |

一条规则：**报告默认给品牌负责人看。**
其余两类的细节放到折叠区与筛选器里。

### 2.2 五个行业任务

五个任务对应五个模板。每个任务有自己的输入槽位与产出。

| 任务 | 触发 | 典型问题 | 产出 |
|---|---|---|---|
| T1 新品 VOC | 新品上市前 6–8 周 | “这款吸乳器在德国的主要差评主题是什么？” | VOC 洞察报告 + 编码本 |
| T2 竞品追踪 | 月度或竞品动作触发 | “Momcozy 和 Medela 在北美的定位差在哪？” | 竞争洞察报告 + 价格表 |
| T3 选品验证 | 季度选品会 | “婴儿推车在欧洲哪个价格带有空位？” | 选品机会报告 + 需求矩阵 |
| T4 达人投放复盘 | 投放结束后 2 周 | “这批达人带来的评论里，哪些是真实口碑？” | 达人复盘报告 + 噪声隔离 |
| T5 合规预警 | 每周或事件触发 | “我们的 SKU 有没有被召回或被判医疗宣称？” | 合规证据卡 + 风险清单 |

### 2.3 必须支持的输入槽位

每个任务都从同一个表单开始。表单字段固定，不随任务变化。

| 槽位 | 字段 | 必填 | 说明 | 例 |
|---|---|---|---|---|
| 品牌 | `brand` | 是 | 本方品牌 | Momcozy |
| 品类 | `category` | 是 | 母婴二级品类 ID。取自 `taxonomy/maternal_v1.json` | 吸乳器 / 婴儿推车 / 睡袋 |
| 竞品 | `competitors` | 否 | 0–5 个 | Medela |
| 市场 | `markets` | 是 | ISO 国家码，多选 | US / DE / JP |
| 语言 | `locale_by_market` | 是 | 每个市场指定采集语言 | DE → de |
| 时间窗 | `window` | 是 | 起止日期 | 近 90 天 |
| 决策问题 | `decision_question` | 是 | 一句话，可判定 | “Fit 与支撑哪个是主要摩擦？” |
| 不回答什么 | `does_not_answer` | 否 | 显式排除。默认带通用禁用清单 | “不推断销量与市场份额” |
| 负责人 | `owner` | 是 | 默认取当前用户。可改 | 项目负责人 |
| 任务类型 | `task_type` | 否 | T1–T5。留空时由系统推断 | T1 |

必填规则：

- 缺任一必填项不得开工。
- 竞品与不回答清单可空。
- `task_type` 留空时，S1 用规则加分类器给出候选与置信度。
  置信度低于 0.7 时，必须由用户确认。

`does_not_answer` 直接进入报告的证据边界。
Monid 的报告有同等机制。我们保留。

预算与停止条件不放在表单里。它们属于 `Authorization`，在 S2 批准时填写。

## 3. 产品形态

### 3.1 借 Monid 什么

借六件事：四件来自控制面，两件来自 API 语义。

| 借 | 理由 |
|---|---|
| 目录骨架：分类 rail + 紧凑行 + 搜索置顶 | 已验证可用，密度合适 |
| 端点详情：透明价格 + verified + 内嵌 playbook | 是 Monid 目录层最强的资产 |
| 三个动词：discover / inspect / run | 语义清晰，责任边界明确 |
| 端点由调用方显式 pin | 报告里每个数字可追溯到一次 run |
| run ledger | 成本与调用可审计 |
| `SKILL.md` 四道机制 | agent 零文档接入 |

### 3.2 不借 Monid 什么

| 不借 | 理由 |
|---|---|
| 订阅叙事与钱包 | 内部工具，用额度就够 |
| 客户端异步加载目录 | 不可分享，SEO 为零，首屏空 |
| 90px 展示字号与二进制纹理 | 与 B2B 工作台密度冲突 |
| 144 篇 programmatic 博客 | 不做内容农场 |
| 外部 agent 生成报告 | 无门禁、无 claim 模型、不可复现 |
| Mintlify 托管文档 | 数据外流，品牌不可控 |

### 3.3 信息架构

公开区与授权区分开。共 11 条路由，其中 8 条一级导航。

```text
公开区（5 条）
  /                     首页
  /capabilities         能力目录
  /capabilities/[id]    能力详情
  /reports/public/[id]  分享的报告
  /docs                 文档

授权区（6 条）
  /workbench            工作台首页（任务入口）
  /workbench/[taskId]   任务详情（对话 + 计划 + 证据）
  /reports              报告中心
  /reports/[id]         报告阅读页
  /connectors           连接器与凭据
  /settings             设置（成员、额度、审计）
```

规则：

- `/workbench` 是唯一入口。不是 `/dashboard`。
- 任务、运行、原始记录都是报告的下钻。不单独做一级入口。
- 公开区与授权区共用同一份目录数据。

## 4. 核心任务链

五段。每段有明确的输入、输出与人机分工。

```text
问题 → 计划 → 采集 → 分析 → 报告
 ↑                  ↑
 人工批准计划与成本   人工批准证据门禁
```

### 4.1 五段规格

| 段 | 输入 | 系统做 | 人做 | 输出 | 可跳过 |
|---|---|---|---|---|---|
| S1 问题 | 表单七槽位 | 校验、补全、识别任务类型 | 确认决策问题 | 结构化任务单 | 否 |
| S2 计划 | 任务单 | 选模板、列数据源、估成本、给排除理由 | 批准或改计划 | 计划单 + 成本估算 | 否 |
| S3 采集 | 计划单 | 执行 run、记录用量、标健康度 | 批准超出额度的调用 | 原始记录 + run ledger | 否 |
| S4 分析 | 原始记录 | 规范化、编码、算指标、生成 claim 与反证 | 裁决边界、医疗、法务 | claim 表 + 证据表 | 否 |
| S5 报告 | claim 表 | 渲染报告与 SOP、导出、分享 | 签收 | HTML 报告 + SOP | 否 |

### 4.2 每段的门禁

门禁不是提示。门禁是硬阻断。

| 门禁 | 触发 | 阻断什么 | 解除条件 |
|---|---|---|---|
| G-Plan | S2 结束 | 未批准计划不得执行 | 有人点批准 |
| G-Cost | 估算超额度 | 不得发起付费调用 | 有人提高额度或裁剪计划 |
| G-Evidence | S4 结束 | 无证据的 claim 不得进报告 | 补证据，或降级为 Hypothesis |
| G-Claim | claim 涉及医疗、法务、召回 | 不得标记为 Confirmed | 人工复核签字 |
| G-Publish | S5 结束 | 未签收不得对外分享 | 有人签收 |

### 4.3 三态结果

每次采集必须落到三态之一。

| 态 | 含义 | 报告如何处理 |
|---|---|---|
| 有结果 | 返回 ≥ 1 条可用记录 | 进入分析 |
| 空结果 | 调用成功，但无记录 | 记为 Evidence gap。不得写成“没有需求” |
| 失败 | 调用失败或凭据缺失 | 记为 Blocked。列在限制里 |

这条规则来自 Monid 的设计：
供应商非 2xx 是成功信封，不是异常。
我们要更进一步：**空结果必须是一种可交付的事实状态。**
报告里写“0 条合格记录表示门禁阻断，不表示没有反馈”。

## 5. 能力层规格

四层。每层有最小契约与验收判据。

### 5.1 契约层：ToolContract

新增一层。不重写采集内核。
用适配器包住现有可执行 collector。

先分清三个计数，不要混用：

| 计数 | 数值 | 含义 |
|---|---|---|
| collector type | 86 注册 / 99 声明 | 采集器实现类 |
| 可执行 collector type | 33 | 外访策略放行 |
| endpoint_type 映射 | 284 | 端点级映射 |
| Apify endpoint type | 95 | 走 `apify_actor` 的端点 |

`tool_catalog` 的计数单位是 **endpoint_type**，不是 collector type。
一个 `apify_actor` collector 承载 95 个 endpoint 合同。

最小字段集：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tool_id` | string | 是 | 稳定 ID。规则见下 |
| `provider` | string | 是 | 上游，如 `apify` |
| `endpoint_type` | string | 是 | 现有映射键 |
| `actor_id` | string | 条件 | Apify 类必填，取自 `_APIFY_ENDPOINT_DEFAULTS` |
| `display_name` | string | 是 | 中文名 |
| `category` | enum | 是 | 七个稳定值，见 5.2.2 |
| `markets` | string[] | 是 | ISO 国家码 |
| `input_schema` | JSON Schema | 是 | draft 2020-12 |
| `output_schema` | JSON Schema | 是 | 至少声明必返字段 |
| `content_types` | enum[] | 是 | `review` / `product` / `creator` / `ad` / `recall` / `trend` / `web_page` |
| `cost_model` | CostModel | 是 | 见下 |
| `risk_level` | enum | 是 | `low` / `medium` / `high` |
| `max_evidence_grade` | enum | 是 | 该工具能达到的上限，不是本次等级。见 5.4.2 |
| `contract_version` | string | 是 | 语义化版本 |
| `verified_at` | datetime | 是 | 最近实测时间 |
| `last_records_count` | int | 是 | 最近一次实测条数。0 且 status=success 视为可疑 |
| `health_status` | enum | 是 | `healthy` / `stable` / `degraded` / `outage` / `unknown` |
| `p50_latency_ms` | int | 否 | 最近 30 天实测中位数 |
| `execution_kind` | enum | 是 | `offline` / `guarded_http` / `provider_api` / `unsupported` |

`tool_id` 生成规则（确定性，不手填）：

```text
tool_id = "{provider}.{endpoint_type}.{market_scope}"
market_scope = 单市场时用 ISO 码小写；多市场时用 "multi"
```

例：`apify.apify_amazon_reviews_axesso.us`。

CostModel：

| 字段 | 类型 | 说明 |
|---|---|---|
| `currency` | string | ISO 4217，本项目统一 `USD` |
| `unit` | enum | `call` / `record` / `1k_records` |
| `unit_price` | decimal | 单价，保留 6 位小数 |
| `min_charge` | decimal | 最小计费额，默认 0 |
| `free_tier` | int | 免费条数，默认 0 |
| `quantity_basis` | string | 数量怎么算：`records_returned` / `records_requested` / `calls` |
| `estimate_formula` | string | 可执行的估算式，例 `max(min_charge, ceil(qty/1000)*unit_price)` |
| `source_url` | string | 定价页 |
| `updated_at` | date | 定价核对日 |

风险判定矩阵（`risk_level` 由三轴取最高）：

| 轴 | low | medium | high |
|---|---|---|---|
| 数据敏感性 | 公开商品信息 | 公开用户生成内容 | 含个人信息或需登录 |
| 法律与条款 | 明确允许 | 条款模糊 | 明令禁止或需授权 |
| 单次成本 | < $0.05 | $0.05–$1 | > $1 |

决策表：

| risk_level | 估算 ≤ 剩余额度 | 估算 > 剩余额度 |
|---|---|---|
| `low` | 直接执行 | 阻断，提示提额 |
| `medium` | 执行并在 ledger 标 `auto` | 需一次点击批准 |
| `high` | 需一次点击批准 | 阻断 |

验收判据：

- 目录里每一个条目都有 `input_schema`、`cost_model`、`risk_level`、`verified_at`。缺一项不得上线。
- Apify 类条目必须有 `actor_id`，且该 actor 必须存在于 `_APIFY_ENDPOINT_DEFAULTS`。
- 每个条目有 `verified_at`。超过 30 天标 stale。
- `last_records_count = 0` 且 `run_status = success` 的条目进入月度复核队列。判据来自 `platform_packages/notes` 的 silent-failure 记录。
- 幽灵端点 0。判据可复跑。

### 5.2 目录与发现

#### 5.2.1 唯一事实源

一个事实源：`tool_catalog`。
它由现有 collector 注册表与 endpoint 映射派生。
不维护第二份清单。

**与旧 `capability_catalog` 的关系（必须二选一，不能并存）：**

选方案 A：扩展旧表。

1. 给 `CapabilityImplementation` 增加 `tool_id`、`input_schema`、`output_schema`、`risk_level`、`cost_model`。
2. `tool_catalog` 只做投影视图。
3. 旧表继续作为写入源。

选方案 B：新表替代。

1. `tool_catalog` 为写入源。
2. 旧表冻结为只读。
3. 双读两个发布周期。
4. 给迁移脚本与回滚脚本。

本 PRD 采用方案 B。理由是旧表字段不足以承载 schema 与成本。
迁移步骤见 11.5。

规则：

- 目录与执行层读同一张表。
- 目录条目必须能被执行。不能执行的标 `unsupported` 并隐藏。
- 别名视图只做展示，不产生第二个 ID。
- 三处消费方必须返回同一组 `tool_id`。见 11.5.3。

验收判据：

- 目录条目数 = 可执行条目数 + 显式 unsupported 条目数。
- 差集为 0。

#### 5.2.2 分类：按任务，不按供应商

Monid 按 provider 与 leaf category 组织。
我们按 job-to-be-done 组织。

| 一级分类（`category` 稳定值） | 覆盖工具 |
|---|---|
| `consumer_insight` | Amazon 评论 / Trustpilot / Reddit / 社媒评论 / TikTok 评论 |
| `competitor_price` | Amazon 商品与价格 / TikTok Shop / 独立站 / Google Shopping |
| `selection_demand` | 搜索趋势 / 榜单 / 类目页 / 关键词 |
| `creator_content` | TikTok 达人 / Instagram / YouTube / 达人表现 |
| `compliance_recall` | CPSC / EU Safety Gate / OPSS / FDA / 药监 |
| `channel_retail` | 零售商页面 / Walmart / Target / 独立站 |
| `content_source` | 网页正文 / 文档 / RSS |

供应商名作为二级 facet，不是一级分类。

映射规则：284 个 `endpoint_type` 各映射到一个 `category`。
映射表存在 `tool_catalog.category`，由种子脚本生成。
未映射的端点不得进 discover。

#### 5.2.3 discover 语义

请求：

```json
{ "query": "德国吸乳器差评", "markets": ["DE"], "limit": 10 }
```

响应每条包含：

```text
tool_id · display_name · category · markets · cost_estimate
health · p50_ms · verified_at · content_types · why_this
```

`why_this` 是一句话，说明为什么推荐它。
这是 Monid 的 `hints` 的可读版本。

规则：

- 排序按任务匹配度，不按供应商。
- 不可用工具不出现在默认结果里。显式请求时排最后。
- 健康度只作 tie-breaker。

验收判据：

- 输入“德国吸乳器差评”，前 3 条必须包含 Amazon 评论类工具。
- 每条结果都有成本估算与最近核验时间。

### 5.3 编排层

#### 5.3.1 计划单

计划单是 S2 的产物。它必须可读。

```text
任务：德国吸乳器 VOC
模板：T1 新品 VOC
数据源：
  1. Amazon.de 评论（近 90 天，N≈800）  成本 $0.42  证据等级 L4
  2. Trustpilot 评论                     成本 $0.08  证据等级 L4
  3. Reddit r/beyondthebump             成本 $0.12  证据等级 L4
排除：
  - TikTok 评论：德语样本不足 50 条，不足以分群
  - 召回数据：本次不答复合规问题
预计成本：$0.62
预计耗时：4–7 分钟
```

规则：

- 每个数据源必须给排除理由或包含理由。
- 排除项保留在计划里，不静默丢弃。
- 计划单可编辑，编辑后重算成本。

#### 5.3.2 解锁真实调用

当前 workflow 执行固定 `provider_call=False`、`evidence_grade=L2_fixture_local`。
这是 R5 的根因。

改造要点：

1. 保留 planner 的候选扩展与预算逻辑。
2. 把候选源从 fixture 换成 `tool_catalog`。
3. 按 `risk_level` 与额度决定是否允许真实调用。
4. 回执写真实 `evidence_grade`。
5. 每次调用写 run ledger，带 `unit_price`、`total_cost`、`remaining_budget`。

验收判据：

- 一次真实调用后，回执 `evidence_grade` 为 `L4_authorized_live`。
- `TaskRun` 上能读到单价、总价、剩余额度。

### 5.4 证据层

#### 5.4.1 claim 与 evidence 多对多

必须新增 `claim`。
现有模型只有 `Evidence → IntelligenceItem`。

```text
claim
  id · task_id · text · claim_status · evidence_grade · owner
  scope_market · scope_window · scope_sample_n
  counterevidence_text

claim_evidence        （多对多）
  claim_id · evidence_id · role

evidence
  id · raw_record_id · url · excerpt · captured_at
  source_tool_id · market · locale · evidence_grade
```

`role` 取值：

| role | 含义 |
|---|---|
| `support` | 支持该 claim |
| `counter` | 反驳该 claim |
| `context` | 仅作背景，不参与判定 |
| `gap` | 本该有但没有 |

每条 claim 必须至少有 1 条 evidence。
若只有 `gap`，status 必须是 `Hypothesis` 或 `Blocked`。

验收判据：

- 报告里任取一条结论，能点到原文 URL 或原始记录。
- 反证字段非空率 100%。允许写“未发现反证”，但字段必须存在。

#### 5.4.2 证据等级

五个等级。数值不是置信度，是可复核性。

**证据等级属于一次 run，不属于一个工具。**

`ToolContract.max_evidence_grade` 是该工具能达到的上限。
`RunEvidenceGrade.grade` 是本次运行的实际等级。
计划单写 `target_grade`。合同写 `actual_grade`。

| 等级 | 含义 | 可写进报告的结论 |
|---|---|---|
| `L0_unverified` | 有定义，未实测 | 只能出现在计划里 |
| `L1_contract` | 契约已校验，未调用 | 不能写结论 |
| `L2_fixture_local` | 用夹具回放 | 只能写方法验证 |
| `L3_live_single` | 单次真实调用，样本小 | 只能写 Directional |
| `L4_authorized_live` | 授权真实调用，样本达标，有时间窗 | 可写 Confirmed |

确定性计算规则（不调用模型）：

```text
if not live_call:            grade = L2_fixture_local
elif not authorization_id:   grade = L3_live_single
elif sample_n < required_n:  grade = L3_live_single
elif window_days < required:  grade = L3_live_single
elif source_count < required: grade = L3_live_single
else:                        grade = L4_authorized_live
```

`RunEvidenceGrade` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `run_id` | uuid | 关联 TaskRun |
| `live_call` | bool | 是否真实调用 |
| `authorization_id` | uuid? | 关联 Authorization |
| `sample_n` | int | 合格记录数（过 G6 后） |
| `required_n` | int | 模板阈值 |
| `window_days` | int | 实际时间窗天数 |
| `required_window_days` | int | 模板阈值 |
| `source_count` | int | 有效数据源数 |
| `required_source_count` | int | 模板阈值 |
| `grade` | enum | 计算结果 |

`Authorization` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | uuid | — |
| `approver` | uuid | 批准人 |
| `scope` | string | 批准范围：模板 + 市场 + 时间窗 |
| `max_cost_usd` | decimal | 批准的成本上限 |
| `granted_at` | datetime | — |
| `expires_at` | datetime | 过期后回落到 L3 |

各模板阈值（唯一事实源，Playbook 引用这张表）：

| 模板 | `required_n` | 口径 | `required_window_days` | `required_source_count` |
|---|---|---|---|---|
| T1 VOC | 每层 30 条 | 帧成员数 | 60 | 2 |
| T2 竞品 | 每 brand×market 20 条商品 | 规范记录数 | 30 | 2 |
| T3 选品 | 每价格带 50 条商品 | 规范记录数 | 90 | 2 |
| T4 达人 | 20 个达人，每人 20 条评论 | 可用评论数 | 30 | 2 |
| T5 合规 | 命中或未匹配均需 12 个月窗 | — | 365 | 2 |

规则：

- 报告首屏必须显示两项：本次报告的**最低** `actual_grade`，以及 `gate_status`。
- 任一 claim 的等级低于 `L4` 时，该 claim 不得用“确认”“证明”“必然”等词。
- 证据等级由系统计算，不由模型声明。
- `expires_at` 过期的 Authorization 不得再用于新 run。

### 5.5 报告渲染层

#### 5.5.1 一份数据合同，两个渲染器

这是逆向得到的最重要结构。

```text
report_contract.json
   ├─ report.html     决策者视图（结论切片）
   └─ sop.html        执行者视图（流程切片）
```

合同字段：

顶层必须带 `schema_version`（语义化版本）与 `template_id`。

```json
{
  "schema_version": "1.0.0",
  "template_id": "t1_voc",
  "generated_at": "ISO-8601",
  "identity": { ... },
  "decision": { ... },
  "gates": [ ... ],
  "coverage": { ... },
  "metrics": [ ... ],
  "claims": [ ... ],
  "evidences": [ ... ],
  "run_ledger": [ ... ],
  "limits": [ ... ],
  "unknowns": [ ... ],
  "artifact": { ... }
}
```

各组的元素 schema：

**identity**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `task_id` | uuid | 是 | — |
| `brand` | string | 是 | 本方品牌 |
| `category` | string | 是 | 母婴品类 ID，取自 `taxonomy/maternal_v1.json` |
| `competitors` | string[] | 否 | 0–5 个 |
| `markets` | string[] | 是 | ISO 国家码 |
| `window` | object | 是 | `{start, end, days}` |
| `product` | string | 否 | 产品名 |
| `model` | string | 否 | 型号 |
| `variant_id` | string | 否 | 变体 ID |
| `sku` | string | 否 | 本方 SKU |
| `asin` | string | 否 | 目标市场 ASIN |
| `parent_asin` | string | 否 | 父 ASIN |
| `bundle` | string | 否 | 套装定义 |
| `offer` | string | 否 | 报价单元 |
| `mapping_confidence` | number | 否 | 0–1。低于 0.8 进 quarantine |
| `family_children` | object[] | 否 | 家族成员：`{variant_id, sku, asin, color, size}` |

**decision**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `decision_question` | string | 是 | 一句话 |
| `answer` | string | 是 | 结论句 |
| `protect` | string[] | 是 | 要守住的资产。来自 `decision-compass`。可为空数组 |
| `resolve` | string[] | 是 | 要解决的矛盾。可为空数组 |
| `prove` | string[] | 是 | 要验证的假设。可为空数组 |

`protect` / `resolve` / `prove` 是首屏决策指南的三个固定槽位。
允许空数组。不得省略键。

**gates[]**

| 字段 | 类型 | 说明 |
|---|---|---|
| `gate_id` | string | `G0`–`G10` 或 `G-Plan` / `G-Cost` / `G-Evidence` / `G-Claim` / `G-Publish` |
| `status` | enum | `pending` / `pass` / `fail` / `blocked` |
| `owner` | uuid? | 判定人 |
| `decided_at` | datetime? | — |
| `note` | string? | — |

**coverage**

按 `{source_tool_id, market, window}` 三键聚合。
每个单元给 `record_count`、`frame_member_count`、`status`（有结果 / 空结果 / 失败）。

**metrics[]**

| 字段 | 类型 | 说明 |
|---|---|---|
| `metric_id` | string | 稳定 ID |
| `label` | string | 中文标签 |
| `numerator` | number | — |
| `denominator` | number | — |
| `count_type` | enum | `raw_object` / `occurrence` / `canonical_record` / `frame_member` / `annotation` / `metric_row` |
| `frame` | string | 口径描述 |
| `as_of` | date | 数据日期 |
| `note` | string? | 限制 |

**claims[]**

| 字段 | 类型 | 说明 |
|---|---|---|
| `claim_id` | string | 稳定 ID |
| `text` | string | 结论句 |
| `claim_status` | enum | `confirmed` / `directional` / `hypothesis` / `evidence_gap` / `blocked` |
| `evidence_grade` | enum | `L0_unverified`–`L4_authorized_live` |
| `scope` | object | `{market, window, sample_n}` |
| `counterevidence_text` | string | 必填。可写“未发现反证” |
| `owner` | uuid | 本 claim 的责任人。与 task owner 分开 |
| `evidence_ids` | string[] | 至少 1 条 |

**evidences[]**

| 字段 | 类型 | 说明 |
|---|---|---|
| `evidence_id` | string | — |
| `claim_id` | string | 归属 claim |
| `role` | enum | `support` / `counter` / `context` / `gap` |
| `raw_record_id` | uuid? | — |
| `source_tool_id` | string | 必填 |
| `url` | string? | 原文链接 |
| `excerpt` | string? | 摘录 |
| `captured_at` | datetime | — |
| `market` | string | — |
| `locale` | string | — |
| `evidence_grade` | enum | 该条证据所属 run 的等级 |

**run_ledger[]**

| 字段 | 类型 | 说明 |
|---|---|---|
| `run_id` | uuid | — |
| `tool_id` | string | — |
| `endpoint_type` | string | — |
| `actor_id` | string? | Apify 类必填 |
| `unit` | string | — |
| `quantity` | number | — |
| `unit_price` | decimal | — |
| `total_cost_usd` | decimal | — |
| `authorization_id` | uuid? | — |
| `evidence_grade` | enum | 该 run 的实际等级 |
| `started_at` / `finished_at` | datetime | — |
| `outcome` | enum | `success` / `empty` / `failed` |

**limits[] / unknowns[]**

字符串数组。每条一句话。
`limits` 写本次不能推断什么。`unknowns` 写本次缺什么数据。

**artifact**

| 字段 | 类型 | 说明 |
|---|---|---|
| `report_html_sha256` | string | 报告 HTML 的哈希 |
| `sop_html_sha256` | string | SOP HTML 的哈希 |
| `contract_sha256` | string | 合同自身的哈希 |

哈希规则：

```text
contract_sha256 = SHA-256(RFC 8785 规范化 JSON，排除 artifact 组)
```

规则：

- 两个渲染器读同一份合同。
- 任何 headline 数字不得写死在模板里。
- 合同与 HTML 一起存档。三个哈希都写进两份页脚。
- 合同必须通过 `report_contract.schema.json` 校验。校验失败不得发布。

验收判据：

- 改合同里的一个数字，两个渲染器的输出都变。
- 报告页脚能读到两个 HTML 哈希与合同哈希。
- 合同校验有单元测试。故意破坏必填字段时必须报错。

#### 5.5.2 取代现有渲染器

现有 `_render_daily_report` 只输出三个通用章节。
替换为六段式 exhibit 模板。
保留 `Report` / `ReportSubscription` / `ReportAuditEvent` 模型与 `send` 能力。

新增：

- `ReportArtifact` 表：存合同 JSON、HTML、哈希、版本。
- 导出：HTML 与 PDF。
- 分享：项目内链接 + 过期时间 + 访问审计。

不新增：

- 公开社区。
- 自助支付。

### 5.6 计量与额度

#### 5.6.1 三种成本口径

| 口径 | 何时算 | 用途 |
|---|---|---|
| estimate | 计划生成时 | 批准前展示 |
| accrued | 执行中按已用时重算 | 长任务预警 |
| settled | 调用结束后按实测结算 | 账单与审计 |

#### 5.6.2 规则

- 每个 tool 有 rate card。没有 rate card 的工具不得进目录。
- 非 2xx 归零。
- 2xx 但空结果，按实际调用计费，但在报告里标 `gap`。
- 单次额度与每日额度分开。
- 超额度阻断，不降级。降级会让报告不可复现。

验收判据：

- 打开任一次运行，能看到单价、数量、总价、剩余额度。
- 额度耗尽时，发起调用返回明确错误码，不静默跳过。

### 5.7 Agent 接入

现有 MCP 有 13 个工具：5 个通用工具 + 8 个 TikTok 工具。
目标 18 个：保留 13 个，新增 5 个。

| 工具 | 状态 | 说明 |
|---|---|---|
| `list_platforms` | 保留 | — |
| `list_capabilities` | 改造 | 返回 `tool_catalog` 投影 |
| `describe_capability` | 改造 | 返回完整 ToolContract |
| `get_playbook` | 改造 | 返回结构化 playbook |
| `collect` | 保留 | 执行入口 |
| `tiktok_*`（8 个） | 保留 | 内容、电商、达人工具。不合并 |
| `discover` | 新增 | 自然语言检索，返回带理由的候选 |
| `inspect` | 新增 | 返回输入 schema、输出字段、成本、风险 |
| `get_run` | 新增 | 查单次运行状态与用量 |
| `list_records` | 新增 | 分页取原始记录 |
| `create_report` | 新增 | 用合同生成报告 |

规则：

- 所有工具走同一个调用门。
- 每个项目一把 `ProjectApiKey`。表字段：
  `{id, project_id, key_hash, name, tool_allowlist[], daily_collect_quota, created_by, last_used_at, revoked_at}`。
- 中间件按 `key_hash` 解析 project，把 `project_id` 注入请求上下文。
- 全局 `SCRAPY_MCP_TOKEN` 保留一个发布周期做双认证。写明退役日期。
- 根 `/skills/dih/SKILL.md` 提供零文档接入。
- `/llms.txt` 提供机器可读索引。

验收判据：

- 一个外部 agent 只读 `SKILL.md`，能完成 discover → inspect → collect → list_records。
- 工具数量有快照测试。新增或删除工具必须更新快照。
- key 调用白名单外的工具返回 403。
- 超额度返回明确错误码。
- 不同 project 不能互读记录。
- 全局 token 退役后，无项目 key 的请求返回 401。

## 6. 页面规格

每页给结构、数据源与验收判据。

### 6.1 首页 `/`

六区块。总高 4,500–5,500px。
比 Monid 短，因为我们内容少。

| # | 区块 | 内容 | 验收 |
|---|---|---|---|
| 1 | 首屏 | 一句话主张 + 决策问题输入框 + 3 个示例问题 | 输入框可直接跳 `/workbench?q=` |
| 2 | 数据源墙 | 只放已接通且有实测的数据源 | 每个 logo 可点，落到能力详情 |
| 3 | 五步流程 | 问题 → 计划 → 采集 → 分析 → 报告 | 每步可点，落到文档对应节 |
| 4 | 真实报告 | 一份已脱敏的报告片段，带证据徽章 | 点击进报告阅读页 |
| 5 | 行业模板 | 五个模板卡，各带一句适用场景 | 每卡可点，预填表单 |
| 6 | 常见问题 | 数据权利、证据等级、时效、费用、可复现性 | 折叠可展开 |

不写：

- 订阅口号。
- 钱包与免费额度。
- 声明式规模数字。只写实测数字。

首屏主张文案（建议）：

> 把一次母婴出海问题，变成一份有证据的洞察报告。

### 6.2 能力目录 `/capabilities`

| 区块 | 规格 |
|---|---|
| 搜索栏 | 置顶，粘性。支持自然语言。结果计数可见 |
| 分类 rail | 240px 粘性。七个一级分类 |
| facet | 市场、内容类型、成本区间、健康度、最近核验 |
| 结果区 | 紧凑行，不是卡片网格 |
| 行字段 | 名称、分类、覆盖市场、成本、健康度、最近核验、证据等级 |
| 空态 | 区分三种：无结果、无权限、加载失败 |
| URL 状态 | 所有筛选写入 query string |

验收判据：

- 首屏 SSR 出结果，不依赖客户端请求。
- 刷新页面筛选状态不丢。
- 搜索“德国吸乳器差评”前 3 条命中评论类工具。

### 6.3 能力详情 `/capabilities/[id]`

| 区块 | 内容 |
|---|---|
| 头部 | 名称、分类、覆盖市场、成本、健康度、最近核验 |
| 输入 | 参数表，按 schema 渲染，含类型、必填、默认值、示例 |
| 输出 | 字段表，含类型与示例 |
| 示例 | 一次真实调用的请求与截断响应 |
| 内嵌 playbook | 步骤、坑点、验收、风险边界 |
| 相关 | 同类工具、替代方案、上游依赖 |
| 操作 | 复制 CLI / MCP / REST 三种调用 |

这是与 Monid 差距最大的一页。
Monid 的 modal 没有参数表与示例。我们要有。

验收判据：

- 参数表从 `input_schema` 渲染，不手写。
- 示例来自真实 run，带 `run_id`。

### 6.4 工作台 `/workbench`

单页。左中右三栏。

```text
左：项目与任务列表
中：对话 + 计划单 + 执行进度
右：证据抽屉 + 成本 + 门禁状态
```

流程：

1. 输入问题。
2. 系统出计划单。
3. 人批准或修改。
4. 系统执行，实时显示每一步。
5. 系统产出报告，跳到阅读页。

验收判据：

- 新用户不读文档，5 分钟内产出第一份报告。
- 必须经过的路由数 ≤ 2。
- 计划单可编辑。编辑后成本重算。
- 执行中可中止。中止保留已完成部分。

### 6.5 报告中心 `/reports`

| 区块 | 内容 |
|---|---|
| 筛选 | 任务类型、品牌、市场、时间、状态 |
| 列表 | 标题、结论句、最低证据等级、生成时间、签收状态 |
| 行操作 | 打开、导出、分享、复制结论 |

### 6.6 报告阅读页 `/reports/[id]`

按第 7 节规格。

必须有的交互：

1. 章节锚点导航。
2. 市场筛选。
3. 人群或分群 tab。
4. 证据抽屉，一次展开全部。
5. 明暗主题。
6. 打印。
7. 复制单条结论。

不做的交互：

- 排序。报告不是表格。
- 图表 tooltip。数据点即标签。

### 6.7 其余页面

| 页面 | 规格 | 优先级 |
|---|---|---|
| `/connectors` | 合并平台目录、凭据配置、实时可用性 | P1 |
| `/settings` | 成员、角色、额度、审计日志 | P1 |
| `/docs` | 三栏。API 参考、数据源、报告规范、行业模板、证据与引用 | P1 |
| `/reports/public/[id]` | 只读分享页，带过期与访问审计 | P2 |

## 7. 报告规格

### 7.1 章节骨架

T1 VOC 模板用 11 章。其余模板可裁剪。

| # | 章节 | 一句话目标 |
|---|---|---|
| 00 | Executive Answer | 一句决策句 + 3 张关键数字卡 + 证据状态条 |
| 01 | Core Tension | 主要矛盾是什么 |
| 02 | Experience Signature | 哪些主题正向、哪些负向 |
| 03 | Sample Lenses | 样本设计如何改变结论 |
| 04 | Mixed Experience | 混合体验的共现模式 |
| 05 | Need States | 需求场景分群 |
| 06 | Moments of Truth | 风险出现在哪个环节 |
| 07 | Social Firewall | 社媒能否代表自然口碑 |
| 08 | Evidence Applicability | 覆盖到了什么、没覆盖什么 |
| 09 | Validation Agenda | 先验证哪三件事 |
| 10 | Trust & Limits | 能说什么、不能说什么 |

每章一个结论句作 H2。
结论句必须能被单独引用。

### 7.2 六段式 exhibit

| 段 | 必填 | 规则 |
|---|---|---|
| 1 结论图题 | 是 | 一句话，含数字 |
| 2 scope + 徽章 | 是 | 样本量、时间窗、证据等级 |
| 3 图表 | 是 | CSS 实现。不用图表库 |
| 4 三段读图 | 是 | Interpretation / Counterevidence / Decision |
| 5 人声 | 否 | 注明“人工释义，不是原文引语”并给记录 ID |
| 6 来源脚注 + 证据抽屉 | 是 | Basis / Unit / Limit / Status |

第 4 段是硬要求。
缺 Counterevidence 的 exhibit 不得渲染。

### 7.3 claim 状态机

证据等级与 claim 状态是两套层级。不要混用名称。

证据等级描述**数据有多可复核**。
claim 状态描述**这句结论能说到多强**。

```text
L0_unverified
   ↓ 契约校验
L1_contract
   ↓ 夹具回放
L2_fixture_local
   ↓ 单次真实调用
L3_live_single
   ↓ 样本达标 + 时间窗 + 授权
L4_authorized_live
```

等级决定 claim 状态的上限：

| 证据等级 | 允许的最高 claim 状态 |
|---|---|
| `L0_unverified` | 不得生成 claim |
| `L1_contract` | 不得生成 claim |
| `L2_fixture_local` | `hypothesis` |
| `L3_live_single` | `directional` |
| `L4_authorized_live` | `confirmed` |

claim 状态的可用词表：

| claim 状态 | 允许 | 禁止 |
|---|---|---|
| `confirmed` | “确认”“显示”“达到” | — |
| `directional` | “方向性支持”“迹象表明” | “证明”“必然” |
| `hypothesis` | “假设”“待验证” | “显示”“达到” |
| `evidence_gap` | “未覆盖”“样本不足” | 任何结论性表述 |
| `blocked` | “门禁未解除”“不可推断” | 任何结论性表述 |

`evidence_gap` 与 `blocked` 是结果状态，不是失败。
它们必须出现在报告里。

### 7.3.1 两个显示项，不合并

报告首屏同时显示两行：

```text
证据等级：最低 L3_live_single · 门禁：G7 PENDING
claim 分布：confirmed 2 · directional 5 · hypothesis 3 · gap 1 · blocked 1
```

证据等级回答“数据够不够硬”。
门禁状态回答“流程走没走完”。
claim 分布回答“结论强度结构”。

三项分开显示。不得合并成一个“可信度”数字。

### 7.4 禁止输出

每个模板必须声明自己的禁止输出清单。
至少包含：

1. 不推断销量、份额、营收。
2. 不把评论方向性证据写成总体比例。
3. 不做医疗结论。健康类表述必须标“非医疗建议”。
4. 不把社媒声称当作自然消费者口碑。
5. 不把不同样本来源的计数相减或相加。
6. 不把定性优先级热力图当作量化评分。
7. 不在证据等级不足时给单一结论。

### 7.5 SOP 视图

同一份合同渲染第二份页面。

SOP 包含：

| 区块 | 内容 |
|---|---|
| 阶段 stepper | G0–G10，每阶段给 inputs / outputs / acceptance / rollback |
| 数据合同 | 六种计数定义：原始对象、出现、规范记录、帧成员、标注、指标行 |
| 算法 | 准入、去重、编码、校准、计算、解释、行动、复核 |
| 校准 | 双盲编码与一致性指标 |
| skill 清单 | 每个 skill 的输入输出与验收 |
| 检查清单 | 交付前逐项勾选 |
| 验证记分卡 | 校验项通过数 / 总数 |
| 案例边界 | 本次跑到哪个门禁 |

验收判据：

- 报告与 SOP 读同一份合同。
- 合同的 gate 状态在两份页面一致。
- 换品牌重跑，SOP 的阶段与验收不变。

## 8. 行业模板

五个模板。每个绑定数据源、字段、证据等级、报告章节。

### 8.1 T1 新品 VOC

| 项 | 内容 |
|---|---|
| 目的 | 上市前找主要摩擦与预期错配 |
| 主数据源 | Amazon 评论：`apify_amazon_reviews_axesso`（`axesso_data/amazon-reviews-scraper`，实测 99.9%，按 `domainCode` 分市场） |
| 备数据源 | `apify_amazon_reviews_scraper`（`junglee/amazon-reviews-scraper`，实测成功 5 条）。**主源空时才启用，且需人批准** |
| 禁用 | `apify_amazon_reviews_extractor`（`web_wanderer/amazon-reviews-extractor`）。2026-10-15 实测恒 0 条，`severity=blocker` |
| 补充源 | Trustpilot（`apify_trustpilot_reviews_scraper`，实测成功）、TikTok 评论（`apify_tiktok_comments_scraper`） |
| 风险源 | `apify_reddit_scraper`（`harshmaur/reddit-scraper`，实测 failed 0 条）。启用前必须重测 |
| 核心字段 | 评论原文、评分、日期、市场、语言、变体、是否已验证购买 |
| 编码维度 | Fit、支撑、漏液、清洁、泵量、噪声、便携、可穿性、价值 |
| 分母规则 | 锁定 frame。不得跨来源相加 |
| 证据等级 | 需 `L4` 才能写 prevalence。阈值见 5.4.2 |
| 章节 | 00–10 全用 |
| 门禁 | G7 校准未通过时，所有结论降为 Directional |

### 8.2 T2 竞品追踪

| 项 | 内容 |
|---|---|
| 目的 | 还原货架、还原定价、还原定位 |
| 数据源 | Amazon 商品与价格（`apify_amazon_product_scraper` 实测成功、`apify_amazon_price_tracker` 实测成功）、TikTok Shop（`apify_tiktok_shop_search_scraper` 实测成功 3 条）、独立站（`ecommerce_product_page`，需域名 grant）、零售商页（`apify_walmart_product_scraper` / `apify_target_products_scraper`，优先于 `generic_web`） |
| 核心字段 | 型号、变体、offer、价格、货币、促销、库存状态、评论数、评分、A+ 内容 |
| 关键规则 | 同一型号名不等于同一 offer。必须先做 model → variant → bundle → offer 映射 |
| 章节 | 执行摘要 / 情境-冲突-问题-答案 / 竞争架构 / 市场与价格 / 人群与叙事 / 90 天行动 / 证据边界 |
| 禁止 | 不把页面价当成交均价。不把评论数当销量 |

### 8.3 T3 选品验证

| 项 | 内容 |
|---|---|
| 目的 | 找价格带空位与需求缺口 |
| 数据源 | Amazon 榜单：改用 `apify_amazon_bestsellers` 的 `position` + `categoryFullName` 字段（实测 failed 0 条，启用前必须重测）。类目页（`ecommerce_product_discovery`，需域名 grant）、TikTok Shop 搜索（`apify_tiktok_shop_search_scraper`，实测成功）、搜索趋势（`apify_google_trends_scraper`） |
| 禁用 | `apify_tiktok_shop_search_v2`。只在 `_ENDPOINT_TO_COLLECTOR` 有一行映射，`_APIFY_ENDPOINT_DEFAULTS` 无此键，调用返回 400 |
| 备用榜单 | `apify_amazon_product_scraper`（`junglee/amazon-crawler`）的 `rank` 字段 |
| 核心字段 | 价格、评分、评论数、上架时间、变体数、类目排名 |
| 核心算法 | 价格带 × 需求强度 × 竞争密度的三轴矩阵 |
| 章节 | 机会结论 / 价格带 / 竞争密度 / 需求信号 / 候选 SKU / 验证计划 / 证据边界 |
| 禁止 | 不推断实际销量。榜单排名不等于销量 |

### 8.4 T4 达人投放复盘

| 项 | 内容 |
|---|---|
| 目的 | 分清真实口碑与投放噪声 |
| 数据源 | TikTok 达人（`tikhub_tiktok_creator_info`、`tikhub_tiktok_user_posts`）、TikTok 视频（`apify_tiktok_scraper`）、TikTok 评论（`apify_tiktok_comments_scraper`）、Instagram（`apify_instagram_*`） |
| 核心字段 | 达人 ID、粉丝数、互动率、视频、发布日、评论、是否有商业标识 |
| 核心算法 | 噪声隔离。按实体、市场、意图匹配隔离 |
| 章节 | 投放概览 / 噪声隔离 / 内容主题 / 评论真实度 / 达人分层 / 复投建议 / 证据边界 |
| 禁止 | 不把商业内容下的评论当自然口碑 |

### 8.5 T5 合规预警

| 项 | 内容 |
|---|---|
| 目的 | 把合规状态挂到每条结论上 |
| 数据源 | `public_feed`（FDA Food Safety Recalls、UK OPSS、UK NHS、PR Newswire）与 `generic_web`（CPSC、EU Safety Gate） |
| 前置条件 | 四个采集器全部属 `guarded_http`。默认 `COLLECTION_HTTP_GRANTS=[]`，**未配置 grant 时一律拒绝**。必须先完成 M1.5 |
| 抽取要求 | `public_feed` 只返回 RSS 条目（title / link / published_at / author / tags / summary），`generic_web` 只返回正文与 HTML。两者都产不出通报结构化字段，必须加抽取层。见下 |
| 抽取契约 | `{recall_id, product_name, brand, risk_type, market, published_at, action, url}` |
| 验收 | 先用 20 条已知通报建 golden set。`recall_id` 与 `url` 必须 100%，`brand` 与 `risk_type` ≥ 90% |
| 核心字段 | 通报号、产品名、品牌、风险类型、市场、日期、处置措施、原文链接 |
| 核心算法 | 品牌与 SKU 匹配。匹配不到记 `gap`，不记“无风险” |
| 章节 | 风险结论 / 召回状态 / 宣称风险 / 市场限制 / 处置建议 / 证据边界 |
| 禁止 | 不做法律意见。不给“合规”结论。只给“已核查的公开通报状态” |

### 8.6 模板注册表

`ReportTemplate` 是唯一事实源。
PRD 第 8 节与 Playbook 第 2–6 节都引用它。

| 字段 | 类型 | 说明 |
|---|---|---|
| `template_id` | enum | `t1_voc` / `t2_competitor` / `t3_selection` / `t4_creator` / `t5_compliance` |
| `version` | string | 语义化版本 |
| `title` | string | 中文名 |
| `sections[]` | object[] | `{id, title, required, exhibit_type}` |
| `sources[]` | string[] | 允许的 `tool_id` 前缀 |
| `required_fields[]` | string[] | 合同必须出现的字段 |
| `evidence_rules` | object | 引用 PRD 5.4.2 的阈值 |
| `prohibited_outputs[]` | string[] | 本模板的禁止输出 |
| `gates[]` | string[] | 必须通过的 G 阶段 |

规则：

- 章节 ID 在 PRD、Playbook、渲染器三处一致。
- 新增模板必须先在注册表登记，再写渲染器。
- `prohibited_outputs` 不得为空。最低七条见 7.4。

### 8.7 模板的复用要求

每个模板必须满足：

1. 换品牌、换品类、换市场后可跑。
2. 数据源可增减，章节结构不变。
3. 证据等级与禁止输出随模板固定。
4. 报告与 SOP 共用一份合同。

验收判据（可执行）：

- 每个模板跑 2 品牌 × 2 市场，共 4 份报告。
- 每份报告的必需字段非空率 100%。
- 与黄金报告的段落级 diff 通过。
- 全空报告判失败，不计入通过数。

## 9. 非目标

本版本明确不做。

| 不做 | 理由 |
|---|---|
| 对外 SaaS 与自助支付 | 内部工具。计费用额度 |
| 公开社区与内容市场 | 无运营能力 |
| programmatic SEO 博客 | 不做内容农场 |
| 自动生成医疗或法律结论 | 风险不可控 |
| 跨供应商自动 fallback | 会让报告不可复现 |
| 实时流式采集 | 报告是周期性交付物 |
| 移动端编辑 | 只保证移动端可读 |
| 自建浏览器集群 | 用现有 provider 与受控 http |

## 10. 依赖与风险

| # | 风险 | 影响 | 处置动作 | 责任里程碑 | 验收判据 |
|---|---|---|---|---|---|
| 1 | 4 个 `guarded_http` 采集器默认无 grant。`COLLECTION_HTTP_GRANTS` 默认 `[]`，`http_grant()` 缺配置即抛 `CollectionPolicyDenied` | T5 全部 6 个源、T2/T3 的域名页在默认配置下必然被拒 | 新增 M1.5。首批 host：`generic_web` 至少 cpsc.gov、ec.europa.eu；`public_feed` 至少 fda.gov、gov.uk、prnewswire.com；`ecommerce_product_page` 列 T2 首批独立站域名；`ecommerce_product_discovery` 列类目页域名。写入 `.env.example` 与两套 compose | M1.5 | 对 4 个类型各跑一次真实调用，全部返回记录；grant 过期测试返回明确错误码 |
| 2 | 53 个采集器被永久拒绝 | 中文社媒、OSINT、浏览器类不可用 | 明确不在本期范围。文档写清 | M1 | 目录中 0 条 `unsupported` 类型可被 discover 返回 |
| 3 | 13 个 catalog 类型不是独立 collector。11 个经 `apify_actor` 端点路由可执行；2 个无执行路径 | 若按“全部隐藏”处置，会删掉 T2/T3 的数据源 | 只隐藏 2 个：`apify_shopify_full_catalog`、`bilibili_video_info`。11 个可执行项进目录 | M1 | 目录包含 `apify_amazon_bestsellers`、`apify_amazon_price_tracker`；不含上述 2 个 |
| 4 | 25 条路由未挂载 | 能力存在但不可达 | 逐条决定：挂载或删除 | M0 | 未挂载路由数为 0，且每条有决定记录 |
| 5 | 137 个测试在基线失败（133 integration + 4 unit） | 无法判断回归 | 采用“不得新增失败”策略，不要求清零 | M0 | `pytest -q` 失败集合 ⊆ `reports/live-sweep/baseline-pytest-failures.txt` |
| 6 | LLM 只有 Mock。`settings.llm_provider` 未被消费 | 报告无法自动起草 | 接入真实模型。所有起草结果进人工批准 | M4 | 20 条评测集通过；起草结果 100% 标 `drafted_by=model` 且有批准人 |
| 7 | 11 个模块 43 处直接调用 + 124 条已挂载路由经 `get_auth_context` 回退 demo workspace | 多租户隔离不真实 | 上线前移除兜底 | M0 | 无 token 请求返回 401；跨项目读取返回 403 |
| 8 | 数据源条款与隐私 | 合规风险 | 模板记录来源权利与使用限制 | M1 | 每个工具条目有 `rights_status`、`license_url`、`terms_notes`、`checked_at` |
| 9 | provider 凭据只走环境变量 | 无法按项目隔离 | 迁移到项目级凭据 | M1 | 两个项目用不同 key 调同一工具，各自成功且互不可见 |
| 10 | catalog 多个数字不一致（303/275 工作树 vs 286/258 生产） | 报告数据不可信 | 先统一事实源，再谈报告 | M0 | `catalog_digest` 在 catalog API、MCP、控制台三处一致 |
| 11 | Amazon 评论主力 actor 曾失效（`web_wanderer` 恒 0 条，`severity=blocker`） | T1/T2 主样本可能为空 | 主源改 axesso；加 CI preflight 与真实 smoke | M1 | 模板引用的每个 endpoint 同时存在于 `_ENDPOINT_TO_COLLECTOR`、`_APIFY_ENDPOINT_DEFAULTS`、catalog；smoke 断言 `records_count > 0` |
| 12 | TikTok R1 的 21 张 canonical 表未应用 | T4 达人数据只能落原始记录 | 备份 + 目标授权 + 应用迁移 + 回滚演练；或 T4 移出首批 | M7b | 21 张表已应用；100 条 fixture 通过；回滚演练记录在案 |

## 11. 里程碑

按依赖排序。每个里程碑有独立验收。

| 里程碑 | 内容 | 输入 | 输出 | 验收 | 预估 |
|---|---|---|---|---|---|
| M0 基线 | 统一 catalog 事实源；清幽灵端点；决定 25 条未挂载路由；移除 demo 兜底 | 工作树 | 单一 catalog；路由决定表 | 幽灵端点回归测试为绿；失败集合 ⊆ 基线；无 token 返回 401 | 1 周 |
| M1 契约层 | ToolContract 与适配器；33 个 collector type；95 个 Apify endpoint 合同 | M0 的 catalog | `tool_catalog` 表 | 每个条目有 schema、CostModel、risk、`max_evidence_grade`、`verified_at` | 2 周 |
| M1.5 外访授权 | 为 4 个 `guarded_http` 类型配置精确域名 grant | M1 的 tool 清单 | grant 配置与轮换流程 | 4 个类型各跑一次真实调用并返回记录 | 1 周 |
| M2 目录 | `/capabilities` 与详情页，SSR + facet | M1 + M1.5 | 目录与详情页 | 首屏 SSR 出结果；参数表由 schema 渲染 | 2 周 |
| M2.5 证据阈值 | 落地 5.4.2 的模板阈值与 `RunEvidenceGrade` 计算函数 | M1 | 计算函数与阈值表 | 四个等级的单元测试通过 | 0.5 周 |
| M3 编排 | 计划单、成本估算、真实调用解锁 | M1.5 + M2.5 | 计划单与执行回执 | 一次真实 run 回执 `L4`；run 带单价、总价、剩余额度 | 3 周 |
| M4 证据层 | `claim` / `claim_evidence`；证据状态机 | M2.5 | 证据表与状态机 | 结论可点回原文；反证字段 100% | 2 周 |
| M5 报告 | 合同、两个渲染器、导出与分享 | M4 | `ReportArtifact` | 改合同数字，两页同步变 | 3 周 |
| M6 工作台 | 单页任务链 | M3 + M5 | `/workbench` | 新用户 5 分钟出第一份报告 | 2 周 |
| M7a 模板一批 | T1、T5、T2 | M1 + M3 + M4 + M5 | 三份黄金报告 | 每模板 2 品牌 × 2 市场跑通 | 2 周 |
| M7b 模板二批 | T3、T4 | M7a + TikTok R1 迁移 | 两份黄金报告 | 换品牌可跑；T4 依赖 21 张表已应用 | 2 周 |
| M8 接入 | SKILL.md、llms.txt、MCP 工具补齐 | M2 + M3 | 接入包 | 外部 agent 零文档接入 | 1 周 |

总计约 22.5 周。

依赖图：

```text
M0 → M1 → M1.5 → M3 → M6
      ↓      ↓      ↑
      M2 → M2.5 → M4 → M5 → M6
                          ↓
                    M7a → M7b
```

关键约束：

- M3 依赖 M2.5。没有阈值就无法判定 `L4`。
- M7b 的 T4 依赖 TikTok R1 迁移已应用。未应用时 T4 顺延。
- M8 可与 M6 并行。

## 11.5 迁移与上线

新增表与改造表必须写迁移脚本。不允许手工改库。

### 11.5.1 表变更

| 表 | 变更 | 回填 | 回滚 |
|---|---|---|---|
| `tool_catalog` | 新建 | 由 `collector_catalog` + `_ENDPOINT_TO_COLLECTOR` 生成 | 删表 |
| `claims` | 新建 | 从现有 `intelligence_items` 的 title/summary 生成初版。`claim_status` 默认 `hypothesis` | 删表 |
| `claim_evidence` | 新建 | 由现有 `evidences` 按 `intelligence_id` 回填，`role` 默认 `support` | 删表 |
| `evidences.intelligence_id` | 改为 nullable | 先加新列，双写一个周期，再切读 | 保留旧列 |
| `report_artifacts` | 新建 | 旧报告不回填，只对新报告生成 | 删表 |
| `report_shares` | 新建 | — | 删表 |
| `project_api_keys` | 新建 | 迁移现有全局 token 为单项目 key | 恢复全局 token |
| `reports.report_type` | 扩枚举 | 映射旧值为 `daily_digest` | 保留旧值 |

### 11.5.2 灰度顺序

| 阶段 | 范围 | 观察指标 | 回退条件 |
|---|---|---|---|
| 1 | 内部一个项目 | catalog 一致性、真实调用成功率 | 任一不一致 |
| 2 | T1 模板单市场 | 报告可读性、证据可点击率 | 证据可点击率 < 95% |
| 3 | T1 多市场 + T2 | 成本偏差、并发稳定性 | 成本偏差 > 20% |
| 4 | 五个模板 | 全量指标 | 任一 P0 缺陷 |

### 11.5.3 双写与切读

`tool_catalog` 上线后，`/api/collectors/catalog`、MCP `list_capabilities`、控制台目录三处同时读新表。
保留两个发布周期。

对账测试：

```text
set(tool_id from catalog API)
  == set(tool_id from MCP list_capabilities)
  == set(tool_id from console)
```

三处不一致时，发布阻断。

## 12. 验收清单

上线前逐项核对。

### 12.1 产品

- [ ] 新用户不读文档，5 分钟内产出第一份报告。
- [ ] 报告首屏能复述一句决策句。
- [ ] 任取一条结论，能点到原文或原始记录。
- [ ] 报告页脚有合同哈希与生成时间。
- [ ] 报告与 SOP 的 gate 状态一致。
- [ ] 空结果显示为 Evidence gap，不显示为“无需求”。
- [ ] 失败结果显示为 Blocked，并列在限制里。
- [ ] 证据等级不足时，结论用词合规。

### 12.2 能力

- [ ] 幽灵端点差集为 0，并有回归守卫测试。
- [ ] 目录每个条目有输入 schema、输出字段、成本、风险、核验时间。
- [ ] 每个执行回执有真实 `evidence_grade`。
- [ ] 每次运行有单价、数量、总价、剩余额度。
- [ ] 额度耗尽时返回明确错误码。
- [ ] 无执行路径的 2 个类型不出现在 discover；11 个经 `apify_actor` 可执行的仍在目录。
- [ ] 53 个 unsupported 类型不出现在目录。

### 12.3 接入

- [ ] 外部 agent 只读 `SKILL.md` 能完成 discover → inspect → run。
- [ ] MCP 18 个工具可用（13 个现有 + 5 个新增）。
- [ ] 每个请求能定位到项目。
- [ ] 全局 token 已退役。
- [ ] `/llms.txt` 与 `/llms-full.txt` 可访问。

### 12.4 质量

- [ ] 基线测试全绿。
- [ ] 每条根因判据可复跑。
- [ ] 报告模板有黄金样本，可回归比对。
- [ ] 五个模板各有一份完整样例报告。

## 13. 与旧文档的关系

| 文档 | 保留 | 变更 |
|---|---|---|
| [Monid 逆向 v1](../architecture/【逆向报告】Monid网站UI与能力逆向.md) | 首页与目录的证据 | 三条判断由 v2 修正 |
| [整站能力整合方案](../architecture/【技术方案】DIH整站能力整合方案.md) | 单一目录、单一调用门、受控适配器 | 补契约层与报告层 |
| [控制台能力地图](../architecture/【能力图谱】DIH-控制台能力地图.md) | 页面清单与状态分布 | 页面重组为第 6 节 |
| [首页与目录视觉规范](../architecture/【设计规范】DIH首页与目录视觉规范.md) | 品牌映射、间距、组件角色 | 补报告页视觉 |
| 本 PRD | — | 新增产品定义与验收 |

本 PRD 取代旧文档中的产品范围部分。
技术实现细节仍以旧文档为准。
