# 裁决 D：报告表述

## 0. 最终裁决

**把“5 个模型家族的跨模型一致率 / 独立盲标”全部改成“同一模型族在 5 个身份提示下的同族自一致”。报告里不能把“独立验证”“跨模型验证”“模型家族”当作事实陈述；否定句（“不是跨模型独立验证”）可以保留。**

一句话：**5 个标注者不是 5 个模型；κ=0.8354 是同一模型换 5 个身份提示的稳定性，不是独立验证，也不是人工准确率。**

## 1. 事实基础

### 1.1 实际模型

`~/.claude/settings.json`：

```json
"CLAUDE_CODE_SUBAGENT_MODEL": "group/auto-deepseek-flash:max[1m]"
```

5 个标注身份是 `sol`、`terra`、`luna`、`g55`、`mini`。它们全部运行在 DeepSeek Flash 系列（`deepseek-flash` / `deepseek-v4.1-flash`；路由 `group/auto-deepseek-flash:max[1m]`）。

**`sol` / `terra` / `luna` 这些名字是身份提示，不是模型家族。** 它们看起来像 GPT 模型名，这正是当前报告措辞会误导读者的原因。报告里必须写明“标注身份”，不能写“模型家族”。

发布前复核：如果某次运行对单个标注者用了 per-agent model override，以 override 为准；没有 override 时，以上述 settings 为准。

### 1.2 现在的数字是什么

`calibration/cross-model/cross-model-stats.json` / `cross-model-report.md`：

| 范围 | presence Fleiss κ | 说明 |
| --- | ---: | --- |
| ALL | 0.8354 | 20 条 / 680 个 item×aspect 格 |
| TikTok | 0.8525 | 12 条 |
| Reddit | 0.7357 | 8 条 |

- 有标注格 49 / 680；present 仅 5.4%；631 个格是 5 人共同未标注。
- 所以 κ 主要由“都认为没提”驱动，不是“都标得一样好”。
- `is_product_experience` 的 κ 是 0.6562（`cross-model-report.md` §6），4 条分歧是 B01、B06、B13、B16。这个数字受裁决 A 的文档冲突影响，不能当作体验定义的一致性证据。

### 1.3 必须同时说清的三件事

1. **这是同族自一致**：说明实际模型是 DeepSeek Flash 系列，5 个只是身份提示。
2. **它比单次自证强在哪**：同一模型在不同身份提示下仍能稳定复现同一批 aspect 的 present/absent 判断；它检验的是提示稳健性，不是模型多样性。
3. **它不是独立验证，不是人工准确率**：没有第二个模型家族，没有人工双盲；κ 主要来自共同未标注。

## 2. 逐处替换（`voc/report.py`）

### 2.1 第 501 行附近：docstring

现在：

```python
    """Three-row evidence basis: LLM-vs-gold, cross-model, human validation.

    The rows must stay separate.  The gold row is self-证 (LLM labels checked
    against an LLM-built gold set); the cross-model row is independent model
    agreement; the human row is still missing while G7 is blocked.  None of
    the three is a human accuracy estimate.
    """
```

改为：

```python
    """Three-row evidence basis: LLM-vs-gold, same-model multi-prompt, human validation.

    The rows must stay separate.  The gold row is self-证 (LLM labels checked
    against an LLM-built gold set); the second row is same-model agreement
    under different identity prompts, not independent model agreement; the
    human row is still missing while G7 is blocked.  None of the three is a
    human accuracy estimate.
    """
```

### 2.2 第 519–524 行：`cross_meaning`

现在：

```python
        cross_meaning = (
            "5 个模型家族独立盲标的跨模型一致性；不是准确率，也不是人工验证。"
            f"{cm['n_items']} 条 / {cm['n_cells']} 个 item×aspect 格；"
            f"有标注 {cm['annotated']} 格，present 仅 {cm['prevalence_pct']:.1f}%，"
            "κ 主要由共同未标注驱动。"
        )
```

改为：

```python
        cross_meaning = (
            "5 个标注身份（sol / terra / luna / g55 / mini）全部运行在 DeepSeek Flash 同一族"
            "（group/auto-deepseek-flash:max[1m]，实际为 deepseek-flash / deepseek-v4.1-flash），"
            "所以这是同族自一致，不是跨模型独立验证。"
            "它比单次自证多出的信息是：同一模型族在 5 个不同身份提示下仍能稳定复现同一批 aspect 的 present/absent 判断；"
            f"{cm['n_items']} 条 / {cm['n_cells']} 个 item×aspect 格；"
            f"有标注 {cm['annotated']} 格，present 仅 {cm['prevalence_pct']:.1f}%，"
            "κ 主要由共同未标注驱动。它不是独立验证，也不是人工准确率。"
        )
```

### 2.3 第 527 行：没有 artifact 时的 fallback

现在：

```python
        cross_meaning = "跨模型一致率未做；不能用它替代人工准确率。"
```

改为：

```python
        cross_meaning = "同模型多提示一致率未做；不能用它替代人工准确率。"
```

### 2.4 第 538 行：表格行标签

现在：

```python
        "<td>跨 5 模型一致率（新）</td>"
```

改为：

```python
        "<td>同模型多提示一致率（新）</td>"
```

### 2.5 第 545–546 行：表格下方 micro 说明

现在：

```python
        "<div class='micro'>跨模型一致率不是人工准确率；共识不是 truth oracle。"
        "三行并列是为了区分“自证”和“独立一致”，不能互相替代。</div>"
```

改为：

```python
        "<div class='micro'>同族自一致不是人工准确率；共识不是 truth oracle。"
        "三行并列是为了区分“单次自证”“同模型多提示稳定性”和“人工验证”，不能互相替代。</div>"
```

### 2.6 第 1015–1026 行：`cross_h1` / `cross_note`

现在：

```python
        cross_h1 = (
            f"；跨 5 模型一致率另列为 Fleiss κ={cross_numbers['kappa']:.4f}"
            f"（{cross_numbers['n_items']} 条 / {cross_numbers['n_cells']} 格），"
            "但这不是人工准确率"
        )
        cross_note = (
            f"跨 5 模型 Fleiss κ={cross_numbers['kappa']:.4f}"
            f"（ALL；TikTok {cross_numbers['tiktok_kappa']:.4f} / "
            f"Reddit {cross_numbers['reddit_kappa']:.4f}）是模型间一致率，"
            "不是人工准确率；三行证据基础见 Trust & limits。"
        )
```

改为：

```python
        cross_h1 = (
            f"；同模型多提示一致率另列为 presence Fleiss κ={cross_numbers['kappa']:.4f}"
            f"（{cross_numbers['n_items']} 条 / {cross_numbers['n_cells']} 格；"
            "5 个身份同一模型族），但这不是独立验证，也不是人工准确率"
        )
        cross_note = (
            f"同模型多提示 presence Fleiss κ={cross_numbers['kappa']:.4f}"
            f"（ALL；TikTok {cross_numbers['tiktok_kappa']:.4f} / "
            f"Reddit {cross_numbers['reddit_kappa']:.4f}）是同一模型族"
            "（deepseek-flash / deepseek-v4.1-flash）在 5 个身份提示下的自一致率，"
            "不是跨模型验证，也不是人工准确率；三行证据基础见 Trust & limits。"
        )
```

### 2.7 第 1027–1028 行：fallback

现在：

```python
        cross_h1 = "；跨 5 模型一致率未做，不能用它替代人工准确率"
        cross_note = "跨 5 模型一致率未做，不能用它替代人工准确率；三行证据基础见 Trust & limits。"
```

改为：

```python
        cross_h1 = "；同模型多提示一致率未做，不能用它替代人工准确率"
        cross_note = "同模型多提示一致率未做，不能用它替代人工准确率；三行证据基础见 Trust & limits。"
```

### 2.8 第 1353–1354 行：Trust & limits 的标题和段落

现在：

```html
  <h3>证据基础：自证、跨模型一致、人工验证是三件事</h3>
  <p class="muted">旧的 precision 是 LLM 对 LLM gold set 的自证；新加的是 5 个模型家族的跨模型一致率；人工验证仍未做。三者不能互相替代，跨模型一致率也不能写成准确率。</p>
```

改为：

```html
  <h3>证据基础：单次自证、同模型多提示稳定性、人工验证是三件事</h3>
  <p class="muted">旧的 precision 是 LLM 对 LLM gold set 的自证；新加的 κ 是同一模型族（deepseek-flash / deepseek-v4.1-flash）在 5 个身份提示下的稳定性，不是跨模型独立验证；人工验证仍未做。三者不能互相替代，同模型一致率也不能写成准确率。</p>
```

## 3. 全局替换规则

替换完成后，`voc/report.py` 和生成的 `report.html` 里不能再出现：

| 禁止说法 | 替换为 |
| --- | --- |
| 5 个模型家族 | 5 个标注身份 / 5 个身份提示 |
| 跨模型一致率 | 同模型多提示一致率 |
| 跨 5 模型一致率 | 同模型多提示一致率 |
| 独立盲标 | 不同身份提示下的盲标 |
| 独立一致 | 同模型多提示稳定性 |
| 模型间一致率 | 同一模型的自一致率 |
| 跨模型独立验证 | 同族自一致（不是独立验证） |

允许保留的内部名称：

- 变量/参数 `cross_model`、`_cross_model_numbers`；
- HTML 属性 `data-cross-model-table`、`data-cross-model-agreement`；
- 目录/文件名 `calibration/cross-model/`、`cross-model-stats.json`、`cross-model-report.md`。

**不要改这些内部标识**。`tests/test_pipeline.py:668,671` 和 `voc/validate_report.py:57` 依赖 `data-cross-model-table` / `data-cross-model-agreement` 的字面值。本次只改人类可见文本，不改选择器。

## 4. 其他需要同步的可见文本

- `calibration/cross-model/cross-model-report.md` 的标题“跨模型一致率报告”和正文“这是跨模型一致性”也应改成“同模型多提示一致率报告 / 同族自一致”。这是内部 artifact，但报告会引用它；如果对外展示，必须用同一口径。
- `calibration/README.md` 如果写了“跨模型”，同样处理。
- `report.html` 是构建产物；改完 `voc/report.py` 后重新 build，不要手改 HTML。

## 5. 诚实声明

- 本裁决不改任何数字。κ=0.8354（ALL）、0.8525（TikTok）、0.7357（Reddit）保持不变；变的只是对数字含义的说明。
- κ 是 presence agreement，不是 aspect-level accuracy；它主要反映“都认为没提”（631/680 格共同未标注）。报告必须保留“κ 主要由共同未标注驱动”这一句。
- `is_product_experience` 的 κ=0.6562 受裁决 A 的文档冲突影响。不要在报告里把它写成“体验定义一致性”；它测的是“标注者跟了哪份文档”。
- `calibration/cross-model/cross-model-stats.json` 的 `is_product_experience.fleiss.kappa` 字段当前是模板占位符（`0.6562499999999999`），不是数字。发布前必须修掉；在修掉之前，引用 `cross-model-report.md` §6 的 0.6562，不要引用这个 JSON 字段。
- 本裁决不把同族自一致升级为“验证”。它是提示稳健性检查；独立验证仍然缺位，G7 仍然 BLOCKED。
