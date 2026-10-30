# VOC 人工双盲校准工具包

本目录让一个人独立标注 20 条原文，再自动计算他与 LLM 的 Cohen's kappa。
标注过程是盲的：标注者看不到任何 LLM 标注结果。

目录：`/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/calibration/`

## 1 为什么做这一步

当前的 high-only、strict 精度是：

| 来源 | TP | FP | high aspect | gold aspect | P | R |
|---|---:|---:|---:|---:|---:|---:|
| TikTok | 38 | 4 | 42 | 77 | 90.5% | 49.4% |
| Reddit | 2 | 2 | 4 | 8 | 50.0% | 25.0% |
| ALL | 40 | 6 | 46 | 85 | 87.0% | 47.1% |

这张表要分信源读。TikTok 的 90.5% 已达标；Reddit 只有 4 个 high aspect，错 2 个就掉到 50.0%。
把两者合并成 87.0% 会同时高估 Reddit、低估 TikTok。

更关键的是：**当前 87.0% 是 LLM 对 LLM 的一致性，不是人工验证。**
gold set 冻结不改；本工具包产出第一份独立人工证据。

## 2 三步操作

### 第一步：打开标注页

双击 `label.html`。macOS 也可以运行：

```bash
open /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/calibration/label.html
```

页面是单文件，无 CDN、无外部字体、无网络请求。断网可用。

标注者只能看 `label.html`。不要打开：
`mapping.json`、`llm-coding/coded/ALL.jsonl`、`eval-result*.json`、`gold-set-50.jsonl`、`kappa-report.md`。

### 第二步：标完 20 条并导出

1. 先回答「这条在评价产品吗？」。选「否」时选择原因。
2. 选「是」后，从 taxonomy 多选 aspect；每个选中的 aspect 必须选极性。
3. 建议粘贴支撑原文片段。导出时不是必填。
4. 顶部显示「第 N/20 条」和完成数。进度自动保存在本机浏览器。
5. 标完点底部「导出我的标注」，得到 `voc-human-labels-YYYYMMDD-HHMM.json`。

### 第三步：计算 kappa

```bash
cd /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/calibration

python3 compute-kappa.py \
  --human ~/Downloads/voc-human-labels-20261030-1041.json
```

默认输出：`kappa-report.md`。

本目录当前已有一份 `kappa-report.md`，顶部标了 `SELF-TEST SAMPLE / 自验样例`。
它由 `selftest/fake-human-labels.json` 生成，不是真实校准结果。真实运行会覆盖它。

可选机器可读指标：

```bash
python3 compute-kappa.py \
  --human ~/Downloads/voc-human-labels-20261030-1041.json \
  --json-out kappa-metrics.json
```

常用参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--sample` | `blind-sample.jsonl` | 盲样本 |
| `--mapping` | `mapping.json` | item_id 到 canonical_id 的映射 |
| `--coded` | `../llm-coding/coded/ALL.jsonl` | LLM 编码结果 |
| `--min-confidence` | `high` | LLM 参考口径：`high` / `medium` / `all` |
| `--out` | `kappa-report.md` | Markdown 报告 |
| `--top-n` | `5` | 分歧清单条数 |

## 3 文件说明

| 文件 | 用途 | 给标注者看？ |
|---|---|---|
| `label.html` | 离线标注界面，已内嵌 20 条原文和 taxonomy | 是 |
| `blind-sample.jsonl` | 20 条盲样本，只有 `item_id/source/title/text/rating` | 可以，但通常用 HTML |
| `mapping.json` | `item_id` 到 `canonical_id` 的映射 | **否** |
| `sample-manifest.json` | seed、抽样总体、数量、哈希 | 否 |
| `compute-kappa.py` | 计算 kappa 并生成报告 | 否 |
| `build-calibration.py` | 重新抽样并生成 `label.html` | 否 |
| `label.template.html` | 标注页模板，构建时注入数据 | 否 |
| `selftest/` | 自验用的假标注和校验脚本 | **否**，不是真实标注 |

## 4 kappa 怎么算

### 4.1 统计单元

对每条原文、每个 taxonomy aspect，比较两个标注者的二值判断：**这个 aspect 是否出现**。
一个单元格 = 一个 `(item, aspect)` 对。20 条 × 34 个 aspect = 680 个单元格。

四格计数：

| | LLM 标了 | LLM 没标 |
|---|---:|---:|
| 人标了 | a | b |
| 人没标 | c | d |

```text
po = (a + d) / n
pe = ((a+b)(a+c) + (c+d)(b+d)) / n²
κ  = (po - pe) / (1 - pe)
```

`κ = 1` 完全一致；`κ = 0` 等于随机；`κ < 0` 低于随机。
`pe = 1` 时 κ 无定义，报告写 `n/a`。

### 4.2 三个层次

- **逐 aspect κ**：每个 aspect 在自己的 20 条上算一个 κ。
- **分信源 κ**：TikTok 12 条、Reddit 8 条分别算。`ALL` 只做汇总，不能替代分信源结论。
- **micro / macro**：
  - `micro κ`：把同一信源内所有 `item×aspect` 单元格池化后算一个 κ；
  - `macro κ`：逐 aspect κ 的算术平均。

### 4.3 极性和产品体验判定

- **极性一致率**：只统计双方都标了同一个 aspect 的单元格。报告 exact（极性完全相同）和 family（把 `qualified_positive/qualified_negative` 折叠成正/负）。
- **产品体验判定**：只看「这条在评价产品吗？」的是/否，单独算一个 2×2 κ。

### 4.4 低阳性比例陷阱

20 条 × 34 aspect 里，大多数单元格是「双方都没标」。这些单元格会抬高一致率和 micro κ。
例如自验里故意漏掉 33.3% 的阳性 aspect，micro κ 仍有 0.792。
因此：

- 不要只看 micro κ；
- 要看逐 aspect κ、macro κ；
- 要看 `presence mismatch`（一方标了、另一方没标）；
- 要看第 7 节的 top 5 分歧清单。

## 5 门槛和读法

| κ | 等级 |
|---:|---|
| ≥ 0.80 | almost perfect（几乎完全一致） |
| ≥ 0.60 | substantial（实质一致） |
| ≥ 0.40 | moderate（中等） |
| ≥ 0.20 | fair（一般） |
| ≥ 0 | slight（轻微） |
| < 0 | poor（差，低于随机） |

- **0.60 是合格线**：≥0.60 为 substantial。
- **0.80 是高标准线**：ref 的 G7 用 0.80。达到 0.80 才算 almost perfect。
- 触发 top 5 的条件：总体 κ < 0.60，**或任一 aspect 的 κ < 0.60**。
- 20 条样本很小。逐 aspect κ 不稳定。把结果当作方向性证据，不要当作精确精度。
- 发现定义歧义时，改 taxonomy 定义并重新抽样。不要在这 20 条上反复调参，也不要改 gold set。

## 6 盲标规则

**这一步不能自动化，必须由一名真人独立完成。**
不能让 LLM 代标，也不能用已有的 LLM 结果反推答案。

1. 标注者只看 `label.html`，不看任何自动标注或评估结果。
2. 标注者独立判断，不与其他标注者讨论这 20 条。
3. 不能让 LLM 代替人填写标注。那会复制同一套偏差，kappa 失效。
4. 标注中途不要打开 `mapping.json`。它能把 `item_id` 映射回语料 ID。
5. 如果标注者已经看到 LLM 结果，这次校准作废，换人或换样本重做。

页面本身不含任何 LLM 标注结果，也没有「参考答案」入口。

## 7 自验

自验用一份故意错的假标注，证明脚本能跑通、算术正确、分歧清单能生成。
假标注不是真实人工数据。

```bash
cd /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/calibration

python3 selftest/make-fake-labels.py

python3 compute-kappa.py \
  --human selftest/fake-human-labels.json \
  --out selftest/kappa-report-selftest.md \
  --json-out selftest/kappa-metrics-selftest.json

python3 selftest/verify-hand-calc.py
```

假标注的构造：

- 从 LLM 的 33 个 high aspect 出发；
- 每第 3 个删掉，共删 11 个 = **33.3% presence 分歧**；
- 保留的 aspect 中每第 4 个翻转极性，共 5 个；
- 因此同时测试 presence kappa、极性表和 top 5。

自验结果：

| 信源 | 条数 | 一致率 | κ (micro) | κ (macro) |
|---|---:|---:|---:|---:|
| TikTok | 12 | 97.8% | 0.758 | 0.675 |
| Reddit | 8 | 99.3% | 0.871 | 0.743 |
| ALL | 20 | 98.4% | 0.792 | 0.727 |

手算核对（ALL，`SUP.GENERAL` 总体支撑）：

```text
a = 2（双方都标）
b = 0（只有人标）
c = 3（只有 LLM 标）
d = 15（双方都没标）
n = 20

po = (2 + 15) / 20 = 0.85
pe = ((2)(5) + (18)(15)) / 400 = 0.70
κ  = (0.85 - 0.70) / (1 - 0.70) = 0.50
```

脚本输出同为 `0.500`。独立校验脚本还会逐项重算全部 34 个 aspect、三个信源的 micro κ、产品体验判定 κ 和 top 5 排序。

自验的 top 5 分歧 aspect：

1. `SUP.GENERAL` 总体支撑
2. `GEN.OVERALL_EVALUATION` 总体评价
3. `COM.SKIN_CHAFE` 皮肤摩擦
4. `COM.SOFTNESS` 柔软触感
5. `VAL.PRICE_VALUE` 价格价值

最后一行应为：

```text
ALL CHECKS PASSED
```

注意：micro κ = 0.792 看起来不低，但假标注实际漏了 33.3% 的阳性 aspect。
680 个格子里有 647 个是「双方都没标」，所以 micro κ 被抬高。
这正是报告同时给出逐 aspect κ、macro κ 和 top 5 的原因。

## 8 边界

- **gold set 未改动。**
- **counting / evidence / claims 的评级逻辑未改动。**
- 本工具包只新增文件，不修改现有管线代码。
- 样本只从「至少有一个 high aspect」的记录里抽。它不是全语料随机样本，不能当 precision/recall 估计。
- 20 条用于发现系统性问题，不用于精确估计。需要更高置信度时，换 seed 重新抽样，再找另一名标注者独立标注。
- `mapping.json` 是唯一能把盲样本映射回语料 ID 的文件。不要给标注者看。

## 9 故障排查

| 现象 | 处理 |
|---|---|
| 双击 `label.html` 空白 | 确认打开的是生成的 `label.html`，不是 `label.template.html` |
| 导出没有下载 | 换 Chrome / Edge 打开；检查浏览器下载权限 |
| 进度丢了 | 进度在浏览器 localStorage。不要清浏览器数据，换回同一浏览器/配置 |
| `人工标注缺了样本条目` | 20 条没有全部回答。回到页面补齐再导出 |
| `sample_id 与 mapping 不一致` | 导出的文件不属于本样本。用本目录的 `label.html` 重新导出 |
| `aspect code 不存在` | 标注文件被手工改过。重新从页面导出 |
| `判定为「否」却带了 aspect` | 手工改坏了。重新从页面导出 |

## 10 重新抽样

当前样本固定 seed `20261030`，可复现：

```bash
python3 build-calibration.py
```

换 seed：

```bash
python3 build-calibration.py --seed 20261031
```

重跑会覆盖 `blind-sample.jsonl`、`mapping.json`、`sample-manifest.json`、`label.html`。
旧的标注文件不能再用于新样本。
