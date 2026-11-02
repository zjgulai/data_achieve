# 报告语言与数字闸门（2026-11-03）

## 1. 目标

业务报告交付前，自动检查四类问题：

1. 禁用术语。用读者能懂的话替换行话。
2. 孤立百分比。每个百分比要有分母。
3. 图表缺来源或缺统计范围。
4. 报告缺证据等级，也没有声明描述性归档。

闸门失败时退出 1。导入器遇到失败时拒绝导入。

## 2. 单一实现

闸门只有一份实现和一份词表：

- 实现：`apps/api/src/data_intelligence_hub/report_quality/`
- 词表：`apps/api/src/data_intelligence_hub/report_quality/rules.json`
- CLI：`python -m data_intelligence_hub.report_quality.cli`
- 仓库入口：`scripts/check_report_language.py`（只做路径转发）

不新建第四个校验器。`tools/insight-report/validate.py` 增加 `--gate` 模式，复用同一实现。`tools/insight-report/ir_impl/validate.py` 重复副本已删除。

## 3. 检查规则

### 3.1 禁用术语

词表来自 `.claude/skills/report-review/SKILL.md` 第二步：样本不足、样本量偏小、接近下限、外推、显著、p 值、置信区间、归因、口径、结构化、赋能、抓手、闭环、沉淀、建议关注、维度、层面、颗粒度。

allowlist 只放两类：

- 明确的否定用法，例如「不能往外推」。
- 既有报告的结构标签，例如「关键数字 · 口径」和「维度 / 数量 / 零散情况」表头。

### 3.2 分母

百分比在以下任一上下文里有分母词，就算通过：

- 同一文本块 20 字以内。
- 同一段落、列表项、表格单元格。
- 所在图表或表格容器。
- 章节标题的下一个图表或表格。

分母词：条、样本、记录、总数、视频、账号、评论、组、行、次、例、分母，以及 `分子/分母` 形式。

禁写示例块（含「不能写」「不能把」「不能说」等）里的百分比不检查。这些是反例，不是报告结论。

### 3.3 图表与证据

- 每张图必须有数据来源和统计范围。
- 报告必须在 manifest 写 `source_status=snapshot_only`，或在正文写证据等级/描述性归档。
- `--strict` 要求 manifest 有 `generated_at`，或正文有日期。

## 4. 接入点

| 位置 | 行为 |
|---|---|
| `import_insight_report.validate_bundle` | fail-closed；失败抛 `InsightImportError` |
| `tools/insight-report/validate.py --gate` | 命令行模式；退出 0/1 |
| `.github/workflows/ci.yml` | 对当前 `report.html` 跑 `--strict` |
| `scripts/daily-report.sh` | advisory；只写 `REPORT_LANGUAGE_GATE=pass|fail`，不阻断 |

日报是内部成果总结，不是业务报告。report-review skill 明确不把内部复盘纳入业务报告审阅。因此日报只记录，不阻断。业务报告的导入和 CI 是 fail-closed。

## 5. 验收证据（2026-11-03）

- 63 词夹具：`apps/api/tests/fixtures/report_language_63.html`，命中 63 条禁用词，退出 1。
- 当前报告：`tools/insight-reports/tiktok-viral-topic/2026-10-31/report.html`，PASS；检查 279 个百分比、6 张图；证据为 `descriptive_archive`。
- 单测：`apps/api/tests/unit/test_report_language_gate.py` 10 passed；导入器测试 11 passed。
- 反例测试：加 1 个裸百分比、加 1 个禁用词、图表缺来源，均失败。

## 6. 已知限制

- 分母按文本块与容器判断，不是严格的 20 字全局限定。复杂排版可能漏判或误判。
- allowlist 里的「维度」表头是既有报告的例外。新报告不应再使用该词。
- VOC 报告仍用 `voc_pipeline/voc/validate_report.py` 的 12 条禁写结论；本闸门只覆盖 insight 报告与通用业务报告。
- 日报的 advisory 结果需要人工看日志；后续可把日报 prompt 的术语改干净，再考虑 fail-closed。

## 7. 复现

```bash
python3 scripts/check_report_language.py \
  --html tools/insight-reports/tiktok-viral-topic/2026-10-31/report.html \
  --manifest tools/insight-reports/tiktok-viral-topic/2026-10-31/manifest.json \
  --strict

cd apps/api && uv run pytest -q tests/unit/test_report_language_gate.py
```