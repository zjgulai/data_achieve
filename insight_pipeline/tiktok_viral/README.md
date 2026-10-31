# TikTok 母婴爆款选题分析管线

一句话：从 288 条已爆 TikTok 母婴视频的 deepread 标签里，回答“拍什么、哪些能照拍、评论区在要什么”。

本目录保存分析脚本、输入导出和中间产物。最终报告包在仓库另一处：

```text
tools/insight-reports/tiktok-viral-topic/2026-10-31/
  manifest.json      # 导入清单；字节数与 SHA-256 校验
  report.html        # 182,450 字节，单文件，六张内联 SVG
  report.md          # 55,510 字节，可编辑源，不导入
```

`report.html` 是 `/insight/new` 的导入源。导入器按 `manifest.json` 校验，不读本目录的中间产物。

## 1. 数据来源

数据来自本地 Docker 容器 `abi_migtest` 的 `abitest` 库，只读。生产环境没有这份数据。

| 表 | 行数 | 用途 |
| --- | ---: | --- |
| `raw.si_tiktok_video` | 31,366 | 392 个 hashtag × 43 天的采样池 |
| `raw.si_tiktok_comment` | 47,073 | 评论区需求挖掘 |
| `raw.si_tiktok_hashtag_snapshot` | 102,153 | hashtag 快照 |
| `raw.si_metric_snapshot` | 4,856 | 指标快照 |
| `raw.si_author_video_snapshot` | 904 | 9 个竞品账号，136 条去重视频 |

- 采集窗口：2026-10。数据最后写入：2026-10-28。
- 样本：392 个 hashtag × 43 天，每个 tag 取榜单 top20；其中 288 条带 deepread 的 `theme_tags` 与 `mechanism_tags`。
- `deepread288.tsv` 是这 288 条的导出，9 列：`video_id`、`hashtag`、`peak_play`、`digg`、`comment`、`share`、`theme_tags`、`mechanism_tags`、`caption`。
- `data/comments_all.tsv` 是 47,073 条评论的原始导出，11 列。它是 `comments.json` 的唯一原始输入，不能从生产重新采集。

## 2. 跑一次

```bash
cd insight_pipeline/tiktok_viral
bash run.sh
```

`run.sh` 固定 `PYTHONHASHSEED=0`，用于稳定并列排序。逐步命令：

```bash
cd insight_pipeline/tiktok_viral
export PYTHONHASHSEED=0

python3 -B final_analysis.py        # mech-clusters.json + mech-clusters.md
python3 -B render_md.py             # 覆盖 mech-clusters.md，生成完整版
python3 -B build_replicability.py   # replicability.json
python3 -B saturation_analysis.py   # saturation.json
python3 -B tools/gen_json.py        # comments.json
python3 -B gen_charts.py            # 写入报告包 report.html
python3 -B verify.py                # 只读校验
```

`theme-clusters.json` 是冻结输入，不由脚本生成。它包含 13 个母题、993 个 theme 到母题的映射，以及 `assigned_by`（`manual` 或 `rule:关键词`）。原生成脚本未保留；改品类时要重新制作这份映射。

## 3. 每一步产出什么

| 步骤 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `final_analysis.py` | `deepread288.tsv` | `mech-clusters.json`、`mech-clusters.md` | 806 个 mechanism 归入 10 族；JSON 含矩阵、Top 5、季节性拆分 |
| `render_md.py` | `mech-clusters.json`、`deepread288.tsv` | `mech-clusters.md` | 覆盖上一步的简版 Markdown，生成完整报告 |
| `build_replicability.py` | `deepread288.tsv`、`theme-clusters.json`、`mech-clusters.json` | `replicability.json` | 288 条逐条分档：高/中/低/无法判断 |
| `saturation_analysis.py` | `deepread288.tsv`、`_si_tag_stats.tsv`、`_competitor_videos.tsv`、`_brand_snapshot_summary.tsv`、两份 cluster JSON | `saturation.json` | 竞争饱和、空白、竞品对照、行动假设 |
| `tools/gen_json.py` | `data/comments_all.tsv`、`tools/labels.json`、`top500.tsv`、`rand500.tsv` | `comments.json` | 评论意图、问题、季节性、机会 |
| `gen_charts.py` | `parts/*.html`、`parts/figures/*.svg` | 报告包 `report.html` | 拼接正文，内联六张 SVG |
| `verify.py` | 以上全部 | 标准输出 | 失败退出非零 |
| `classify_replicability.py`（可选） | `deepread288.tsv`、`theme-clusters.json` | `data/_classified_first.json` | 早期人工复核中间件，已被 `replicability.json` 取代；不进版本库 |
| `analyze.py`（可选） | `deepread288.tsv` | 终端统计 | 早期探索，无文件产出 |
| `tools/clusters.py`、`tools/mine*.py`（可选） | `data/comments_all.tsv` | 终端输出、`data/questions*.tsv` | 评论探索；TSV 可再生，不进版本库 |

`mech-mapping.tsv` 与 `replicability.tsv` 是报告引用的冻结明细表，由对应 JSON 人工导出，保留用于追溯。

## 4. 目录结构

```text
insight_pipeline/tiktok_viral/
├── README.md
├── run.sh
├── verify.py
├── analyze.py
├── final_analysis.py
├── classify_replicability.py
├── build_replicability.py
├── saturation_analysis.py
├── render_md.py
├── gen_charts.py
├── review_number_diff.py
├── deepread288.tsv                  # 91,815 字节，288 行
├── _si_tag_stats.tsv                # 19,951 字节
├── _competitor_videos.tsv           # 45,958 字节
├── _brand_snapshot_summary.tsv      # 467 字节
├── top500.tsv                       # 29,223 字节
├── rand500.tsv                      # 28,215 字节
├── theme-clusters.json              # 203,588 字节，冻结输入
├── theme-clusters.md                # 32,682 字节
├── mech-clusters.json               # 49,917 字节
├── mech-clusters.md                 # 34,716 字节
├── mech-mapping.tsv                 # 31,237 字节
├── replicability.json               # 418,599 字节
├── replicability.tsv                # 87,373 字节
├── saturation.json                  # 509,593 字节
├── comments.json                    # 56,566 字节
├── parts/                           # 报告正文，重建后与成品逐字节一致
│   ├── _head.html ... _s07_foot.html
│   └── figures/FIG1.svg ... FIG6.svg
├── tools/                           # 评论挖掘脚本
│   ├── gen_json.py
│   ├── labels.json
│   ├── clusters.py
│   ├── mine.py / mine2.py / mine3.py
└── data/
    └── comments_all.tsv              # 13,258,181 字节，47,073 条评论
```

## 5. 已知限制

- 数据是采样，不是全量：392 个 hashtag × 43 天，每个 tag 取榜单 top20；288 条是 deepread 选取结果，不是随机样本。
- 只有 caption 与已有标签，没有字幕、画面、音频或投流数据。不能判断视频内容细节，也不能做因果推断。
- 采集窗口是 2026-10。万圣节相关 64/288（22.2%），季节性会抬高节点类内容的占比。报告同时给出全样本与去万圣节版本。
- `peak_play` 是抓取时的峰值，不是生命周期总播放。
- 评论最多取每个视频 120 条；79 个视频触顶，占评论 24.3%。评论结论是样本内描述。
- `theme-clusters.json` 的 993 条映射含人工覆盖；一个 theme 只归一个母题。换品类后旧映射不适用。
- 报告数字只描述这批视频，不保证拍了一定爆。`saturation.json` 的并列排名可能随 Python 哈希种子变化；`run.sh` 固定种子 0。

## 6. 换品类要改哪里

1. 换 `deepread288.tsv`。保持 9 列和相同列序；`peak_play` 用同一口径。
2. 重做 `theme-clusters.json`。定义新母题，给 993 个或新的 theme 标签建立映射，并记录 `assigned_by`。这是人工/模型判断，不是规则脚本。
3. 改 `final_analysis.py` 的 `FAMILIES` 与 `RULES`。10 个机制族和关键词规则是母婴语料调的。
4. 改 `build_replicability.py`。检查 `CATS` 的逐条类别顺序、`BRAND_TERMS`、分档 rubric 和理由模板。
5. 改 `saturation_analysis.py`。更新 `TOPIC_RULES`、`TOPIC_TO_MOTIF`、竞品列表、`TAG_STATS` 与 `BRAND_SUMMARY` 输入。
6. 改 `tools/gen_json.py`。评论意图正则含多语言，但商品词与场景词要换成新品类。
7. 重写 `render_md.py` 的叙述文本；它把结论写死在代码里。
8. 重建报告：替换 `parts/` 正文与 `parts/figures/` 的 SVG，再跑 `gen_charts.py`。`fig1()..fig6()` 是旧版图表草稿，不用于最终报告。
9. 改 `verify.py` 的期望值：288、13、806、47,073 等都与本批数据绑定。

## 7. 版本库收录边界（.gitignore 判据）

收录：

- 全部分析脚本与 `parts/` 报告构建源。
- 小体量 JSON：`theme-clusters.json`（204 KB）、`replicability.json`（419 KB）、`saturation.json`（510 KB）、`mech-clusters.json`（50 KB）、`comments.json`（57 KB）。它们不是原始数据的重复，而是报告数字的直接来源，改动应可审查。
- 数据导出：`deepread288.tsv`（92 KB）和四份小 TSV 输入。没有它们，核心步骤不能重跑。
- `data/comments_all.tsv`（13.3 MB）。这是唯一一份原始评论导出，源库只在本地，生产没有；丢失后 `comments.json` 不能重建。它是本目录最大的单文件，但仍低于 100 MB，Git 可承受。
- 报告包 `tools/insight-reports/tiktok-viral-topic/2026-10-31/`。导入器按字节校验，必须入库。

不收录：

- `data/questions.tsv`、`data/questions_sorted.tsv`（约 2.3 MB）。可由 `comments_all.tsv` 重新生成。
- `data/_classified_first.json`（约 265 KB）。早期分类复核件，已被 `replicability.json` 取代。
- `__pycache__/`、PDF、PDF 逐页 PNG、`chrome-profile/`、`report-before*.html`、`sections/` 草稿、`_audit_*` / `_review_*` 文本。它们是渲染副本、浏览器缓存或过程稿，不是分析结果。
- 如果将来单个 JSON 超过几十 MB，先 gzip 或放到仓库外，不要直接提交。

## 8. 报告构建源说明

`/tmp` 中的 `parts/` 是旧草稿，与最终 `report.html` 不一致。本次归档从最终成品反向拆出 `parts/` 与 `parts/figures/`：

- `parts/_head.html`、`_s01.html` ... `_s07_foot.html` 按 `<section id="s01">` 等边界拆分。
- 六张内联 `<svg>` 提取为 `parts/figures/FIG1.svg` ... `FIG6.svg`，正文中留 `<!--FIG1-->` 等占位。
- `gen_charts.py` 用 `"".join()` 拼接，并优先读取静态 SVG。重建结果与成品逐字节一致：182,450 字节，SHA-256 `415445711c9fc293d330c34cbb6a273af768348adbefe18739a4318ad31ed8d1`。
- `fig1()..fig6()` 保留为旧图表草稿的兜底，静态图存在时不会调用。

`report.html` 正文里有 44 处 `/tmp/...` 来源路径。导入 manifest 做两段字面量替换：`/tmp/viral/` 替换为空，`/tmp/deepread288.tsv` 替换为 `deepread288.tsv`。替换后正文 181,984 字节，SHA-256 `f7f7c4f0b5483e789740345cff7c115100283b5ec1847cd181ef55e7f00b50dc`。不要手改 `report.html` 或替换规则，否则哈希校验失败。

## 9. 验证结果

- `bash run.sh` 通过，最后输出 `pipeline OK`。
- `python3 -B verify.py` 输出 `PASS`：288 行输入、13 个母题、10 个机制族、288 条可复刻性记录、47,073 条评论；报告包源文件与正文哈希均匹配。
- 连续运行两次，`mech-clusters.json`、`mech-clusters.md`、`replicability.json`、`saturation.json`、`comments.json`、`report.html` 六个产物逐字节一致。
- 与 `/tmp` 原件对比：`mech-clusters.json` 仅 `meta.source` 从 `/tmp/deepread288.tsv` 改为 `deepread288.tsv`，其余相等；`replicability.json` 同样；`comments.json` 完全相等；`report.html` 逐字节相等。
- `review_number_diff.py` 是启发式数字对账，不是门禁。它会报告措辞差异导致的 token 增减，属预期。

## 10. 原路径映射

| 原路径 | 仓库路径 |
| --- | --- |
| `/tmp/deepread288.tsv` | `deepread288.tsv` |
| `/tmp/viral/theme-clusters.json` | `theme-clusters.json` |
| `/tmp/viral/theme-clusters.md` | `theme-clusters.md` |
| `/tmp/viral/mech-clusters.json` | `mech-clusters.json` |
| `/tmp/viral/mech-clusters.md` | `mech-clusters.md` |
| `/tmp/viral/mech-mapping.tsv` | `mech-mapping.tsv` |
| `/tmp/viral/replicability.json` | `replicability.json` |
| `/tmp/viral/replicability.tsv` | `replicability.tsv` |
| `/tmp/viral/saturation.json` | `saturation.json` |
| `/tmp/viral/comments.json` | `comments.json` |
| `/tmp/viral/data/comments_all.tsv` | `data/comments_all.tsv` |
| `/tmp/viral/report.html` | `tools/insight-reports/tiktok-viral-topic/2026-10-31/report.html` |
| `/tmp/viral/report.md` | `tools/insight-reports/tiktok-viral-topic/2026-10-31/report.md` |
| `/tmp/viral/parts/` | `parts/`（按成品重建） |
| `/tmp/viral/tools/` | `tools/` |
