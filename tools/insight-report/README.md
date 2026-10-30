# insight-report — 可运行的 VOC 洞察报告生成器

本目录把 `ref/` 的自动化洞察报告逆向为可执行管线。输入是一次 run 的真实 artifacts，输出是 `report-data.json` 与单文件 `report.html`。不联网，不引入第三方库，不编造数字。

## 一条命令

```bash
cd /Users/lute/Project/data_scrapy/tools/insight-report/ir_impl
python3 build.py --run input/run-20261029 --out out/run-20261029
```

输出：

| 文件 | 内容 |
| --- | --- |
| `out/run-20261029/report-data.json` | 唯一渲染输入；符合 `schema.json` |
| `out/run-20261029/report.html` | 单文件报告；CSS 与 JS 内联；可离线打开与打印 |
| `out/run-20261029/validation-result.json` | 数据与 HTML 的逐项校验结果 |
| `out/run-20261029/delivery-manifest.json` | 产物 sha256 |

单独运行：

```bash
python3 assemble.py --run <run_dir> --out <report-data.json>
python3 validate.py --data <report-data.json>
python3 render.py --data <report-data.json> --out <report.html>
python3 validate.py --html <report.html> --data <report-data.json>
python3 selftest.py
```

## 文件

| 文件 | 职责 |
| --- | --- |
| `schema.json` | DATA-CONTRACT 的机器可读版本；`validate.py` 内置 JSON Schema 子集校验器 |
| `assemble.py` | 从 run artifacts 组装 `report-data.json`；数字全部来自 artifact 或确定性计算 |
| `validate.py` | fail-closed 校验：schema、四问、七件套、四键脚注、六级状态、Hero 比值、反模式 |
| `render.py` | 读 JSON，调用分节模板，输出单文件 HTML |
| `charts.py` | 10 类纯 CSS 图表；签名统一为 `chart_xxx(data) -> str` |
| `templates/` | Hero、shell、claim、exhibit、readout、source-foot、status-legend、prohibited、omissions |
| `templates/sections/` | 11 个独立可插拔 section 函数（00–10） |
| `styles.py` | 全部内联 CSS；浅色/深色/打印/移动端 |
| `selftest.py` | 14 项自检；包含 fail-closed 负向测试 |
| `ir_contract.py` | 共享常量；隔离命名，避免与同目录其他实现冲突 |

## Fail-closed 规则

- `validate.py` 缺 required 字段、四问缺一栏、七件套缺一件、source-foot 缺一键、证据状态非法，都退出非零。
- Hero 的 4 个数字只允许比值（`3 / 27`）、缺口（`250 → 248`）或零缺口（`0 metric rows`）。总量型数字直接 `assert` 失败。
- 每张图自动附 `Basis / Unit / Limit / Status` 四行。缺失参数渲染 `UNKNOWN`，不省略。
- 每个结论块强制 4 栏。缺栏渲染红色 `EVIDENCE INCOMPLETE` 占位；正常构建在校验阶段就会失败，不会写出最终 HTML。
- `prohibited_outputs` 必须是 footer 前最后一个实质 block。
- 07 节 `SOCIAL FIREWALL` 因 `evidence.social` 为空整节省略。省略原因写入可见的“本报告省略了什么”。
- 反模式拦截：总体情绪率、饼图百分比、NPS、ROI 排名、净值打分、把覆盖当漏斗、跨 frame 百分比。`导致` / `漏斗` / `满意率` 只在显式否定句式中放行。

## 真产出

本轮报告来自 `input/run-20261029`（`voc_pipeline/artifacts/run-20261029` 的冻结快照；728K；10 个输入文件）：

- 10 个 section（07 省略）、9 个 exhibit、11 条 claim。
- 248 canonical records 来自 250 occurrences；2 条重复合并，跨 frame membership 257。
- G7 BLOCKED；metric rows = 0。
- 每条 claim 的数字带 `source_path`；每个 exhibit 带四问与四键脚注。
- 深色模式、打印、1200px 与 390px 均无横向溢出；零控制台错误。

## 已知边界

- 没有社媒池，所以没有 07 节与 E07。
- 没有逐变体评论计数，variant 网格的 review_count 全部是 `[Evidence gap]`。
- 没有 G7 第二编码员，所有体验结论最高为 Supported hypothesis；正式指标为 0。
- 没有 TikTok SKU ↔ Amazon ASIN crosswalk，两个来源不合并。
- Amazon 评论正文返回 302，DTC/Okendo 未配置；这两类证据不出现。
- `key_aspects` 从 21 个 observed aspect code 中选 12 个，选择规则写在 E02 drawer。

## 验证命令与结果

```bash
python3 build.py --run input/run-20261029 --out out/run-20261029
python3 validate.py --data out/run-20261029/report-data.json
python3 validate.py --html out/run-20261029/report.html --data out/run-20261029/report-data.json
python3 /Users/lute/Project/data_scrapy/ref/extract/validate_report.py out/run-20261029/report.html --strict
python3 selftest.py
```

实测：build PASS；data 14/14 checks PASS；HTML 10/10 checks PASS；ref validator PASS；selftest 14/14 PASS。
