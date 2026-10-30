# 裁决 A：体验门槛

## 0. 最终裁决

**选立场 3，并加一条可执行的排除规则：记录级 `is_product_experience = true`；如果记录同时是求推荐/求助帖，加 `experience_scope = partial`；如果求助记录里唯一的“评价”只是对上一胎未指明产品的顺带一提，则为 `false`。分布类结论必须按 `full` / `partial` 分层，不能合并。**

一句话：**有真实评价就保留，但要把“求推荐”这个语境单独标出来；没有可归属的评价，只是顺带说旧产品，就不算体验。**

这条裁决同时回答两个冲突：

| 冲突 | 旧 SPEC | 旧契约 §3 | 本裁决 |
| --- | --- | --- | --- |
| 求推荐 + 真实评价 | 整条 `false` | 整条 `true`，只编码评价 | `true` + `experience_scope=partial` |
| 三方转述（B16） | `false`，`third_party_event` | `true`，替家人买后转述算体验 | `true`；`experience_source=relayed`；`third_party_event` 只留给外部事件 |

## 1. 为什么不能选立场 1（严格 false）

### 1.1 gold set 自己就同时用了两套规则

`gold-set-50.jsonl` 里有 4 条“求推荐/求助”记录。它们的标签不一致：

| canonical_id | 原文摘要 | gold `is_product_experience` | gold note |
| --- | --- | --- | --- |
| `c-1x65j91`（B17） | “Someone help me find a good belly band please!” + “I honestly hated my belly band my first pregnancy” | `false` | “求推荐帖；提到上一胎的带子只是顺带说‘不喜欢’，且是未指明的其他产品，按 FC-10 不计。” |
| `c-1s8bn5y` | “How are we managing round ligament pain? Taking any and all suggestions.” + “I just started using a belly band… jury is still out” | `true`，`SUP.GENERAL:unknown` | “刚开始用带子，明确说效果未定（unknown）。” |
| `c-1w3knom` | “Anyone been able to jog up to their due date?” + “actually using a belly band are helping” | `true`，`SUP.GENERAL:positive` | “明确把带子列为有帮助的因素；标题问句会触发求助规则。” |
| `c-1upreg8` | “Has anyone else run in them?” + 详细评价位置、托举、组合 | `true`，3 个 aspect | “正文是详细使用体验（通用便宜带子）……” |

`c-1w3knom` 的 note 最关键：**gold 明确知道标题是问句、会触发求助规则，仍然标了 `true`**。所以“gold 支持严格 false”这个说法不成立。gold 自己就是矛盾体：`c-1x65j91` 按“顺带、未指明、上一胎”排除，另外 3 条按“有评价就 true”纳入。

如果选立场 1，会把 3 条 gold-true 记录（`c-1s8bn5y`、`c-1w3knom`、`c-1upreg8`）翻成 false，直接丢掉 5 个 gold aspect。这是改 gold 之外最大的 gold 冲突。

### 1.2 立场 1 会删掉最有价值的摩擦证据

natural frame 的 39 条本人体验里，有 20 条是“求助/求推荐 + 有评价”。其中：

- C04 的 3 条摩擦记录里，2 条来自求推荐帖：`c-1opsx7o`（“Which pregnancy belly band is the best?”）和 `c-1q2ir63`（“running belly band recs?”）。
- C05 的唯一共现记录就是 `c-1opsx7o`：舒适正向 + 支撑负向。
- `c-1opsx7o` 还是 C04 里唯一 `product_match=exact_current_family` 的摩擦记录。

立场 1 会把 C04 从 3 条摩擦降到 1 条（只剩 `c-1sn9hb1`），把 C05 从“1/3 共现”降到 full 层“0/1”。这不是“更干净”，而是**把最有产品指向的证据删掉，只留下没有求助语境的记录**，会系统性地偏向“满意且主动分享”的样本。

## 2. 为什么不能只选立场 2（宽松 true、不标记）

立场 2 的数字与现在一样，但它把两种不同的产生机制混在一起：

- `full`：作者主动分享使用体验，评价是记录的主目的。
- `partial`：作者在征集意见，评价是求助语境的一部分。评价会被后续回复污染，作者也可能为了 justification 而强调某一点。

当前 C04 的 3 条摩擦里 2 条是 partial；C05 的 3 条舒适正向里 2 条是 partial，唯一共现 1/1 是 partial。把 1/3 写成“自然样本的共现”会掩盖这个事实。立场 2 不是错在数字，而是错在**不告诉你数字从哪来**。

## 3. 最终规则（可直接执行）

### 3.1 `is_product_experience`

`true` 当且仅当记录里至少有一条**可归属、可引用**的第一手产品评价。可归属指满足以下任一：

1. 评价对象是记录语境里的当前产品（当前孕期、当前购买、当前使用、当前比较）；
2. 评价对象是明确指定的产品/品牌（例如 “Azband”、“the fitsplint”、“Momcozy”、“Ergonest”）；
3. 记录不是求推荐/求助，且评价是作者本人的主要陈述（即使产品没有点名、即使发生在过去）。

以下不算：

- 只提到“我买了/我有”，没有属性、效果或极性；
- **在求推荐/求助记录里**，唯一的评价是上一胎/过去使用、且没有指明品牌或型号的产品（“my belly band my first pregnancy”）。这类只是背景，不是本条记录的求购证据；
- 评价的是别的品类，且与支撑带无关；
- 纯提问、纯情绪、纯新闻。

注意：非求助记录里的过去评价，如果是记录的主内容（例如回复别人“我上一胎用带子缓解了背痛”），仍然算体验；不要因为“过去”就一律排除。排除只针对“求助 + 顺带提旧产品”的组合。

### 3.2 `experience_scope`

每条记录必须恰好取一个值：

| 值 | 条件 |
| --- | --- |
| `full` | `true`，且作者不是在为自己的决策求推荐/求助/征求他人经验 |
| `partial` | `true`，且作者在为**自己的决策**求推荐、求助、问“哪个好/要不要买/有没有人试过”等征集意见 |

注意：回复别人时反问“Have you tried them?”不算 partial；那不是作者在为自己的决策征集意见，是在帮对方澄清。只有作者本人在征集意见才算 partial。
| `none` | `false` |

`is_product_experience=false` 时，`aspects` 必须为空，`experience_scope=none`。

### 3.3 `experience_source`（只解决 B16）

| 值 | 条件 |
| --- | --- |
| `first_person` | 作者本人使用并评价 |
| `relayed` | 作者是购买者/直接经手人，转述家人或朋友的使用效果 |

B16 `c-7659258409535112974`（“Bought for my daughter and she said…”）判 `true`、`experience_source=relayed`、`experience_scope=full`。理由：它是 verified-purchase 评论，购买和经手都是作者本人；`third_party_event` 只用于工会罢工、快递延误、门店缺货、平台政策这类外部事件，不用于家人转述。

### 3.4 分布类结论的分层规则

以下结论必须分 `full` / `partial` 两层报告，不能合并：

- prevalence、share、发生率；
- 方向一致度（C13 及任何 Direction 类指标）；
- 共现率（C05）；
- 任何“自然样本里 X 占 Y”的措辞。

纯存在性/计数事实可以给 pooled 总数，但必须同时给出两层数字，并在同一段写明“pooled 不是分布”。

## 4. 对每条 claim 的具体影响

### 4.0 三种立场对照表

| 口径 | experience 记录 | C04 摩擦记录 | C05 舒适正向 / 共现 | C13 decisive | C03 exact-model 体验 |
| --- | ---: | --- | --- | ---: | ---: |
| 立场 1 严格 false | 19 | 1 | 1 / 0 → Evidence gap | 32 | 0 |
| 立场 2 宽松 true | 39 | 3 | 3 / 1 | 32 | 0 |
| 立场 3 本裁决 | 37 = full 19 + partial 18 | pooled 3 = full 1 + partial 2 | pooled 3 / 1 = full 1/0 + partial 2/1 | 32 | 0 |

关键读法：

- 立场 1 和立场 2 的 C13 都是 32，因为 C13 的 32 条里没有求推荐帖。
- 立场 3 的 C04/C05 pooled 摩擦/共现计数与立场 2 相同，但分层后 2/3 摩擦和 1/1 共现来自 partial 层；full 层的 C05 是 0/1。experience 记录数从 39 降到 37。
- 立场 1 的 C04 从 3 降到 1，C05 从 1/3 降到 0/1；这是删证据，不是提纯。
- C03 在三种立场下都是 0，因为唯一的 exact-model 记录是纯求助帖。

### 4.1 C04（自然样本摩擦）

现状：natural 149 条，本人体验 39 条，support negative 3，friction records 3，fit/stab/value 均 0。

按本裁决重算：20 条“求助/求推荐 + 有评价”里，18 条转为 `true / partial`，2 条（`c-1x65j91`、`c-1sn8eo1`）因只有“上一胎未指明产品”的顺带评价转为 `false`。因此本人体验从 39 降到 37（full 19 + partial 18），被排除记录从 110 升到 112。C04 的 pooled 摩擦数字不变（仍是 3），但分层后 2/3 在 partial 层。

| 层 | 记录数 | support negative | fit | stability | value | 摩擦记录 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full` | 19 | 1 | 0 | 0 | 0 | 1（`c-1sn9hb1`） |
| `partial` | 18 | 2 | 0 | 0 | 0 | 2（`c-1opsx7o`、`c-1q2ir63`） |
| pooled | 37 | 3 | 0 | 0 | 0 | 3 |

- pooled 数字仍是 3，和现在一样；但 2/3 来自 partial 层。
- C04 的 headline 必须写成“full 1 / partial 2”，或“pooled 3，其中 full 1、partial 2”。不能只写“3 条”。
- C04 的 grade 仍是 Confirmed（计数事实），不因分层掉档。
- 两条因“上一胎未指明产品”转为 false 的记录（`c-1x65j91`、`c-1sn8eo1`）没有 friction 标注，不影响 C04 的数字。

### 4.2 C05（共现）

现状：舒适/外观正向 3 条，其中 1 条同时有核心摩擦；share 0.333。

按本裁决重算：

| 层 | 舒适正向 | 其中共现 | 共现记录 |
| --- | ---: | ---: | --- |
| `full` | 1（`c-19rm4lmi0oa78`） | 0 | — |
| `partial` | 2（`c-1opsx7o`、`c-1rqq680`） | 1 | `c-1opsx7o` |
| pooled | 3 | 1 | `c-1opsx7o` |

- pooled 1/3 在数字上仍成立，但唯一的共现 1/1 全部来自 partial 层。
- C05 不能再写成“自然样本里舒适与支撑存在共现”。只能写成“partial 层观察到 1 条共现；full 层 0/1”。
- 如果报告只允许一个 headline，C05 在 full 层是 **Evidence gap**；pooled 1/3 只能作为 partial 层观察，不能作为总体共现率。
- `c-1rqq680`（“How did you all make it through the rest of the third trimester?”）是 partial，因为它有求建议语句；它的舒适正向不进入 full 分母。

### 4.3 C13（唯一 Directional）

**结论：C13 不受影响，n_records 仍是 32，不掉档。**

实测 `coded-corpus.jsonl`：C13 的 32 条 direction 记录全部来自 TikTok `tiktok_shop_verified` 帧，全部 `experience=True`、`experience_reason=first_person_use`。32 条里来自求推荐帖的条数是 **0**。

任务里的“27→32”是历史口径；当前 `claims.json`、`coded-corpus.jsonl` 和 `llm-coding/eval-result-high.json` 的 C13 都是 32。本文按当前 32 算。

| 口径 | decisive | same | opposite | agreement | 门槛 |
| --- | ---: | ---: | ---: | ---: | --- |
| 现状 | 32 | 26 | 6 | 81.2% | n≥8、authors≥2、≥70%，通过 |
| 立场 1（求推荐 false） | 32 | 26 | 6 | 81.2% | 不变，通过 |
| 立场 3（partial 分层） | 32 | 26 | 6 | 81.2% | 不变，通过 |
| 若把 B16 relayed 排除 | 31 | 25 | 6 | 80.6% | 仍通过 |

- 任务里“降到 <8 条会掉档”的担心不成立：C13 的分母不是 Reddit 求推荐帖，而是 TikTok verified-purchase 评论；求推荐条数是 0，所以立场 1 的下降量是 **0**。
- 如果额外决定把 B16（`c-7659258409535112974`，relayed）排除，n 从 32 降到 31，仍然 ≥8，方向一致度 80.6%，仍是 Directional。是否排除 B16 不影响 C13 的档位。
- C13 的 `direction_stats` 不读 `experience` 字段；即使读，32 条全是 first_person_use，结果一样。

### 4.4 C03（Evidence gap）

**结论：C03 不受影响，exact-model 本人体验仍是 0。**

- `momcozy` 命中 109 条；`product_match=exact_current_family` 16 条；直接讨论 belly band 11 条；提到 Ergonest/CozySupport/YB001 的 exact-model 记录 1 条（`c-1o715fe`）。
- `c-1o715fe` 是纯求助帖：“do pregnancy belly bands actually help? … I’m not sure which ones really work. Has anyone here actually tried…”；`experience=False`、`aspects=[]`。
- 立场 1、2、3 都不会把它变成体验；exact-model 本人体验在三种立场下都是 0。
- C03 的 Evidence gap 是结构性的（缺 exact-variant 评论层），不是体验门槛造成的。

### 4.5 其他 claim

- C11：用 journey/outcome 计数，不读 `experience` 字段；不受影响。
- C08：medical self-report 计数，不看体验门槛；不受影响。
- C10/C07：G7 状态与 metric rows；不受影响。

## 5. 与 blind κ 的关系

跨身份校准的 `is_product_experience` Fleiss κ = 0.6562（`calibration/cross-model/cross-model-report.md` §6），4 条分歧是 B01、B06、B13、B16。

这 4 条分歧不是 aspect 定义分歧，是文档分歧：盲标规格要求“求推荐 = false”，契约要求“有评价 = true”。5 个标注者分别跟了不同文档。

按本裁决：

| item | canonical_id | 本裁决 | blind 多数 | 说明 |
| --- | --- | --- | --- | --- |
| B01 | `c-1sn8eo1` | false | 3/5 false | 上一胎未指明产品，顺带评价，不算 |
| B06 | `c-1vztlvl` | true / partial | 4/5 false | 当前产品，有明确效果；多数跟了旧 SPEC |
| B13 | `c-1tue1fz` | true / partial | 3/5 false | 当前产品，有明确负向；多数跟了旧 SPEC |
| B16 | `c-7659258409535112974` | true / relayed | 4/5 true | 家人转述，购买者本人；不是 third_party_event |
| B17 | `c-1x65j91` | false | 5/5 false | 上一胎未指明产品，顺带评价；与 gold 一致 |
| B18 | `c-1q2ir63` | true / partial | 5/5 false | 当前产品（fitsplint）明确“不再有用”；多数跟了旧 SPEC |

结论：**不能把 0.6562 当作“标注者对体验定义的一致性”证据**。它测的是“谁读了哪份文档”。按本裁决重新盲标后，这 4 条分歧会消失或转为 scope 分歧；新 κ 必须重新测量，不能把旧 κ 改写成新 κ。

## 6. 文档修改点（唯一口径）

### 6.1 盲标规格 `/tmp/voc-blind-box/SPEC.md`

把：

> `false` for: asking for recommendations, asking which product is best, news or educational content, complaints about stores, logistics, or unions, and anything that is not about product performance.

改为：

> `false` only when the record has no attributable first-hand evaluation of the product. In a recommendation/help-seeking record, a past, unspecified product mention (“my belly band my first pregnancy”) is background and does not count. If the record has a real evaluation and also asks for recommendations, set `is_product_experience=true` and `experience_scope=partial`. If it has no such request, set `experience_scope=full`.

把：

> `third_party_event`

改为：

> `third_party_event` only for external events (strikes, shipping delays, store stock, platform policy). A direct purchaser relaying a family member’s use is `true`, `experience_source=relayed`.

### 6.2 生产契约 `llm-coding/CODING-CONTRACT.md`

- §2 schema 增加 `experience_scope`（`full` / `partial` / `none`）和 `experience_source`（`first_person` / `relayed`）。
- §3 补充规则 1 改为：

> 同一条记录里既有真实产品评价又有提问：`is_product_experience=true`，`experience_scope=partial`，只编码评价部分，`notes` 记 “also asks …”。如果唯一的评价只是对上一胎未指明产品的顺带一提，则 `false`、`help_seeking`。

- §3 表格中 `third_party_event` 行改为“外部事件”；家人/朋友转述另列 `true` / `relayed`。
- §3 补充规则 2/3 保留。

### 6.3 可复现的判据（给编码器）

对每条记录按顺序问：

1. 有没有第一手产品评价？没有 → false。
2. 记录是不是求推荐/求助？是，且唯一的评价是上一胎未指明产品的顺带一提 → false（`help_seeking`）。
3. 记录是否同时在求推荐/求助/征求他人经验？是 → partial；否 → full。
4. 作者是使用者本人，还是购买者转述家人？转述 → `experience_source=relayed`。

## 7. 诚实声明

- 本裁决不改 gold set。`c-1x65j91` 的 gold `false` 与本裁决一致；`c-1s8bn5y`、`c-1w3knom`、`c-1upreg8` 的 gold `true` 也与本裁决一致。4 条 gold 求助记录全部一致，0 冲突。
- 本裁决会推翻 blind 多数在 B06、B13、B18 上的 false 票。理由不是“多数错了”，而是“多数按旧 SPEC 投票，旧 SPEC 被本裁决废止”。
- 本裁决不改变 C04/C05 的 pooled 摩擦/共现数字（仍是 3 和 3/1），但会改变 `experience_natural_records`（39→37）和 `experience_dropped`（110→112）。2/3 摩擦和 1/1 共现来自 partial 层。任何把 pooled 当分布的写法都必须在报告里删掉。
- 本裁决不改变 C13 的 32/26/6/81.2%。如果未来把 B16 排除，数字变为 31/25/6/80.6%，仍是 Directional。
- 本裁决不改变 C03 的 0。C03 的缺口是 exact-variant 层缺失，不是体验门槛。
