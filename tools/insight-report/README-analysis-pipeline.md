# insight-report analysis pipeline

把 `voc_pipeline/artifacts/run-20261029` 的真实原始数据，跑成符合
`ref/extract/DATA-CONTRACT.md` 的 `report-data.json`，再渲染成单文件
`report.html`。只用 Python 3 标准库；不联网；不读 `ref/`；CSS 全部内联。

这个文件与同目录其他实现隔离：入口是 `build_report.py`，包名是
`insight_report`，输出目录是 `out/insight-report-run-20261029/`。

## 一条命令

```bash
bash tools/insight-report/run-analysis.sh
```

或：

```bash
python3 tools/insight-report/build_report.py \
  --run-dir voc_pipeline/artifacts/run-20261029 \
  --out tools/insight-report/out/insight-report-run-20261029
```

## 产物

| 文件 | 内容 |
| --- | --- |
| `report-data.json` | 唯一渲染输入；11 个 section、14 条 claim、9 个 exhibit、8 条禁止输出 |
| `report.html` | 单文件报告；零外部请求；每图带 Basis/Unit/Limit/Status |
| `validation-result.json` | 382 条 JSON 检查 + 83 条 HTML 检查的逐条结果 |
| `delivery-manifest.json` | 所有产物的 sha256、字节数、生成时间 |
| `ingest-ledger.json` | raw 响应、失败请求、sha256 对账 |
| `identity-freeze.json` | 父/子 ASIN、18 个变体、confidence、缺口 |
| `occurrences.jsonl` / `canonical-records.jsonl` / `coded-corpus.jsonl` | 三层记录 |
| `counting-ledger.json` | 六级计数与逐级扣减原因 |
| `corpus-summary.json` / `metric-summary.json` | 对账与指标 |
| `claims.json` / `evidence-ledger.json` | claim、分级、反证、NumberRef |

## 模块

| 文件 | 职责 | SOP 技能 |
| --- | --- | --- |
| `insight_report/ingest.py` | 读 Arctic Shift raw + Amazon PDP HTML + ledger；校验 sha256 | `voc-source-pilot` 部分 |
| `insight_report/identity.py` | 解析 PDP，冻结 parent/child/variant，写 confidence | `voc-product-identity` |
| `insight_report/counting.py` | raw → occurrence → canonical → frame membership → annotation → metric row | `voc-canonicalize` |
| `insight_report/coding.py` | 关键词规则编码 aspect / polarity / severity / context / journey / outcome / gap / medical | `voc-coding-calibration` 部分 |
| `insight_report/evidence.py` | 六级证据判定、反证槽位、`NO_COUNTEREVIDENCE_FOUND` | `voc-insight-analysis` 部分 |
| `insight_report/metrics.py` | coverage、共现矩阵、需求场景、NumberRef 解析 | 组装辅助 |
| `insight_report/render.py` | 单文件 HTML、10 类图表、7 件套 exhibit | `voc-interactive-report` |
| `insight_report/validate.py` | 机器 schema、30 条不变式、反模式、渲染后检查 | `voc-validation-handoff` |
| `build_report.py` | 串起全流程，写 artifact 与最终报告 | `voc-research-orchestrator` 部分 |

### 14 个 SOP skill 状态

- 已实现：`voc-product-identity`、`voc-canonicalize`、`voc-insight-analysis`、
  `voc-interactive-report`、`voc-validation-handoff`。
- 部分实现：`voc-source-pilot`（只校验血缘，不采集）、
  `voc-coding-calibration`（规则编码已实现，双人 agreement 未实现）、
  `voc-research-orchestrator`（本地编排，不调度人工 gate）。
- 只消费：`voc-taxonomy-freeze`（读冻结 taxonomy）、
  `voc-stratified-collection`（读冻结 ledger）。
- 未实现：`voc-decision-charter`、`voc-source-rights-audit`、
  `voc-strategy-activation`、`voc-measurement-review`。

## 证据与门禁

- 六级状态：Confirmed、Directional、Supported hypothesis、Evidence gap、
  Blocked、Not authorized；判定顺序固定，先命中先停。
- G7 未执行，`metric_rows = 0`，体验结论最高只到 Supported hypothesis。
- 每条 claim / exhibit 都有 Observed / Interpretation / Counterevidence /
  Decision implication 四问。
- 每个 exhibit 都有 `exhibit-head`、`exhibit-scope`、`evidence-badge`、
  `exhibit-body`、`exhibit-readout`、`source-foot`、`evidence-drawer`。
- 反证找不到时写 `NO_COUNTEREVIDENCE_FOUND: ...`。
- 禁止输出清单在正文最后：总体情绪率、饼图百分比、NPS、ROI 排名、净值打分、
  把覆盖当漏斗、跨 frame 百分比比较、把 annotation 当人数、医学结论。

## 数据边界

- 输入只有 Reddit Arctic Shift 公开归档与 Amazon PDP HTML。
- Amazon 评论正文返回 302；DTC/Okendo 未配置；没有问卷。
- 没有第二编码员，G7 保持 BLOCKED。
- 没有 TikTok SKU ↔ Amazon ASIN crosswalk，两源变体不能合并。
- 社媒语料为 0，section 07 输出 Blocked gap。
- `gap` 轴没有非 unknown 标注，`expectation_gap_counts` 全部落到 unknown。

## 扩展点

- 新数据源：实现 `ingest.Reader`，返回 `RawResponse`；下游不用改。
- 新编码器：实现 `coding.Coder.code_record`；`RuleCoder` 是可复算默认实现。
- 新图表：在 `render.CHART_RENDERERS` 注册；`validate` 检查 role/aria-label。
- 新 claim：用 `evidence.make_claim`；grade 必须由 `grade_inputs` 机械复算。

## 自检

```bash
python3 -m unittest discover -s tools/insight-report/tests -v
```