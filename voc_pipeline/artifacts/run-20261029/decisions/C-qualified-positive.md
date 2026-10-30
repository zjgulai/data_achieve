# 裁决 C：qualified_positive

## 0. 最终裁决

**加。** 在契约的 polarity 枚举中加入 `qualified_positive`，并与 `qualified_negative` 对称定义。判定条件是：**总体极性为正面，但同一属性上带实质性程度/条件保留，且保留不足以构成独立负向 aspect。**

一句话：**负向可以“有条件”，正向也必须可以“有条件”；否则正向保留只能被塞进 `positive`（丢保留）或 `mixed`（被方向统计排除），两边都失真。**

## 1. 现状与冲突

### 1.1 三份文件不一致

| 文件 | 对 `qualified_positive` 的规定 |
| --- | --- |
| `voc/taxonomy.py` / `taxonomy.json` 的 `polarity_enum` | **包含** `qualified_positive`（6 个值之一） |
| `llm-coding/CODING-CONTRACT.md` §2 | 枚举只有 `positive / negative / qualified_negative / mixed / unknown`，**禁止输出** `qualified_positive` |
| `gold-set-50.jsonl` | **使用了 2 个** `qualified_positive` |

契约是唯一的例外。冻结 taxonomy 已经承认这个值，gold 也用了它，只有契约禁止。

### 1.2 gold 的 2 个 `qualified_positive`

| canonical_id | evidence | 原文语境 | 为什么不是纯 positive |
| --- | --- | --- | --- |
| `c-7658003601176119053` | “Almost fully takes away the sciatica” | “Almost fully takes away the sciatica I’ve had for the last 20 weeks of pregnancy. Truly a lifesaver!” | “Almost fully” 是明确的保留：几乎完全，但不是完全 |
| `c-7686709601646593805` | “There is some relief” | “There is some relief but the pregnancy ball was the best purchase… I found KT tapping more supportive than the belt.” | “some relief” + 明确说不如孕球/KT 胶带 |

这两条都是“总体正向 + 同属性保留”，不是纯 positive，也不是 mixed（正负不是同等 material，整体判断仍是正向）。

### 1.3 gold 的 4 个 `qualified_negative` 暴露了第二个不一致

| canonical_id | evidence | 实际语义 |
| --- | --- | --- |
| `c-7667963659528931085` | “did not find that it provided optimal relief” | 负向 + 程度保留（not optimal） |
| `c-7667963659528931085` | “experienced some stomach discomfort” | 负向 + 程度保留（some） |
| `c-7679740736191088397` | “wish it added just a little more support” | 负向 + 程度保留（just a little more） |
| `c-1upreg8` | “still wanted more lift” | 负向 + 程度保留（more） |

契约写的是“总体负面但带明确**让步**”（concession）。gold 实际用的是“总体负面 + 程度**保留**”（degree hedge）。4 条里没有一条是“negative but admits a positive”；它们都是“negative but not absolute”。

所以裁决 C 不只加 `qualified_positive`，还要把 `qualified_negative` 的定义改成对称的“程度/条件保留”，否则两个值仍然不对称。

## 2. `qualified_positive` 的判定条件

### 2.1 四个条件（全部满足才用）

1. **正向判断明确**：文本对同一属性给出了正面评价，不是“没有负面”这种缺省推断。
2. **保留可引用**：同一子句或紧邻子句里有明确的 hedge/limitation，例如 `almost`, `mostly`, `some`, `somewhat`, `just enough`, `only`, `not fully`, `wish it were more`, `but`, `compared with X it is less`。
3. **保留针对同一属性**：保留必须落在同一个 aspect 上，不能是另一个属性的问题。
4. **不可拆分且总体仍正向**：不能拆成“正向 aspect + 负向 aspect”；如果正负同等 material，用 `mixed`，不用 `qualified_positive`。

### 2.2 什么时候用 `qualified_positive` 而不是 `positive`

| 情形 | 用 | 例子 |
| --- | --- | --- |
| 纯正向，没有保留 | `positive` | “does give me support” |
| 正向 + 同属性程度保留 | `qualified_positive` | “Almost fully takes away the sciatica” |
| 正向 + 同属性条件保留 | `qualified_positive` | “It works, as long as I don’t wear it all day” |
| 正向 + 不同属性的负向 | 拆成两个 aspect，不用 qp | “great support but the straps dig in” → `SUP.GENERAL positive` + `COM.PRESSURE_DIGGING negative` |
| 正向 + 负向同等 material，拆不开 | `mixed` | “supportive but digs in after an hour”（同一子句、无法拆） |
| 比较句，主体仍明显更好 | `positive` | “better than my other bands” |
| 不确定、反讽、假设句 | `unknown` | “if it only stayed put” |
| “I wish I had bought it sooner” | `positive` | 这不是对产品的保留，是对购买时机的后悔 |

### 2.3 与 `qualified_negative` 的对称性

| | 总体极性 | 保留类型 | gold 例子 | 方向统计归入 |
| --- | --- | --- | --- | --- |
| `qualified_positive` | 正面 | 程度/条件保留（almost, some, mostly, just enough） | “Almost fully takes away the sciatica” | positive family |
| `qualified_negative` | 负面 | 程度/条件保留（not optimal, some, just a little more） | “did not find that it provided optimal relief” | negative family |

对称规则：

1. 两者都是**总体 X + 同属性保留**，不是“X + 反向 material”。
2. 两者都要求保留/限制**可引用**；没有 quote 就不用。
3. 两者都**不能拆**；能拆成两条 aspect 时必须拆。
4. 两者在方向统计里都归入总体极性（`positive` / `negative` family），不进入 `mixed`。
5. 两者都不允许“保留 + 反向 material 同等存在”；那是 `mixed`。

### 2.4 与 `mixed` 的边界

| | 判断 |
| --- | --- |
| `qualified_positive` | 正向是主判断；保留是程度/条件，反方向没有 material 主张 |
| `qualified_negative` | 负向是主判断；保留是程度/条件，正方向没有 material 主张 |
| `mixed` | 正负都 material，且同一子句拆不开；方向统计把它排除出分子和分母 |

关键：**不要把“正向 + 轻微保留”塞进 `mixed`。** `mixed` 在 `direction_stats` 里被排除，会让 C13 的 decisive 分母无谓缩小。

## 3. 契约修改点

### 3.1 `llm-coding/CODING-CONTRACT.md` §2 枚举

把：

> `aspects[].polarity`：`positive` / `negative` / `qualified_negative` / `mixed` / `unknown`

改为：

> `aspects[].polarity`：`positive` / `qualified_positive` / `negative` / `qualified_negative` / `mixed` / `unknown`

### 3.2 契约 §2 的注意事项

把：

> 注意：冻结 taxonomy 里还有 `qualified_positive`，本契约**不输出**该值。正向但带轻微保留时用 `positive`，把保留写进 `notes`。

改为：

> `qualified_positive` 与 `qualified_negative` 对称使用：总体正向但同一属性上带实质性程度/条件保留、且保留不足以拆成独立负向 aspect 时，用 `qualified_positive`；总体负向但带实质性程度/条件保留时，用 `qualified_negative`。两者都要求保留可引用；能拆成两条 aspect 时必须拆。

### 3.3 契约 §5 极性表

增加一行：

| 值 | 用法 |
| --- | --- |
| `qualified_positive` | 总体正面，但同一属性上带实质性程度/条件保留；保留不足以构成独立负向 aspect，且不能拆成两条 aspect |

把 `qualified_negative` 的用法从“总体负面但带明确让步”改为“总体负面，但同一属性上带实质性程度/条件保留（hedge 或让步）”。

### 3.4 盲标规格 `/tmp/voc-blind-box/SPEC.md`

在 Polarity values 中增加 `qualified_positive`，定义与 3.3 相同。否则盲标者仍然只能选 `positive` / `mixed`，下一次校准还会出现同样的不对称。

## 4. 对 gold 与 claim 的影响

### 4.1 gold strict 匹配

- 当前 high-only strict：TP 40 / gold 85 = 47.1% recall，FP 6，precision 87.0%。
- gold 的 2 个 `qualified_positive` 单元目前**永远无法匹配**，因为契约禁止输出该值。这是 2/85 = 2.4% 的结构性天花板。
- 加 `qualified_positive` 后，这 2 个单元变成可匹配。若编码器同时执行裁决 B（把 sciatica 和 some relief 归到 `SUP.PRESSURE_OFFLOAD`），最多可 +2 TP：
  - recall：42/85 = 49.4%（仍远低于 90%，天花板不是主因）。
  - precision 取决于是否替换旧 FP：如果编码器把现有的 `SUP.BACK positive`（`c-765800…`）和 `SUP.GENERAL negative`（`c-766796…`）替换成正确的 `SUP.PRESSURE_OFFLOAD`，FP 从 6 降到 4，precision = 42/46 = 91.3%；如果只是新增 2 个 qp、不删除旧 FP，precision = 42/48 = 87.5%。实际数字必须重新编码后测量。
- 如果只加 C、不执行 B，这 2 条仍会因 code 错（BACK / 无 SUP）而匹配不上。**C 解决极性天花板，B 解决 code 天花板，两者必须同批。**

### 4.2 C13

**不变：32 / 26 / 6 / 81.2%。**

`voc/claims.py` 的 `direction_stats` 已经这样写：

- `has_pos = bool(polarities & {"positive", "qualified_positive"})`
- `has_neg = bool(polarities & {"negative", "qualified_negative"})`

也就是说，代码早就把 `qualified_positive` 当 positive family。加这个值不会改变 C13 的分子/分母。反而如果不加、把正向保留塞进 `mixed`，`direction_stats` 会把该记录排除出 decisive 分母，C13 的 n 可能下降。加 `qualified_positive` 是保护 C13 分母的做法。

### 4.3 C04 / C05

- `voc/claims.py` 的 `nat_polarity` 已经把 `qualified_positive` 归入 positive（`if ann.polarity in {"positive", "qualified_positive"}`）。
- 当前 natural 语料里 `qualified_positive` 数量是 0，所以 C04/C05 的现有数字不变。
- 如果重新编码后出现 `qualified_positive`，它仍计入 positive family，不会翻转摩擦/共现的方向。

### 4.4 其他 claim

- C11 / C08 / C10 / C07 / C03 不读 polarity，不受影响。
- 报告里的 polarity 分布会多一个值；`polarity_peak` 等展示需要能处理第六个值。

## 5. 不加的后果（为什么“不加”不可接受）

如果坚持不加，只能把 `qualified_positive` 归到 `positive` 或 `mixed`：

| 归档 | 后果 |
| --- | --- |
| 归 `positive` + notes | 保留只存在于自由文本 `notes`，strict 匹配永远丢这 2 个 gold 单元；2/85 = 2.4% 的结构天花板永久存在；报告无法统计“有条件正向” |
| 归 `mixed` | `direction_stats` 把该记录排除出 decisive 分母；C13 的 n 会被无谓削减；`mixed` 的本义（正负同等 material、拆不开）被污染 |
| 归 `unknown` | 把明确的正向判断降级为不确定；错误 |

“gold 里有而契约禁止”不是可接受的理由。冻结 taxonomy 已经包含这个值；契约是唯一的例外。修复方向是让契约追上 taxonomy 和 gold，不是让 gold 迁就契约。

## 6. 诚实声明

- 本裁决不改 gold。2 个 gold `qualified_positive` 保持原样。
- 本裁决不承诺 strict recall 到 90%。它只移除 2/85 = 2.4% 的极性天花板；剩余天花板来自裁决 B 的 3 个 gold 重复单元（3/85 = 3.5%）和 6-aspect cap。
- 本裁决有过度使用风险：编码器可能把“轻微保留”误标成 `qualified_positive`，而 gold 标 `positive`，造成 strict precision 下降（family 匹配仍是 positive）。因此必须把 2.2 的非例清单写进契约，并在下一次校准中单独检查 `qualified_positive` 的 precision。
- 本裁决不改变 C13 的 32/26/6/81.2%。如果编码器把正向保留误标成 `mixed`，C13 的 n 会下降；这是不执行本裁决的风险，不是本裁决的后果。
