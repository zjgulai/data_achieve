这是同族自一致，不是人工准确率。

# 同模型多提示一致率报告

## 1. 数据与自检

- 盲标目录：`/tmp/voc-blind-box`。
- 样本：20 条（B01–B20）。TikTok 12 条，Reddit 8 条。
- taxonomy：34 个 aspect，14 个 family。
- 标注者：sol、terra、luna、g55、mini。
- 标注身份 `sol / terra / luna / g55 / mini` 是 5 个不同身份提示，全部运行在 DeepSeek Flash 同一族（`group/auto-deepseek-flash:max[1m]`，实际为 `deepseek-flash` / `deepseek-v4.1-flash`）；因此本报告测的是同一底座模型的同族自一致，不是跨模型独立验证。

| 标注者 | 记录数 | 自检 | 结果 |
|---|---|---|---|
| sol | 20 | 通过 | 纳入 |
| terra | 20 | 通过 | 纳入 |
| luna | 20 | 通过 | 纳入 |
| g55 | 20 | 通过 | 纳入 |
| mini | 20 | 通过 | 纳入 |

排除：无。5 份全部通过自检。

## 2. presence 一致率（Fleiss' kappa）

统计单位是 item × aspect 格。共 680 个格，每个格有 5 个二元判定（标了 = 1，未标 = 0）。

| 范围 | 格数 | present 判定数 | present 比例 | P_o | P_e | Fleiss κ | 强度 |
|---|---|---|---|---|---|---|---|
| TikTok | 408 | 154 / 2040 | 7.5% | 0.9794 | 0.8604 | **0.8525** | 几乎完全 |
| Reddit | 272 | 29 / 1360 | 2.1% | 0.9890 | 0.9583 | **0.7357** | 较强 |
| ALL | 680 | 183 / 3400 | 5.4% | 0.9832 | 0.8981 | **0.8354** | 几乎完全 |

## 3. 两两 Cohen's kappa（presence）

矩阵按 680 个格的全部二元判定计算。

| | sol | terra | luna | g55 | mini |
|---|---|---|---|---|---|
| sol | — | 0.9456 | 0.7660 | 0.7772 | 0.8571 |
| terra | 0.9456 | — | 0.7935 | 0.8366 | 0.8857 |
| luna | 0.7660 | 0.7935 | — | 0.7892 | 0.8408 |
| g55 | 0.7772 | 0.8366 | 0.7892 | — | 0.8587 |
| mini | 0.8571 | 0.8857 | 0.8408 | 0.8587 | — |

- 最低：sol–luna（κ = 0.7660）。
- 最高：sol–terra（κ = 0.9456）。

每个标注者与其他人的平均 κ：

| 标注者 | 与他人平均 κ |
|---|---|
| sol | 0.8365 |
| terra | 0.8654 |
| luna | 0.7974 |
| g55 | 0.8154 |
| mini | 0.8606 |

## 4. 极性一致率

只在“至少 2 个标注者标了同一 aspect”的格上计算。合格格数：42 / 680（6.2%）。

| 指标 | 数量 | 一致率 |
|---|---|---|
| exact polarity（格级全员一致） | 42 / 42 | 100.0% |
| polarity family（格级全员一致） | 42 / 42 | 100.0% |
| exact polarity（标注者对级） | n/a | 100.0% |
| polarity family（标注者对级） | n/a | 100.0% |

极性族映射：positive 与 qualified_positive 同族（positive）；negative 与 qualified_negative 同族（negative）；mixed 单独一族；unknown 单独一族。

每个格标注人数分布：0 人 631，1 人 7，2 人 7，3 人 4，4 人 5，5 人 26。

## 5. 共识分布

强共识 = 至少 4/5 人标注，且极性族一致。弱共识 = 至少 3/5 人标注，且极性族一致。其余为分歧。
有标注的格共 49 个，计入分布。无人标注的格 631 个，是全体的共同未标注，不计入共识分布。

| 共识等级 | 格数 | 占比 |
|---|---|---|
| 强共识 | 31 | 63.3% |
| 弱共识 | 4 | 8.2% |
| 分歧 | 14 | 28.6% |

分歧拆分：极性族冲突 0 个，标注人数不足 14 个。

分歧格清单（共 14 个）：

| item | aspect | 标注人数 | 判定 |
|---|---|---|---|
| B01 | COM.GENERAL | 2 | sol=negative, terra=negative, luna=—, g55=—, mini=— |
| B02 | FIT.BODY_SHAPE | 2 | sol=negative, terra=negative, luna=—, g55=—, mini=— |
| B04 | ADJ.RANGE_TENSION | 2 | sol=—, terra=—, luna=—, g55=negative, mini=negative |
| B05 | SUP.BACK | 1 | sol=—, terra=—, luna=positive, g55=—, mini=— |
| B05 | ACT.COMPATIBILITY | 1 | sol=—, terra=—, luna=—, g55=positive, mini=— |
| B06 | SUP.GENERAL | 2 | sol=positive, terra=positive, luna=—, g55=—, mini=— |
| B06 | ACT.COMPATIBILITY | 1 | sol=positive, terra=—, luna=—, g55=—, mini=— |
| B07 | GEN.OVERALL_EVALUATION | 1 | sol=—, terra=—, luna=positive, g55=—, mini=— |
| B09 | MAT.FABRIC | 2 | sol=positive, terra=—, luna=positive, g55=—, mini=— |
| B10 | APP.COLOR_AESTHETIC | 1 | sol=—, terra=—, luna=unknown, g55=—, mini=— |
| B11 | COM.GENERAL | 2 | sol=—, terra=—, luna=positive, g55=—, mini=positive |
| B13 | COM.GENERAL | 2 | sol=negative, terra=negative, luna=—, g55=—, mini=— |
| B16 | COM.SKIN_CHAFE | 1 | sol=—, terra=—, luna=positive, g55=—, mini=— |
| B16 | GEN.OVERALL_EVALUATION | 1 | sol=—, terra=—, luna=positive, g55=—, mini=— |

按 source：

| source | 强共识 | 弱共识 | 分歧 |
|---|---|---|---|
| TikTok | 27 | 4 | 8 |
| Reddit | 4 | 0 | 6 |

分歧最多的 aspect（按极性族冲突格数）：

无。14 个分歧格都是标注人数不足，不是极性冲突。

## 6. is_product_experience 补充

20 条样本中，16 条全员一致，4 条有分歧。
Fleiss κ = 0.6562（P_o = 0.8900，P_e = 0.6800）。

| item | source | 判定 |
|---|---|---|
| B01 | Reddit | sol=true, terra=true, luna=false, g55=false, mini=false |
| B06 | Reddit | sol=true, terra=true, luna=false, g55=false, mini=false |
| B13 | Reddit | sol=true, terra=true, luna=false, g55=false, mini=false |
| B16 | TikTok | sol=true, terra=true, luna=true, g55=false, mini=true |

## 7. 结论

- presence Fleiss κ：ALL 0.8354；TikTok 0.8525；Reddit 0.7357。
- 两两矩阵：最低为 sol–luna（0.7660），最高为 sol–terra（0.9456）。
- 极性：exact 100.0%，family 100.0%（合格格 42 个）。
- 共识：强 31，弱 4，分歧 14。
- 极性没有冲突。多标注格 42 个，exact 与 family 都是 100%。分歧全部来自 presence，即“这个 aspect 该不该标”。
- 被排除的标注者：无。
- 再次强调：这是同族自一致，不是人工准确率。

## 8. 限制

- 这是同族自一致，不是人工准确率。5 个标注身份全部运行在 DeepSeek Flash 同一族（`deepseek-flash` / `deepseek-v4.1-flash`），只是身份提示不同；这不是跨模型独立验证，也不是人工准确率。所有标注者都是 LLM。它们可能共享训练数据与标注偏差。一致不等于正确。
- 样本只有 20 条，aspect 有 34 个。多数格是共同未标注。
- 34 个 aspect 共享同一 item，格之间不独立。κ 不能用 680 个格直接算标准误或置信区间。
- presence κ 建立在大量“共同未标注”格上。ALL 的 present 比例只有 5.4%。κ 主要反映“都认为没提”的一致，不能单独当作“标得一样好”的证据。正例覆盖要看共识分布与极性一致率。Reddit 的 present 比例仅 2.1%，κ 对少数正例更敏感。
- 未读取 gold set、`coded/`、`mapping.json`、`claims.json`。gold set 未改动。
- 本报告只描述一致性与分歧位置，不判断哪一方更接近事实。

