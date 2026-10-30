# 置信度门槛策略 v1

冻结日期：2026-10-30
适用产物：`llm-coding/coded/ALL.jsonl`（330 条有文本记录，225 个 aspect）
实现：`voc/llm_coder.py`

## 1 当前决定

- 只采信 `confidence == "high"` 的 aspect。
- 默认门槛为 `high`。用 `VOC_MIN_CONFIDENCE=high|medium|all` 或 `voc build --min-confidence ...` 切换。
- `medium` 与 `low` 的 aspect 全部弃权：不进入 `annotations`，不参与任何计数。

## 2 实测分布

### 2.1 全量 corpus

| 置信度 | aspect 数 | 占 225 的比例 | 含该档 aspect 的记录数 | gold aspect 数 | gold TP | gold FP | strict precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| high | 165 | 73.3% | 91 | 46 | 40 | 6 | 87.0% |
| medium | 58 | 25.8% | 51 | 18 | 11 | 7 | 61.1% |
| low | 2 | 0.9% | 2 | 0 | 0 | 0 | — |

按来源：

| 来源 | high | medium | low |
| --- | ---: | ---: | ---: |
| Reddit | 30 | 15 | 2 |
| TikTok Shop | 135 | 43 | 0 |

26 条记录同时含多个置信档。门槛按 aspect 生效，不按整条记录丢弃。

### 2.2 gold set 分层

`eval-result.json` 的 `precision_by_confidence_strict`：high 46 个 aspect，TP 40，FP 6，precision 87.0%；medium 18 个，TP 11，FP 7，precision 61.1%；low 0 个。

## 3 判定标准（从实际标注反推）

本节记录冻结标注里可观察到的边界。`high` 的定义就是 `ALL.jsonl` 中已经写下的标签。门槛原样采信它，不重新打分，也不改写历史标注。

### high

span 直接说出对产品的判断，方向明确，读者不需要补一步推断。可以是短句，也可以是总体评价。

实际例子：`Very comfortable`、`it doesn't slide around as much`、`I love it`、`Velcro wouldn't stay latched.`、`No me gustó`。明确否定同样可以是 high；否定不等于低置信。

### medium

需要一步推断、转述或归因才能得到属性判断。实际出现的形态：

1. 省略片段：`And support.`、`Supports`。
2. 总体推荐或购买意向代替属性证据：`Would definitely order again`、`I don't recommend it`。
3. 第三方转述：`My wife loves the belt`、`My daughter in law loved it.`。
4. 假设或预测：`If you get one, maybe size up 1 or 2 sizes`、`you will sweat a lot`、`it will ride up and move`。
5. 弱化或偶发：`does help sometimes`、`sometimes wearing belly band helps`。
6. 混杂归因：`Belly band + yoga ball have helped my lower back`、`the combo felt way better`。
7. 非英语或语法不完整片段：`no la puedo acomodar bien en mi vientre`。
8. 否定反面需要两步：`Isn't uncomfortable`。

边界噪声：泛化夸奖并非一律 medium。`I love it` 是 high，`I like it` 是 medium。标签是模型判断，v1 不把它改写成确定性规则。

### low

归因依赖条件、语气或上下文，存在另一种合理解读。

实际例子：`A belly band seems to make things worse`、`which some had been remedied during the day by KT tape or a belly band`。全量只有 2 个，gold set 中为 0。契约 §5 的定义（依赖语气、反讽或上下文）与实际标注一致。

## 4 为什么门槛是 high

- high precision 87.0%，medium 61.1%，相差 25.9 个百分点。
- FP 率：high 6/46 = 13.0%；medium 7/18 = 38.9%。
- high 仍有 6 个 FP，集中在三类：support 族边界 2（如 `Almost fully takes away the sciatica` 编成 SUP.BACK，gold 用 SUP.PRESSURE_OFFLOAD）、极性模糊 2（`experienced some stomach discomfort`、`I wish it added just a little more support`）、跨产品范围 2（Reddit 记录说的是别的护带）。high-only 降低 FP，但不能清零。
- medium 的 7 个 FP 集中在推断型模式：泛化夸奖 2、support 族边界 1、极性模糊 1、他人泛称 1、推荐 vs 总体 1、排除语义 1。
- 反面代价：Reddit 在 high-only 下 precision 50.0%、recall 25.0%，低于 all 模式的 62.5% / 62.5%。总体提升来自 TikTok（42 个 high aspect，90.5% / 49.4%）。不能把 high-only 说成所有来源都变好。

## 5 代价（实测，2026-10-30）

| 模式 | corpus aspect 注解 | 有 aspect 的记录 | 弃权审计行 | strict P/R ALL | TikTok P/R | Reddit P/R | C13 决定性 / 同向 / 反向 / 一致度 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| all | 223 | 116 | 0 | 79.7 / 60.0 | 82.1 / 59.7 | 62.5 / 62.5 | 40 / 31 / 9 / 77.5% |
| medium | 221 | 114 | 2 | 79.7 / 60.0 | 82.1 / 59.7 | 62.5 / 62.5 | 40 / 31 / 9 / 77.5% |
| high | 164 | 90 | 60 | 87.0 / 47.1 | 90.5 / 49.4 | 50.0 / 25.0 | 32 / 26 / 6 / 81.2% |

说明：全量有 225 个 aspect，但 all 模式只有 223 个 aspect 注解。差值是 2 个极性为 `unknown` / `mixed` 的 aspect，它们本来就按弃权处理。high 的 165 个 aspect 中，1 个极性为 `unknown`，所以 high 模式是 164 个注解。

代价：

- 丢掉 60/225 = 26.7% 的 corpus aspect；注解从 223 降到 164（-59）。
- gold set 上 coder aspect 从 64 降到 46（-28.1%）；recall 从 60.0% 降到 47.1%（-12.9 个百分点）；precision 从 79.7% 升到 87.0%（+7.3 个百分点）。
- C13 的决定性记录从 40 降到 32（-20%）；同向 31→26，反向 9→6，一致度 77.5%→81.2%。等级仍是 Directional（n_records=32、n_authors=31、agreement=81%、single_coded）。
- 只有 2 条 claim 的文本或数字变化：C04（negative annotation 17→13 等）和 C13。没有任何 claim 变成 Evidence gap，grade 分布不变。

## 6 结构性天花板（门槛不能解决）

1. gold set 有 2 个 `qualified_positive` aspect。本轮冻结的编码产物是在旧契约下生成的（契约当时禁止该值），所以严格口径下这些 gold aspect 在本轮产物中仍无法匹配。裁决 C 已让契约与 taxonomy 接受 `qualified_positive`；下一次重新编码后极性天花板移除，但这 2 条仍受 code 天花板（裁决 B）约束。
2. 有 2 条 gold 记录的 aspect 数超过契约的 6 条上限（14 和 8 条）。按上限截断后，最多 10 个 gold aspect 结构性不可得。

后果：47.1% 的 recall 不全是置信度代价。即使 high-only 编码完全正确，严格 recall 也达不到 100%。

## 7 冻结与审计

- 定义：`high` 即冻结产物中的标签。实现按 `low=0 < medium=1 < high=2` 排序，保留 rank ≥ 门槛的 aspect。不重新打分，不把 medium 提升为 high。
- 审计文件：`artifacts/run-20261029/confidence-dropped.jsonl`。每行含 `canonical_id` / `code` / `polarity` / `confidence` / `evidence_span`，另附 `reason=below_confidence_threshold` 与 `threshold`。
- 被弃 aspect 同步写入 `unknown_aspects`，reason 为 `below_confidence_threshold`，带 span。
- `all` 模式会把审计文件重写为空文件，避免旧审计残留。
- 复现：

```bash
VOC_MIN_CONFIDENCE=all python3 -m voc.cli build --run run-20261029
VOC_MIN_CONFIDENCE=medium python3 -m voc.cli build --run run-20261029
VOC_MIN_CONFIDENCE=high python3 -m voc.cli build --run run-20261029
```

- 改动门槛必须出新版本策略，并重跑 gold eval。不许为了数字调整 confidence 判定。
