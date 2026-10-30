# 裁决 B：support 族拆分

## 0. 最终裁决

**选方案 2：三个 code 全部保留，重写 include/exclude，并加一条强制优先级。`SUP.GENERAL` 降为兜底 code；`SUP.BACK` 只收点名背部/腰部；`SUP.PRESSURE_OFFLOAD` 收“重量被卸掉/压力被缓解”，其中 weight/load 语句优先于 `lower back` 字面。`SUP.BELLY_LIFT` 收明确的托肚子。**

一句话：**不是概念重叠，是 include 词让三个 code 都能被同一句话触发；把“谁优先”写死，重叠就消失。**

## 1. 问题实证

### 1.1 gold 与编码器的现状

`gold-set-50.jsonl` 的 SUP 族计数：

| code | gold 数 | high-only LLM 命中 | 备注 |
| --- | ---: | ---: | --- |
| `SUP.GENERAL` | 13 | 5 | 大量泛化 support |
| `SUP.BACK` | 8 | 8 | 编码器全中 |
| `SUP.PRESSURE_OFFLOAD` | 8 | **0** | recall 0% |
| `SUP.BELLY_LIFT` | 4 | 3 | 缺 1 条 qualified_negative |

`SUP.PRESSURE_OFFLOAD` 的 8 条 gold 原文：

| canonical_id | evidence | gold polarity | 实际语义 |
| --- | --- | --- | --- |
| `c-7667963659528931085` | did not find that it provided optimal relief | qualified_negative | 泛化“缓解不足” |
| `c-7686709601646593805` | There is some relief | qualified_positive | 泛化“有一些缓解” |
| `c-7658003601176119053` | Almost fully takes away the sciatica | qualified_positive | 坐骨神经痛缓解 |
| `c-7659507976003651341` | offers noticeable relief | positive | 泛化“明显缓解” |
| `c-7659258409535112974` | easing her pelvic pain | positive | 骨盆痛缓解（代述） |
| `c-7665021905910384398` | helps relieve the pain | positive | 泛化“缓解疼痛” |
| `c-7690266633513518861` | helped so much with hip and lower back pain | positive | 背/髋痛缓解，同时被标 `SUP.BACK` |
| `c-7701363030302459661` | eases the pain in her lower abdomen | positive | 下腹痛缓解（代述） |

结论：gold 的 8 条 `SUP.PRESSURE_OFFLOAD` **全部是 relief/ease 语义**，没有一条是纯 weight-off；真正的 weight-off 语句（B05 “the weight off my pelvis and lower back”）不在 gold 里。所以新定义不能只收 weight/load，否则会丢掉 gold 的全部 8 条；必须同时收“无背部指向的 relief/ease”，并用优先级把 weight 语句从 BACK 手里拿走。

而 `SUP.BACK` 的 include 含 `lower back`、`back pain`，`SUP.GENERAL` 的 include 含 `support`。结果：

- “excellent support for my lower back” 同时命中 BACK（lower back）和 GENERAL（support）；
- “helped so much with hip and lower back pain” 同时命中 BACK（lower back）和 PRESSURE（relief 语义）；
- “the weight off my pelvis and lower back is incredible” 同时命中 PRESSURE（weight off）和 BACK（lower back）。

### 1.2 B05 的具体分歧

B05 `c-1mdp0wu`：

> “I’m still wearing it right now because **the weight off my pelvis and lower back is incredible**.”

- 5 个盲标者里 5/5 都标了 `SUP.PRESSURE_OFFLOAD`，其中 1 个（luna）同时多标了 `SUP.BACK`，因为 include 有 `lower back` 字面。分歧不是“没人认为是卸重”，而是“卸重之外还该不该多标一个 BACK”。
- 实际语义是卸重：主语是 “the weight off”，不是 “back support”。`lower back` 只是重量离开的部位。
- 当前 LLM 编码器在 `c-1mdp0wu` 上输出的正是 `SUP.PRESSURE_OFFLOAD positive`，说明这个概念不是不可编码，而是 gold 子集上的执行/定义问题。

### 1.3 include 词的实际重叠

| 句子 | 命中 GENERAL | 命中 BACK | 命中 PRESSURE | 命中 BELLY_LIFT |
| --- | --- | --- | --- | --- |
| “excellent support for my lower back” | support | lower back / back support | — | — |
| “the weight off my pelvis and lower back” | — | lower back | weight off | — |
| “helped so much with hip and lower back pain” | — | lower back / back pain | relief/ease 语义 | — |
| “lift and support the baby” | support / lift | — | — | lift + baby |
| “helps relieve the pain” | — | — | relieve | — |

重叠不是“用户分不清”，是**include 词没有排他性**。用户分得清“背被托住”和“重量被卸掉”；分不清的是关键词匹配。

## 2. 三个方案比较

| 方案 | 做法 | 优点 | 致命问题 | 判定 |
| --- | --- | --- | --- | --- |
| 1 合并 | `SUP.BACK` + `SUP.PRESSURE_OFFLOAD` → `SUP.LOAD_RELIEF` | 彻底消除 BACK/PRESSURE 边界 | gold 有 8 个 BACK + 8 个 PRESSURE；合并后 16 个旧 code 单元在 strict 下全部不可匹配（18.8% gold）；且丢掉“背部结构支撑”与“骨盆卸重”的区分 | 否 |
| 2 重定义 | 三者保留，include/exclude 互斥 + 优先级 | 保留信息；gold code 名不变；只产生 3 个 gold 重复单元的结构上限 | 需要编码器严格执行优先级 | **是** |
| 3 废弃 | 删除 `SUP.PRESSURE_OFFLOAD` | 表面消除 0 recall | 概念真实存在（B05、`c-7674647274773759757`、`c-7667984767955748622`）；删除后这些记录会被 `lower back` 拉回 BACK，正是要修的错 | 否 |

### 2.1 为什么不能合并

- gold 的 `SUP.BACK` 8 条和 `SUP.PRESSURE_OFFLOAD` 8 条是两批不同原文。合并后，`gold-set-50.jsonl` 里的旧 code 名（BACK/PRESSURE）在 strict code+polarity 下无法匹配新 code（LOAD_RELIEF），除非 eval 额外做 code 映射。那是 16/85 = 18.8% 的结构性损失，比方案 2 的 3/85 = 3.5% 大 5 倍。
- `c-7659507976003651341` 同时有 “excellent support for my lower back”（背部支撑）和 “offers noticeable relief”（缓解）。合并会把两种不同的产品利益压成一个 code，后续实验无法区分“加强腰背结构”与“加强卸重”。
- `c-7671622567216498445` 同时有 “saving my back”（背部）和 “lift and support the baby”（托举）。合并 BACK+PRESSURE 不影响 BELLY_LIFT，但说明用户会在一句话里区分不同支撑机制；合并会丢信息。

### 2.2 为什么不能废弃

`SUP.PRESSURE_OFFLOAD` 的 0 recall 是**编码器在 gold 子集上没输出这个 code**，不是语料里没有这个概念。真实原文：

- B05 `c-1mdp0wu`：“the weight off my pelvis and lower back is incredible”；
- `c-7674647274773759757`：“it takes the weight of the baby”；
- `c-7667984767955748622`：“it feels like a weight is lifted”。

这 3 条都是明确的负载转移。删除 code 后，它们只能落到 `SUP.BACK`（因为含 lower back/belly）或 `SUP.GENERAL`（因为 support），B05 的 1/5 分歧会变成 5/5 的 BACK 误标。这不是修复，是把错误制度化。

## 3. 新定义（可直接替换 `voc/taxonomy.py` 第 33–36 行）

### 3.1 强制优先级（先于 include 词匹配）

对每条 aspect，按以下顺序判断，**第一个命中的 code 就是唯一 code**：

1. `SUP.BELLY_LIFT`：出现 lift / hold up + belly / bump / bundle。
2. `SUP.PRESSURE_OFFLOAD`：出现 weight/load 转移语义（weight off, takes the weight, weight is lifted, pressure off）。
3. `SUP.BACK`：点名背部/腰部（back pain, backache, lower back, back support, my back），且没有第 2 步的 weight/load 语义。
4. `SUP.PRESSURE_OFFLOAD`：出现 relief/ease/take away + pain/pressure，且没有点名背部。
5. `SUP.GENERAL`：只有泛化 support/supportive，且没有部位、没有 weight/load、没有 lift belly。
6. 都不满足：不标 SUP aspect。

关键：**第 2 步优先于第 3 步**。这样 “the weight off my pelvis and lower back” 归 PRESSURE，不归 BACK。

### 3.2 code 定义

| code | definition | include | exclude |
| --- | --- | --- | --- |
| `SUP.GENERAL` | 对支撑效果的评价；仅在没有部位、没有重量转移、没有托起肚子语义时使用。 | `support, supportive, holds me`（兜底） | `back pain / lower back / back support / my back` → BACK；`weight off / take the weight / weight is lifted` → PRESSURE；`lift my belly / hold up bump / holding up her bundle` → BELLY_LIFT；`comfortable / soft` → COM.* |
| `SUP.BACK` | 对下背、腰部支撑或该部位疼痛缓解的评价。 | `back pain, backache, lower back, back support, my back` | `weight off / take the weight / weight is lifted`（即使同句有 lower back）→ PRESSURE；无背部指向的 support → GENERAL；姿势/运动 |
| `SUP.PRESSURE_OFFLOAD` | 对重量被卸掉、负载/压力被转移，或疼痛/压力得到缓解的评价。 | `weight off, takes the weight, weight is lifted, pressure off, relieve/ease/take away pain or pressure` | 仅描述松紧；单纯 support → GENERAL/BACK；点名 lower back/back pain 且无 weight/load 语义 → BACK；lift/hold up belly → BELLY_LIFT；weightless 仅描述带子本身轻 → APP.LOW_PROFILE/COM.*；缓解来自其他物品/行为 → 不标 |
| `SUP.BELLY_LIFT` | 明确描述把肚子托起来、兜住或托举。 | `lift my belly, lift your belly, hold up bump, holding up her little bundle, 托起肚子` | 仅说 support → GENERAL；仅说 weightless → PRESSURE/COM.* |

机器匹配用的 lexicon（必须过 §3.1 的优先级，不能单独用）：

```text
SUP.GENERAL          = ("support", "supportive")   # 兜底，必须过优先级过滤
SUP.BACK             = ("back pain", "backache", "lower back", "back support", "my back")
SUP.PRESSURE_OFFLOAD = ("weight off", "weight is lifted", "take(?:s|n)? (?:the )?weight",
                        "pressure off", "reliev", "relief", "eas(?:e|es|ed|ing)",
                        "take(?:s|n)? away")
SUP.BELLY_LIFT       = ("lift(?:s|ing)? (?:that |my |your |the )?(?:big )?belly",
                        "hold(?:s|ing)? (?:up )?(?:my |the |her )?(?:bump|belly|bundle)",
                        "belly lift")
```

### 3.3 两个额外判据

- **归属判据**：relief/ease 必须能归到支撑带。原文如果写的是“swimming pool… take the extra weight off my joints”，不标 `SUP.PRESSURE_OFFLOAD`，因为主语是泳池，不是带子。
- **weightless 判据**：`weightless` 只在“身体负载被卸掉”的句子里算 PRESSURE；如果只是“带子本身很轻”，归 `APP.LOW_PROFILE` 或 `COM.GENERAL`。例：`c-7677755508020528910` 的 “very comfortable and weightless but supports the belly just enough” 是带子轻，不是卸重。

## 4. 至少 10 条原文落码

| # | canonical_id | 原文 | 新 code | 理由 |
| --- | --- | --- | --- | --- |
| 1 | `c-1mdp0wu`（B05） | “the weight off my pelvis and lower back is incredible” | `SUP.PRESSURE_OFFLOAD positive` | weight/load 语义优先于 lower back；解决 1/5 BACK 分歧 |
| 2 | `c-7659507976003651341` | “excellent support for my lower back” | `SUP.BACK positive` | 点名背部；不另标 GENERAL |
| 2b | `c-7659507976003651341` | “offers noticeable relief” | `SUP.PRESSURE_OFFLOAD positive` | 独立子句的泛化 relief；与 2 分开 |
| 3 | `c-7690266633513518861` | “helped so much with hip and lower back pain” | `SUP.BACK positive` | 点名背部/髋部；没有 weight 语义；gold 同时标 PRESSURE 是重复 |
| 4 | `c-7658003601176119053` | “Almost fully takes away the sciatica” | `SUP.PRESSURE_OFFLOAD` + `qualified_positive`（极性按裁决 C） | 无 back 字面；relief 形式；当前编码器标 BACK positive 是 code+polarity 双错 |
| 5 | `c-7665021905910384398` | “helps relieve the pain” | `SUP.PRESSURE_OFFLOAD positive` | 无部位；relief 形式 |
| 6 | `c-7667963659528931085` | “did not find that it provided optimal relief” | `SUP.PRESSURE_OFFLOAD qualified_negative` | relief 形式，负向；当前编码器标 GENERAL negative 是 code 错 |
| 7 | `c-7671622567216498445` | “saving my back” | `SUP.BACK positive` | 点名 back |
| 7b | `c-7671622567216498445` | “lift and support the baby” | `SUP.BELLY_LIFT positive` | lift + baby；不另标 GENERAL |
| 8 | `c-7674647274773759757` | “it takes the weight of the baby” | `SUP.PRESSURE_OFFLOAD positive` | weight 语义 |
| 8b | `c-7674647274773759757` | “Very good support system” | `SUP.GENERAL positive` | 泛化 support，无部位/重量 |
| 9 | `c-7667984767955748622` | “it feels like a weight is lifted” | `SUP.PRESSURE_OFFLOAD positive` | weight 语义 |
| 9b | `c-7667984767955748622` | “lifts that big belly effortlessly” | `SUP.BELLY_LIFT positive` | lift + belly |
| 9c | `c-7667984767955748622` | “I didn’t think it would support my big belly but it does” | `SUP.GENERAL positive` | 泛化 support；没有 lift 动词 |
| 10 | `c-7677755508020528910` | “very comfortable and weightless but supports the belly just enough” | `COM.GENERAL positive` + `SUP.GENERAL`（极性按裁决 C 判） | weightless 是带子轻，不是卸重；不标 PRESSURE |
| 11 | `c-19rjykcrivso1` | “swimming pool… take the extra weight off my joints” | 不标 SUP | 缓解来自泳池，不是带子；归属判据 |
| 12 | `c-1svdohq` | “something that takes pressure off my pelvis/lower back” | 不标 SUP | 这是求推荐的需求描述，不是使用评价 |

## 5. 对 gold 的影响

### 5.1 结构上限：3 个 gold 重复单元

新定义要求“一句话一个 SUP code”。gold 里有 3 个单元是同一子句的第二个 SUP 标签，按新规则不可匹配：

| canonical_id | 重复单元 | 同一子句的另一个 code | 处理 |
| --- | --- | --- | --- |
| `c-7671622567216498445` | `SUP.GENERAL positive` “lift and support the baby” | `SUP.BELLY_LIFT positive`（同 span） | BELLY_LIFT 优先；GENERAL 不标 |
| `c-7659507976003651341` | `SUP.GENERAL positive` “excellent support” | `SUP.BACK positive` “excellent support for my lower back” | BACK 优先；GENERAL 不标 |
| `c-7690266633513518861` | `SUP.PRESSURE_OFFLOAD positive` “helped so much with hip and lower back pain” | `SUP.BACK positive`（同 span） | BACK 优先；PRESSURE 不标 |

这 3 个单元**当前编码器本来就没有匹配**（`c-767162` 只出 BACK+BELLY_LIFT；`c-765950` 只出 BACK；`c-769026` 只出 BACK）。所以新定义**不损失任何当前 true positive**。结构上限是 3/85 = 3.5%。

### 5.2 PRESSURE 的定义上限：7/8

8 条 gold PRESSURE 里，7 条在新定义下可被该 code 正当表达（第 7 条 `c-769026…` 是重复单元）。当前观察 recall 是 0/8。新定义把**定义上限**从 0/8 提到 7/8；实际 recall 必须重新编码后测量，不能预设。

当前编码器在这些记录上的输出显示改动是可行的：

| canonical_id | 当前输出 | 新定义应输出 |
| --- | --- | --- |
| `c-7667963659528931085` | `SUP.GENERAL negative` | `SUP.PRESSURE_OFFLOAD qualified_negative` |
| `c-7658003601176119053` | `SUP.BACK positive` | `SUP.PRESSURE_OFFLOAD qualified_positive` |
| `c-7659507976003651341` | `SUP.BACK positive` | `SUP.BACK positive` + `SUP.PRESSURE_OFFLOAD positive` |
| `c-7665021905910384398` | 无 SUP | `SUP.PRESSURE_OFFLOAD positive` |
| `c-7701363030302459661` | 无 SUP | `SUP.PRESSURE_OFFLOAD positive` |
| `c-7659258409535112974` | `SUP.BELLY_LIFT positive` | `SUP.BELLY_LIFT positive` + `SUP.PRESSURE_OFFLOAD positive` |
| `c-7686709601646593805` | 无 SUP | `SUP.PRESSURE_OFFLOAD qualified_positive` |

### 5.3 对 6 个 false positive 的影响

当前 high-only 有 6 个 FP，其中 2 个是 `support_family_boundary`：

- `c-7658003601176119053`：编码器 `SUP.BACK positive`，gold `SUP.PRESSURE_OFFLOAD qualified_positive`；
- `c-7667963659528931085`：编码器 `SUP.GENERAL negative`，gold `SUP.PRESSURE_OFFLOAD qualified_negative`。

这两个正是本裁决要修的。新定义 + 裁决 C 的 `qualified_positive` 一起执行后，它们应从 FP 转为 TP。另外 4 个 FP 属于裁决 A（`c-1x65j91` 的 2 个）和裁决 C（2 个 polarity hedge），不由 B 单独解决。

## 6. 对其他 claim 的影响

下表只算 **B 单独执行**。A 和 C 的叠加影响见各自裁决；A 会改变 C04/C05 的分层，C 会改变 qp 的可表达性。

| claim | 影响 | 理由 |
| --- | --- | --- |
| C13 | **不变**：32 / 26 / 6 / 81.2% | `direction_stats` 按 SUP family 聚合，不按具体 SUP code；BACK→PRESSURE 的重新分配不改变同向/反向 |
| C04 | **不变**：support negative 3、friction records 3 | `SUPPORT_CODES` 包含全部 4 个 SUP code；重新分配不改变 family 计数 |
| C05 | **不变**：舒适正向 3、共现 1 | 共现用的是 COM/APP × SUP/FIT/STB negative；SUP 内部换 code 不影响 |
| C03 | 不变：exact-model 体验 0 | B 不涉及体验门槛 |
| gold strict precision/recall | 定义上限提高；当前 TP 不减 | 3 个重复单元当前本来就没匹配；PRESSURE 上限 0→7/8 |

## 7. 诚实声明

- 本裁决不改 gold。3 个 gold 重复单元会永久成为 strict 结构上限（3/85 = 3.5%）。报告必须把它们列为“gold 内部重复标注”，不能算成编码器错误。
- 本裁决不承诺 PRESSURE recall 一定到 7/8。它只把定义从“不可表达”改成“可表达”；实际 recall 必须重新编码后测量。
- 本裁决会让 taxonomy 的 include/exclude 与已冻结的 `VOC-BAND-v1.0` 不同。新编码必须带新版本号（建议 `VOC-BAND-v1.1`）；gold 保持 v1.0。eval 按 code 比较，不按 version 拒绝。
- 本裁决不改变 C13 的档位。B05 的 1/5 分歧会消失，因为它测的是 `SUP.BACK` vs `SUP.PRESSURE_OFFLOAD` 的文档边界；新规则把 weight 语句唯一归到 PRESSURE。
