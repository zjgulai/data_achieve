# 裁决 F：基线入样资格（video 层）

## 0. 最终裁决

**只有 10 条 exact 进入目标商品基线。38 条 medium 降级为 category_reference，单列，不进基线，不出结论。29 条 low 与 64 条 no_signal 只计数。**

一句话：**本轮视频层基线是 n=10，不是 n=48。任何分层都标 `insufficient_sample`，只给计数和逐条明细。**

附带裁决：

1. 撤回「同标题」措辞。duplicate_listing_anchor 是「同品牌 YB001 系列的其他 listing；product_id 不同，标题相似但不相同」。
2. 提问帖 `7696910923616881951` 归入 category_reference 的 `consideration` 子类。它不进基线，不进高表现集合，不进素材选型样本。
3. 金标集不动。n>=8 门槛不放宽。

## 1. 三层 cohort 定义

### 1.1 exact（n=10）

#### 判定条件

同时满足：

- `relation_type == "target_exact"`
- `confidence == "high"`
- `target_baseline_eligible == true`
- 视频锚点中存在 `product_id == 1729474995478630680`

证据：

- `/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/creator-video/relations/coverage.json` → `video_product_target.status_distribution.confirmed = 10`
- 同上 → `video_product_target.baseline_eligibility.target_exact_baseline_n = 10`
- `/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/creator-video/relations/video-product-target-baseline.jsonl` 共 10 行

#### 允许产出

- 计数：n=10。
- 整体描述统计：中位数、四分位、最小值、最大值。每条必须标 `n=10`。
- 逐条明细：video_id、时长、播放、互动率、`platform_is_ad`、锚点 product_id。
- 否定性结论：说明样本不足以支持分层或因果判断。

#### 禁止产出

- 任何分层中位数或分层互动率。
- 任何显著性检验、置信区间、p 值。
- 任何因果推断。
- 把 exact 与 category_reference 合并成「48 条基线」。
- 用 exact 的 10 条给内容形态排名。

### 1.2 category_reference（n=38）

#### 判定条件

`confidence == "medium"`，且属于下列两类之一：

| 子类 | relation_type | n | 判定 |
| --- | --- | ---: | --- |
| 其他 listing 锚点 | `duplicate_listing_anchor` | 19 | 锚点 product_id 与目标不同，但锚点标题属于 Momcozy YB001 系列 |
| 文案品牌+品类 | `text_brand_and_category` | 19 | 无商品锚点；文案或话题同时命中品牌词与支撑带品类词 |

证据：

- `coverage.json` → `video_product_target.confidence_distribution.medium = 38`
- `coverage.json` → `video_product_target.relation_type_distribution.duplicate_listing_anchor = 19`
- `coverage.json` → `video_product_target.relation_type_distribution.text_brand_and_category = 19`

19 条 duplicate listing 的锚点只涉及 3 个 product_id：

| product_id | 视频数 | 与目标商品的关系 |
| --- | ---: | --- |
| `1729625924185592807` | 17 | 同品牌同系列的其他 listing |
| `1729495174330226663` | 1 | 同品牌同系列的其他 listing |
| `1731287236556526567` | 1 | 同品牌同系列的其他 listing |

#### 允许产出

- 按子类计数：19 + 19。
- 描述文案层面的事实：提到了什么品牌词、品类词、痛点、场景。
- 逐条明细：video_id、relation_type、原文摘录。必须带 `category_reference` 标签。
- 把文案当作语言证据引用。例如：消费者如何称呼产品、如何描述疼痛、如何提问。

#### 禁止产出

- 进入目标商品基线。
- 计算目标商品的中位互动率、四分位、置信区间、p 值。
- 与 exact 的 10 条做「哪类跑赢」比较。
- 把 38 条与 10 条合并成任何分母。
- 说这些视频「代表目标商品的表现」。
- 说 duplicate listing 与目标商品「同标题」或「同一商品」。

### 1.3 unclassified（n=93）

| 子类 | relation_type | n | 说明 |
| --- | --- | ---: | --- |
| low | `text_category_only` | 14 | 只命中品类词 |
| low | `hashtag_category_only` | 7 | 只在话题命中品类词 |
| low | `other_brand_category_anchor` | 6 | 锚到其他品牌支撑带 |
| low | `sibling_product_anchor` | 2 | 锚到 Momcozy 其他产品 |
| no_signal | `no_signal` | 64 | 无品牌、品类或锚点信号 |

合计：29 low + 64 no_signal = 93。

证据：

- `coverage.json` → `video_product_target.confidence_distribution.low = 29`
- `coverage.json` → `video_product_target.confidence_distribution.none = 64`
- `coverage.json` → `video_product_target.relation_type_distribution` 中上述 5 类计数

#### 允许产出

- 计数：29、64、以及 29 内部的 14/7/6/2。
- 审计用 video_id 清单。清单来自
  `/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/creator-video/baseline/baseline.json` → `unclassified`。

#### 禁止产出

- 任何描述统计。
- 任何基线或分层。
- 任何显著性检验。
- 任何内容形态结论。
- 把 low 的品类锚点写成目标商品事实。low 行可以记录「锚到品类内其他产品」这一事实，但不能进入任何基线。

### 1.4 三层汇总

| cohort | n | 定义 | 能否进基线 | 能否出结论 |
| --- | ---: | --- | --- | --- |
| exact | 10 | 锚点 product_id == 目标商品 | 能，唯一允许 | 能，仅整体描述与逐条明细 |
| category_reference | 38 | 同品牌其他 listing，或文案品牌+品类 | 不能 | 只能描述，不能比较 |
| unclassified | 93 | 29 low + 64 no_signal | 不能 | 只能计数 |

## 2. 每层允许的结论类型

### 2.1 cohort × 操作矩阵

| 操作 | exact（n=10） | category_reference（n=38） | unclassified（n=93） |
| --- | --- | --- | --- |
| 计数 | 允许 | 允许，按 19 + 19 分子类 | 允许，只计数 |
| 整体描述统计（中位数、四分位） | 允许，必须标 n=10 | 受限：只能描述品类参照，不能算目标商品基线 | 禁止 |
| 逐条明细 | 允许，带锚点与指标 | 允许，带 relation_type 与原文 | 禁止；只保留审计用 ID 清单 |
| 分层中位数 | 本轮禁止；任何分层单元 n<8 | 禁止 | 禁止 |
| 显著性检验 | 禁止 | 禁止 | 禁止 |
| 因果推断 | 禁止 | 禁止 | 禁止 |

### 2.2 规则解释

- **exact 到「整体描述统计」为止。** 10 条可以看整体中位数和四分位，可以逐条列。不能切层，不能检验，不能归因。
- **category_reference 到「描述」为止。** 可以数、可以引用原文、可以说「这些文案提到什么」。不能说「这类表现更好」，也不能算目标商品的中位数。
- **unclassified 到「计数」为止。** 除计数外不产出任何统计量。
- **n>=8 是硬门槛。** 任何分层单元少于 8 条，只能写 `insufficient_sample` 和计数。不得为了「看起来有结论」降低门槛。
- **矩阵之外的操作默认禁止。** 需要新操作时，先新增裁决，不能在本轮直接做。

## 3. 10 条 exact 的实际样本量约束

### 3.1 分层计数：全部不满足 n>=8

时长分层：

| 时长档 | n | 是否达到 n>=8 |
| --- | ---: | --- |
| <=15s | 1 | 否 |
| 16-30s | 4 | 否 |
| 31-60s | 4 | 否 |
| >60s | 1 | 否 |

链接与广告披露：

| 维度 | 取值分布 | 是否可分层 |
| --- | --- | --- |
| `has_link` | true 10 / false 0 | 否；只有一个取值 |
| `ad_disclosure` | true 10 / false 0 | 否；只有一个取值 |
| `platform_is_ad` | true 9 / false 1 | 否；false 单元 n=1 |

证据：

- `baseline.json` → `sufficiency_assessment.high_only_sensitivity.duration_bucket_counts`
- 同上 → `has_link_counts = {"true": 10}`
- 同上 → `ad_disclosure_counts = {"true": 10}`
- 同上 → `status = "insufficient_sample"`
- 同上 → `note`：「No duration bucket reaches n=8, and has_link/ad_disclosure have a single value. High-only data cannot support any layered baseline.」

**结论：本轮任何分层基线都不成立。** 时长、链接、广告披露三个维度全部只能给计数，标 `insufficient_sample`。

### 3.2 唯一允许的统计：整体分布（n=10）

| 指标 | 中位数 | 四分位区间 | 最小值 | 最大值 |
| --- | ---: | ---: | ---: | ---: |
| 播放量 | 172,650 | 25,300 – 389,675 | 1,025 | 1,500,000 |
| 互动率 | 1.19% | 0.63% – 2.63% | 0.46% | 4.80% |
| 时长（秒） | 32 | — | 11 | 68 |

补充计数：

- 锚点命中目标 product_id：10 / 10。
- `has_link = true`：10 / 10。
- `ad_disclosure = true`：10 / 10。
- `platform_is_ad = true`：9 / 10。

口径说明：

- 互动率 =（like + comment + share + collect）/ play。
- 四分位用 Python `statistics.quantiles` 默认线性插值。
- 每一行都必须标 `n=10`。
- 这些数字是「10 条 exact 的描述分布」，不是「目标商品基线」，也不是「品类基线」。

### 3.3 逐条明细

| video_id | 时长(s) | 播放 | 互动率 | platform_is_ad |
| --- | ---: | ---: | ---: | --- |
| 7596080221900639543 | 11 | 317,200 | 0.79% | true |
| 7613588163990129950 | 34 | 1,500,000 | 1.12% | true |
| 7624603263974788382 | 39 | 208,100 | 1.27% | true |
| 7630157203525225742 | 30 | 607,100 | 0.46% | true |
| 7669995620307881230 | 39 | 143,300 | 1.28% | true |
| 7691166964626066701 | 68 | 38,000 | 4.39% | true |
| 7692109722316475661 | 46 | 202,000 | 0.67% | true |
| 7695942452426968333 | 28 | 31,500 | 4.80% | true |
| 7700940453163699486 | 21 | 6,701 | 0.51% | true |
| 7702214491013942559 | 26 | 1,025 | 2.05% | false |

数据源：`/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/creator-video/baseline/baseline.json` → `video_level` 中 10 条 `target_exact` 行。

### 3.4 明确禁止

- 写「48 条基线」「高/中置信 48 条基线」「进入基线 48」。
- 写「31-60s 跑赢」「>60s 互动率更高」等任何时长分层结论。
- 写任何 p 值、置信区间、倍数。
- 用 mixed 48 条的时长档中位数选「高表现视频」。
- 把 10 条 exact 叫作「高表现组」。当前 8 条高表现集合里只有 1 条 exact。
- 把 exact 的 10 条与 category_reference 的 38 条放在同一张分层表里比较。

### 3.5 C16 的重述

C16 的否定结论保留：**没有任何内容形态在预定义维度上以可排除偶然的方式跑赢基线。**

但依据必须改写：

- 旧依据：48 条 high/medium 混合样本的分层检验。
- 新依据：10 条 exact 不支持任何分层单元达到 n>=8，因此无法检验。
- 正确写法：「10 条 exact 样本不足以检验任何内容形态是否跑赢；本轮不能判断哪类形态更好。」
- 错误写法：「已证明没有内容形态跑赢。」这句话把「无法检验」说成了「证明无差异」。

## 4. 修掉「同标题」的错误表述

### 4.1 错误来源链

| 位置 | 现有措辞 | 问题 |
| --- | --- | --- |
| `creator-video/collect-summary.json:225` | 「Several product IDs carry the same Momcozy YB001 / CozySupport Ergonest title.」 | same title 事实错误 |
| `creator-video/collect-summary.json:192` | 字段名 `same_title_other_product_ids` | 字段名把错误固化 |
| `creator-video/collect-summary.json:148` | 「multiple product IDs share the same Momcozy YB001 / CozySupport Ergonest title」 | 同上 |
| `/Users/lute/Project/data_scrapy/tools/creator_video_relations.py:479-483` | `reason`：「the product title is the same Momcozy YB001 / CozySupport Ergonest listing per collector evidence_gaps」 | 错误进入生成逻辑 |
| `creator-video/relations/coverage.json:118` | 「their medium basis is the anchor product title (same Momcozy YB001 / CozySupport Ergonest title)」 | 同上 |
| `creator-video/relations/coverage.json:172` | 「Duplicate-listing anchors have the same Momcozy YB001 / CozySupport Ergonest title but a different product_id」 | 同上 |
| `creator-video/baseline/baseline.md:187` | 「19 条 duplicate_listing_anchor（锚到同标题不同 product_id）」 | 报告措辞错误 |
| `creator-video/baseline/baseline.json:2202` | 同上 | 同上 |
| `report.html:322` | 表格单元「同标题不同 product_id」 | Exhibit 07 错误 |
| `report.html:310` | 「high/medium 的 48 条进入基线」 | 把 medium 混入基线 |
| `report.html:320` | Exhibit 07 标题「48 条进入高/中置信商品关联基线」 | 同上 |
| `/Users/lute/Project/data_scrapy/voc_pipeline/voc/report.py:949` | 表格行「同标题不同 product_id」 | 报告生成器错误 |
| `creator-video-summary.json:1019` | 「锚到同标题不同 product_id」 | 摘要错误 |

### 4.2 事实核对

目标商品锚点标题：

> Momcozy Pregnancy Belly Band YB001, CozySupport Ergonest Maternity Belly Band, Invisible Pregnancy Belt for Back, Abdomen, Waist,A, Pregnancy Stuff, Maternity Clothing Abdominal Binder

三个其他 listing 的锚点标题：

| product_id | 视频数 | 锚点标题 |
| --- | ---: | --- |
| `1729625924185592807` | 17 | Momcozy Pregnancy Belly **Belt** YB001, CozySupport Ergonest Maternity Belly Band, Invisible Pregnancy Belt for Back, Abdomen, Waist tiktok shop, A, Maternity clothing, Pregnancy stuff |
| `1729495174330226663` | 1 | Momcozy  Pregnancy Belly Band YB001, CozySupport Ergonest Maternity Belly Band, Invisible Pregnancy Belt for Back, Abdomen, Waist tiktok shop，C |
| `1731287236556526567` | 1 | Momcozy Maternity Belly **Belt**, Invisible Maternity Sling, CozySupport Ergonest Maternity Belly Belt, Invisible Maternity Sling for Abdomen and Waist,-【B】 |

逐项差异：

- `1729625924185592807`：目标标题是「Belly Band」，这条是「Belly **Belt**」；后缀也不同。
- `1729495174330226663`：品牌名后有双空格；后缀是「tiktok shop，C」，不是目标的「A, Pregnancy Stuff, Maternity Clothing Abdominal Binder」。
- `1731287236556526567`：标题开头是「Momcozy Maternity Belly Belt, Invisible Maternity Sling」，没有「Pregnancy Belly Band YB001」这一串。

**没有一条标题与目标标题完全相同。**「同标题」是事实错误。

### 4.3 替换措辞

标准短句：

> 锚点指向同品牌 YB001 系列的其他 listing；product_id 不同，标题相似但不相同。

标准长句：

> 19 条 duplicate_listing_anchor：视频锚到 Momcozy YB001 系列的其他 listing，共 3 个 product_id（1729625924185592807 17 条、1729495174330226663 1 条、1731287236556526567 1 条）。这些 listing 与目标商品同品牌、同系列、同品类，但 product_id 不同，标题也不完全相同。它们不是目标商品，只能作为品类参照。

逐处替换：

| 位置 | 替换为 |
| --- | --- |
| `baseline.md:187` | 「19 条 duplicate_listing_anchor（锚到同品牌 YB001 系列的其他 listing；product_id 不同，标题相似但不相同）」 |
| `baseline.json:2202` | 同上 |
| `report.html:322` | 「同品牌同系列的其他 listing；product_id 不同」 |
| `voc/report.py:949` | 第三个元组元素改为「同品牌同系列的其他 listing；product_id 不同」 |
| `coverage.json:118` | 「their medium basis is the anchor product title: same Momcozy YB001 series, similar but not identical title, different product_id」 |
| `coverage.json:172` | 「Duplicate-listing anchors point to Momcozy YB001-series listings with different product_ids and similar but not identical titles; they are not merged.」 |
| `collect-summary.json:225` | 「Several product IDs carry similar Momcozy YB001-series titles; IDs are not merged into the target-product baseline.」 |
| `collect-summary.json:192` | 字段名改为 `same_series_other_product_ids` |
| `collect-summary.json:148` | 「multiple product IDs carry similar Momcozy YB001-series titles」 |
| `tools/creator_video_relations.py:479-483` | 「anchor product_id differs from the target; the anchor title belongs to the same Momcozy YB001 series but is not identical; product IDs are not merged」 |
| `creator-video-summary.json:1019` | 用标准短句 |
| `report.html:310` | 「high 10 条进入目标商品基线；medium 38 条单列为品类参照」 |
| `report.html:320` | Exhibit 07 标题改为「10 条锚定目标商品；38 条单列为品类参照」 |

### 4.4 为什么不能当同一商品

1. **product_id 是平台商品主键。** 目标 `1729474995478630680` 与三个 listing 的 ID 不同。不同 ID 就是不同 listing。
2. **标题不相同。** 「Belly Band」与「Belly Belt」是不同措辞；后缀与颜色/规格代码也不同。
3. **同品牌、同系列、同品类不等于同一 SKU。** 不能据此推断同一卖家、同一价格、同一库存、同一履约。
4. **锚点归属不同。** 视频锚到另一个 listing，互动属于那个 listing 的曝光，不能归因到目标商品。
5. **合并会污染基线。** 一旦合并，目标商品的 10 条会被 19 条其他 listing 的视频稀释，任何中位数都不再是目标商品的。

因此：duplicate_listing_anchor 只能进 category_reference，只能描述，不能进目标商品基线。

### 4.5 同步范围

本轮只冻结措辞，不改金标集，不改代码。下一次重跑前，以下产物中的「同标题」和「48 条基线」都视为未修正：

- `creator-video/collect-summary.json`
- `creator-video/relations/coverage.json`
- `creator-video/relations/video-product-candidates.jsonl` 的 `evidence`/`notes`
- `creator-video/baseline/baseline.md`
- `creator-video/baseline/baseline.json`
- `creator-video-summary.json`
- `report.html`
- `voc/report.py`
- `tools/creator_video_relations.py`

重跑后的验收 grep：

- 在 `report.html`、`baseline.md`、`baseline.json`、`coverage.json`、`creator-video-summary.json`、`collect-summary.json`、`voc/report.py`、`tools/creator_video_relations.py` 中搜索「同标题」：命中数必须为 0。
- 搜索「same ... title」：命中数必须为 0，或只出现在明确否定句「not the same title」中。
- 搜索「进入基线」：只能出现「10 条」，不能出现「48 条」。
- 搜索 `qid 7696910923616881951`：不得出现在 `high_performers`、分层表、显著性检验中。

## 5. 提问帖的处理

### 5.1 事实

视频 `7696910923616881951`：

| 字段 | 值 | 来源 |
| --- | --- | --- |
| 原文 | `Mom cozy Belly bands. What do yal think? I want to order one and try it out. I’m in so much pain because of how rapidly my belly is growing. Probably gonna be a big baby lol #fypシ #pelvicpain #pregnant #pregnancy #momof2` | `video-snapshots.json` → `desc` |
| relation_type | `text_brand_and_category` | `video-product-candidates.jsonl` |
| confidence / status | `medium` / `probable` | 同上 |
| target_baseline_cohort | `target_text_evidence_review` | 同上 |
| anchor_product_ids | `[]` | 同上 |
| detail_snapshot | `null` | `video-snapshots.json` |
| snapshot_source | `search_only` | 同上 |
| 平台广告标记 | `is_ads = false` | 原始搜索响应 `video-search-momcozy-belly-band-review-sort0-page1.json` |
| 商品锚点字段 | `bottom_products = null`、`products_info = null`、`right_products = null`、`anchors_extras = ""` | 同上 |
| 播放 | 551 | `search_snapshot.statistics.play_count` |
| 点赞 / 评论 / 分享 / 收藏 | 34 / 18 / 0 / 0 | 同上 |
| 互动率 | 9.44% | （34 + 18 + 0 + 0）/ 551 |
| 时长 | 90.734 秒 | `baseline.json` → `high_performers.videos` |
| 时长档 | >60s，档内 n=10 | 同上 |
| low_denominator_flag | `true` | 同上 |
| 是否进入 8 条高表现 | 是，第 6 条 | `baseline.json` → `high_performers.videos` |

### 5.2 归到哪一层

归入 **category_reference**，子标签 `consideration`。

理由：

- 无商品锚点，无商品链接。
- 平台 `is_ads = false`。
- 文案是「要不要买」的提问，不是「已经用了」的展示。
- 文案只命中品牌词「mom cozy」与品类词「belly bands」，所以 relation_type 仍是 `text_brand_and_category`。

它不属于 exact，不进基线，不进高表现集合，不进素材选型样本。

### 5.3 它对「素材选型」有没有价值

有，但不是表现价值。

可用价值：

- **需求信号**：用户主动说「I want to order one and try it out」，说明已进入考虑期。
- **痛点语言**：`I’m in so much pain because of how rapidly my belly is growing` 是消费者原话，可用于文案角度和卖点排序。
- **异议清单**：`What do yal think?` 说明用户在买前征求他人意见，可用于评论区运营与 FAQ。
- **称呼变体**：用户写「Mom cozy」而不是「Momcozy」，可用于搜索词与文案拼写覆盖。

不可用价值：

- 不能当表现样本。551 播放、52 次互动，互动率 9.44% 是小分母结果，不是「高互动」。
- 不能当带货素材。视频没有展示商品、没有使用过程、没有购买链接。
- 不能进高表现集合，也不能进分层中位数。

### 5.4 判定规则：consideration 还是 material

#### material 的必要条件

同时满足：

- **M1 有商品证据**：锚点命中目标 product_id，或画面/口播明确展示并使用了目标商品。
- **M2 有本人使用证据**：第一人称过去时或进行时，例如 `I ordered`、`I got`、`I use`、`I’ve been using`、`mine`、`it helped me`。
- **M3 不是以「要不要买」为主**：文案主体是使用体验、效果、对比、教程，而不是征求购买意见。

#### consideration 的判定条件

同时满足：

- **C1 无商品证据**：`anchor_product_ids` 为空；`has_link` 为 false 或 unknown；平台 `is_ads = false`。
- **C2 有未来意图或提问**：出现下列任一信号：
  - `I want to order`
  - `should I buy` / `should I get`
  - `what do you think` / `what do yal think`
  - `thinking about` / `considering`
  - `recommend?` / `which one` / `is it worth`
- **C3 无本人使用证据**：没有 M2 中的任何表达；没有 before/after、没有 on-body demo、没有「replying to」式证言。

判定顺序：

1. 先看 C1。有商品锚点或购买链接，直接排除 consideration。
2. 再看 M2。有本人使用证据，判 material candidate。
3. 再看 C2 与 C3。C1 + C2 + C3 同时成立，判 consideration。
4. 三者都不成立，判 `unknown`。`unknown` 不进任何样本，只计数。

#### 边界说明

- **consideration 与 relation_type 正交。** 一条视频可以是 `text_brand_and_category`，同时内容标签是 `consideration`。relation_type 回答「与商品的关系」，content tag 回答「内容形态」。
- **consideration 不是低质内容。** 它只是不能回答「什么素材表现好」。它可以回答「消费者买前在想什么」。
- **material 也不自动进基线。** material 只是内容形态标签；进基线仍要求 exact 锚点。
- **判定必须引用原文。** 每条 consideration 判定都要附上触发词所在的原文片段，不能只写标签。

### 5.5 `7696910923616881951` 的处理动作

1. 从 `high_performers.videos` 移除。它当前是 8 条中的第 6 条，靠 551 播放、52 次互动、9.44% 互动率入选，`low_denominator_flag = true`。
2. 保留在 category_reference 的 38 条计数中，加 `consideration` 标签。
3. 报告如需引用，只能放在「考虑期信号」小节，引用原文，不给互动率排名。
4. 高表现集合按 exact-only 重算后只有 1 条（`7695942452426968333`）。写 n=1，标 `insufficient_sample`。不得为了凑数保留提问帖。

## 6. 硬约束与验收

- 金标集不动。本裁决不修改 `gold-set-50.jsonl` 或任何 gold 标注。
- n>=8 门槛不放宽。任何分层单元 n<8，只写 `insufficient_sample` 和计数。
- 每一处改动都能指到具体原文或字段。引用格式：文件路径 + 行号或 JSON 字段路径。
- category_reference 可以描述，不能出「哪类跑赢」的结论。
- 报告变薄是预期结果，不是缺陷。10 条 exact 只能支持整体分布和逐条明细。

验收清单：

- [ ] 视频层基线分母为 10，不是 48。
- [ ] `report.html` 不再出现「48 条基线」「进入基线 48」。
- [ ] `report.html`、`baseline.md`、`baseline.json`、`coverage.json`、`creator-video-summary.json`、`collect-summary.json`、`voc/report.py`、`tools/creator_video_relations.py` 中「同标题」命中数为 0。
- [ ] 时长、链接、广告披露三个维度全部标 `insufficient_sample`，只给计数。
- [ ] `7696910923616881951` 不在 `high_performers`。
- [ ] category_reference 的 38 条单列，未与 exact 合并。
- [ ] 金标集未改动。
