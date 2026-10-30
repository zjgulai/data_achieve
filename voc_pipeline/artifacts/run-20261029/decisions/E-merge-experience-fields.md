# E：合并体验字段（`product_match` + `experience_scope`）

- 日期：2026-10-30
- 状态：已实现（v1/v2 已重建；report 32/32、spec 13/13、单测 124/124）。
- 实现记录：`voc/canonical.py`、`voc/coder.py`、`voc/llm_coder.py`、
  `voc/claims.py`、`voc/metrics.py`、`voc/build.py`、`voc/validate_report.py`；
  一次性修正账本 `product_match_overrides.json`；审计产物
  `scope-audit.json`、`compat-experience-diff.json`。
- 取代：`A-experience-gate.md` §3.1（`is_product_experience` 的归属规则）；`A2-partial-redefinition.md` §2.2 的 R0 前置条件。
- 不改：gold set；A2 的 `partial` 定义；C05 的立场；C13 的 TikTok 口径。
- 基线：`artifacts/run-20261029`（v1）。对照：`artifacts/run-20261029-v2`。

## 0 数字口径

本节只对账，不重新论证 A/A2 的结论。所有契约数字都从当前产物重算。

| 口径 | 冲突总数 | on-topic | off-target | 来源 |
|---|---:|---:|---:|---|
| 修正前快照 | 47 | 22 | 25 | `/tmp/voc-fix/run-before/scope-conflicts.json`（coder `llm-v1`） |
| 当前 v1 | 35 | 6 | 29 | `artifacts/run-20261029/scope-conflicts.json` |
| 当前 v2 | 34 | 5 | 29 | `artifacts/run-20261029-v2/scope-conflicts.json` |

四点说明：

1. 47/22/25 是 A2 修复前的临时快照。它的 22 条 on-topic 与 54 条盲判校准集的 C 组逐条相同（已核对 canonical_id 集合，交集 22/22）。因此“22 条 on-topic、17 条假冲突、5 条站得住”是可复现的。
2. 当前产物是 35/34，不是 47/46。简报里的 46 无法从任何现存产物复现。最近的两个口径是 47（修复前）与 35/34（当前）。本文全部用 35/34 计算。
3. 54 条盲判重算：三档一致 43/54；两两 46/46/48（85.2% / 85.2% / 88.9%）；应用 5 条修复后，规则与多数 exact 一致 44/54。简报里的 52/54 无法从 `/tmp/voc-scope-blind` 复现，本文不引用。
4. 简报的 Reddit `experience=true` 是 33（full 8 / partial 25）。当前产物是 v1 32（full 7 / partial 25）、v2 33（full 7 / partial 26）。本文用产物值。差异来自 coder 版本，不影响契约结论。
5. 合并实现后，`scope-conflicts.json` 退役，改名为 `scope-audit.json`（schema v2）。"conflict" 指标不再维护；上表只作历史对账。

## 1 为什么现在的双字段是错的

### 1.1 两个字段现在各回答什么问题

| 字段 | 现在的用途 | 实际回答的问题 | 结构问题 |
|---|---|---|---|
| `is_product_experience` | 冻结标签；控制 aspect 是否产出；同时被当作“体验记录”的筛选条件 | “这条算不算体验？”和“能不能出 aspect？” | 一个布尔值同时承担“有没有评价”和“是不是我们的产品”两件事 |
| `experience_scope` | 独立评估评价的实质程度 | “评价有多实质？” | 它已经独立评估，却不被允许单独决定 aspect |

`is_product_experience=false` 时，A/A2 要求 `aspects` 为空、`scope=none`。但 A2 之后，scope 是独立评估的。于是冻结布尔和 scope 会给出不同答案。当前 35（v1）/ 34（v2）条冲突就是这两套答案的差集。

### 1.2 三类具体矛盾

| 记录 | 冻结布尔 | scope | product_match | 三个字段各自说什么 |
|---|---|---|---|---|
| `c-phyrbxj` | false | partial | category_adjacent | 布尔说“没有体验”；scope 说“有附带的第一手评价”；product_match 说“在品类内”。aspects 被布尔压掉 |
| `c-ph09yrn` | false | full | exact_current_family（错） | 布尔说“没有”；scope 说“full”；product_match 说“目标家族”。原文是 Momcozy 尿布桶；“husband”里的 `band` 被当成产品词 |
| `c-19rg8fid9ublx` | false | partial | exact_current_family（错） | 布尔说“没有”；scope 说“partial”；product_match 说“目标家族”。原文是 Momcozy 哺乳内衣，`band extender` 是内衣带 |
| `c-pgsk2oe` | true | full | brand_other_product | 布尔说“有体验”；product_match 说“别的产品”；规则 coder 说 `product_mismatch`、scope none |
| `c-1r7qvfd` | false | none | category_adjacent | 布尔和 scope 都说“没有”；三判官 2/3 说 partial。这是已知 miss，不是冲突 |

`c-pgsk2oe` 是反向矛盾：冻结布尔把它算进体验，但产品门禁把它算出去。规则 coder 的 `product_mismatch` 分支已经把 scope 设为 none。两个 coder 在同一记录上给出相反结论。

### 1.3 17 条假冲突说明“布尔碰巧对了，但系统说不出为什么”

54 条盲判的 C 组就是修复前的 22 条 on-topic 冲突。三判官多数对其中 17 条判 `none`：

| 记录 | 多数 | 判官理由（摘录） |
|---|---|---|
| X14 `c-1oxvlu4` | none | 只陈述过去使用事实，未评价产品；正文是求训练建议 |
| X18 `c-1u6texf` | none | 腹带内容是对医生说法的转述，不是第一手评价 |
| X21 `c-1u7ofya` | none | 只讨论二手吸奶器归属与新旧顾虑，没有对产品性能的评价 |

旧 scope 规则过宽，把这 17 条判成 partial/full。冻结布尔判 false 是对的，但布尔不携带理由，也不携带“评价有多实质”。所以系统只能事后靠盲判发现错误，不能事前解释。

### 1.4 根因

一个概念被两个字段分别表达，并承担三个职责：

1. 有没有第一手评价；
2. 评价有多实质；
3. 这条记录属不属于我们的产品。

职责 1 和 3 被塞进 `is_product_experience`，职责 2 放进 `experience_scope`。当两个字段由不同过程生成（冻结标签 vs 正文评估），它们必然漂移。修法不是加对账规则，而是拆职责。

## 2 新模型

### 2.1 保留、删除、职责

| 字段 | 层级 | 取值 | 唯一职责（一句话） | 处置 |
|---|---|---|---|---|
| `product_match` | canonical record | `exact_current_family` / `category_adjacent` / `brand_other_product` / `irrelevant` | 这条记录评价的产品是不是本研究的产品族（支撑带/托腹带） | 保留；收紧定义 |
| `experience_scope` | coded record | `full` / `partial` / `none` | 记录里有没有可归属的第一手评价，以及这条评价的证据权重 | 保留 |
| `experience_source` | coded record | `first_person` / `relayed` | 第一手评价来自作者本人，还是经手人转述 | 保留 |
| `experience_reason` | coded record | 枚举或短文本 | 产生该 scope 的可审计原因 | 保留；只作诊断，不作门禁 |
| `is_product_experience` | 输入标签 | `true` / `false` | 无 | 删除 |
| `experience` | 发布字段 | `true` / `false` | 无 | 删除；改为派生视图 |
| `scope_conflict` | 发布字段 | `true` / `false` | 无 | 删除；新模型下不可能出现 |

`product_match` 的定义必须收紧。当前实现用子串匹配：`"band" in text` 会命中 `husband`、`band extender`。它只按“品牌 + `band` 子串”判断，不区分产品线：Momcozy 的尿布桶、哺乳内衣、吸奶器、孕妇枕都被标成 `exact_current_family`。新定义如下：

| 值 | 定义 |
|---|---|
| `exact_current_family` | 被评价的产品是本研究的产品族（belly band / support belt / maternity band），且记录提到本研究品牌/型号；或它是该产品 SKU 的 verified-purchase 评论 |
| `category_adjacent` | 被评价的产品是同品类（支撑带/托腹带），但不是本研究品牌；或记录只泛泛讨论品类 |
| `brand_other_product` | 提到本研究品牌，但被评价的是另一条产品线（尿布桶、哺乳内衣、吸奶器、孕妇枕等） |
| `irrelevant` | 既不涉及本研究产品族，也不涉及本研究品牌 |

当前产物没有 `other` / `unknown`。`brand_category` 只出现在旧的 consumer contract 和 metric 过滤条件里，当前 canonicaliser 不产出它。旧产物出现 `brand_category` 时，按 `exact_current_family` 处理并写日志；出现未知值时 fail closed，不得当作 on-topic。

### 2.2 派生谓词

```
on_topic(r)       = r.product_match in {"exact_current_family", "category_adjacent"}
has_evaluation(r) = r.experience_scope in {"full", "partial"}
in_cohort(r)      = on_topic(r) and has_evaluation(r)
emit_aspects(r)   = in_cohort(r) and bool((r.text or "").strip())
```

`emit_aspects` 和 `in_cohort` 使用同一个表达式。这是本契约的核心：不存在第二个布尔门禁。

### 2.3 取值组合矩阵

行是 `product_match`，列是 `experience_scope`。所有 12 个字段取值组合在语义上都允许。“冲突”这个概念消失。禁止的是字段与 `aspects` 的组合：

| | `full` | `partial` | `none` |
|---|---|---|---|
| `exact_current_family` | 允许；产出 aspects | 允许；产出 aspects | 允许；不产出 aspects |
| `category_adjacent` | 允许；产出 aspects | 允许；产出 aspects | 允许；不产出 aspects |
| `brand_other_product` | 允许；不产出 aspects（off-target experience） | 允许；不产出 aspects | 允许；不产出 aspects |
| `irrelevant` | 允许；不产出 aspects（off-target experience） | 允许；不产出 aspects | 允许；不产出 aspects |

禁止的组合：

1. `experience_scope=none` 且 `aspects` 非空。
2. `experience_scope=none` 且 `experience_source=relayed`（没有评价可转述）。
3. 任一字段取枚举外的值。
4. `product_match` 缺失。
5. `brand_other_product` 或 `irrelevant` 且 `aspects` 非空。
6. `exact_current_family` 或 `category_adjacent` 且 `scope=none` 且 `aspects` 非空。

`brand_other_product × full` 和 `irrelevant × full` 是“off-target experience”。它们可以存在，必须进入审计账本，永远不进入任何产品 claim。

### 2.4 aspect 产出的确切条件

```
emit_aspects(record, coded) =
    record.product_match in {"exact_current_family", "category_adjacent"}
    and coded.experience_scope in {"full", "partial"}
    and bool((record.text or "").strip())
```

没有其他条件。没有 per-claim 例外。没有“某条 claim 需要它，所以放宽”的开关。

### 2.5 布尔值的两个职责分别由谁接

| 旧问题 | 旧答案 | 新答案 |
|---|---|---|
| 有没有可归属的第一手评价？ | `is_product_experience` | `experience_scope != "none"` |
| 能不能产出 aspect？ | `is_product_experience` | `on_topic AND experience_scope in {full, partial}` |
| 在不在体验群体里？ | `experience` | 同上 |
| 是不是 off-target 评价？ | 无法表达 | `experience_scope != "none" AND NOT on_topic` |

### 2.6 scope 定义不变

`full` / `partial` 的判定继续用 A2 §2。A2 的 R0（`is_product_experience=false` → none）删除，因为该字段不存在。R1–R7 保留。

本契约只收紧一条 scope 假阳性：`c-1uuim67`。它的证据句是“my pelvic and groin pain has not gone away”，这是症状，不是产品评价。规则 coder 把上一句的 `belly band` 当作锚点，判了 partial。新契约要求评价句本身含产品词或指代。该记录在准入前改为 `none`。这是收紧，不是放宽。详见 §5.2。

## 3 向后兼容

### 3.1 读旧的 LLM 编码输入

旧输入是 `llm-coding-v2/coded/ALL.jsonl` 这类行，含 `is_product_experience`、`experience_scope`、`aspects`。新代码按以下顺序读：

1. 校验 `experience_scope`。缺失或非法时，用 `assess_experience_scope(record)` 从正文重算。永远不从 `is_product_experience` 推 scope。
2. 从 canonical record 读 `product_match`，应用 §5.2 的 6 条修正。记录来源 `auto` 或 `override`。
3. 用 §2.4 计算 `in_cohort` 和 `emit_aspects`。
4. `is_product_experience` 只作审计信号，不作门禁：
   - `true` + 新 scope `none` → downgrade。压掉 aspects。写 `downgrades`。
   - `false` + 新 scope 非 none + on-topic → 准入候选。先过人工证据核对或重编码，再产出 aspects。写 `admit_candidates`。
   - `false` + 新 scope 非 none + off-target → off-target 评价。不产出 aspects。写 `off_target_evaluations`。
   - `false` + 新 scope `none` → 无变化。
5. 禁止映射 `true→full`、`true→partial`、`false→none`、`false→partial`。旧布尔不携带证据权重。

**实现澄清（2026-10-30）**：第 1 步的 `experience_scope` 校验只作审计对照。
实际 scope 始终由 `assess_experience_scope(record)` 从正文重算。原因是 v2
artifact 的 declared scope 来自 A2 之前的旧规则（A2 §6.4）；如果直接采信，
会用旧规则覆盖 A2 的收紧结果，并改变已经复核过的 118/119。声明值与重算值
不一致时写入 `scope-audit.json` 的 `declared_scope_mismatches`，不静默采用。
TikTok 的 `full` 层仍按 A2 §2.4 的 verified-purchase 集合处理：冻结 true
的审核记录保持 full；冻结 false 且正文无可归属评价的记录保持 none。

### 3.2 读旧的发布产物

旧 `coded-corpus.jsonl` 有 `experience` 布尔和 `scope_conflict`。

- `experience` 标记为 deprecated。新读者不得用它做门禁；按 §2.4 重算。
- 过渡期允许 writer 继续输出 `experience`，值等于 `in_cohort`，并在 schema 元数据写 `"deprecated": true`。消费者迁移后删除。
- 旧 `experience` 与派生 `in_cohort` 不一致时，写 `compat-experience-diff.json`，逐条记录两个值和原因。不得静默覆盖。
- `scope_conflict` 在新输出中恒为 false 或缺失。读者必须忽略。schema 版本加一。

### 3.3 gold set

- 不修改 `gold-set-50.jsonl`。它的 `is_product_experience` 是历史标签。
- 评估脚本可以继续读它，但输出必须标 `legacy gate`。不得把旧 κ 当作新契约的一致性证据。
- 每次构建前后对 gold 文件做 sha256，断言不变。

### 3.4 schema 和消费者

- `coded-corpus` 增加 `contract_version: "E-merge/1"`、`product_match_source`、`product_match_override_reason`。过渡期后可删除 `experience` 和 `scope_conflict`。
- `scope-conflicts.json` 改为 `scope-audit.json` v2，字段为：
  - `off_target_evaluations`：scope 非 none 且 off-target。
  - `downgrades`：旧 true 且新 none。
  - `admit_candidates`：旧 false 且新非 none 且 on-topic。
  - `scope_false_positives`：人工核对拒绝的记录。
  - 删除 `conflicts`、`frozen_false_records`、`conflict_on_topic`、`conflict_off_target`。
- consumer metric contract 的 `product_match in {exact_current_family, brand_category, category_adjacent}` 改为 §2.2 的 on-topic 集合。metric view 增加 `in_experience_cohort`。任何消费者不得只按 `experience_scope` 过滤。

## 4 受影响的代码清单

grep 全仓 `is_product_experience` 得到 20 个代码/文档文件和 45 个数据文件。把派生布尔 `experience` 和前置的 `product_match` 修正计入，受影响代码/文档共 26 个文件：15 个必须改，11 个冻结或只读。

### 4.1 字面量 `is_product_experience`（20 个文件）

| 文件 | 行 | 改动类型 |
|---|---|---|
| `voc/llm_coder.py` | 270, 438, 444, 497, 520 | 改门禁 / 删字段 / 改审计 |
| `tools/merge_v2_coded.py` | 45, 60, 178, 208 | 删字段 / 改校验 |
| `tools/merge_v2_by_batch.py` | 57, 194 | 删字段 / 改校验 |
| `tests/test_pipeline.py` | 1538, 1649, 1680, 1717, 1759, 1782, 1810, 1849, 1952 | 测试 |
| `artifacts/run-20261029/llm-coding/CODING-CONTRACT.md` | 29, 40, 63, 64, 75, 81, 107, 109, 112, 132, 137, 146, 161, 294, 309, 317 | 删字段 / 改契约 |
| `artifacts/run-20261029/llm-coding/validate-coding.py` | 9, 14, 54, 81, 93, 108（2 处）, 109, 302, 303, 304, 306, 313, 322, 431, 443, 444, 500, 506 | 删字段 / 改校验 |
| `artifacts/run-20261029/llm-coding/merge_and_validate.py` | 37, 159, 178, 287 | 删字段 / 改校验 |
| `artifacts/run-20261029/llm-coding/eval_gold.py` | 168, 214 | 只读 gold / 改输出标签 |
| `artifacts/run-20261029/llm-coding/coded/build_batch02.py` | 16, 162, 194 | 冻结 |
| `artifacts/run-20261029/llm-coding-v2/counterexamples/run_encoder.py` | 77 | 改文档 |
| `artifacts/run-20261029/llm-coding-v2/counterexamples/compare_counterexamples.py` | 64 | 改门禁或冻结 |
| `artifacts/run-20261029/calibration/build-calibration.py` | 80 | 只读兼容 |
| `artifacts/run-20261029/calibration/compute-kappa.py` | 290, 293, 398 | 只读兼容 |
| `artifacts/run-20261029/calibration/selftest/verify-hand-calc.py` | 218, 222, 223 | 只读兼容 |
| `artifacts/run-20261029/calibration/selftest/make-fake-labels.py` | 79 | 只读兼容 |
| `artifacts/run-20261029/calibration/cross-model/compute-cross-model.py` | 38, 94, 96, 213, 575, 720 | 只读兼容 |
| `artifacts/run-20261029/calibration/cross-model/cross-model-report.md` | 116 | 历史文档 |
| `artifacts/run-20261029/decisions/A-experience-gate.md` | 5, 22, 54, 83, 192, 219, 234 | 历史文档 |
| `artifacts/run-20261029/decisions/A2-partial-redefinition.md` | 6, 69, 87, 167, 231 | 历史文档 |
| `artifacts/run-20261029/decisions/D-report-wording.md` | 37, 244, 245 | 历史文档 |

### 4.2 派生布尔 `experience`（6 个文件）

这些文件不含字面量，但持有真正的门禁。

| 文件 | 行 | 改动 |
|---|---|---|
| `voc/coder.py` | 708, 713-714, 730-735, 748, 2012-2014, 2026-2027, 2032, 2072-2075, 2089 | 删 `experience` 字段、`scope_conflict` 属性、序列化键；把 `if out.experience` 改为 §2.4 谓词 |
| `voc/claims.py` | 256, 257, 260-265, 291-293, 617, 632-633, 641, 780 | `c.experience` 改为 cohort；改写 experience_dropped 和 basis 文案 |
| `voc/metrics.py` | 152-154 | `if not rec.experience` 改为 cohort |
| `voc/build.py` | 233 | `c.experience` 改为 cohort |
| `voc/report.py` | 1534 | 只读核对；scope 过滤保留。label 表可清理 `brand_category` |
| `tests/test_pipeline.py` | 380, 1667, 1702, 1742, 1770, 1796 | 测试断言改为 cohort |

### 4.3 前置修正：`product_match`（同一变更集）

| 文件 | 行 | 改动 |
|---|---|---|
| `voc/canonical.py` | 251, 263, 291, 295-307 | 子串匹配改为词边界；`exact_current_family` 增加产品族短语；排除同品牌其他产品线 |
| `voc/metrics.py` | 38, 259, 270 | on-topic 集合与 §2.2 对齐；删除 `brand_category` |
| `voc/llm_coder.py` | 78 | `_ON_TOPIC_PRODUCT_MATCH` 与 §2.2 对齐 |
| `voc/build.py` | 462 | consumer contract 文本对齐 |
| `voc/report.py` | 1465 | `brand_category` 仅保留为历史别名 |
| `tests/test_pipeline.py` | 新增 | 增加 `husband`、`band extender`、diaper pail、nursing bra、pregnancy pillow、非 Momcozy 支撑带的用例 |
| `product_match_overrides.json`（新文件） | 新 | 6 条一次性修正账本，见 §5.2 |

### 4.4 汇总

| 类别 | 数量 |
|---|---:|
| 含字面量的代码/文档 | 20 |
| 受影响代码/文档总数 | 26 |
| 必须改 | 15 |
| 冻结或只读 | 11 |
| 含字面量的数据文件 | 45 |
| 其中冻结或历史输入 | `gold-set-50.jsonl`、`fake-human-labels.json`、`sample-manifest.json`、`cross-model-stats.json`、`duplicate-conflicts.json`（只作审计） |
| 其余数据文件 | 重新生成，不手改 |

核心管线改动 5 个文件：`coder.py`、`llm_coder.py`、`claims.py`、`metrics.py`、`build.py`。

## 5 预期数字变化

### 5.1 口径和瀑布

基线是 v1（`artifacts/run-20261029`）。v2 作对照。「起点」是合并前的
`experience=true` 群体；「终点」是 §2.4 谓词算出的 `in_cohort`。

| 步骤 | v1 | v2 | 记录 |
|---|---:|---:|---|
| 起点 `experience=true` | 117（full 89 / partial 28） | 119（full 90 / partial 29） | 合并前产物 |
| 加：真正 on-topic 的准入记录 | +2 | +1 | `c-1r44c1m`、`c-phyrbxj`（v2 已有 `c-1r44c1m`） |
| 减：off-target 的 experience 记录 | -1 | -1 | `c-pgsk2oe` |
| 终点 cohort | **118（full 88 / partial 30）** | **119（full 89 / partial 30）** | §2.4 谓词 |

natural frame：

| 基线 | 起点 | 终点 | full | partial |
|---|---:|---:|---:|---:|
| v1 | 35 | **37** | 7 | 30 |
| v2 | 36 | **37** | 7 | 30 |

v1 和 v2 在 natural frame 上收敛到 37。差别只在全局：v1 的 `c-1r44c1m`
仍是 false，v2 已是 true。

**与 115/116 的差额**：契约初稿的 115/116 写于 A2 scope 收紧完成之前。
收紧后恢复了 3 条被过度收紧的第一手评价（`c-1oyj0g6`、`c-1sw9iyo`、
`c-1w3knom`，均为 partial），因此终点是 118/119，不是 115/116。full 层
不变（88/89），差额全部在 partial 层。这 3 条不是本次合并新增的证据，
是 A2 回归检查的恢复；逐条依据见「规则收紧结果」一节。

**终点与实现的一致性**：实现后逐条重算，v1 = 118（88/30）、v2 = 119
（89/30），与上表一致。重算脚本见附录 A；预检命令里的 `scope_corr`
（`c-1uuim67` → none）在实现中由 scope 规则直接产出，不再需要手工覆盖。

### 5.2 逐条裁决

准入候选是 v1 的 6 条 on-topic 冲突，加上 1 条要移除的 off-target experience。

| # | 记录 | frame | product_match 前→后 | scope | 证据句（逐字） | 裁决 | 理由 |
|---|---|---|---|---|---|---|---|
| 1 | `c-1r44c1m` | natural | `category_adjacent`→同 | partial | “I have a mom cozy belly band but I feel like I need something more” | 准入 | 第一手使用后的不足评价 |
| 2 | `c-phyrbxj` | natural + diagnostic | `category_adjacent`→同 | partial | “I have belly band, compression garment, take multiple baths a day, and I still hurt so bad some days” | 准入 | 第一手无效评价，附带 |
| 3 | `c-1uuim67` | natural | `category_adjacent`→同 | partial→**none** | “Since then, my pelvic and groin pain has not gone away” | 拒绝 | 证据句是症状，不是产品评价；锚点来自上一句 |
| 4 | `c-19rg8fid9ublx` | qualitative_seed | `exact_current_family`→`brand_other_product` | partial | “found the Momcozy nursing/pumping bra with the mesh inset is the most comfortable” | 拒绝 | Momcozy 哺乳内衣，不是支撑带 |
| 5 | `c-19rnylotzfmkh` | qualitative_seed | `exact_current_family`→`brand_other_product` | partial | “I love the Momcozy three pack personally” | 拒绝 | 礼物清单里的 Momcozy 其他产品 |
| 6 | `c-ph09yrn` | qualitative_seed | `exact_current_family`→`brand_other_product` | full | “I LOVE my momcozy diaper pail” | 拒绝 | Momcozy 尿布桶，不是支撑带 |
| 7 | `c-pgsk2oe` | qualitative_seed | `brand_other_product`→同 | full | “I bought two (momcozy and some amazon one) and felt zero support” | 移除 | 当前 product_match 把它判成 off-target；规则 coder 也判 `product_mismatch` |

第 3 条是 scope 假阳性。第 4–6 条是 product_match 假阳性。第 7 条是 product_match 假阴性。

关于第 7 条：三判官对 X36 / `c-pgsk2oe` 都判 full。它确实是对 Momcozy 和 Amazon 支撑带的第一手对比。但当前 `product_match` 因为没有出现 `belly band` 字样而判 `brand_other_product`。本契约不绕过 gate 保留它，理由是：一旦对单条记录开 product_match 例外，gate 就不再是唯一产品门禁。正确做法是单独修分类器，并承担 C03/C11 的计数变化。它进入 `product_match_debt` 清单，下一轮处理。

关于 `c-1uuim67`：如果团队不接受这条 scope 收紧，v1 cohort 变为 119、v2 变为 120。本契约不接受这个口径，因为它的证据句不含产品词或指代，按 A2 定义不构成评价。

### 5.3 17 条假冲突的处理：靠收紧 scope 规则消掉

结论：**17 条假冲突已经由 A2 的 scope 规则收紧消掉，不靠 product_match 门禁。**

理由：

1. 22 条 on-topic 全部是 `category_adjacent`（17）或 `exact_current_family`（5）。product_match 门禁不会挡住它们。如果 scope 仍判 partial/full，它们会进入 cohort。
2. 17 条的问题在 scope 规则过宽，不在产品归属。用 product_match 挡是错的工具。
3. 当前 v2 产物（修正前）的 on-topic 冲突只剩 5 条。17 条已不在冲突集里。

5 条“站得住”的记录分别怎么处理：

| 记录 | 盲判多数 | 新模型处理 |
|---|---|---|
| `c-1r44c1m` | partial | 准入 |
| `c-phyrbxj` | partial | 准入 |
| `c-ph09yrn` | full | product_match 修正后拒绝（尿布桶） |
| `c-19rnylotzfmkh` | partial | product_match 修正后拒绝（礼物清单） |
| `c-1r7qvfd` | partial | 仍是已知 miss；scope 保持 none；单独修 scope 规则，不并入本合并 |

`c-1r7qvfd` 不并入的理由：它是 A2 锚点规则的漏判（“Nothing helps! I've tried stretching, belly band...”），不是字段合并问题。把它塞进本变更会让“合并”和“修规则”混在一起，无法解释 n_records 变化。

### 5.3b A2 回归恢复的 3 条记录

A2 收紧后，`c-1oyj0g6`、`c-1sw9iyo`、`c-1w3knom` 一度被判 none。逐条复核
发现是过度收紧：证据句都是第一手评价，不是症状或转述。三条恢复为
`partial`，这是 118/119 与契约初稿 115/116 的全部差额。

| 记录 | 证据句 | 恢复依据 |
|---|---|---|
| `c-1oyj0g6` | “No amount of rest, belly band support, stretching … seems to be helping” | T2 明确保留 `no amount of … help` 的功效总结 |
| `c-1sw9iyo` | “A belly band seems to make things worse” | 单数产品 + 谓语，T1 的泛化建议守卫不应吃掉第一手结果 |
| `c-1w3knom` | “belly band ... are helping” | 括号插入语不是产品评价，不应把极性拉成 mixed |

这三条在合并前已是 `experience=true`，合并没有新增它们的证据权重；它们
只是把 partial 分母从 27 恢复到 30。C11 的 `journey_or_outcome_records`
相应为 v1 33、v2 34（契约初稿写 31/31，差额即这 3 条已有的 JNY.USE /
OUT.NO.BENEFIT 标注，不是新增编码）。

### 5.4 off-target 冲突

当前 v1 有 29 条 off-target 冲突，v2 也是 29 条。把 §5.2 的 3 条 exact 假阳性（`c-19rg8fid9ublx`、`c-19rnylotzfmkh`、`c-ph09yrn`）改判后，off-target 变为 32 条。

它们保留 `scope=full/partial`，因为原文确实评价了某个产品。它们不产出 aspects，因为 `product_match` 是 off-target。它们不进入任何产品 claim：

- C04/C05 先按 natural frame 过滤，再按 cohort 过滤。
- C13 只取 TikTok verified-purchase，全部 `exact_current_family`。
- C11 的 relevant set 只含 on-topic。

这是“scope 描述评价实质，product_match 描述产品归属”的直接结果。off-target 评价不是错误，是另一类证据。

### 5.5 claim 影响

下表是**实现后逐条重算**的值，不是初稿估算。合并前后 `counts.n_records`
逐条对账，见下表最后两列。

| claim | 数字 | v1 前→后 | v2 前→后 | 原因 |
|---|---|---:|---:|---|
| C04 | `counts.n_records` | 3→3 | 3→3 | 没有新增摩擦记录 |
| C04 | `experience_natural_records` | 35→37 | 36→37 | +2 / +1，均为 partial；来自 `c-1r44c1m`、`c-phyrbxj` |
| C04 | `experience_full_records` | 7→7 | 7→7 | `c-pgsk2oe` 不在 natural |
| C04 | `experience_partial_records` | 28→30 | 29→30 | +2 / +1 |
| C04 | `experience_dropped` | 114→112 | 113→112 | 149 − cohort |
| C05 | `counts.n_records` | 0→0 | 1→1 | 没有新增舒适正向+摩擦共现 |
| C05 | `comfort_positive_records` | 3→3 | 3→3 | 新增记录没有舒适正向标注 |
| C05 | `with_friction` | 0→0 | 1→1 | 同上 |
| C05 | `experience_partial_records` | 28→30 | 29→30 | cohort 变化 |
| C13 | `counts.n_records` | 32→32 | 31→31 | 只取 TikTok；无变化 |
| C11 | `counts.n_records` | 33→33 | 34→34 | journey/outcome 标注未变 |
| C11 | `relevant_records` | 136→131 | 136→131 | 5 条 exact-family 改判 |
| C11 | `journey_or_outcome_share` | 0.243→0.252 | 0.250→0.260 | 分子不变，分母 131 |
| C03 | exact-family 计数 | 16→10 | 16→10 | 5 条 exact 假阳性改判（另 1 条改 adjacent） |
| C03 | `exact_like` | 11→11 | 11→11 | 文本谓词不变 |
| C03 | `exact_model_experience` | 0→0 | 0→0 | 没有 exact-model 记录 |
| C07 | `eligible_records` | 308→303 | 308→303 | 5 条 `brand_other_product` 离开 eligible 集合 |

**C04/C05/C13 的 `counts.n_records` 全部不变**（C04 3、C05 0/1、C13
32/31）。C11 的 `counts.n_records` 也不变（33/34）。变的只有 experience
分母、C03/C07 的 product_match 派生计数和 C11 的分母。

**没有任何 claim 升级**：实现前后 12 条 claim 的 `grade` 逐条相同。
C11 的 share 从 0.243 升到 0.252（v2 0.250→0.260），原因是分母去掉 5 条
非目标记录，分子 33/34 不变；这是分类器修正，不是证据变强。

6 条 product_match 修正是：`c-1u7ofya`、`c-19rnylotzfmkh`、
`c-19rg8fid9ublx`、`c-ph09yrn`、`c-pdjzq5u` → `brand_other_product`；
`c-pdp6hz8` → `category_adjacent`。前 5 条离开 exact-family 计数与
eligible 集合，`c-pdp6hz8` 离开 exact-family 但仍在 on-topic。

### 5.6 为什么不是 46 或 160

- 46 不是当前冲突数。合并前的当前产物是 35（v1）/ 34（v2）；合并后
  `conflict` 指标退役。
- 如果把门禁写成 `scope != none`，v1 会得到 150 条（58 partial + 92
  full），v2 151 条；natural frame 会变成 42 条。这会混入 32 条
  off-target 评价。本契约的门禁是 `on_topic AND scope != none`，结果是
  v1 118、v2 119。
- 本契约不是放宽，是把一个布尔拆成两个正交字段。
- 因此模块级增长是 +2（v1）或 +1（v2），不是 +46。减少的 1 条是
  `c-pgsk2oe`。多出来的记录只有 `c-1r44c1m` 和 `c-phyrbxj`（v1；v2 只有
  `c-phyrbxj`）。natural frame 另含 A2 回归恢复的 3 条（§5.3b），它们合并
  前已是 `experience=true`，不计入本次模块级增长。

### 5.7 硬约束对账

| 硬约束 | 对账 |
|---|---|
| 不许改 gold set | `gold-set-50.jsonl` 只读；构建前后 sha256 断言。`eval_gold.py` 只读旧标签，不改写。 |
| claim 的证据基数不许悄悄放大 | C04/C05/C13 的 `counts.n_records` 全部不变（C04 3、C05 0/1、C13 32/31）；C11 的 `counts.n_records` 也不变（33/34）。变的是 experience 分母、C03/C07 的 product_match 派生计数和 C11 的分母，逐条列在 §5.2 和 §5.5。没有未列出的变化。 |
| 没有 claim 因合并升级 | 实现前后 12 条 claim 的 `grade` 逐条相同。C11 的 share 从 0.243→0.252（v2 0.250→0.260）只因分母去掉 5 条非目标记录，分子不变。 |
| 54 条盲判回归 | 用 `coder.code_record` 重算，规则与判官多数一致 **52/54**；三档一致 **43/54**。仅有的 2 条 miss 是已登记的 X35 `c-1r7qvfd` 和 X41 `c-1tkhcj3`（正文为空）。 |
| gold sha256 | `e1dcc693d7c832dc…`，构建前后一致。 |
| 不许为让某条 claim 好看而放宽 scope 规则 | 本契约只收紧一条 scope（`c-1uuim67`），没有放宽。C05 的 full 层共现仍按同产品守卫；本次不重编码，不新增舒适/摩擦标注。 |

## 6 风险

| # | 风险 | 触发点 | 检测方法 | 处置 |
|---|---|---|---|---|
| 1 | product_match 假阳性，把别的产品算进来 | `husband` 命中 `band`；`band extender`；同品牌尿布桶/内衣/吸奶器/孕妇枕 | 单元测试含 `husband`、`band extender`、diaper pail、nursing bra、pregnancy pillow；对 cohort 断言每条都有产品族短语 | 词边界匹配 + 产品族短语 + §5.2 的 6 条修正账本 |
| 2 | product_match 假阴性，丢掉真实体验 | 评论用“one”指代支撑带；记录没有 `belly band` 字样 | 盲判集 X36 / `c-pgsk2oe`；`product_match_debt` 清单 | 不绕过 gate；下一轮单独修分类器，并解释 C03/C11 变化 |
| 3 | scope 假阳性，把症状当评价 | 锚点来自上一句；证据句不含产品词或指代 | 每条准入记录必须给出逐字证据句；证据句必须含产品词或指代 + 极性。`c-1uuim67` 是反例 | 收紧锚点：产品词必须在同一子句，或在同段且距离受限；`c-1uuim67` 改 none |
| 4 | scope 假阴性，漏掉真实评价 | `c-1r7qvfd`（“Nothing helps”） | 54 条盲判集；已知 miss 清单 | 保持 none；单独修 scope 规则；不并入本合并 |
| 5 | experience 分母漂移，share 变化 | C04/C05 的 partial 层从 25/26 变 27 | 构建前后 diff `claims.json`；逐条记录变化 | 每次变化必须在 §5.2 有记录；没有记录的差异视为失败 |
| 6 | 旧消费者读 `experience` 或 `is_product_experience`，静默当成 false | 下游脚本、报表、API | schema 校验；grep 消费者；`compat-experience-diff.json` | 过渡期输出 deprecated 派生字段；发迁移通知 |
| 7 | C05 同产品守卫回归，把不同产品拼成共现 | 新增准入记录含多产品 | 断言 `cross_product=true` 的行 `both=false`；回归测试用 `c-1opsx7o` | 保留同产品守卫；不因为 cohort 变化而放宽 |
| 8 | TikTok 硬编码 `exact_current_family`，非支撑带评论混入 | TikTok 评论实际是别的 SKU | 抽样核对 ASIN/商品标题；构建时校验 SKU 白名单 | 摄入时加 SKU/产品族校验；不确定时 fail closed |
| 9 | 盲判是模型判官，不是人工；若判官同族，独立性与人工准确率都有限 | 判官运行身份未在产物中固化 | 核对判官运行身份；`cross-model-report.md` 已注明同族自一致 | 把 54 条当回归集，不当准确率；准入记录做人工 spot-check |
| 10 | 重编码新增记录时产生新 aspect，C04/C05 变大 | 对 `c-1r44c1m`、`c-phyrbxj` 重新跑 LLM coder | 逐条 diff aspects；若新增摩擦/舒适标注，停止并复核 | 本次不重编码。两条在规则 coder 和现有 LLM 行里都没有 aspect 标注 |
| 11 | gold set 被改动 | 任何脚本重写 `gold-set-50.jsonl` | 构建前后 sha256 断言 | 只读；CI 检查 |
| 12 | `brand_category` 枚举不一致 | consumer contract、metrics、llm_coder 的 on-topic 集合含该值 | 枚举一致性测试 | 统一为 §2.2 的 4 值；旧值映射为 exact 并写日志 |

### 6.1 上线门禁

本合并上线前必须同时满足：

1. `c-1uuim67` 的 scope 已改为 none，或该记录已从准入清单移除。
2. 6 条 product_match 修正已写入账本，C03/C11 的变化已复核。
3. C04/C05/C13 的 `n_records` 与本文一致；任何偏差都有逐条记录的解释。
4. gold set 的 sha256 未变。
5. 旧消费者的 `experience` 兼容字段已发版，或迁移公告已发出。
6. 54 条盲判集作为回归测试运行，三档一致率不低于 43/54。

## 附录 A 复核方法

所有数字都可从当前产物重算。核心步骤：

1. 读 `canonical-records.jsonl` 和 `coded-corpus.jsonl`。
2. 按 §5.2 的 6 条修正覆盖 `product_match`。
3. 按 §2.4 计算 cohort。
4. 对 `claims.json` 的 C03/C04/C05/C11/C13 做前后 diff。
5. 对 `gold-set-50.jsonl` 做 sha256 断言。

预检命令（不改文件）：

```
python3 -I - <<'PY'
import json
p = "voc_pipeline/artifacts/run-20261029"
recs = {r["canonical_id"]: r for r in map(json.loads, open(p + "/canonical-records.jsonl"))}
coded = {r["canonical_id"]: r for r in map(json.loads, open(p + "/coded-corpus.jsonl"))}
corr = {
    "c-1u7ofya": "brand_other_product",
    "c-19rnylotzfmkh": "brand_other_product",
    "c-19rg8fid9ublx": "brand_other_product",
    "c-ph09yrn": "brand_other_product",
    "c-pdjzq5u": "brand_other_product",
    "c-pdp6hz8": "category_adjacent",
}
on_topic = {"exact_current_family", "category_adjacent"}
scope_corr = {"c-1uuim67": "none"}
def pm(cid):
    return corr.get(cid, recs[cid]["product_match"])
def sc(cid):
    return scope_corr.get(cid, coded[cid]["experience_scope"])
cohort = [
    cid for cid in coded
    if pm(cid) in on_topic and sc(cid) in {"full", "partial"}
]
print(len(cohort), sum(sc(c) == "full" for c in cohort))
PY
```

预期输出：`118 88`（v1）。v2 路径输出 `119 89`。实现后产物已包含 6 条
product_match 修正；脚本里的 `corr` 对当前产物是幂等的，只用于复现历史口径。
