# 报告结构夹具

本目录存放 B5 的三个报告合同结构夹具。

**这是结构夹具，不是真实黄金报告。**
真实黄金报告需要 T1、T5、T2 各跑 2 品牌 × 2 市场。

## 这些文件是什么

| 文件 | 模板 | 用途 |
| --- | --- | --- |
| `t1_voc.contract.json` | T1 新品 VOC | 校验合同结构、语义规则与两个渲染器 |
| `t5_compliance.contract.json` | T5 合规预警 | 校验命中、未匹配与空结果三种覆盖状态 |
| `t2_competitor.contract.json` | T2 竞品追踪 | 校验多竞品、多市场与价格证据结构 |

每个文件是一份完整的 `report_contract.json`。它通过 `ReportContract` 结构校验，
也通过 `validate_contract` 语义校验。

## 数据边界

- 全部数据是合成的结构数据。它们不来自真实采集。
- `brand`、`competitor` 与 `url` 都带 `Fixture` 或 `example.com` 标记。
- 每个 claim、evidence 与 run_ledger 行的 `evidence_grade` 都不高于
  `L2_fixture_local`。夹具只能写方法验证。
- 每个文件的 `limits` 都写明夹具身份。`gates` 的 `G-Publish` 都是 `blocked`。
- `coverage` 的记录数很小。它们只演示结构，不表示达到模板阈值。

## 产物哈希

- `artifact.report_html_sha256` 与 `artifact.sop_html_sha256` 留空。
  结构夹具不绑定渲染产物。
- `artifact.contract_sha256` 是夹具内容的真实哈希。
  复核时用 `schemas.report_contract.contract_sha256` 重算。
  该哈希排除 `generated_at` 与 `artifact`。

## 真实黄金报告还缺什么

1. T1、T5、T2 各跑 2 个品牌 × 2 个市场。
2. 每次运行都有未过期的授权与真实成本记录。
3. 每条 claim 达到 `L4_authorized_live`，样本、时间窗与来源数都达到
   `tool_catalog/evidence_thresholds.py` 的阈值。
4. T5 先建 20 条已知通报的 golden set，并达到 100% / 90% 的抽取验收线。
5. 真实评论、价格、通报原文与可点击的原文链接。
