# A2：重定义 `experience_scope=partial`

- 日期：2026-10-30
- 状态：裁决稿，待实现与全量重跑
- 取代：`A-experience-gate.md` §3.2 的 `experience_scope` 判定条件
- 不改：gold set、`is_product_experience` 的归属规则、`experience_source` 的定义、C05 的立场

## 0 最终裁决

**一句话定义：`partial` = 记录里有可归属的第一手产品评价，但评价是附带的或未定的；它只能作旁证，不能进入实质性分布层。**

保留 `partial`，不取消。但它不再表示“作者在求助”，也不再由标题或正文的请求形式触发。它只表示评价的**证据权重**不足：评价不是记录的主内容，或评价本身尚未定论。

这条定义看评价实质，不看文本形式。标题问号、正文里的“求推荐”、是否同时比较三款产品，都不单独决定 `partial`。

## 1 `partial` 到底要拦什么

先立原则：`partial` 拦**证据质量或证据权重风险**，不拦文本形态，不拦语境差异。

逐条判断七种情形：

| # | 情形 | 风险类型 | 是否由 `partial` 承担 | 处理位置与机器判定 |
|---|---|---|---|---|
| 1 | 标题是问句 | 文本形式 | **否** | `title` 不进入 scope 计算。只看正文的评价句与篇幅占比。 |
| 2 | 正文含求助/征求建议 | 语境 | **否** | `request_context` 只作上下文标记。评价充分 → `full`；评价附带 → `partial`（因为附带，不因为求助）。 |
| 3 | 评价对象是别人（家人/朋友） | 二手来源 | **否** | 购买者本人经手并转述 → `experience_source=relayed`；非购买者的转述 → `HEARSAY_RE` 排除该子句；整条都是转述 → `none`。 |
| 4 | 评价的是过去的、未指明的产品 | 归属风险 | **否** | 仅当记录里唯一的评价是“过去 + 未指明”时，`is_past_unspecified_evaluation` → `none`。具名品牌/型号不受此限。非求助记录里的过去评价若是主内容，保留 `full`，但不得用于型号级结论。 |
| 5 | 评价与求助内容混杂，评价只占很小篇幅 | 证据权重 | **是** | 不满足 §2.2 的 R3–R6 实质性阈值时判 `partial`。核心信号是评价句数与评价篇幅占比。 |
| 6 | 同时评价多款产品 | 记录级归属 | **否** | scope 仍按评价权重判；多产品记录可以是 `full`。记录级共现/方向指标必须加“同产品”守卫，不能把 A 产品的舒适正向和 B 产品的支撑负向拼成一条共现。 |
| 7 | 评价里带第三方转述 | 二手来源 | **否** | `HEARSAY_RE` 排除转述子句；第一手子句仍可编码。整条只有转述 → `none`。 |

结论：`partial` 只剩两个用例。

1. **附带评价**：记录的主内容是求助、症状叙述、孕期故事或其他话题，产品评价只是其中一句。
2. **未定评价**：作者刚用上产品，明确说效果未定（“jury is still out”“not sure if it helps”），没有决定性极性。

第 3、4、7 种情形已有专用字段或专用排除规则，不由 `partial` 重复承担。第 1、2、6 种情形不是评价质量缺陷，不能降级。

## 2 可执行判定

### 2.1 术语与信号

对每条 canonical record，取 `body = record.text`，标题不参与评价句提取。

**评价句（decisive evaluation clause）**：一个子句同时满足以下五条。

1. **产品指代**：含具名品牌/型号（Momcozy、Frida Mom、Keababies、Azband、fitsplint、Lasora、Ergonest 等），或含品类名词（belly band、belt、support band 等），或含代词（it/this/they）且同段最近先行词是上述产品。
2. **极性**：含正向、负向或限定极性线索（“helps”“doesn't help”“no longer helping”“sometimes helps”“not comfortable”等）。只写“我买了/我有/我穿着”但没有属性、效果或极性，不算评价句。
3. **断言**：不是问句，不是假设句（if/would/might），不是传闻（`HEARSAY_RE`），不是第三方外部事件。
4. **归属**：评价对象是当前产品、具名品牌/型号，或（非求助记录里）作者本人的主要陈述。联合归因不算：正向析取“KT tape or a belly band helped”不能拆分到带子；负向合取“none of rest, belly band, stretching helped”可以把否定分配到带子。
5. **非未定**：不是“jury is still out”“not sure if it's helping”“just started”“too early to tell”这类明确未定的表述。未定表述进入信号 `P`，不进入 `N`。

**信号**：

| 信号 | 定义 | 机器实现 |
|---|---|---|
| `N` | 评价句数量（句子级去重） | 用 `CLAUSE_SPLIT` + `SEGMENT_SPLIT` 切分，逐子句跑上述五条 |
| `C` | 评价句总字符数 | `sum(len(clause))` |
| `S` | 评价篇幅占比 | `C / max(1, len(body))` |
| `A` | 不同属性/方面数，且每个方面有决定性极性 | 优先用 taxonomy aspect code；无 code 时数评价句里的属性名词（support、comfort、softness、breathability、heat、stability/slip、fit/size、price、durability、ease of use） |
| `P` | 只有未定评价的当前产品使用 | 当前产品 + 未定标记，且 `N=0` |

### 2.2 决策表

按优先级从上到下，命中即停。

| 优先级 | 条件 | 判定 |
|---|---|---|
| R0 | `is_product_experience = false` | `none` |
| R1 | `N = 0` 且 `P = false` | `none` |
| R2 | `N = 0` 且 `P = true` | `partial` |
| R3 | `A ≥ 2` 且 `S ≥ 0.15` | `full` |
| R4 | `C ≥ 500` 且 `A ≥ 2` | `full` |
| R5 | `N ≥ 2` 且 `S ≥ 0.35` | `full` |
| R6 | `N ≥ 3` 且 `S ≥ 0.25` | `full` |
| R7 | `N ≥ 1` 且以上都不命中 | `partial` |

阈值是政策常量，不是每题可调的参数。把 `0.15 / 500 / 0.35 / 0.25` 写进配置并在本轮冻结。任何调整都必须重跑 18 条 partial 与 20 条 Reddit full 的对照表，并记录原因。

R4 是绝对篇幅条件：即使记录很长、评价占比不高，只要评价本身有 500 字以上且覆盖至少两个属性，就按 `full` 处理。它覆盖“500 字以上第一人称具体产品评价”的情形，防止长文中一段扎实的对比被占比稀释。

**判定伪代码**：

```python
def scope(rec) -> str:
    body = rec.text or ""
    if not is_product_experience(rec):
        return "none"
    evals = [c for c in clauses(rec) if is_decisive_eval(c, rec)]
    provisional = is_provisional_only(rec)
    if not evals:
        return "partial" if provisional else "none"
    n = len(evals)
    c = sum(len(e) for e in evals)
    s = c / max(1, len(body))
    a = distinct_attributes(evals)
    if (a >= 2 and s >= 0.15) or (c >= 500 and a >= 2) or (n >= 2 and s >= 0.35) or (n >= 3 and s >= 0.25):
        return "full"
    return "partial"
```

### 2.3 四个必答案例

| 案例 | 判定 | 语料中的实例 | 理由 |
|---|---|---|---|
| 标题是问句 + 正文有 500 字以上第一人称具体产品评价 | `full` | `c-1opsx7o`：标题 “Which pregnancy belly band is the best?”，正文 2020 字，逐项对比 Frida Mom / Momcozy / Keababies | 标题不参与判定。正文有多个评价句和多个属性，`A ≥ 2`、`S` 很高。标题问号不降级。 |
| 标题是问句 + 正文只有一句“我也在用 X，还行” | `partial` | `c-1q2ir63`：“I have the fitsplint and the last week or so I feel like it is no longer helping.” 正文 446 字，随后求推荐 | 评价句 1 句，`S ≈ 20%`，不满足 R3–R6。评价真实但附带。 |
| 标题是问句 + 正文完全没有本人评价 | `none` | `c-1o715fe`：标题 “do pregnancy belly bands actually help?”，正文全是症状和提问，没有第一手使用评价 | `N = 0`，`P = false`。没有可归属评价，不能进 `partial`。 |
| 标题不是问句 + 正文含“大家有什么推荐吗” | 看评价实质 | `c-1vztlvl`：标题 “Turning in my sleep is excruciating”，正文末尾 “Looking for any advice”，带子评价只有一句 | 请求本身不降级。该条因为评价只有 1 句、`S ≈ 20%` 判 `partial`。若正文有 500 字以上具体评价，判 `full`；若没有评价，判 `none`。 |

补充说明：

- **问句标题不是充分条件，也不是必要条件。** `c-1opsx7o` 有问句标题但判 `full`；`c-1vztlvl` 没有问句标题但有求助句，仍判 `partial`，原因是评价附带。
- **“求推荐”不是降级理由。** 求助语境只说明记录的目的，不说明评价不可靠。评价是否可靠，看评价句的数量、属性数和篇幅占比。
- **多产品不是降级理由。** `c-1opsx7o` 同时评价三款产品，仍是 `full`。但记录级指标必须按产品段归属，见 §4.3。

## 3 与旧标准的差异

| 维度 | 旧标准（v1 rule + v2 prompt） | 新标准（A2） | 变化原因 |
|---|---|---|---|
| 触发条件 | `help_seeking = true`（标题问句，或正文命中 `HELP_SEEK_RE`）+ 有任何真实评价 | 评价句数量、属性数、评价篇幅占比 | 旧标准是形式代理，不是评价实质 |
| 标题问句 | 直接触发 `partial` | 完全不参与 | 标题是文本形式，不是证据质量 |
| 正文求推荐 | 直接触发 `partial` | 只作 `request_context` 标记 | 求助语境不等于评价低质量 |
| 求助记录里的充分评价 | `partial` | `full` | 评价是记录主内容时，求助不降级 |
| 非求助记录里的附带评价 | `full` | `partial` | 旧标准只按语境分层，漏掉了“一句话顺带评价”的低权重记录 |
| 未定评价 | 求助记录 `partial`；非求助记录 `full` | `partial` | 未定评价是证据质量风险，两个语境都应标 |
| 多产品对比 | 求助记录 `partial`；非求助记录 `full` | 按评价权重判，通常是 `full` | 多产品是记录级归属问题，不是评价质量问题 |
| 过去 + 未指明产品 | 求助记录 `none`；非求助记录 `full` | 不变 | 与 gold B01/B17 一致，不改 |
| 家人/朋友转述 | `experience_source=relayed` | 不变 | 已有专用字段，不由 `partial` 重复承担 |
| `partial` 的含义 | 作者在为自己的决策征集意见 | 评价是附带的或未定的 | 从“语境”改为“证据权重” |

**旧标准的实际表现**：18 条 partial 里，13 条的旧判定与新判定一致，4 条应从 `partial` 升为 `full`，1 条应从 `partial` 降为 `none`。旧标准不是全错，但它把 4 条高信息量评价降级了，其中 `c-1opsx7o` 是全语料信息密度最高的一条。旧标准还在 full 层留下了若干“一句话顺带评价”的记录，新标准会对称地把它们降为 `partial`。

**v2 不能用来验证旧标准**：`llm-coding-v2/counterexamples/prompt-user.txt` 第 75–82 行把 `partial` 明确写成“the author is asking for recommendations, help, ...”。v2 的 17/18 partial 是同一套规则的复述，不是独立的实质判断。A2 实现后，v2 的 `experience_scope` 字段必须重算或重跑，不能直接沿用。

## 4 预期影响

### 4.1 18 条 partial 的逐条判定

| canonical_id | 关键原文片段（可检索） | 旧 | 新 | 依据 |
|---|---|---|---|---|
| `c-1vztlvl` | “wore my belly band while sleeping, which helped support my muscles when turning” | partial | **partial** | N=1，S≈20%；正文主体是睡眠疼痛故事 |
| `c-1tftmti` | “ergonest maternity belly band are basically keeping me functional at work” | partial | **partial** | N=1，S<15%；正文主体是待产清单求助 |
| `c-1srusk5` | “my dr suggested a belly band which does help sometimes” | partial | **partial** | N=1，S<15%；正文主体是症状询问 |
| `c-1sg6gqr` | “I have tried the belly band, but it doesn't fix the pain” | partial | **partial** | N=1，S<15%；正文主体是腹痛询问 |
| `c-1s8bn5y` | “jury is still out on if it's helping” | partial | **partial** | P=1；未定评价，无决定性极性 |
| `c-1s2rcvx` | “it caused me to break out all over my back” | partial | **partial** | N=1，S≈27%；过去具名 Azband，评价附带 |
| `c-1qnhsit` | “sometimes wearing belly band helps” | partial | **partial** | N=1，S<15%；正文主体是髋痛询问 |
| `c-1pwnioo` | “my legs felt like jello and the muscles in my thighs started firing” / “didn't stop until I took the band off” | partial | **full** | N≥3，S≈50%；整条是产品不良反应报告 |
| `c-1oyj0g6` | “No amount of rest, belly band support, stretching, or use of supportive pillows when sleeping seems to be helping” | partial | **partial** | N=1，S<15%；否定分配到带子，但评价附带 |
| `c-1opsx7o` | “The fabric is really soft” / “The support doesn't last if you wear it too long” | partial | **full** | N≥3，S>50%；2020 字三产品逐项对比，A≥2 |
| `c-1ofb8c1` | “some had been remedied during the day by KT tape or a belly band” | partial | **none** | 正向析取，无法拆分到带子；无可归属评价 |
| `c-1w3knom` | “actually using a belly band are helping” | partial | **partial** | N=1，S<15%；正文主体是跑步经验与提问 |
| `c-1upreg8` | “Four runs in and the band stays put.” / “the combo felt way better” | partial | **full** | N≥3，S≈60%；详细第一手使用体验 |
| `c-1tue1fz` | “use a belly band but it's just not comfortable anymore” | partial | **partial** | N=1，S<15%；正文主体是跑步困难 |
| `c-1sw9iyo` | “A belly band seems to make things worse” | partial | **partial** | N=1，S<15%；正文主体是 Braxton Hicks 询问 |
| `c-1rqq680` | “it doesn't slide around as much” / “The velcro is also a lot softer” / “the belly band has helped quite a bit” | partial | **full** | N≥3，S≈50%；1750 字详细体验，A≥2 |
| `c-1q2ir63` | “I have the fitsplint and the last week or so I feel like it is no longer helping” | partial | **partial** | N=1，S≈20%；正文主体是求推荐 |
| `c-1pnbhda` | “the compression has helped with the pain” | partial | **partial** | N=1，S<15%；正文主体是腹肌拉伤询问 |

**汇总：18 条中 4 条升 `full`，13 条保持 `partial`，1 条降 `none`。**

- 升 `full`：`c-1opsx7o`、`c-1rqq680`、`c-1upreg8`、`c-1pwnioo`。
- 降 `none`：`c-1ofb8c1`。
- 其余 13 条保持 `partial`，原因是评价只有 1 句、篇幅占比低，或评价未定。

**gold 对账**：18 条里只有 3 条在 gold set 中。`c-1upreg8`（gold true → 新 `full`）、`c-1w3knom`（gold true → 新 `partial`）、`c-1s8bn5y`（gold true → 新 `partial`）。三条都保持 `is_product_experience=true`，0 条与 gold 冲突。`c-1s8bn5y` 之所以不判 `none`，是因为 gold 把它标为 true 且带 `SUP.GENERAL:unknown`；“未定评价”正是 `partial` 的第二个用例。

### 4.2 full 层的对称复核（预审，待全量重跑）

新规则必须对称应用，否则只是补丁。对 20 条 Reddit full 记录做预审；81 条 TikTok full 记录都是 verified-purchase 商品评论，评价是记录主体，默认保持 `full`。

| canonical_id | 关键原文片段 | 正文长度 | 预估 | 理由 |
|---|---|---|---|---|
| `c-1sn9hb1` | “now using a belly band doesn't help” | 1771 | full → **partial** | 一句话评价藏在临产焦虑长文里 |
| `c-1m42ylt` | “with the belly band, I was back to sprinting around the court with ease” | 1120 | full → **partial** | 主体是网球故事；效果与 belly taping 混杂 |
| `c-1pfyruu` | “yes I'm wearing a belly band... but it doesn't help much” | 847 | full → **partial** | 主体是疼痛 rant；带子只占一句 |
| `c-1lijqy4` | “start using a belly band early... It really helps!” | 398 | full → **partial** | 主体是 5k 成就分享；带子是附带建议 |
| `c-19rn656rs3pnk` | “Even my belly band or varicose garment will give relief for a short time” | 437 | full → **partial** | 回复里的附带经验 |
| `c-19rq03p7e949w` | “I have a belly band but it doesn't feel better” | 431 | full → **partial** | 回复里的附带负面评价 |
| `c-19rkynhhprt2c` | “I use a belly band with a back support element too which also helps” | 520 | full → **partial**（边界） | 多条建议中的一句 |
| `c-19rljfjm31o5e` | “I did utilize a belly band more in my second pregnancy and that helped a lot with back pain” | 812 | full → **partial** | 主体是剖腹产恢复故事 |
| `c-19rjykcrivso1` | “I got a belly band and that helps give my growing belly support” | 605 | full → **partial**（边界） | 首句评价清楚，但后面是多种缓解手段清单 |
| `c-1o9a0w1` | “hopefully finish with my trusty momcozy belly band” | 271 | full → **none**（边界） | “trusty”是态度，不是属性/效果评价 |
| `c-1tkhcj3` | 标题 “My favorite belly band! Babybellyband Pregnancy Support Belt”，正文为空 | 0 | full → **none** | 标题不是体验报告；与 `coder.py` 的 “title alone is a headline” 一致 |

其余 9 条 Reddit full 记录的主体就是产品评价，保持 `full`：`c-1oht78y`、`c-1rpxflg`、`c-1mdp0wu`、`c-19rt15mqlhu00`、`c-19rm4lmi0oa78`、`c-19rtrxy45qs8x`、`c-19rhmz6kcrj45`、`c-pgsk2oe`、`c-19rt8k4ja4txf`。

**净影响估计**（预审，非最终数）：

| 层 | 现 | 预计 | 说明 |
|---|---:|---:|---|
| `full` | 101 | 94–97（中心约 96） | 减 7–9 条 full→partial，减 1–2 条 full→none，加 4 条 partial→full |
| `partial` | 18 | 22–24（中心约 23） | 减 4 条到 full，减 1 条到 none，加 7–9 条 full→partial，加 2 条 none→partial |
| `none` | 304 | 304–305 | 加 1 条 partial→none，加 1–2 条 full→none，减 2 条 none→partial |

区间端点不对应同一组边界判定。中心估计 96 + 23 + 304 = 423。

`none → partial` 的 2 条来自 v2 已经识别、v1 漏掉的附带评价：`c-1r44c1m`（“I have a mom cozy belly band but I feel like I need something more”）与 `c-1r7qvfd`（“Nothing helps! I've tried stretching, belly band...”）。A2 的规则与 v2 在这两条上一致。

这张表只用于估计规模，不作为最终数字。实现后必须用 A2 函数全量重跑 423 条，再更新 `claims.json`、`report.html`、`validation-result.json`。

### 4.3 对下游 claim 的影响

**C04（自然样本摩擦）**：

- pooled 摩擦记录仍是 3 条。
- full 层：1 条，`c-1opsx7o`（SUP.GENERAL negative）。
- partial 层：2 条，`c-1sn9hb1`（SUP.BACK negative）、`c-1q2ir63`（SUP.GENERAL negative）。
- 层计数 full 1 / partial 2 不变，但 full 层记录的身份从“临产长文里的一句‘带子不帮忙’”换成“三产品逐项对比里的 Frida 支撑衰减”。这是证据质量的提升，不是数字的提升。
- natural 本人体验总数会小幅变化（约 -1 至 +1），需重跑确认。

**C05（共现）——必须加同产品守卫，A2 本身不得直接升档**：

- 新规则下，full 层舒适正向 3 条：`c-19rm4lmi0oa78`、`c-1opsx7o`、`c-1rqq680`。
- 如果 C05 继续按记录级计数，`c-1opsx7o` 会让 full 层共现变成 1/3，C05 会从 Evidence gap 变成 Confirmed。
- 但 v1 冻结编码里的这条“共现”是**跨产品**的：
  - 舒适正向 span：“soft, breathable, and feels nice against the skin” → 位于 Momcozy 段（正文偏移 850 起）。
  - 支撑负向 span：“The support doesn't last if you wear it too long” → 位于 Frida Mom 段（正文偏移 456 起）。
  - 两者不是同一款产品。记录级计数把它们拼成一条共现，是归属错误。
- 因此，A2 落地的同时必须加 C05 的同产品守卫：共现的两条 span 必须落在同一个产品段。加守卫后，v1 的 `c-1opsx7o` 不计入共现，C05 仍是 **Evidence gap**。
- 在 v2 编码下，Frida 段同时有 “The fabric is really soft”（COM.SOFTNESS positive）和 “After standing or walking for a bit, my lower back starts to ache again”（SUP.BACK negative），同产品守卫可以通过，C05 才可能变成 Confirmed。这是 v2 的独立证据，不是 A2 放宽标准的结果。若走这条路，headline 必须写 n=1、单一作者，不能写成总体共现率。
- 结论：**A2 不授权 C05 升档。** 先加同产品守卫，再按 v1/v2 分别复核。当前 v1 报告保持 Evidence gap。

**C13 / C03**：不受影响。C13 的 32 条全部来自 TikTok verified-purchase，`partial` 恒为 0；C03 的 exact-model 本人体验仍是 0。

### 4.4 与硬约束的对账

| 约束 | 对账 |
|---|---|
| 不许改 gold set | 未改。18 条里 3 条 gold 记录全部保持 `is_product_experience=true`，0 冲突。 |
| 不许为让 C05 升档而放宽标准 | A2 是对称规则：4 条 partial→full，同时 7–9 条 full→partial、1–2 条 full→none。C05 在 v1 下因同产品守卫仍是 Evidence gap。 |
| 不许把 partial 改成“几乎全是 full” | 18 条中 13 条保持 partial，只有 4 条升 full。全语料 partial 预计 22–24 条，约占 423 条的 5%。 |
| 每题都要能指到具体原文片段 | §4.1 与 §4.2 的每一行都给了可检索的原文片段。 |

## 5 `partial` 还剩什么用例，是否取消

**判断：保留 `partial`，但按 A2 重定义。不取消，不简化成 full/none 二档。**

理由：

1. **它不是空档。** 18 条旧 partial 里 13 条仍判 partial；加上 full 层与 none 层的重分类，全语料预计仍有 22–24 条 partial，约占 5%。这不是“为了保住档位硬造用例”。
2. **剩余用例有明确区别。** 典型三条：
   - `c-1sn9hb1`：1771 字临产焦虑长文，带子评价只有 “now using a belly band doesn't help” 一句。
   - `c-1q2ir63`：446 字求推荐帖，带子评价只有 “I have the fitsplint... it is no longer helping” 一句。
   - `c-1s8bn5y`：649 字症状帖，带子评价只有 “jury is still out on if it's helping”。
   这三条都有真实的一手产品信号，但都不能支撑“full 层分布”的结论。把它们并入 full 会高估证据基础；把她们降为 none 会丢掉真实信号。
3. **取消的代价更高。** 如果取消 partial，只有两种做法：
   - 并入 full：20 多条一句话评价进入 full 分布，C04/C05 的分母被稀释，等于放宽标准。
   - 降为 none：丢掉 20 多条真实的一手信号，尤其是负面和质量问题信号。
   两种做法都比保留一个“附带/未定”档位更差。
4. **取消的触发条件**（留给未来复核）：如果全量重跑后 partial <5 条，或 partial 与 full 在 aspect 分布、极性分布上不可区分，则取消 partial，改用一个正交布尔 `evaluation_incidental`，distribution 只取 `evaluation_incidental=false`。当前数据不支持这个结论。

**`partial` 的新语义标签**：文档和报告里把 partial 写成“附带评价”或“未定评价”，不要写“求助语境”。枚举值 `partial` 保持不变，避免破坏契约；如需更清楚，可在展示层加别名 `incidental`。

## 6 实施清单

本裁决只定义规则，不改代码。落地时需要以下改动。

| 文件 | 改动 |
|---|---|
| `voc/coder.py` | 新增评价句提取与 `N/C/S/A/P` 计算；`code_record()` 用 §2.2 决策表替代 `help_seeking → partial`；保留 `help_seeking()` 只作 `request_context` 与 past-unnamed 排除；更新 `CodedRecord.experience_scope` 的注释（706–714 行）与 986–993 行的赋值逻辑。 |
| `voc/llm_coder.py` | 不再直接信任 v2 行里的 `experience_scope`（344–372 行）。v2 的该字段编码的是旧规则；要么用 A2 函数重算，要么用新 rubric 重跑 v2。 |
| `voc/claims.py` | C05 增加同产品守卫（见 §4.3）；把 C05 counterevidence 里的“评价可能被求助语境污染”改为“评价是附带的或未定的”；C04 分层措辞按新语义更新。 |
| `voc/report.py` | `_sample_rows` 的 scope 过滤语义不变；报告里的层标签与解释改为“附带/未定”，不再写“求助语境”。 |
| `tests/test_pipeline.py` | 更新 4 处旧断言：`test_purchase_help_post_with_evaluation_is_partial_in_cooccurrence`（约 330–350 行，问句标题 + 充分评价应改判 full）、`test_help_seeking_with_current_evaluation_is_partial`（约 360–370 行，`c-1vztlvl` 类记录仍 partial，保留）、`test_llm_coder_marks_help_seeking_evaluation_partial`（约 1529 行，视评价句数与占比改判）、以及任何把“求助”直接等同 partial 的注释。 |
| `artifacts/.../decisions/A-experience-gate.md` | 在 §3.2 加一行“已被 A2 取代”，保留历史裁决原文，不改写。 |
| 重跑 | v1 与 v2 编码、`claims.json`、`report.html`、`validation-result.json`、`tests/test_pipeline.py`。记录新的 artifact sha256。 |

## 7 局限与待复核

1. **阈值是预审校准。** `0.15 / 0.35 / 0.25` 是在 18 条 partial + 20 条 Reddit full 上做的预审，不是全语料的最终校准。实现后要在 423 条上重跑，检查是否有系统性偏移。
2. **评价句提取仍有假阴性。** `c-1upreg8` 在 v1 里 0 个 aspect，但正文是详细体验。规则不能只依赖 v1 的 aspect 数，必须用句子级评价句。`c-1upreg8` 靠 `N≥3` 和 `S≈60%` 判 full。
3. **边界条目需人工复核。** `c-1ofb8c1`（联合归因判 none）、`c-19rjykcrivso1`（多 remedy 清单判 partial）、`c-1o9a0w1`（“trusty”算不算评价）是三个边界。规则已写明判定方向，但应在实现后人工抽检。
4. **TikTok 的硬编码不变。** `coder.py:760–762` 对 `tiktok_shop` 直接返回 `help_seeking=False`。A2 下这仍然正确，因为 verified-purchase 评论的评价是记录主体；但 81 条 TikTok full 记录里若有“一句话顺带评价”，仍需按 §2.2 复核，不能因为它们不是求助帖就默认 full。
5. **多产品记录的指标层问题未在本裁决内解决。** A2 只解决 scope；C05 的同产品守卫是配套改动，必须单独实现、单独验证。所有记录级 aspect 聚合（不只 C05）都应对多产品记录做产品段归属，否则会出现同类跨产品拼接。
