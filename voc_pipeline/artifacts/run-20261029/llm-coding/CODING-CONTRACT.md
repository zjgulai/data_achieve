# VOC 编码契约（v1）

> **历史输入契约（E-merge 后只读）**。本文件描述生成 `llm-coding/coded/ALL.jsonl`
> 时的冻结规则。E-merge 已删除 `is_product_experience` 作为发布门禁：它现在
> 只作审计信号，aspect 的唯一门禁是
> `product_match ∈ {exact_current_family, category_adjacent} AND experience_scope ∈ {full, partial} AND text 非空`
> （`decisions/E-merge-experience-fields.md` §2.4）。不要按本文件重新解释
> 已发布产物的 cohort。

本文件是编码员唯一要遵守的规格。开始编码前先读 `taxonomy.json`；aspect code 只能从该文件的 `aspects[].code` 里选，context code 只能从 `contexts[].code` 里选。

## 0. 适用范围与硬禁令

- 输入是 `batches/batch-01.jsonl` … `batch-08.jsonl`，每行一条记录。
- 输出是每行一个 JSON 对象，与输入**逐行对应、顺序一致、不多不少**。
- **禁止读取**以下文件，否则精度作废：
  - `artifacts/run-20261029/gold-set-50.jsonl`
  - `artifacts/run-20261029/gold/gold-set-50.raw.jsonl`
- 禁止使用品牌官网、商品页、外部知识补充文本里没有的信息。只根据当前这一条记录判断。
- 禁止把 star rating 当作证据。rating 只是上下文；没有文本证据就不标 aspect。

## 1. 输入字段

每行可能包含：

| 字段 | 说明 |
| --- | --- |
| `canonical_id` | 记录 ID，输出必须原样回填 |
| `source` | `reddit` 或 `tiktok_shop` |
| `title` | 标题，可能为空字符串 |
| `text` | 正文，保证非空 |
| `product_match` | `exact_current_family` / `category_adjacent` / `brand_other_product` / `irrelevant` |
| `rating` | 仅 TikTok 有的 1–5 星，可能不存在 |
| `verified_purchase` | 仅 TikTok 有，可能不存在 |

`product_match` 只描述这条记录与本品类的关系，**不决定** `is_product_experience`。判断仍以文本为准。

少数记录 `text` 为空但 `title` 非空（共 14 条）。这类记录仍要编码，原文范围就是 `title`，`evidence_span` 必须出现在 `title` 里。

## 2. 输出 schema

每行必须是下面这个对象，字段一个不少、一个不多：

```json
{
  "canonical_id": "c-xxxxxxxx",
  "is_product_experience": true,
  "experience_reason": "first_person_use",
  "experience_scope": "partial",
  "experience_source": "first_person",
  "aspects": [
    {
      "code": "SUP.BACK",
      "polarity": "positive",
      "evidence_span": "my lower back pain has eased",
      "confidence": "high"
    }
  ],
  "contexts": ["CTX.PREGNANCY_T3"],
  "journey": "repeat_use",
  "outcome": "relief",
  "medical_self_report": false,
  "notes": "none"
}
```

### 字段枚举

- `experience_reason`：`first_person_use` / `help_seeking` / `third_party_event` / `product_mismatch` / `question` / `other`
- `experience_scope`：`full` / `partial` / `none`；`is_product_experience=false` 时必须为 `none`
- `experience_source`：`first_person` / `relayed`；只有 `is_product_experience=true` 且作者是购买者/直接经手人、转述家人或朋友的使用效果时才用 `relayed`
- `aspects[].polarity`：`positive` / `qualified_positive` / `negative` / `qualified_negative` / `mixed` / `unknown`
- `aspects[].confidence`：`high` / `medium` / `low`
- `journey`：`purchase` / `selection` / `first_use` / `repeat_use` / `return` / `null`
- `outcome`：`relief` / `no_relief` / `null`
- `contexts[]`：只能取 `taxonomy.json` 中 `contexts[].code`（12 个 `CTX.*`），可以是空数组
- `medical_self_report`：布尔值
- `notes`：字符串，一句话；没有歧义就写 `"none"`

注意：`qualified_positive` 与 `qualified_negative` 对称使用：总体正向但同一属性上带实质性程度/条件保留、且保留不足以拆成独立负向 aspect 时，用 `qualified_positive`；总体负向但带实质性程度/条件保留（hedge 或让步）时，用 `qualified_negative`。两者都要求保留可引用；能拆成两条 aspect 时必须拆。journey / outcome 输出的是上面的普通字符串，**不是** taxonomy 里的 `JNY.*` / `OUT.*` code。

## 3. `is_product_experience` 判定

先执行本节规则，再标 aspect。

### Normative experience rule (verbatim in SPEC.md and CODING-CONTRACT.md §3)

`is_product_experience = true` if and only if the record contains at least one
attributable, quotable first-hand product evaluation.

An evaluation is attributable when at least one of these holds:

1. The evaluated object is the current product in the record's context
   (current pregnancy, current purchase, current use, current comparison).
2. The evaluated object is a specific named product or brand (for example
   "Azband", "the fitsplint", "Momcozy", "Ergonest").
3. The record is not a recommendation/help-seeking record, and the evaluation
   is the author's main statement, even if the product is unnamed or the use
   happened in the past.

These do not count:

- Only "I bought it" or "I have it", with no attribute, effect, or polarity.
- In a recommendation/help-seeking record, the only evaluation is of an
  unnamed product from a previous pregnancy or past use ("my belly band my
  first pregnancy"). That is background, not purchase evidence for this
  record.
- The evaluation is about another product category and unrelated to support
  bands.
- Pure question, pure emotion, or pure news.

`experience_scope` takes exactly one value:

- `full`: `is_product_experience = true`, and the author is not asking for
  recommendations, help, or other people's experience for their own decision.
- `partial`: `is_product_experience = true`, and the author is asking for
  recommendations, help, "which one is best / should I buy / has anyone
  tried", or other opinions for their own decision.
- `none`: `is_product_experience = false`. In this case `aspects` must be
  empty.

A question the author asks while replying to another person ("Have you tried
them?") does not make the record `partial`: the author is not collecting
opinions for their own decision. Only the author's own request counts.

`experience_source` takes exactly one value:

- `first_person`: the author used and evaluated the product.
- `relayed`: the author is the purchaser or direct handler and relays a family
  member's or friend's use. A direct purchaser relaying a family member's use
  is `true` with `experience_source = relayed`.

`third_party_event` is reserved for external events (strikes, shipping delays,
store stock, platform policy). It is not used for a family member's relayed
use.

Decision procedure, in order:

1. Is there a first-hand product evaluation? If no, `is_product_experience =
   false` (`experience_reason = help_seeking` if the record asks for
   recommendations or help; otherwise `question` or `other`).
2. Is the record a recommendation/help-seeking record, and is the only
   evaluation an unnamed product from a previous pregnancy or past use? If
   yes, `is_product_experience = false`, `experience_reason = help_seeking`.
3. Is the author also asking for recommendations, help, or other people's
   experience for their own decision? If yes, `experience_scope = partial`; if
   no, `experience_scope = full`.
4. Is the author the user, or a purchaser relaying a family member? Relayed
   means `experience_source = relayed`; otherwise `first_person`.

### 中文对照表

| 情形 | is_product_experience | experience_scope | experience_source | experience_reason |
| --- | --- | --- | --- | --- |
| 本人/经手人评价当前产品，或明确指定品牌/型号的产品 | `true` | 无求助 `full`；同时求助 `partial` | `first_person` | `first_person_use` |
| 求推荐/求助，且有当前产品的可归属评价 | `true` | `partial` | `first_person` | `first_person_use` |
| 求推荐/求助，唯一评价是上一胎/过去使用、未指明品牌或型号的产品 | `false` | `none` | `first_person` | `help_seeking` |
| 反复求助、求推荐、问“哪个好/要不要买”，且完全没有产品评价 | `false` | `none` | `first_person` | `help_seeking` |
| 购买者/直接经手人转述家人或朋友的使用效果 | `true` | 无求助 `full`；同时求助 `partial` | `relayed` | `first_person_use` |
| 工会罢工、快递延误、线下门店买不到、平台政策等外部事件 | `false` | `none` | `first_person` | `third_party_event` |
| 讨论的是别的品类（吸奶器、孕妇装、婴儿车等），或产品与主题无关 | `false` | `none` | `first_person` | `product_mismatch` |
| 纯提问，不含产品评价 | `false` | `none` | `first_person` | `question` |
| 纯新闻、科普、情绪倾诉，无产品指向 | `false` | `none` | `first_person` | `other` |
| 只提到“我买了/我有”，没有任何评价、效果或属性描述 | `false` | `none` | `first_person` | `other` |

补充规则：

1. 同一条记录里既有真实产品评价又有提问：`is_product_experience = true`，`experience_scope = partial`，只编码评价部分，`notes` 记“also asks …”。如果唯一的评价只是对上一胎未指明产品的顺带一提，则 `false`、`help_seeking`。
2. 说别的品牌但属于**同品类**：`true`（品类体验）；只编码文本真实评价到的属性，不要把本品类的预期套上去。
3. 收到商品破损、有使用痕迹、包装问题：`true`，用 `FUL.PRODUCT_CONDITION`。仅抱怨快递慢、没送到：`false`，`third_party_event`。
4. `false` 时 `aspects` 必须是空数组 `[]`。
5. `experience_scope` 必须三选一；`partial` 只标记“作者在为本人决策征集意见”的语境，不是质量更低的记录。任何分布类结论必须分 `full` / `partial` 两层报告，不能把 pooled 当分布。

## 4. Aspect 判定

- 一个 aspect 对应一个可评价的产品属性，不是关键词命中。
- 一句话里有多个属性，可以标多个 aspect，但每个 aspect 必须有**自己的** `evidence_span`。
- 同一个子句只能有一个极性。真的同时有正负（“supportive but digs in after an hour”）→ 拆成两条 aspect，各带自己的 span；拆不开才用 `mixed`。
- 只标文本明确评价到的属性。文本没有提到“背部”就不要标 `SUP.BACK`。
- 比较句（“better than X”）只对被评价的主体成立，不要外推到 X，也不要给 X 标 aspect。
- 每条记录最多 **6** 个 aspect。超过 6 个说明标太松，重标，保留证据最强的 6 个。

### 各 family 的边界提示

完整定义、include/exclude 和例句见 `taxonomy.json`。常见混淆：

- `SUP.GENERAL` 只收“支撑/托举”语义；单纯“穿着舒服”走 `COM.*`。
- `SUP.BACK` 必须有背部/腰部指向；泛泛的姿势、运动不加。
- `SUP.PRESSURE_OFFLOAD` 是“重量被卸掉”的主观感受；只描述松紧不算。
- `FIT.SIZE_ACCURACY` 是收到后的尺码对错；买之前的选码提问不算。
- `FIT.COVERAGE` 是覆盖面积；颜色覆盖、视觉遮挡不算。
- `ADJ.STRAP_DESIGN` 是结构（绑带/魔术贴/扣件）；整体支撑评价不算。
- `ADJ.DONNING` 是穿脱难易；购买时间、包装不算。
- `STB.STAY_IN_PLACE` 是下滑/卷边/移位；支撑不足不算。
- `STB.STRAP_POSITION` 是绑带压到不合适的位置；单纯“紧”不算。
- `COM.SOFTNESS` 是面料触感；支撑不算。
- `COM.BREATHABILITY_HEAT` 是闷热/出汗/透气；环境温度不算。
- `COM.SKIN_CHAFE` 是摩擦/红印/瘙痒/皮疹；局部压痛不算。
- `COM.PRESSURE_DIGGING` 是局部压痛/勒痕/digging；皮肤摩擦不算。
- `COM.WEAR_TOLERANCE` 是全天/长时间穿着；单次短时不算。
- `COM.GENERAL` 是整体舒适；具体部位的评价不算。
- `APP.UNDER_CLOTHING` 是衣下可见性；外穿不算。
- `APP.LOW_PROFILE` 是体积小/不臃肿；面料厚薄本身不算。
- `APP.COLOR_AESTHETIC` 是颜色/外观；功能不算。
- `MAT.FABRIC` 是面料材质本身；舒适评价不算。
- `MAT.DURABILITY` 是洗后/长期损坏；单次清洗不算。
- `MAT.ELASTICITY_RETENTION` 是被撑松/失去弹性；初始弹性不算。
- `MAT.THICKNESS` 是厚薄；体积/隐蔽性不算。
- `MAT.CARE` 是清洗护理方式；耐用性不算。
- `VAL.PRICE_VALUE` 是价格/性价比；赠品、包装不算。
- `CX.RETURN_EXCHANGE` 是退货/换货/退款体验；购买前的犹豫不算。
- `FUL.PRODUCT_CONDITION` 是到货状态/包装/二手痕迹；物流时效不算。
- `GEN.OVERALL_EVALUATION` 是整体好恶/推荐；单一属性不算。
- `USE.LAYERING` 是内穿/外穿/叠穿方式；衣下可见性不算。
- `ACT.COMPATIBILITY` 是走路/跑步/工作/站立/坐着/睡觉时的可用性；静态合身不算。
- `SAF.PRESSURE_PLACEMENT` 是对腹部受力位置的安全担忧；一般不适不算。

## 5. 极性定义

| 值 | 用法 |
| --- | --- |
| `positive` | 明确正面；或明确说问题不存在（“doesn't slip”“no chafing”） |
| `qualified_positive` | 总体正面，但同一属性上带实质性程度/条件保留；保留不足以构成独立负向 aspect，且不能拆成两条 aspect |
| `negative` | 明确负面 |
| `qualified_negative` | 总体负面，但同一属性上带实质性程度/条件保留（hedge 或让步）；保留不足以构成独立正向 aspect，且不能拆成两条 aspect |
| `mixed` | 同一 aspect 内正负并存，确实无法拆分（原则上应先尝试拆） |
| `unknown` | 提到了该属性，但好坏无法判断、语气反讽、条件句、或证据不足 |

- `qualified_positive` 的保留必须可引用：`almost`, `mostly`, `some`, `somewhat`, `just enough`, `only`, `not fully`, `compared with X it is less`。没有可引用的保留就写 `positive`。
- `qualified_positive` 不是“轻微正面”的垃圾桶：正负同等 material 且拆不开时用 `mixed`；不同属性的负向必须拆成两条 aspect，不能塞进 `qualified_positive`。
- 比较句里主体仍明显更好（“better than my other bands”）用 `positive`；对购买时机的后悔（“I wish I had bought it sooner”）用 `positive`，它不是对产品的保留。
- `qualified_negative` 与 `qualified_positive` 对称：总体负向 + 同属性程度/条件保留（“not optimal”, “some discomfort”, “want a little more”）；保留不是独立正向 material。
- `unknown` **不等于** `negative`。没有 polarity cue 就写 `unknown`，不要默认负向。
- 形容词本身的褒贬不等于“对产品而言的好坏”。“soft”在“soft but useless”里不构成正向支撑评价。
- 否定词作用域看完整句：“did not find it provided optimal relief”是负向；“didn't have any pain”是正向（问题不存在）。
- 反讽、假设句（“if it only stayed put”）按字面负面处理，`confidence` 降为 `low` 或 `medium`。

`confidence` 的定义：

| 值 | 用法 |
| --- | --- |
| `high` | span 直接、明确说出该判断，换一个人读也会得到同一结论 |
| `medium` | 需要一步明显推断（例如 “didn't have any pain” → 问题不存在） |
| `low` | 依赖语气、反讽或上下文，存在另一种合理解读 |

## 6. `evidence_span` 规则（最关键）

1. 必须**逐字**摘自 `title` 或 `text`：不改拼写、不补标点、不翻译、不合并段落、不加省略号、不改弯引号。
2. 必须是原文的连续子串。校验器会做精确子串匹配，匹配不上整条 aspect 作废。
3. 长度 ≤ **120 个字符**（按 Unicode 字符计，空格也算）。
4. 一条 span 只能支撑一个 aspect。两个 aspect 不能共用同一条 span。
5. 写不出 span，就说明这条判断没有依据：删掉该 aspect。
6. 优先选最短的、能独立说明问题的片段，不要整段复制。
7. span 可以来自 `title`，也可以来自 `text`，但不要跨两者的拼接边界。

## 7. 其他字段

### contexts

只写文本明确支持或可直接推出的 `CTX.*`：

- 孕周/孕期：`CTX.PREGNANCY_T2`（13–27 周）、`CTX.PREGNANCY_T3`（28 周以后）
- 体型：`CTX.BODY_PLUS_SIZE`、`CTX.BODY_TALL_LONG_TORSO`、`CTX.BODY_SHORT_TORSO`
- 多胎：`CTX.MULTIPLES`
- 场景：`CTX.ACTIVITY_WORK`、`CTX.ACTIVITY_EXERCISE`、`CTX.DURATION_ALL_DAY`
- 购买关系：`CTX.PURCHASE_GIFT`
- 皮肤：`CTX.SENSITIVE_SKIN`
- 产后：`CTX.POSTPARTUM`

没有明确依据就留空数组。context 不是 aspect，不需要 `evidence_span`，但必须能从文本看出来。

### journey

只选一个，取记录的主导阶段：

- `purchase`：下单/购买决策/价格/在哪买
- `selection`：选码/选型号/比较款式
- `first_use`：第一次试穿/刚收到
- `repeat_use`：用了一段时间/日常使用/复购
- `return`：退货/换货/退款
- `null`：判断不了

### outcome

只在文本明确谈到疼痛或不适的结果时填写：

- `relief`：明确说疼痛/不适得到缓解（“eases the pain”“my back pain is gone”）
- `no_relief`：明确说没有缓解/没用
- `null`：未提疼痛结果；仅仅“舒服”“有支撑”不算 outcome

### medical_self_report

仅当文本以**第一人称自述**疼痛、疾病（SPD、PGP、坐骨神经痛等）或对腹部/胎儿受压的安全担忧时为 `true`。转述他人不算。它只是一个 flag，不要为它创建 aspect。

### notes

一句话，标出歧义点（例如“品牌不同但同品类”“同时也在求助”“反讽”）。没有就写 `"none"`。不要写分析过程。

## 8. 绝对禁止

1. 给没有产品评价的记录标 aspect（`is_product_experience = false` 时 `aspects` 必须为空）。
2. 一条 `evidence_span` 支撑多个 aspect。
3. 用形容词本身的褒贬代替“对产品而言的好坏”。
4. 编造 span，或改写原文去凑 span。
5. 使用 `taxonomy.json` 以外的 code。
6. 没有 span 的 aspect。
7. 猜极性；拿不准就 `unknown` 或不标。
8. 因为 rating 高就补正面 aspect，或因为 rating 低就补负面 aspect。
9. 读取 gold set（见第 0 节）。

## 9. 输出格式

- UTF-8，每行一个 JSON 对象，行尾 `\n`。
- 不要 Markdown 代码围栏，不要数组外层，不要空行，不要注释，不要解释文字。
- `canonical_id` 必须与输入完全一致，输出行数与输入行数一致，顺序一致。
- 每条记录都必须有输出，即使是 `is_product_experience = false` 也要输出完整对象。
- 建议输出到 `outputs/batch-01.jsonl` … `outputs/batch-08.jsonl`（与输入批次同名）。

## 10. 提交前自检

1. 每个输入 `canonical_id` 恰好出现一次，顺序一致。
2. 每条 `evidence_span` 都能在对应记录的 `title`/`text` 里精确找到，且 ≤120 字符。
3. 每个 `code` 都在 `taxonomy.json` 的 aspects 里。
4. `is_product_experience = false` 的记录 `aspects` 全为空。
5. 每条记录 aspect 数 ≤6。
6. 同一条记录内没有重复的 `evidence_span`。
7. 没有读取 gold set。
8. 跑一遍校验器（默认就指向本目录下的 `batches/`、`outputs/`、`batch-report.json`）：

```bash
python3 /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/llm-coding/validate-coding.py
```

也可以显式传参：

```bash
python3 /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/llm-coding/validate-coding.py \
  --batches-dir /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/llm-coding/batches \
  --outputs /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/llm-coding/outputs \
  --report /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/llm-coding/batch-report.json
```

校验器报 `ok: true` 才算完成。`unknown` 比例高不是错误，`evidence_span` 匹配失败是错误。
