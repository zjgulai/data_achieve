# VOC 人工双盲校准 — Cohen's kappa 报告

- 生成时间：2026-10-30T02:50:53.160853+00:00
- 盲样本：`/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/calibration/blind-sample.jsonl`（20 条）
- 人工标注：`selftest/fake-human-labels.json`
- LLM 参考：`/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/llm-coding/coded/ALL.jsonl`
- taxonomy：`/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/llm-coding/taxonomy.json`
- 参考口径：LLM `confidence` = high（默认） 的 aspect；低于门槛的 aspect 不计入。
- 样本分布：TikTok 12 条，Reddit 8 条
- 统计单元：每条 × 每个 taxonomy aspect 的「是否标注」二值判断；极性单独报告。
- 主口径：**micro κ**（同一信源内所有 item×aspect 单元格池化）；同时报 **macro κ**（逐 aspect κ 的算术平均）。

> 此前的 87.0% 是 LLM 对 LLM 的一致性，不是人工验证。
> 本报告用于人工双盲校准；TikTok 与 Reddit 必须分开看，不能用一个 ALL 数字糊过去。

## 1 结论摘要

| 信源 | 条数 | 单元格 | 人+ | LLM+ | 双方+ | 人独有 | LLM 独有 | 一致率 | κ (micro) | κ (macro) | 等级 (micro) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| TikTok | 12 | 408 | 15 | 24 | 15 | 0 | 9 | 97.8% | 0.758 | 0.675 | substantial（实质一致） |
| Reddit | 8 | 272 | 7 | 9 | 7 | 0 | 2 | 99.3% | 0.871 | 0.743 | almost perfect（几乎完全一致） |
| ALL（仅汇总） | 20 | 680 | 22 | 33 | 22 | 0 | 11 | 98.4% | 0.792 | 0.727 | substantial（实质一致） |

**总体 κ（micro）= 0.792；macro = 0.727。** ALL 行只用于汇总，不能替代分信源结论。

- κ < 0.60 的 aspect：5 个；最低 κ = 0.000。涉及：皮肤摩擦（COM.SKIN_CHAFE）、柔软触感（COM.SOFTNESS）、价格价值（VAL.PRICE_VALUE）、总体评价（GEN.OVERALL_EVALUATION）、总体支撑（SUP.GENERAL）。

> 注意：micro κ 对低阳性比例很敏感。样本里绝大多数 item×aspect 单元格是「双方都没标」，这些单元格会抬高一致率。即使漏掉三分之一的正向 aspect，micro κ 仍可能看起来不低。因此必须同时看逐 aspect κ、macro κ 和第 7 节的分歧清单。

等级按 Landis & Koch 常用分档：≥0.80 almost perfect；≥0.60 substantial；≥0.40 moderate；≥0.20 fair；≥0 slight；<0 poor。

## 2 分信源

### TikTok（12 条，408 个判断单元格）

- 人类标注阳性：15；LLM 阳性：24；双方都标：15。
- 一致率：97.8%；κ (micro)：0.758（substantial（实质一致））；κ (macro)：0.675（substantial（实质一致））。
- 有阳性的 aspect：15 个；κ 可计算的 aspect：15 个。

### Reddit（8 条，272 个判断单元格）

- 人类标注阳性：7；LLM 阳性：9；双方都标：7。
- 一致率：99.3%；κ (micro)：0.871（almost perfect（几乎完全一致））；κ (macro)：0.743（substantial（实质一致））。
- 有阳性的 aspect：5 个；κ 可计算的 aspect：5 个。

## 3 逐 aspect（ALL 20 条）

| Aspect | 系列 | 人+ | LLM+ | 双方+ | 不一致 | 一致率 | κ | 等级 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 总体支撑（SUP.GENERAL） | 支撑 | 2 | 5 | 2 | 5 | 85.0% | 0.500 | moderate（中等） |
| 背部支撑（SUP.BACK） | 支撑 | 2 | 2 | 2 | 1 | 100.0% | 1.000 | almost perfect（几乎完全一致） |
| 压力卸载（SUP.PRESSURE_OFFLOAD） | 支撑 | 2 | 2 | 2 | 0 | 100.0% | 1.000 | almost perfect（几乎完全一致） |
| 腹部托举（SUP.BELLY_LIFT） | 支撑 | 1 | 1 | 1 | 1 | 100.0% | 1.000 | almost perfect（几乎完全一致） |
| 尺码准确（FIT.SIZE_ACCURACY） | 尺码与合身 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 体型适配（FIT.BODY_SHAPE） | 尺码与合身 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 孕期增长区间（FIT.GROWTH_RANGE） | 尺码与合身 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 覆盖范围（FIT.COVERAGE） | 尺码与合身 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 带体/绑带设计（ADJ.STRAP_DESIGN） | 调节与结构 | 2 | 2 | 2 | 0 | 100.0% | 1.000 | almost perfect（几乎完全一致） |
| 穿脱难度（ADJ.DONNING） | 调节与结构 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 松紧调节（ADJ.RANGE_TENSION） | 调节与结构 | 1 | 1 | 1 | 0 | 100.0% | 1.000 | almost perfect（几乎完全一致） |
| 保持位置（STB.STAY_IN_PLACE） | 稳定性 | 1 | 2 | 1 | 1 | 95.0% | 0.643 | substantial（实质一致） |
| 绑带位置（STB.STRAP_POSITION） | 稳定性 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 柔软触感（COM.SOFTNESS） | 舒适 | 0 | 1 | 0 | 1 | 95.0% | 0.000 | slight（轻微） |
| 透气与发热（COM.BREATHABILITY_HEAT） | 舒适 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 皮肤摩擦（COM.SKIN_CHAFE） | 舒适 | 0 | 1 | 0 | 1 | 95.0% | 0.000 | slight（轻微） |
| 局部压迫（COM.PRESSURE_DIGGING） | 舒适 | 1 | 1 | 1 | 0 | 100.0% | 1.000 | almost perfect（几乎完全一致） |
| 长时间穿着（COM.WEAR_TOLERANCE） | 舒适 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 总体舒适（COM.GENERAL） | 舒适 | 4 | 4 | 4 | 0 | 100.0% | 1.000 | almost perfect（几乎完全一致） |
| 衣下表现（APP.UNDER_CLOTHING） | 外观与衣下表现 | 1 | 1 | 1 | 0 | 100.0% | 1.000 | almost perfect（几乎完全一致） |
| 轻薄低体积（APP.LOW_PROFILE） | 外观与衣下表现 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 颜色外观（APP.COLOR_AESTHETIC） | 外观与衣下表现 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 面料（MAT.FABRIC） | 面料与耐用 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 耐用性（MAT.DURABILITY） | 面料与耐用 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 弹性保持（MAT.ELASTICITY_RETENTION） | 面料与耐用 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 厚薄（MAT.THICKNESS） | 面料与耐用 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 清洗护理（MAT.CARE） | 面料与耐用 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 价格价值（VAL.PRICE_VALUE） | 性价比 | 0 | 1 | 0 | 1 | 95.0% | 0.000 | slight（轻微） |
| 退换（CX.RETURN_EXCHANGE） | 退换与服务 | 1 | 1 | 1 | 1 | 100.0% | 1.000 | almost perfect（几乎完全一致） |
| 到货状态（FUL.PRODUCT_CONDITION） | 到货状态 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 总体评价（GEN.OVERALL_EVALUATION） | 总体评价 | 3 | 7 | 3 | 4 | 80.0% | 0.494 | moderate（中等） |
| 穿着方式（USE.LAYERING） | 穿着方式 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |
| 活动兼容（ACT.COMPATIBILITY） | 活动兼容 | 1 | 1 | 1 | 0 | 100.0% | 1.000 | almost perfect（几乎完全一致） |
| 受力位置安全（SAF.PRESSURE_PLACEMENT） | 受力安全 | 0 | 0 | 0 | 0 | — | — | 双方均未标注 |

「不一致」= 一方标了另一方没标（presence）+ 双方都标但极性不同（polarity）。κ 只使用 presence 二值；极性差异不计入 κ，但在「不一致」列和 top 5 中单列。

## 4 分信源逐 aspect κ

| Aspect | TikTok κ | TikTok 一致率 | Reddit κ | Reddit 一致率 | ALL κ |
|---|---:|---:|---:|---:|---:|
| 总体支撑（SUP.GENERAL） | 0.000 | 83.3% | 0.714 | 87.5% | 0.500 |
| 背部支撑（SUP.BACK） | 1.000 | 100.0% | — | — | 1.000 |
| 压力卸载（SUP.PRESSURE_OFFLOAD） | 1.000 | 100.0% | 1.000 | 100.0% | 1.000 |
| 腹部托举（SUP.BELLY_LIFT） | 1.000 | 100.0% | — | — | 1.000 |
| 尺码准确（FIT.SIZE_ACCURACY） | — | — | — | — | — |
| 体型适配（FIT.BODY_SHAPE） | — | — | — | — | — |
| 孕期增长区间（FIT.GROWTH_RANGE） | — | — | — | — | — |
| 覆盖范围（FIT.COVERAGE） | — | — | — | — | — |
| 带体/绑带设计（ADJ.STRAP_DESIGN） | 1.000 | 100.0% | — | — | 1.000 |
| 穿脱难度（ADJ.DONNING） | — | — | — | — | — |
| 松紧调节（ADJ.RANGE_TENSION） | 1.000 | 100.0% | — | — | 1.000 |
| 保持位置（STB.STAY_IN_PLACE） | 0.625 | 91.7% | — | — | 0.643 |
| 绑带位置（STB.STRAP_POSITION） | — | — | — | — | — |
| 柔软触感（COM.SOFTNESS） | 0.000 | 91.7% | — | — | 0.000 |
| 透气与发热（COM.BREATHABILITY_HEAT） | — | — | — | — | — |
| 皮肤摩擦（COM.SKIN_CHAFE） | 0.000 | 91.7% | — | — | 0.000 |
| 局部压迫（COM.PRESSURE_DIGGING） | 1.000 | 100.0% | — | — | 1.000 |
| 长时间穿着（COM.WEAR_TOLERANCE） | — | — | — | — | — |
| 总体舒适（COM.GENERAL） | 1.000 | 100.0% | 1.000 | 100.0% | 1.000 |
| 衣下表现（APP.UNDER_CLOTHING） | — | — | 1.000 | 100.0% | 1.000 |
| 轻薄低体积（APP.LOW_PROFILE） | — | — | — | — | — |
| 颜色外观（APP.COLOR_AESTHETIC） | — | — | — | — | — |
| 面料（MAT.FABRIC） | — | — | — | — | — |
| 耐用性（MAT.DURABILITY） | — | — | — | — | — |
| 弹性保持（MAT.ELASTICITY_RETENTION） | — | — | — | — | — |
| 厚薄（MAT.THICKNESS） | — | — | — | — | — |
| 清洗护理（MAT.CARE） | — | — | — | — | — |
| 价格价值（VAL.PRICE_VALUE） | 0.000 | 91.7% | — | — | 0.000 |
| 退换（CX.RETURN_EXCHANGE） | 1.000 | 100.0% | — | — | 1.000 |
| 到货状态（FUL.PRODUCT_CONDITION） | — | — | — | — | — |
| 总体评价（GEN.OVERALL_EVALUATION） | 0.500 | 75.0% | 0.000 | 87.5% | 0.494 |
| 穿着方式（USE.LAYERING） | — | — | — | — | — |
| 活动兼容（ACT.COMPATIBILITY） | 1.000 | 100.0% | — | — | 1.000 |
| 受力位置安全（SAF.PRESSURE_PLACEMENT） | — | — | — | — | — |

TikTok 每格 n=12 条；Reddit 每格 n=8 条；ALL 每格 n=20 条。n/a 表示该 aspect 在该信源里没有阳性或没有方差。

## 5 极性一致率

只统计双方都标了同一个 aspect 的单元格。exact = 极性字符串完全相同；family = 把 qualified_positive/qualified_negative 折叠成正/负后再比。

| Aspect | 双方都标 | 极性 exact | exact 一致率 | family 一致 | family 一致率 |
|---|---:|---:|---:|---:|---:|
| 总体支撑（SUP.GENERAL） | 2 | 0 | 0.0% | 0 | 0.0% |
| 背部支撑（SUP.BACK） | 2 | 1 | 50.0% | 1 | 50.0% |
| 压力卸载（SUP.PRESSURE_OFFLOAD） | 2 | 2 | 100.0% | 2 | 100.0% |
| 腹部托举（SUP.BELLY_LIFT） | 1 | 0 | 0.0% | 0 | 0.0% |
| 带体/绑带设计（ADJ.STRAP_DESIGN） | 2 | 2 | 100.0% | 2 | 100.0% |
| 松紧调节（ADJ.RANGE_TENSION） | 1 | 1 | 100.0% | 1 | 100.0% |
| 保持位置（STB.STAY_IN_PLACE） | 1 | 1 | 100.0% | 1 | 100.0% |
| 局部压迫（COM.PRESSURE_DIGGING） | 1 | 1 | 100.0% | 1 | 100.0% |
| 总体舒适（COM.GENERAL） | 4 | 4 | 100.0% | 4 | 100.0% |
| 衣下表现（APP.UNDER_CLOTHING） | 1 | 1 | 100.0% | 1 | 100.0% |
| 退换（CX.RETURN_EXCHANGE） | 1 | 0 | 0.0% | 0 | 0.0% |
| 总体评价（GEN.OVERALL_EVALUATION） | 3 | 3 | 100.0% | 3 | 100.0% |
| 活动兼容（ACT.COMPATIBILITY） | 1 | 1 | 100.0% | 1 | 100.0% |

## 6 产品体验判定一致性

这一项只看「这条在评价产品吗？」的是/否，不看 aspect。

| | LLM 是 | LLM 否 |
|---|---:|---:|
| 人 是 | 20 | 0 |
| 人 否 | 0 | 0 |

一致率：100.0%；κ：n/a（无法计算（无方差））。

## 7 分歧最大的 top 5 aspect

> 触发条件：总体 κ < 0.60，或至少一个 aspect 的 κ < 0.60。本次 micro κ = 0.792，macro κ = 0.727，最低 aspect κ = 0.000。

### 1. 总体支撑（SUP.GENERAL）

- κ(ALL)：0.500；人+：2；LLM+：5；双方+：2。
- 存在分歧的单元格：5 个（presence 3 + polarity 2）。

| 题目 | 人工标注 | LLM 标注 |
|---|---|---|
| B06 | 负向 · “which helped support my muscles when turning” | 正向 · “which helped support my muscles when turning” |
| B07 | 未标注 | 正向 · “So supportive” |
| B09 | 未标注 | 正向 · “the comfort & support” |
| B14 | 未标注 | 正向 · “that helps give my growing belly support” |
| B18 | 正向 · “it is no longer helping” | 负向 · “it is no longer helping” |

### 2. 总体评价（GEN.OVERALL_EVALUATION）

- κ(ALL)：0.494；人+：3；LLM+：7；双方+：3。
- 存在分歧的单元格：4 个（presence 4 + polarity 0）。

| 题目 | 人工标注 | LLM 标注 |
|---|---|---|
| B03 | 未标注 | 负向 · “Didn’t work.” |
| B11 | 未标注 | 正向 · “Love this!” |
| B17 | 未标注 | 负向 · “I honestly hated my belly band” |
| B19 | 未标注 | 负向 · “Not the best quality.” |

### 3. 皮肤摩擦（COM.SKIN_CHAFE）

- κ(ALL)：0.000；人+：0；LLM+：1；双方+：0。
- 存在分歧的单元格：1 个（presence 1 + polarity 0）。

| 题目 | 人工标注 | LLM 标注 |
|---|---|---|
| B04 | 未标注 | 负向 · “the back is very rough and itchy” |

### 4. 柔软触感（COM.SOFTNESS）

- κ(ALL)：0.000；人+：0；LLM+：1；双方+：0。
- 存在分歧的单元格：1 个（presence 1 + polarity 0）。

| 题目 | 人工标注 | LLM 标注 |
|---|---|---|
| B16 | 未标注 | 正向 · “The material is soft” |

### 5. 价格价值（VAL.PRICE_VALUE）

- κ(ALL)：0.000；人+：0；LLM+：1；双方+：0。
- 存在分歧的单元格：1 个（presence 1 + polarity 0）。

| 题目 | 人工标注 | LLM 标注 |
|---|---|---|
| B20 | 未标注 | 正向 · “Worth it!” |

## 8 怎么读这份报告

- κ ≥ 0.60 是 substantial，κ ≥ 0.80 是 almost perfect。低于 0.60 时，先看第 7 节的分歧条目，判断是 taxonomy 定义不清、极性判断不同，还是 LLM 确实标错。
- 20 条样本很小，逐 aspect κ 很不稳定；它用于发现系统性问题，不适合当作精确的精度估计。
- micro κ 会被大量「双方都没标」的单元格抬高。判断 LLM 是否漏标时，优先看逐 aspect κ、macro κ 和 top 5 中的 presence 分歧，不要只报一个 micro κ。
- 样本只抽了「至少有一个 high aspect」的记录，因此这里的 κ 是 high-only 输出的一致性审计，不是全语料的 precision/recall。
- 不要根据这份报告改 gold set，也不要改 claim 评级逻辑。若发现定义歧义，改 taxonomy 定义并重新抽样，而不是在这 20 条上反复调参。

---

gold set 未改动；counting / evidence / claims 逻辑未改动。
