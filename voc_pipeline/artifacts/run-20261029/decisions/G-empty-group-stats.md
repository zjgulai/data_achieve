# 裁决 G：空组与分层统计禁用规则

## 0. 最终裁决

**空组、样本不足层、无对照层一律 fail closed。只报计数，不报统计量。**

**本轮 0 个可用分层。C16 的 observed 不许出现任何中位数、倍数、p 值或置信区间。**

三条附带裁决：

1. C15/C16 headline 按 §4 的确切句子改写。C15 不再写「高/中置信」，C16 不再写「能算出分层互动基线」。
2. C17 的基准是 10 条 exact 视频的整体中位数，不是时长档中位数。C17 的计数必须从 `high_performers.videos` 的 2 条 exact 行取，不能从空的 `common_features.items` 取。
3. 金标集不动。`minimum_layer_n=8` 不放宽。不为凑统计量合并层。

一句话：**10 条 exact 只能报整体分布和逐条计数；任何分层都不成立。**

## 1. 空组定义

### 1.1 权威字段

| 字段 | 本轮值 | 用途 |
| --- | --- | --- |
| `creator-video/baseline/baseline.json` → `aggregation.minimum_layer_n` | 8 | 分层最小样本量 |
| 同上 → `sufficiency_assessment.dimensions_with_usable_layer` | `[]` | 是否有可用分层 |
| 同上 → `sufficiency_assessment.usable_layers` | `[]` | 可用层清单 |
| 同上 → `sufficiency_assessment.bootstrap_performed` | `false` | 是否做过检验 |
| 同上 → `layers.<dimension>.groups.<layer>.usable_layer` | 全部 `false` | 单层判定 |
| 同上 → `layers.<dimension>.groups.<layer>.metrics` | 全部 `null` | 统计量是否存在 |
| 同上 → `layers.<dimension>.groups.<layer>.lift_vs_complement` | 全部 `null` | 倍数是否存在 |

`aggregation.no_stratified_baseline` 的现文本不准确：`has_link:true`、`ad_disclosure:true`、`platform_is_ad:true` 的 n 分别是 10、10、9，都 >=8。准确判据是 `dimensions_with_usable_layer == []` 和 `usable_layer == false`。渲染层必须用后两者，不能只读 `no_stratified_baseline`。

### 1.2 六类空组/不可用

- **G1 零样本组**：`n == 0`。
- **G2 样本不足层**：`0 < n < 8`。
- **G3 对照不足层**：`n >= 8`，但 `complement_n < 8`。单值或近单值维度属于这一类。
- **G4 统计量缺失**：`metrics`、`lift_vs_complement`、`median`、`multiple`、`p_value`、`ci95` 任一为 `null`、缺失、空字符串、`NaN`、`Inf` 或非数值。
- **G5 层标识缺失**：`layer` 为空字符串、`null`，或只有维度名没有层名。
- **G6 维度不可用**：`dimension_status == "insufficient_sample"` 或 `usable_layers == []`。

### 1.3 可用层判定

一个层同时满足以下五条才算可用：

1. `n >= 8`
2. `complement_n >= 8`
3. `metrics` 是非空字典
4. `lift_vs_complement` 是非空字典
5. `status == "ok"` 且 `usable_layer == true`

`n >= 8` 单独不构成可用层。`has_link:true` 有 10 条，但 `false` 组 0 条，不能比较。

### 1.4 本轮实际判定

| 维度 | 各层计数 | n>=8 的层 | 对照 n>=8 | 可用层 |
| --- | --- | --- | --- | --- |
| 时长档 | <=15s 1、16-30s 4、31-60s 4、>60s 1 | 无 | <=15s 9、>60s 9，但层 n<8 | 无 |
| has_link | true 10、false 0、unknown 0 | true | false 组 0；true 的对照 0 | 无 |
| ad_disclosure | true 10、false 0、unknown 0 | true | false 组 0；true 的对照 0 | 无 |
| platform_is_ad | true 9、false 1、unknown 0 | true | false 组 1；true 的对照 1 | 无 |

结论：`usable_layers = []`。C16 只能报计数。

## 2. 每种情况该渲染什么

| 情况 | observed 允许写 | observed 禁止写 |
| --- | --- | --- |
| G1 `n=0` | 「该层 0 条（无样本）」 | 任何中位数、倍数、p 值、CI、百分比估计；`0.00%`、`0.00x`、`p=0.000`、`CI [0.00, 0.00]` |
| G2 `0<n<8` | 「该层 k 条（n=k<8，仅计数）」 | 中位数、倍数、p 值、CI、排名、「跑赢/未跑赢」结论 |
| G3 `n>=8` 且 `complement_n<8` | 「该维度为单值或近单值（true X 条 / false Y 条），无可用对照组」 | 两组比较、倍数、p 值、CI、「跑赢/不显著」 |
| G4 统计量 null/缺失/非数值 | 「统计量未产出」或整句省略 | 用 0.0 代替；渲染 `0.00x`、`p=0.000`、`CI [0.00, 0.00]`、`NaN`、`None` |
| G5 层名为空 | 只写维度计数；记一条结构错误 | 「时长档  的中位…」这类空层名句子 |
| G6 维度不可用 | 只写该维度的整数计数 | 该维度任何统计量 |
| 全部维度不可用 | C16 observed 只写各层整数计数 | C16 observed 出现任何中位数、倍数、p 值、CI |
| 未做检验 | 「样本不足以检验」 | 「没有跑赢」「无显著差异」「不显著」「未发现效果」「无差异」 |

补充规则：

- 计数占比可以写成 `a/b` 或「X 条（分母 Y）」，要求 `a`、`b` 都是整数且 `b >= 1`。空组上下文不要写小数百分比。
- 逐条明细可以写 raw 值，例如视频互动率 `4.80%`，但必须同时给出 `video_id` 和 `n=10` 的分母说明，不能把它写成层统计量。
- 任何 `None` 进入 f-string 格式化前必须拦截。`f"{None:.2f}"` 会抛错，`_flt(None) -> 0.0` 会伪造统计量；两者都不允许。

## 3. 允许的替代表述

### 3.1 C16 observed 的确切句子

无可用分层时，C16 的 observed 必须逐字使用下面这段（数字与 baseline 一致）：

> 10 条基线视频在预定义维度上没有可用分层。时长档：<=15s 1 条、16-30s 4 条、31-60s 4 条、>60s 1 条，四层均小于 8。has_link：true 10 条、false 0 条。ad_disclosure：true 10 条、false 0 条。platform_is_ad：true 9 条、false 1 条，false 组小于 8。没有任何维度同时满足层内 n>=8 与对照组 n>=8，因此本轮不产出任何分层中位数、倍数、p 值或置信区间。结论是样本不足以检验，不是已证明没有内容形态跑赢。

### 3.2 C16 其余三格

- Interpretation：「10 条样本不支持分层检验。结论只能写成样本不足以检验，不能写成已证明没有内容形态跑赢。」
- Counterevidence：「本轮没有可用的对照组；任何点估计都不稳定，不能用于选型。」
- Decision implication：「先把每个候选层扩到层内 n>=8 且有 n>=8 的对照组，再做分层比较。」

### 3.3 可以保留的整体分布

10 条 exact 的整体描述统计可以保留，但只能出现在整体分布块或 C17，不得进入 C16 的 observed。每个数字必须带 `n=10` 和「整体描述，不是分层比较」。

本轮可核对的整体值：

| 指标 | 中位数 | n |
| --- | ---: | ---: |
| 播放量 | 172,650 | 10 |
| 互动率 | 1.19% | 10 |

### 3.4 C17 的基准修正

`baseline.json` → `high_performers.definition` 写的是「2.0 × median interaction rate of the 10 exact videos」。`eligible_duration_buckets` 为空。所以 C17 的「自身时长档中位数」不成立，必须改成「10 条 exact 视频整体中位数」。

可核对的 2 条 exact 行：

| video_id | 互动率 | 对整体中位数倍数 | 时长档 | 档内 n | has_link | ad_disclosure | 关联 |
| --- | ---: | ---: | --- | ---: | --- | --- | --- |
| 7695942452426968333 | 4.80% | 4.023x | 16-30s | 4 | true | true | high/target_exact |
| 7691166964626066701 | 4.39% | 3.677x | >60s | 1 | true | true | high/target_exact |

整体中位数 1.1932%，2 倍阈值 2.3864%。

C17 新 headline：「2 条视频的互动率达到 10 条 exact 视频整体中位互动率的 2 倍以上，它们的共同点只能做计数，不能解释它们为什么跑赢。」

C17 新 observed：「2 条视频的互动率达到 10 条 exact 视频整体中位互动率（n=10，1.19%）的 2 倍以上：分别为 4.02 倍和 3.68 倍。2 条中广告披露 true 2 条、购买链接 true 2 条、时长档 16-30s 1 条、>60s 1 条、31-60s 0 条、<=15s 0 条；播放 <5000 的 0 条。」

C17 的计数必须从 `high_performers.videos` 逐行统计。当前 `common_features.items` 是空数组，`_cv_common()` 返回 `{}`，于是 C17 把广告披露 true、购买链接 true、16-30s、>60s 都渲染成 0，并把全池占比渲染成 0.0%。这是同一类 fail-open，必须一起修。

C17 的 Basis 改为「creator-video/baseline/baseline.json high_performers.videos；分母 = 10 条 exact 视频（整体中位数）」。Limit 改为「只覆盖 10 条 exact 视频；高表现定义是整体中位数 2 倍；2 条不是总体」。

## 4. C15 与 C16 headline 改写

### 4.1 C15 新 headline（逐字）

> 视频层采到 141 条唯一视频和 124 位达人；其中 10 条带有目标商品锚点（target_exact），确证目标商品关联并构成互动基线。

要求：

- 不出现「高/中置信」。
- 不出现「10 条进入基线，只有 10 条锚定」这类自相矛盾。
- 必须保留 141、124、10 三个数字。

C15 的 observed 同步修正：把「high/medium 的 10 条进入基线」改成「relation_type 为 target_exact 的 10 条进入基线」。high 是 10，medium 是 31；baseline 只取 target_exact 的 10 条。medium 31 条是 category reference，不进基线，不进表现统计。

### 4.2 C16 新 headline（逐字）

> 10 条基线视频的样本不足以做分层互动基线：没有任何预定义维度同时满足层内 n>=8 与对照组 n>=8，本轮只报各层计数。

要求：

- 必须出现「样本不足」或「不足以」。
- 不出现「能算出」「算得出」「跑赢」「没有跑赢」。
- 不出现任何具体统计量。

### 4.3 旧句错在哪里

| claim | 旧句 | 错误 |
| --- | --- | --- |
| C15 | 10 条进入高/中置信商品关联基线，只有 10 条锚定目标商品 | baseline 只取 target_exact 10 条；medium 31 条不进基线。「高/中置信」是旧口径。「进入」与「只有」数量相同，语义自相矛盾 |
| C16 | 10 条高/中置信视频能算出分层互动基线，但没有任何内容形态…跑赢它 | 0 个可用层，算不出分层基线。没有检验就不能写「跑赢」或「没有跑赢」 |

## 5. 校验规则设计

### 5.1 规则 A：`no_empty_group_stats`

**判定条件**：报告正文或 `claims[].numbers` 出现下列任一模式，构建失败。

正文模式（扫描前先用现有 `strip_for_scan()` 屏蔽 CSS/JS 和 forbidden catalog）：

| ID | 模式 | 命中含义 |
| --- | --- | --- |
| A1 | `(?<![\d.])0\.00\s*x` | 伪造倍数 |
| A2 | `\bp\s*=\s*0\.000\b` | 伪造 p 值 |
| A3 | `CI\s*\[\s*0\.00\s*,\s*0\.00\s*\]` | 退化 CI |
| A4 | `(中位数\|中位互动率\|倍数\|p\s*值\|p\s*=\|置信区间\|CI)[^。；\n]{0,48}n\s*=\s*0` | 零组上算统计量 |
| A5 | `(中位数\|中位互动率\|倍数\|p\s*值\|p\s*=\|置信区间\|CI)[^。；\n]{0,48}n\s*=\s*[1-7]\b` | 不足 8 的层上算统计量 |
| A6 | `(时长档\|对比测评\|是否演示\|是否有购买链接\|是否有广告披露\|平台广告标记)\s+的` | 层名为空 |
| A7 | `(中位数\|倍数\|p\s*值\|置信区间\|CI)[^。；\n]{0,24}\b(NaN\|None\|Inf\|inf)\b` | 非数值统计量 |

数据模式（`claims[].numbers`）：

- C16 必须带 `stratified_baseline_available`。本轮值为 `false`。
- 当 `stratified_baseline_available == false`，下列键必须为 `null` 或缺失：`top_layer_median_interaction_rate`、`complement_median_interaction_rate`、`median_multiple`、`mann_whitney_p`、`bootstrap_ci_low`、`bootstrap_ci_high`、`has_link_false_multiple`、`ad_disclosure_false_multiple`。
- 任一键是 `0.0`、`0` 或非空字符串 → fail。
- 没有该字段时，退回看 `support_gate_status == "FAILED"`；仍无法判断 → fail closed。

**报错格式**：`no_empty_group_stats: <ID>@<char_offset>: "<原文片段>"`。一次报出全部命中，不只报第一条。

**当前报告预期命中**：`0.00x` 3 处、`p=0.000` 3 处、`CI [0.00, 0.00]` 3 处、空层名 1 处、`n=0` 邻近统计量至少 5 处。修复前这条规则必须 FAIL。

### 5.2 规则 B：`strata_require_min_n`

**判定条件**：把报告正文按 `。；\n` 和 HTML 块切成句子块。含统计词的块必须给出 `n>=8`。

统计词：`分层|中位数|中位互动率|倍数|显著性|p\s*值|p\s*=|置信区间|CI\s*\[|跑赢|对照`。

逐块判定：

| ID | 条件 | 判定 |
| --- | --- | --- |
| B1 | 含统计词，但没有 `n=<整数>` | fail |
| B2 | 有 `n=k`，但所有 k 的最大值 < 8 | fail |
| B3 | 含「补充组/对照组/vs/对比」，但没有第二个不同的 `n>=8` | fail |
| B4 | 含「没有跑赢/无显著差异/不显著/未发现.*效果/无差异」，且最大 n<8 | fail |
| B5 | C15 headline 含「高/中置信」，或 C16 headline 含「能算出/跑赢」 | fail |
| B6 | C15/C16 headline 缺少必需数字或「样本不足」措辞 | fail |

豁免块必须同时满足：

1. 含「本轮无可用分层/无可用分层/仅计数/样本不足/不产出任何分层/不做分层」之一；
2. 不含 `\d+(?:\.\d+)?\s*%`；
3. 不含 `\d+\.\d+\s*x`；
4. 不含 `p\s*=`；
5. 不含 `CI\s*\[`。

豁免只用于「说明为什么不做分层」的句子。含具体统计量的句子不能豁免。

**报错格式**：`strata_require_min_n: <ID>@<char_offset>: "<块原文>"`。

### 5.3 接入构建门

在 `voc/validate_report.py` 增加两个函数：

- `_empty_group_stats_problems(doc: str, claims: list[dict] | None) -> list[str]`
- `_strata_min_n_problems(doc: str, claims: list[dict] | None) -> list[str]`

接入两处：

1. `assert_report_clean()`：把返回的 problems 加进现有 `problems` 列表，和 `_precision_split_problems()` 同一位置。
2. `build_suite()`：增加 `suite.add("no_empty_group_stats", ...)` 和 `suite.add("strata_require_min_n", ...)`，让 `validation-result.json` 能看到这两条。

`run.sh` 已经调用 `python3 -m voc.validate_report`。任一规则 fail，进程退出 1，构建失败。这是 fail closed，不是警告。

### 5.4 必测用例

| # | 注入文本 | 预期 |
| --- | --- | --- |
| 1 | 修复前的真实报告（含 `0.00x`、`p=0.000`、`CI [0.00, 0.00]`） | FAIL A1/A2/A3/A4/A6 |
| 2 | §3.1 的确切 C16 observed | PASS |
| 3 | 「时长档 31-60s 的中位互动率为 2.85%（n=18），倍数 2.24x，p=0.409」 | PASS（n=18>=8） |
| 4 | 「时长档的中位互动率为 0.00%（n=0），倍数 0.00x，p=0.000」 | FAIL A1/A2/A4/B2 |
| 5 | 「has_link=false 为 0.00x（p=0.000，CI [0.00, 0.00]）」 | FAIL A1/A2/A3 |
| 6 | 「没有任何内容形态跑赢它」，同段没有 n>=8 | FAIL B1/B4 |
| 7 | 「10 条基线视频在预定义维度上没有可用分层…本轮不产出任何分层…」 | PASS（豁免） |

### 5.5 数据层契约

渲染层修完后必须满足：

- `_flt(None)` 返回 `None`，不返回 `0.0`。
- `_pct(None)` 返回「—」或「未产出」，不返回 `0.00%`。
- 所有 `:.2f`、`:.3f` 格式化前先判 `is not None`。
- C16 渲染分支先读 `sufficiency_assessment.dimensions_with_usable_layer`；为空时直接走 §3.1 的计数句，不进入统计分支。
- `strongest` 为 `null` 或 `layers_seen` 为空时，不读取 `top_layer`、`top_n`、`top_median`。
- C17 的计数从 `high_performers.videos` 逐行统计；`common_features.items` 为空时不得回退成 0。
- 任一数据源缺失时，fail closed 到计数句，不推断统计量。
