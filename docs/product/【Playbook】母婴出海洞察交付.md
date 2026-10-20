---
name: playbook-maternal-export-insight
description: 母婴跨境出海洞察交付 Playbook。五条任务配方（VOC/竞品/选品/达人/合规），每条给触发条件、输入槽位、采集步骤、分析步骤、报告章节、门禁与验收判据。执行一次洞察交付前先读这份。
---

# Playbook：母婴出海洞察交付

> 版本：v1.0 · 2026-10-20
> 依据：[PRD](./【PRD】母婴出海数据洞察Agent工作台.md) · [Monid 逆向报告 v2](../architecture/【逆向报告】Monid源码-站点-产物-v2.md)
> 参照形态：`ref/monid-prompt-insight/` 的两份 SOP（G0–G10 stepper + 输入输出契约 + 检查清单）

## 0. 用法

本 Playbook 是配方，不是说明。

每次交付按四步走：

1. 选任务类型（T1–T5）。
2. 填七个输入槽位。
3. 按对应任务的阶段序列执行。
4. 过门禁，签收。

不能跳步。跳步的报告不可复现。

## 1. 通用约定

### 1.1 七个输入槽位

所有任务共用。缺一项不得开工。

| # | 槽位 | 必填 | 校验规则 |
|---|---|---|---|
| 1 | 品牌 | 是 | 必须能映射到至少 1 个商品家族 |
| 2 | 品类 | 是 | 必须在母婴二级品类表内 |
| 3 | 竞品 | 否 | 1–5 个。超过 5 个拆两次跑 |
| 4 | 市场 | 是 | ISO 国家码。必须给出语言 |
| 5 | 时间窗 | 是 | 起止日期。默认近 90 天 |
| 6 | 决策问题 | 是 | 一句话，可判定。不能是“了解一下” |
| 7 | 不回答什么 | 否 | 显式排除项。默认带通用禁用清单 |

### 1.2 阶段编号

沿用 G0–G10。三个 cross-stage 常驻。

| 阶段 | 名称 | 产出 |
|---|---|---|
| G0 | Decision Charter | 决策单：问题、owner、范围、预算、停止条件 |
| G1 | Product Identity | 商品家族、变体、ASIN、offer 映射 |
| G2 | Source & Rights Audit | 数据源清单、权利状态、隐私判定 |
| G3 | Source Pilot | 小样本试采，验通链路与字段 |
| G4 | Taxonomy Freeze | 编码本与标签词表冻结 |
| G5 | Stratified Collection | 分层采集，写 run ledger |
| G6 | Canonicalize | 去重、血缘、合格性判定 |
| G7 | Coding Calibration | 双盲编码与一致性校准 |
| G8 | Insight Analysis | 指标、claim、反证 |
| G9 | Strategy Activation | 实验卡、KPI、护栏 |
| G10 | Measurement Review | 复测与漂移监控 |

cross-stage：

| 名称 | 职责 |
|---|---|
| Orchestrator | 编排阶段顺序与门禁 |
| Interactive Report | 渲染报告与 SOP |
| Validation & Handoff | 校验与签收 |

### 1.3 人机分工

用两个正交字段，不用单一字母。

| 字段 | 取值 | 含义 |
|---|---|---|
| `actor` | `agent` / `human` / `joint` | 谁执行 |
| `gate` | `none` / `approve` / `review` / `sign` | 需要哪种人工动作 |

旧的三档标记对应关系：

| 旧标记 | `actor` | `gate` |
|---|---|---|
| A | `agent` | `none` |
| B | `joint` | `approve` |
| C | `human` | `review` 或 `sign` |

`gate` 不为 `none` 的阶段都是门禁点。

门禁命名固定：

```text
G-Plan · G-Cost · G-Evidence · G-Claim · G-Publish
```

S 阶段与 G 阶段的映射：

| S 阶段 | 覆盖的 G 阶段 | 主要门禁 |
|---|---|---|
| S1 问题 | G0 | G-Plan |
| S2 计划 | G1–G4 | G-Plan · G-Cost |
| S3 采集 | G5 | G-Cost |
| S4 分析 | G6–G8 | G-Evidence · G-Claim |
| S5 报告 | G9–G10 | G-Publish |

持久化规则：

- 任务表与运行表只存 G 阶段状态。
- S 阶段是派生视图。由 G 状态聚合，不单独落库。

### 1.4 四种运行结果

每次采集落四态之一。报告必须如实呈现。

| 结果 | 原因码 | 报告写法 | 禁止写法 |
|---|---|---|---|
| 有结果 | — | 给数字、样本量、时间窗 | — |
| 空结果 | `empty` | “0 条合格记录。门禁未解除，不表示没有反馈” | “没有相关反馈”“无需求” |
| 配置缺失 | `config_gated` | “该源缺少配置（X）。已列在限制里” | 静默跳过，或当作空结果 |
| 失败 | `failed` | “采集受阻。原因：X。已列在限制里” | 静默跳过 |

术语约定：

| 中文 | 英文或代码 | 定义 |
|---|---|---|
| 隔离队列 | `quarantine` | 歧义或边界项暂不进分析。由人复核。复核结论与是否计入分母写入限制 |
| 配置缺失 | `config_gated` | Provider 凭据或域名授权未配置。不是采集失败 |
| 降级 | `degraded` | 上游持续不稳定，但未完全不可用。只用于健康度，不用于运行结果 |

健康度与运行结果分开记录。

- `health_status` 存工具健康度：`healthy` / `stable` / `degraded` / `outage` / `unknown`。
- `run.outcome` 存运行结果：`success` / `empty` / `config_gated` / `failed`。

两者不得互相替代。

### 1.5 证据等级

五级。数值不是置信度，是可复核性。

| 等级 | 可写结论 |
|---|---|
| `L0_unverified` | 不写 |
| `L1_contract` | 不写 |
| `L2_fixture_local` | 只写方法验证 |
| `L3_live_single` | 只写 Directional |
| `L4_authorized_live` | 可写 Confirmed |

### 1.6 计数器定义

六种计数。报告里每次出现数字，必须标注用的是哪种。

| 计数 | 定义 | 分母 |
|---|---|---|
| 原始对象 | 采集返回的条目 | 无 |
| 出现 | 一条对象里的一次主题命中 | 原始对象数 |
| 规范记录 | 去重后的独立记录 | 无 |
| 帧成员 | 落进本次分析 frame 的记录 | 规范记录数 |
| 标注 | 人工或模型打的主题标签 | 帧成员数 |
| 指标行 | 可计算的指标，含分子分母 | 帧成员数 |

规则：不得跨帧相加或相减。
不得把“出现”当“记录”报比例。

## 2. T1 新品 VOC

### 2.1 适用

新品上市前 6–8 周。目标是找主要摩擦与预期错配。

### 2.2 输入示例

```text
品牌：Momcozy
品类：可穿戴吸乳器
竞品：Medela
市场：US / DE
时间窗：2026-06-20 至 2026-09-20
决策问题：Fit 与支撑，哪个是主要摩擦？
不回答：不推断销量与市场份额；不做医疗结论
```

### 2.3 阶段序列

| 阶段 | 动作 | 数据源 | 档 | 门禁 |
|---|---|---|---|---|
| G0 | 起草决策单 | — | joint | 人确认 owner 与停止条件（`G-Plan`） |
| G1 | 展开商品家族 | Amazon 商品页、TikTok Shop 详情 | A | 歧义项进 quarantine。人处理 |
| G2 | 盘点来源与权利 | — | A | 人/法务确认可商用与隐私 |
| G3 | 小样本试采 | 每源 20–50 条 | A | 人批准付费调用 |
| G4 | 冻结编码本 | — | B | 人冻结版本 |
| G5 | 分层采集 | 见 2.4 | A | 监控成本与缺口 |
| G6 | 规范化 | — | A | 人抽查代表记录 |
| G7 | 双盲校准 | — | A | 人裁决边界与医疗项 |
| G8 | 算指标与 claim | — | A+B | 人验证解释 |
| G9 | 起草实验 | — | B | 人批准 owner 与资源 |
| G10 | 复测 | — | A | 人决定 scale / revise / stop |

### 2.4 采集配方

`tool_id` 由规则生成，不手填：
`{provider}.{endpoint_type}.{market_scope}`。
例：`apify.apify_amazon_reviews_axesso.de`。
采集配方只列 `endpoint_type` 与 `actor`，运行时按市场生成 `tool_id`。

| 顺序 | 工具 | endpoint_type | actor | 用途 | 备注 |
|---|---|---|---|---|---|
| 1 | Amazon 评论（主） | `apify_amazon_reviews_axesso` | `axesso_data/amazon-reviews-scraper` | 主样本 | 实测 99.9%。按 `domainCode` 分市场。json 数组输入 |
| 2 | Amazon 评论（备） | `apify_amazon_reviews_scraper` | `junglee/amazon-reviews-scraper` | 补采 | 实测成功。主源空时启用，需人批准。结果单列 |
| 3 | Trustpilot | `apify_trustpilot_reviews_scraper` | `memo23/trustpilot-scraper-ppe` | 独立站口碑 | 与 Amazon 分开算帧 |
| 4 | Reddit | `apify_reddit_scraper` | `harshmaur/reddit-scraper` | 自然讨论 | **实测 failed 0 条**。启用前必须重测 |
| 5 | TikTok 评论 | `apify_tiktok_comments_scraper` | 见 defaults | 社媒声量 | 单列，不并入自然口碑 |
| 6 | TikTok Shop 详情 | `apify_tiktok_shop_product_detail` | `pratikdani/tiktok-shop-scraper` | 市场信号 | 只作市场信号，不当评论主源 |

**禁用**：`apify_amazon_reviews_extractor`（`web_wanderer/amazon-reviews-extractor`）。
2026-10-15 实测恒 0 条，`platform_packages/notes/amazon.json` 标 `severity=blocker`。
run 状态 SUCCEEDED 是假象，Amazon 封禁了它的评论端点。

**验收看条数，不看 run 状态。**
电商评论类端点必须断言 `records_count > 0`。

分层维度：

| 维度 | 分几层 | 理由 |
|---|---|---|
| 市场 | 每市场独立帧 | 语言与标准不同 |
| 变体 | 按颜色 / 尺码 | 变体差异是主假设 |
| 评分 | 1–2 星 / 3 星 / 4–5 星 | 避免只读差评 |
| 时间 | 按月 | 找趋势拐点 |

配额规则：

- 每个分层至少 30 条合格记录。
- 不足 30 条时，该层不进 prevalence 计算。
- 只在报告里写 Directional。

### 2.5 编码本

冻结九个维度。每个维度有正向、负向、混合三档。

| 维度 | 正向词 | 负向词 |
|---|---|---|
| Fit | 贴合、合适、没漏 | 不贴、错位、漏液 |
| 支撑 | 稳、托住、不坠 | 下坠、撑不住、要用手扶 |
| 漏液 | 密封、没漏 | 漏、渗、湿衣服 |
| 清洁 | 好洗、可拆 | 难洗、藏污、异味 |
| 泵量 | 出奶快、量足 | 出奶慢、量少 |
| 噪声 | 安静、可隐蔽 | 吵、明显 |
| 便携 | 轻、可穿、外出方便 | 重、线多、出门难 |
| 可穿性 | 隐形、不凸 | 凸、外衣显形 |
| 价值 | 值、划算 | 贵、不值 |

规则：

- 一条记录可命中多个维度，标为多标签。
- 同一记录同一维度只算一次。
- 边界案例进 quarantine，不硬标。

### 2.6 校准

| 项 | 规则 |
|---|---|
| 双盲 | 两名 coder 独立标同一批 |
| 样本 | 50 条分层抽样 |
| 一致性 | 每个维度算 agreement |
| 阈值 | 一致性 < 0.6 的维度重写定义 |
| 裁决 | 边界与医疗项由人裁决并记录 |

未过 G7 时：

- 所有结论降为 Directional。
- 禁止写 prevalence 与比例。

### 2.7 报告章节

按 PRD 第 7 节 11 章。

必须有的四张图：

| 图 | 类型 | 数据 |
|---|---|---|
| 体验签名 | 分叉条形图 | 各维度正负标注数 |
| 混合体验 | 嵌套条形图 | 正向 × 负向共现 |
| 需求状态 | 矩阵 + 明细 | 场景 × 维度 |
| 覆盖缺口 | 瀑布图 | 各源 × 各变体记录数 |

### 2.8 验收

- [ ] 每个数字标注计数类型与分母。
- [ ] 每个结论配反证。
- [ ] 变体覆盖缺口显式列出。
- [ ] 社媒样本单列，未并入自然口碑。
- [ ] G7 状态在首屏可见。
- [ ] 禁止输出清单在文末。

## 3. T2 竞品追踪

### 3.1 适用

月度例行，或竞品有动作时触发。

### 3.2 输入示例

```text
品牌：Momcozy
品类：吸乳器
竞品：Medela / Elvie / Willow
市场：US / DE / FR / JP
时间窗：2026-01-01 至 2026-09-23
决策问题：我们的"可穿"定位，在哪个市场还没被占据？
不回答：不推断销量与份额
```

### 3.3 阶段序列

| 阶段 | 动作 | 档 | 门禁 |
|---|---|---|---|
| G0 | 研究章程：冻结实体、市场、cohort、不回答什么 | B | 人批准 |
| G1 | 商品身份映射 model → variant → bundle → offer | A | 人确认配置等价 |
| G2 | 来源与权利审计 | A | 人确认 |
| G3 | 采集试跑 | A | 人批准付费 |
| G4 | 定价口径冻结 | B | 人确认 |
| G5 | 全量采集 | A | 成本监控 |
| G6 | 规范化与噪声隔离 | A | 人复核排除原因 |
| G7 | claim 分级 | A | 人定级 |
| G8 | 定位与叙事分析 | A+B | 人复核 |
| G9 | 90 天行动 | B | 人批准 |
| G10 | 复测 | A | 人决定 |

### 3.4 采集配方

| 顺序 | 工具 | endpoint_type | 用途 |
|---|---|---|---|
| 1 | Amazon 商品 | `apify_amazon_product_scraper` | 标题、变体、价格、评分 |
| 2 | Amazon 价格追踪 | `apify_amazon_price_tracker` | 价格历史 |
| 3 | Amazon 评论 | `apify_amazon_reviews_axesso` | 评论量级与主题 |
| 4 | TikTok Shop 搜索 | `apify_tiktok_shop_search_scraper` | 新渠道货架（实测成功 3 条） |
| 5 | TikTok Shop 详情 | `apify_tiktok_shop_product_detail` | 价格与评论 |
| 6 | 独立站商品页 | `ecommerce_product_page` | 官方定价与 A+。**需域名 grant** |
| 7 | 零售商页 | `apify_walmart_product_scraper` / `apify_target_products_scraper` | Walmart / Target 货架。优先于 `generic_web` |

### 3.5 关键算法

算法 A：身份映射。

```text
model → variant → bundle → offer → listing
```

每一步记录置信度。低于 0.8 的进 quarantine。

规则：**同一型号名不等于同一 offer。**
不同市场的型号命名不同，不得直接合并。

算法 B：claim 状态。统一使用 PRD §7.3 的五态枚举。

| claim 状态 | 判据 | 显示别名（可选） |
|---|---|---|
| `confirmed` | 官方页面或授权数据，且证据等级 `L4` | Verified |
| `directional` | 多源一致，且有日期，但等级不足 `L4` | Supported |
| `hypothesis` | 单源或推断 | Hypothesis |
| `evidence_gap` | 本该有但没有 | Evidence gap |
| `blocked` | 无法核验或无权利 | Blocked |

**规则：**

- 枚举值是 `confirmed` 等五个 snake_case 名。
- 显示别名只用于界面文案，不得写进合同。
- `evidence_gap` 不得省略。样本不足时必须用它。

算法 C：噪声隔离。

按实体、市场、意图三重匹配隔离。
被隔离的记录不进分母。隔离原因必须可见。

算法 D：优先级。

```text
priority = 任务影响 × 战略契合 × 证据就绪 × 可行性 − 伤害/宣称风险
```

权重由人给。Agent 只计算。

### 3.6 报告章节

七段。

| # | 章节 | 主视觉 |
|---|---|---|
| 1 | 执行摘要 | 3 张 summary card |
| 2 | SCQA + 定位图 | 四格 + 定性坐标 |
| 3 | 竞争架构 | 双 brand lane + tension 卡 |
| 4 | 市场与价格 | 价格表 + 市场热力表 |
| 5 | 人群与叙事 | 人群 tab + 决策旅程 |
| 6 | 90 天行动 | 三阶段路线图 + 机会组合 |
| 7 | 证据边界 | run ledger + source card + 限制 |

### 3.7 验收

- [ ] 价格表标注“页面价，非成交均价”。
- [ ] 热力图标注“定性优先级，非量化评分”。
- [ ] 模型映射置信度 < 0.8 的项进 quarantine 并列明。
- [ ] 定位坐标由人给定，Agent 不自动生成。
- [ ] 不出现销量或份额推断。

## 4. T3 选品验证

### 4.1 适用

季度选品会。目标是找价格带空位与需求缺口。

### 4.2 输入示例

```text
品牌：Momcozy
品类：婴儿推车
市场：DE / FR / UK
时间窗：近 180 天
决策问题：300–500 欧元价格带，有没有被忽视的轻便型需求？
不回答：不预测销量；不做供应链可行性判断
```

### 4.3 阶段序列

| 阶段 | 动作 | 档 | 门禁 |
|---|---|---|---|
| G0 | 冻结目标价格带与品类边界 | B | 人批准 |
| G1 | 定义类目与竞品池 | A | 人确认 |
| G2 | 来源审计 | A | 人确认 |
| G3 | 榜单与类目试采 | A | 人批准 |
| G4 | 指标口径冻结 | B | 人确认 |
| G5 | 全量采集 | A | 成本监控 |
| G6 | 规范化与去重 | A | 人抽查 |
| G7 | 需求信号校准 | B | 人确认信号权重 |
| G8 | 三轴矩阵 | A | 人复核 |
| G9 | 候选 SKU 与验证计划 | B | 人批准 |
| G10 | 复测 | A | 人决定 |

### 4.4 采集配方

| 顺序 | 工具 | endpoint_type | 用途 |
|---|---|---|---|
| 1 | Amazon 榜单 | `apify_amazon_bestsellers` | 类目排名。**实测 failed 0 条**，启用前必须重测 |
| 2 | Amazon 商品 | `apify_amazon_product_scraper` | 价格、评分、变体。可读 `rank` 作榜单备用 |
| 3 | 类目页发现 | `ecommerce_product_discovery` | 补全 SKU 池。**需域名 grant** |
| 4 | TikTok Shop 搜索 | `apify_tiktok_shop_search_scraper` | 新兴渠道（实测成功） |
| 5 | 搜索趋势 | `apify_google_trends_scraper` | 需求方向 |

**禁用**：`apify_tiktok_shop_search_v2`。
它只在 `_ENDPOINT_TO_COLLECTOR` 有一行映射，`_APIFY_ENDPOINT_DEFAULTS` 无此键。
调用返回 400。

### 4.5 三轴矩阵

| 轴 | 计算 | 数据 |
|---|---|---|
| 价格轴 | 价格带宽与密度 | 商品价格 |
| 需求轴 | 搜索趋势 + 评论增速 | 趋势、评论日期分布 |
| 竞争轴 | 头部集中度 + 评分分布 | 榜单排名、评分 |

输出九宫格。每格给候选 SKU 数。

规则：

- 榜单排名不等于销量。报告必须写这句。
- 评论数只作需求代理，不作销量代理。
- 趋势数据是相对值，不给绝对搜索量。

### 4.6 报告章节

| # | 章节 | 主视觉 |
|---|---|---|
| 1 | 机会结论 | 一句决策 + 三轴九宫格 |
| 2 | 价格带 | 价格分布直方图 |
| 3 | 竞争密度 | 头部集中度条形图 |
| 4 | 需求信号 | 趋势折线 + 评论增速 |
| 5 | 候选 SKU | 表格，含证据等级 |
| 6 | 验证计划 | 实验卡 |
| 7 | 证据边界 | 限制清单 |

### 4.7 验收

- [ ] 三轴权重由人给定并记录。
- [ ] 候选 SKU 每条有价格、评分、评论数、证据等级。
- [ ] 趋势数据标“相对值”。
- [ ] 不出现销量预测。

## 5. T4 达人投放复盘

### 5.1 适用

投放结束后 2 周。目标是分清真实口碑与投放噪声。

### 5.2 输入示例

```text
品牌：Momcozy
品类：可穿戴吸乳器
市场：US
时间窗：2026-08-01 至 2026-09-15
决策问题：这批达人带来的评论里，哪些能代表真实使用体验？
不回答：不评估 ROI；不预测复投效果
```

### 5.3 阶段序列

| 阶段 | 动作 | 档 | 门禁 |
|---|---|---|---|
| G0 | 冻结投放清单与判定标准 | B | 人批准 |
| G1 | 达人身份映射 | A | 人处理同名歧义 |
| G2 | 权利与条款审计 | A | 人确认 |
| G3 | 试采 5 个达人 | A | 人批准 |
| G4 | 噪声判定规则冻结 | B | 人确认 |
| G5 | 全量采集 | A | 成本监控 |
| G6 | 规范化与去重 | A | 人抽查 |
| G7 | 真实度分级校准 | B | 人裁决 |
| G8 | 主题与分层 | A | 人复核 |
| G9 | 复投建议 | B | 人批准 |
| G10 | 复测 | A | 人决定 |

### 5.4 采集配方

| 顺序 | 工具 | endpoint_type | 用途 |
|---|---|---|---|
| 1 | 达人信息 | `tikhub_tiktok_creator_info` | 粉丝、认证、地区 |
| 2 | 达人作品 | `tikhub_tiktok_user_posts` | 视频列表 |
| 3 | 达人洞察 | `tikhub_tiktok_creator_insights` | 互动指标 |
| 4 | TikTok 视频 | `apify_tiktok_scraper` | 备用与补全 |
| 5 | TikTok 评论 | `apify_tiktok_comments_scraper` | 评论区 |
| 6 | Instagram 主页 | `apify_instagram_profile_scraper` | 跨平台声量 |

### 5.5 噪声判定

按三重匹配隔离。

| 维度 | 判定 | 处理 |
|---|---|---|
| 实体 | 评论提到的是本产品还是其他 | 其他进 noise |
| 市场 | 是否目标市场语言与地区 | 非目标进 noise |
| 意图 | 是否商业内容下的引导评论 | 商业引导进 noise |

另加两条规则：

- 有商业标识的内容，其评论一律不并入自然口碑。
- 同一账号在短时间内多条相似评论，标疑似协同，单列。

### 5.6 报告章节

| # | 章节 | 主视觉 |
|---|---|---|
| 1 | 投放概览 | 达人 × 视频 × 评论的量级条 |
| 2 | 噪声隔离 | 瀑布图：总评论 → 隔离 → 可用 |
| 3 | 内容主题 | 主题 × 达人热力表 |
| 4 | 评论真实度 | 真实度分布 + 典型案例 |
| 5 | 达人分层 | 分层矩阵 |
| 6 | 复投建议 | 实验卡 |
| 7 | 证据边界 | 限制清单 |

### 5.7 验收

- [ ] 商业化内容单列，未混入自然口碑。
- [ ] 疑似协同评论单列并给判据。
- [ ] 隔离原因逐条可见。
- [ ] 每条建议标注证据等级。

## 6. T5 合规预警

### 6.1 适用

每周例行，或事件触发。

### 6.2 输入示例

```text
品牌：Momcozy
品类：吸乳器 / 婴儿监测器
市场：US / UK / DE / FR
时间窗：近 12 个月
决策问题：我们有哪些 SKU 处在已公开的召回或安全通报中？
不回答：不给法律意见；不判断是否合规
```

### 6.3 阶段序列

| 阶段 | 动作 | 档 | 门禁 |
|---|---|---|---|
| G0 | 冻结 SKU 清单与匹配规则 | B | 人批准 |
| G1 | 商品与型号映射 | A | 人确认别名 |
| G2 | 来源权威性排序 | A | 人确认优先级 |
| G3 | 试采与字段验证 | A | 人批准 |
| G4 | 匹配规则冻结 | B | 人确认 |
| G5 | 全量采集 | A | 成本监控 |
| G6 | 匹配与隔离 | A | 人复核未匹配项 |
| G7 | 风险定级 | B | 人定级 |
| G8 | 处置建议 | B | 人批准 |
| G9 | 通报与跟踪 | A | 人确认发送对象 |
| G10 | 复测 | A | 人决定 |

### 6.4 采集配方

| 顺序 | 工具 | endpoint_type | 来源 | grant host |
|---|---|---|---|---|
| 1 | FDA Food Safety Recalls | `public_feed` | 美国食品药品 | `fda.gov` |
| 2 | UK OPSS Product Safety | `public_feed` | 英国产品安全 | `gov.uk` |
| 3 | UK NHS Medicines & Devices | `public_feed` | 英国医疗器械 | `gov.uk` |
| 4 | PR Newswire Product Recalls | `public_feed` | 企业公告 | `prnewswire.com` |
| 5 | CPSC 召回页 | `generic_web` | 美国消费品安全 | `cpsc.gov` |
| 6 | EU Safety Gate | `generic_web` | 欧盟快速预警 | `ec.europa.eu` |

**前置条件（阻断项）。**

`public_feed` 与 `generic_web` 都属 `guarded_http`。
`COLLECTION_HTTP_GRANTS` 默认 `[]`。
缺 grant 时 `http_grant()` 抛 `CollectionPolicyDenied`。

运行前必须满足：

1. `public_feed` 至少配 3 个 host：`fda.gov`、`gov.uk`、`prnewswire.com`。
2. `generic_web` 至少配 2 个 host：`cpsc.gov`、`ec.europa.eu`。
3. 每条 grant 有 `expires_at`，且未过期。
4. 每个 collector_type 最多 5 个 host。超出按批次轮换。

**抽取契约（第二阻断项）。**

两个采集器都只返回原始文本，不返回通报结构化字段。

| 采集器 | 实际返回 |
|---|---|
| `public_feed` | `title` / `link` / `published_at` / `author` / `tags` / `summary` |
| `generic_web` | `url` / `title` / `text_content` / `html_content` |

必须加一层抽取器。字段：

```text
{recall_id, product_name, brand, risk_type, market, published_at, action, url}
```

抽取器验收：

1. 先建 20 条已知通报的 golden set。
2. `recall_id` 与 `url` 必须 100% 正确。
3. `brand` 与 `risk_type` 必须 ≥ 90%。
4. 未达标的源不进报告，标 `blocked`。

禁止把 `text_content` 直接当结构化字段用。

来源权威性排序（由人确认）：

```text
监管机构原文 > 企业公告 > 新闻稿 > 媒体转载
```

### 6.5 匹配规则

| 层级 | 规则 | 匹配失败处理 |
|---|---|---|
| L1 | 品牌精确匹配 | 进未匹配池 |
| L2 | 型号 / SKU 精确匹配 | 进未匹配池 |
| L3 | 产品名模糊匹配（阈值 0.85） | 人复核 |
| L4 | 同品类不同型号 | 不算命中，标 context |

规则：

- 匹配不到 = `gap`。不写“无风险”。
- 只在证据等级 `L4` 时写“已核查，未发现公开通报”。
- 任何法律结论一律禁止。

### 6.6 风险定级

| 级别 | 判据 | 响应时限 |
|---|---|---|
| P0 | 监管机构已发布，且型号精确匹配 | 24 小时内通报 |
| P1 | 品牌匹配，型号待确认 | 72 小时内核实 |
| P2 | 同品类，可能相关 | 下次例行会讨论 |
| P3 | 仅媒体报道，未获监管确认 | 观察 |

定级由人做。Agent 只给候选与判据。

### 6.7 报告章节

| # | 章节 | 主视觉 |
|---|---|---|
| 1 | 风险结论 | 一句决策 + 风险计数条 |
| 2 | 召回状态 | 表格：通报号、型号、市场、日期、状态 |
| 3 | 宣称风险 | 医疗宣称关键词表 |
| 4 | 市场限制 | 市场 × 限制类型矩阵 |
| 5 | 处置建议 | 实验卡 |
| 6 | 证据边界 | 禁止结论清单 |

### 6.8 验收

- [ ] 每条命中给通报原文链接。
- [ ] 未匹配项显式列出。
- [ ] 不出现“合规”或“合法”结论。
- [ ] P0 项有通报受众人与时间。
- [ ] 证据边界列明“不做法律意见”。

## 7. 通用检查清单

交付前逐项勾选。共 14 项。

| # | 项 | 通过判据 |
|---|---|---|
| 1 | 决策问题 | 一句话，可判定，有 owner |
| 2 | 不回答清单 | 非空，进了报告证据边界 |
| 3 | 商品身份 | 映射置信度全记录，歧义项进 quarantine |
| 4 | 来源权利 | 每个源有权利状态与使用限制 |
| 5 | 试采 | 每源小样本跑通，字段齐 |
| 6 | 编码本 | 冻结版本，有定义与例 |
| 7 | 分层 | 每层样本量可见，不足 30 条不进 prevalence |
| 8 | 计数口径 | 每个数字标计数类型与分母 |
| 9 | 校准 | 一致性低于阈值的维度已重写或降级 |
| 10 | claim | 每条有证据，反证字段存在 |
| 11 | 证据等级 | 系统计算，非模型声明 |
| 12 | 禁止输出 | 文末显式列出 |
| 13 | 合同哈希 | 报告页脚可见 |
| 14 | 签收 | 有人签字，记录时间 |

## 8. 失败处理

| 失败 | 判据 | 处置 |
|---|---|---|
| 数据源全空 | 所有源返回 0 条 | 停止。写方法报告，不写洞察报告 |
| 样本不足 | 任一必需层 < 30 条 | 降为 Directional，扩展时间窗或市场 |
| 校准不过 | 任一核心维度一致性 < 0.6 | G7 阻断。重写定义或缩维度 |
| 成本超限 | 估算超额度 | 阻断。人裁剪计划或提额 |
| 凭据或授权缺失 | provider 返回鉴权错，或 `CollectionPolicyDenied` | 记 `config_gated`。列入限制 |
| 上游故障 | 连续 3 次失败 | 运行结果记 `failed`，健康度记 `degraded`。换替代源或延后 |
| 身份歧义 | 映射置信度 < 0.8 超 20% | G1 阻断。人先做身份清理 |
| 权利不清 | 源无商用授权 | 该源退出。报告标 gap |

## 9. 复测与漂移

每条模板都要有复测节奏。

| 模板 | 复测周期 | 复测内容 | 漂移阈值 |
|---|---|---|---|
| T1 VOC | 季度 | 维度分布、样本结构 | 主维度标注占比变化 > 15% |
| T2 竞品 | 月度 | 价格、offer、定位 | 价格变动 > 10% |
| T3 选品 | 季度 | 价格带密度、趋势 | 空位候选变化 > 30% |
| T4 达人 | 每次投放后 | 噪声比例、达人分层 | 噪声比例变化 > 10 个百分点 |
| T5 合规 | 每周 | 新通报、状态变更 | 任何 P0/P1 新增 |

漂移触发时：

1. 报告标 `stale`。
2. 通知 owner。
3. 决定重跑或标注失效。

## 10. 与现有资产的衔接

| 现有资产 | 本 Playbook 如何用 |
|---|---|
| `docs/playbooks/platforms/*.md`（70 份） | 每个工具的参数与坑点来源。不重复写 |
| `docs/playbooks/【坑点库】DIH-平台采集坑点汇总.md` | 采集前必读。107 条 |
| `docs/architecture/【能力总账】...md` | 数据源可用性判定依据 |
| `ref/monid-prompt-insight/` 四份 HTML | 报告与 SOP 的形态基准。对照验收 |
| [能力图谱](../architecture/【能力图谱】DIH-控制台能力地图.md) | 端点与页面的现状 |

## 11. 第一批要跑通的三条

按依赖与价值排序。

| 顺序 | 模板 | 理由 | 前置条件 | 完成标志 |
|---|---|---|---|---|
| 1 | T1 新品 VOC | 与已有 Momcozy 产物可直接对照。主源 axesso 稳定 | axesso 凭据可用 | 产出一份与 `BumpEase_VOC` 同结构的报告 |
| 2 | T2 竞品追踪 | 复用 T1 的评论数据与价格数据 | Amazon 商品与价格端点已实测 | 产出一份与 `Medela` 同结构的报告 |
| 3 | T5 合规预警 | 数据源结构最简单，但**不是零配置** | 4 条 `public_feed` grant + 2 条 `generic_web` grant；抽取层 | 出完整 T5 报告，含 20 条 golden set 校验 |

**T5 的注意事项。**
`public_feed` 与 `generic_web` 都属 `guarded_http`。
默认 `COLLECTION_HTTP_GRANTS=[]` 时一律拒绝。
必须先配 grant，见 6.4 前置条件。

T3 与 T4 放到第二批。
T4 还依赖 TikTok R1 的 21 张表已应用。

## 12. 已知限制

本 Playbook 当前不能覆盖的事项。

| # | 限制 | 影响 |
|---|---|---|
| 1 | 53 个采集器在外访策略下永久拒绝 | 中文社媒、OSINT、浏览器类不可用 |
| 2 | 13 个 catalog 类型不是独立 collector：11 个经 `apify_actor` 可执行，2 个无执行路径 | 只影响 `apify_shopify_full_catalog` 与 `bilibili_video_info` |
| 3 | 真实 LLM 未接入，只有 Mock | 报告文字需人工代写 |
| 4 | 凭据只走环境变量 | 无法按项目隔离 |
| 5 | TikTok R1 的 21 张 canonical 表未应用 | 达人数据只能落原始记录 |
| 6 | 数据源条款未逐项核验 | 商业化使用前需法务确认 |
| 7 | 多语言编码本只覆盖中英德 | 法西意日需扩表 |
| 8 | 4 个 `guarded_http` 类型默认无 grant | T5 全部源、T2/T3 的域名页默认被拒 |
| 9 | `apify_amazon_reviews_extractor` 已失效 | 该 actor 恒 0 条，禁止使用 |
| 10 | `apify_amazon_bestsellers`、`apify_reddit_scraper` 实测 failed | 启用前必须重测 |
| 11 | `apify_tiktok_shop_search_v2` 无 actor 配置 | 调用返回 400，禁止使用 |

这些限制必须写进每份报告的证据边界。
不得隐藏。
