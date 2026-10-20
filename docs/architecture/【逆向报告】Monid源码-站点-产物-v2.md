---
name: monid-reverse-engineering-v2
description: Monid 第二轮逆向报告（2026-10-20）。基于固定提交源码、线上页面快照与本地报告产物三源交叉，覆盖首页/tools/blog/docs/app 工作台/洞察报告。修正 v1 的三条判断，给出页面壳与能力图谱。制定 PRD、复刻 UI 或评估借鉴范围时先读这份。
---

# Monid 逆向报告 v2：源码 · 站点 · 产物

> 逆向对象：`github.com/monid-ai/monid` @ `96e1569`（2026-10-20）· `https://monid.ai` · `https://app.monid.ai`
> 产物对象：`ref/monid-prompt-insight/` 四份 HTML
> 前序文档：[v1 逆向报告](./【逆向报告】Monid网站UI与能力逆向.md)
> 相邻文档：[PRD](../product/【PRD】母婴出海数据洞察Agent工作台.md) · [Playbook](../product/【Playbook】母婴出海洞察交付.md)

## 0. 结论

本轮取证推翻了三条旧判断。

| # | v1 判断 | v2 证据 | 结论 |
|---|---|---|---|
| 1 | “借鉴路径，不移植运行时” | 仓库 0 个 `.tsx`/`.html`/`.css`/`.sql`，仅 1 处 `Deno.serve`（本地 webhook）。discover 排序、健康度、p50/p95、计价、wallet 均在未公开的 monid-services | 结论成立，理由要改。引擎可嵌入，但不含服务端、UI、DB、计费。移植成本 30–60 人日，瓶颈不在执行器 |
| 2 | “Monid 有研究工作台” | `app.monid.ai` 一级导航只有 6 项：Get Started / Tools / API Keys / Budgets / Resources / Usage。客户端 17 条路由，无 Research / Tables / Playbooks / Reports | 判断错误。app 是按调用计费的工具控制台，不是研究工作台 |
| 3 | “try it out 是输入式交互” | 是 4 张复制提示词卡。用户选 agent 与 method，建 key，复制到外部 agent 执行 | 判断错误。app 内无等待态、无对话、无报告 |

由此得到本轮最重要的产品事实：

**你看到的两份高完成度报告，不是 Monid 生成的。**
它们是外部 agent 调用 Monid 工具后生成的自包含 HTML artifact。
Monid 的 app 只把底层 tool runs 与成本记到 Usage 账本。
所以“复刻 Monid 工作台”这件事，Monid 本身没有答案。
控制面可以借，研究工作台必须自建。

第二条关键事实：

**BumpEase 报告与 SOP 共享同一份数据合同。**
两份 HTML 内嵌的 `siteData` JSON 完全相同。
长度 64,467 字符，sha256 前 16 位 `af5607158f0970ed`。
报告渲染结论切片，SOP 渲染流程切片。
这是“一份证据合同、两个渲染器”的实证。

第三条关键事实：

**报告的说服力来自证据边界，不来自视觉设计。**
反证、未知、门禁、禁用结论、证据边界在每一节都可见。
详见第 5 节。

## 1. 证据与方法

本轮不运行 REA 包。改用三源交叉，所有结论可复核。

| 源 | 覆盖 | 复核方式 |
|---|---|---|
| 源码 | connector 协议、编译、执行、计量、错误模型 | `git clone` 后按 `路径:行号` 定位 |
| 线上 HTML | 首页、`/tools`、详情、`/blog`、文章、`/docs`、`app.monid.ai` | `curl -sL` 取原始 HTML，按选择器与计算样式取证 |
| 本地产物 | 四份洞察报告与 SOP | 直接读 HTML 与内嵌 JSON |

沿用 `reverse-skill` 的 `Evidence → Finding → Path` 结构。
每条结论给出证据、机制、复用判定。
无法取到的写“未验证”，不写推测值。

本轮取证量：

- 子任务 13 个，工具调用 1,257 次。
- 抓取页面 21 个。
- 解析源码文件约 300 个。
- 解剖 HTML 产物 4 份，合计 403,896 字节。

## 2. Monid 的四层结构与真实边界

Monid 不是一个单体产品。它分四层，只有前两层开源。

| 层 | 内容 | 是否开源 | 证据 |
|---|---|---|---|
| 定义层 | connector 声明、endpoint schema、taxonomy | 是 | `connectors/`、`shared/core/schema/` |
| 执行层 | 编译、加载、五段流水线、计量结算 | 是 | `engine/`、`shared/compiler/` |
| 托管层 | discover 排序、健康度、p50/p95、broker 计价、visibility | 否 | 仅客户端契约与公开文档 |
| 控制面 | 账号、key、budget、wallet、usage | 否 | `app.monid.ai` bundle |

### 2.1 开源仓库的实测规模

| 指标 | 数值 | 备注 |
|---|---|---|
| provider 包 | 32 | `connectors/*/provider.ts` 计数 |
| endpoint 定义 | 719 | 全仓扫描 |
| 受控类目 | 64 | 叶子词表 |
| `ids.lock.json` 条目 | 648 | 与 719 差 71。7 个 provider 完全未入锁 |
| fixture | 1,034 | 其中 904 为 `synthetic-*` |
| 仓库代码类型 | 纯 TS/Deno | 无前端、无 SQL、无容器编排 |

`ids:check` 不在 CI 与发布流程里。
这是可复现的运营缺口，复刻时应避免。

### 2.2 五段执行流水线

```text
validate → toRequest → transport/auth → usage settle → output map/validate
```

关键性质：

- 结算发生在解码之后、输出映射之前。
  非 2xx 强制清零用量，并跳过计费钩子。
- 凭证不进入流水线。
  请求只携带未执行的 `auth.inject` 函数引用与凭证 JSON Schema。
  凭证由传输层注入。
- 加载门禁 fail-closed，顺序为
  `BAD_DOC → UNSUPPORTED_DOC → NO_RESOURCE_READER`。
- 无跨供应商 fallback、无自动重试、无熔断。
  只有 `EXECUTION_FAILED` 与 `RESOURCE_OP_FAILED` 标记为可重试。
- 两级超时：`requestMs` 中断单次 fetch，`runMs` 限制轮询循环。

### 2.3 计量代数

只有四种用量模型。

| 模型 | 含义 |
|---|---|
| `FREE` | 不计费 |
| `PER_CALL` | 每次调用计一次 |
| `PER_UNIT` | 按单位计。单位可为 RESULT / TOKEN / CHARACTER / SECOND / MINUTE / CREDIT / PAGE |
| `COMPOSITE` | 多条计量行组合 |

折叠公式：

```text
credits = ceil(quantity / every) × consumes.amount
```

`usage.evidence` 从原始响应取数。
`usage.consolidate` 是供应商自有计量钩子。
非空且已裁剪的 claim 覆盖推导值。
冲突时以 `usage.mismatch.derived` 暴露推导值并告警，run 不失败。仅当 claim 指向未声明的 credit pool 时抛 `FN_CONTRACT`。

`estimate()` 是运行前的纯承诺。
`accrued()` 在声明了 `updateEstimateEveryMs` 时用 `elapsedMs` 重算。
宿主用这对函数做预算预留。

### 2.4 健康度

服务端五态分类器。

| 状态 | 定义 |
|---|---|
| `healthy` | 有新近确认 |
| `stable` | 长期稳定，但无新近数据 |
| `degraded` | 不稳定或趋势下滑 |
| `outage` | 已知不可用 |
| `unknown` | 缺数据 |

双窗口：fresh 与 long。
p50/p95 由服务端按实测运行计算。
outage 默认从 discover 隐藏；显式包含时排最后。
健康度只作 tie-breaker，不参与主排序。

## 3. 页面壳清单

### 3.1 首页 `/`

技术栈：Nuxt SSR + Nuxt UI + Tailwind + Reka UI。不是 Next.js。

结构：12 个纵向区块，1440×900 下总高 5,810px，约 6.46 屏。

| # | 区块 | 高度 | 关键内容 |
|---|---|---|---|
| 1 | header | 73 | Home / Tools / Blog / Docs；GitHub / X / Discord；Get started |
| 2 | hero | 580 | eyebrow 12px mono；h1 90px；可复制 CLI 命令条；tagline |
| 3 | connect | 788 | agent 图形 → Monid 节点 → 扇形连线 → 24 tile 工具墙 |
| 4 | hiw | 624 | 三步流程，三个 213×216 节点 |
| 5 | killed | 232 | “We killed the subscriptions.” |
| 6 | stats | 203 | 2700+ tools / on-demand / 1 balance |
| 7 | terminal | 545 | 880×437 深色终端，完整竞品研究 run |
| 8 | cards | 494 | Skill / MCP / CLI 三卡，387×134 |
| 9 | cta | 502 | 满色 CTA |
| 10 | faq | 714 | 820px 宽，5 条手风琴 |
| 11 | provider | 476 | 供应商招募 |
| 12 | footer | 580 | `#1e1e1e`，三组链接 |

视觉 token 原值：

```text
--bg #fff · --bg-subtle #fafafa · --bg-warm #f5f5f5
--dark #121212 · --dark-2 #1e1e1e
--ink #1e1e1e · --ink-2 #4d4d4d · --muted #6b6b6b
accent #0016d7
边框 1px #ebebeb · 阴影 0 1px 2px #0000000f
圆角 4 / 8 / 16px
```

字体：Outfit（display）/ Inter（sans）/ JetBrains Mono（mono）。

字号阶梯（1440 实测）：

| 层级 | 字号/行高 | 字重 | 字距 |
|---|---|---|---|
| h1 | 90 / 86.4 | 600 | -3.6px |
| h2 | 64 / 67.2 | 600 | -2.24px |
| h3 | 24 | 600 | — |
| body | 16 | 400 | — |
| mono 标签 | 12–12.5 | — | — |

容器：header/footer 1312px，内容 1240px，hero 1100px。

工具墙：桌面 5 列，781–989px 4 列，780px 以下 2 列。tile 232×82，gap 8px。

设计意图判断：

- 卖的是“agent 的工具注册表”，不是企业分析工作台。
- 可信度靠枚举密度、mono 文案、终端日志、动态统计。
- 全页没有客户 logo、没有客户证言、没有产品截图。
- 25 张图片全部是 agent 与 provider logo。

这条很重要：**Monid 靠数量与密度建立可信度。**
本项目靠证据质量与可复核性建立可信度。

### 3.2 目录页 `/tools`

两级目录，不是 endpoint 列表。

- 15 个顶级分类 rail，sticky 240px。
- 191 个 provider / leaf-category tile。
- 3 / 2 / 1 列响应式，tile 297×154.5px，hover 抬升 1px。
- 容器 1240px。
- 卡片字段只有：logo、名称、2 行描述、endpoint 数量。
- 筛选只有分类。没有 provider、价格、输入类型筛选，没有排序。
- 搜索走 API，tile 级。缺 URL 状态与结果计数。
- 目录与 endpoint 数据几乎全部客户端异步加载，SSR 首包是空壳。

可复用的只有骨架与“紧凑行”这一取向。
必须补 SSR、facet、schema、健康度、延迟。

### 3.3 详情页 `/tools/<slug>`

壳由五段组成：hero、endpoint 卡片、use-cases、guides、related。

endpoint 卡片字段：

- provider
- 标题
- `VERIFIED` 标记
- 路径
- 2 行描述
- 价格

24 条一页，cursor + Load more。

endpoint modal 只有价格矩阵与 agent prompt。
缺少六项：参数表、示例请求与响应、延迟、健康度、Try、Add to agent。

这是 Monid 目录层最明显的产品缺口。
也是我们能直接做得更好的地方。

最强可复用资产：详情页内嵌的 how-to guide playbook。

### 3.4 博客 `/blog`

规模：144 篇，6 页，24 篇/页，8 个分类。

布局：1080px 三列卡片网格。

卡片字段：分类、日期、标题、摘要。

文章页：1240px 容器内 760px 正文 + 340px 粘性目录。

写作口吻：

- 第二人称，短句。
- 第一人称复数讲实测。
- 精确价格与日期。
- 反常识钩子。
- 成本优先。

可信度靠可复核数字，不靠形容词。

转化路径是 prompt-first 自助闭环：
复制 prompt → 取 key → 看定价 → 读 quickstart。
没有注册表单，没有 newsletter。

已知不一致，复刻时不要照抄：

- 列表 144 篇，sitemap 有 273 个 `/blog` URL。
- RSS 只有 4 条公告。
- 132/144 篇都标 5 min。
- 没有搜索、订阅、作者页、标签页。

### 3.5 文档 `/docs`

Mintlify 托管，5 个 tab，50 个内容页。

| Tab | 页数 | 组织方式 |
|---|---|---|
| Documentation | 8 | AI Agent 接入排在人类接入之前 |
| Examples | 12 | 按 5 个业务场景分组，prompt-first cookbook |
| API Reference | 11 | sidebar 标题直接写 `METHOD + path` |
| CLI Reference | 12 | Endpoints / Runs / Keys & Access / Examples |
| Integrations | 7 | 3 种接入模式，各自拆“决策页 + Setup 页” |

单页固定顺序：

```text
Request → Headers → Body → Example Request → Response → Next Step
```

三语言示例：curl / TypeScript / Python。

给 agent 的入口有四层：

| 层 | 路径 |
|---|---|
| 根入口 | `/llms.txt`（定制叙事，先要求读 SKILL.md） |
| 文档索引 | `/docs/llms.txt`（50 页机器索引） |
| 全文 | `/docs/llms-full.txt`（50 页拼接） |
| 每页 | `.md` 备用表示 + `Accept: text/markdown` |

`SKILL.md`：429 行，21,925 字节，版本 0.1.7，16 个二级章节。

四道零文档接入机制：

1. 版本握手。
2. 自替换。
3. CLI 自描述。
4. 运行时发现，inspect 优先。

它把工具优先级、成本上限、终态处理写成硬规则，不是建议。

已知缺口：

- 公开 OpenAPI 3.1 有 45 个 path，文档只覆盖 11 个。
- 两者存在字段与错误码漂移。
- 文档站没有消费自己的 spec。

### 3.6 工作台 `app.monid.ai`

这是本轮最重要的修正。

一级导航只有 6 项：

```text
Get Started · Tools · API Keys · Budgets · Resources · Usage
```

客户端路由 17 条。
没有 Research、Tables、Playbooks、Reports、Connectors、Settings。

任意路径都返回同一个 8,793 字节 SPA 壳。
不能用 HTTP 200 判断路由存在。

Get Started 是 5 步连接向导：
`pick → setup → signup → apikey → examples`。

Try it out 的交互模型：

1. 选 agent（9 种）。
2. 选 method（Skill / MCP / Plugin）。
3. 建或授权 key。
4. 复制 4 条示例提示词到外部 agent。

app 内没有等待态，没有对话，没有报告。
执行结果只回落到 Usage 账本。

Usage 是 run ledger，不是任务队列。
字段：provider、endpoint、caller、status、response、cost、duration、input/output。

Budgets 是 workspace 级预算窗口 + 单次 run 上限 + 暂停/审计。
API Keys 支持 scope、过期、撤销、审计，绑 workspace。
Resources 管 durable provider resources 的生命周期。

可借的控制面范式只有 6 件：

1. agent × method onboarding。
2. run ledger。
3. 预算窗口与单次上限。
4. 资源生命周期。
5. 目录与透明价格。
6. key scope 与审计。

必须自建的 5 层：

1. Research / 任务。
2. Playbooks。
3. Tables / 证据表。
4. Reports / 报告渲染。
5. 持久分享。

### 3.7 报告页（产物形态）

不是产品页面，是自包含 HTML artifact。

性质：

- 单文件，零外部依赖。
- 零 SVG，零 Canvas，零图表库。
- 零外部字体，只用系统栈。
- 交互只用原生 JS。

BumpEase 报告：11 章，00–10。
每章一个结论句作 H2。

Medela 报告：7 段竞争战略叙事。
每段先给结论 H2，再给一个主视觉。

交付形态可以直接复用。
生成链路要自建。

## 4. 能力图谱

### 4.1 三个动词

| 动词 | 方法 | 请求 | 响应要点 | 计费 |
|---|---|---|---|---|
| discover | `POST /v1/discover` | `query`、`limit`、`minScore`、`includeUnavailable` | `results[]`：provider、endpoint、description、score、tags、metrics、hints | 免费 |
| inspect | `POST /v1/inspect` | `provider`、`endpoint` | agent 向投影：id、description、summary、结构、输入 schema | 免费 |
| run | `POST /v1/run` | `provider`、`endpoint`、`input{body,queryParams,pathParams}` | 同步 200 + output；异步 202 + runId | 计费 |

关键设计取舍：**端点由调用方选，服务端不代选。**

discover 跨全部 provider 排序并返回候选。
run 必须显式 pin `provider + endpoint`。
健康度只作 tie-breaker。
hints 是自由 map，键不固定。

这条取舍值得抄。它把“选错了”的责任与可见性留在调用方。
对本项目更重要的含义：报告里的每一个数字，都能追溯到一次显式 run。

### 4.2 connector 定义结构

授权时 `EndpointDef` 有 10 个顶层 section：

```text
meta · endpoint · request · input · output · usage · auth · timeouts · lifecycle · resources
```

解析规则：`endpoint ?? provider ?? config default`，逐叶回退。

身份由编译器派生：

```text
id = <provider>#<endpoint-path-sans-slash>
```

输入 schema 用 zod v4 编写，编译为 JSON Schema draft 2020-12。
只保留 JSON Schema 能表达的结构。

输出映射是命令式 JS 函数，不是 JSONPath 或模板 DSL。
`utils.json` 只提供受限的 JSONPath 读助手。

钩子函数必须是闭项：不可 import，不可捕获变量。

这套协议的可迁移点只有一个：**契约先行**。
不必照搬 TypeScript 与 zod。

### 4.3 错误模型

| 错误 | 含义 | 可重试 |
|---|---|---|
| `BAD_DOC` | 定义非法 | 否 |
| `UNSUPPORTED_DOC` | 引擎版本不支持该契约 | 否 |
| `INVALID_INPUT` | 输入不合法 | 否 |
| `FN_CONTRACT` | 钩子返回不符合契约 | 否 |
| `EXECUTION_FAILED` | 执行失败 | 是 |
| `RESOURCE_OP_FAILED` | 资源操作失败 | 是 |

供应商非 2xx 不是错误。
它是成功信封，带 `isProviderError=true`、零用量、可选 `output.fromError`。

这条设计对报告很重要：
**“查了但没结果”必须是一种可交付的结果，不是一个异常。**

## 5. 报告产物解剖

### 5.1 最小内容单元：六段式 exhibit

两份报告反复使用同一结构。

| 段 | 内容 | 例 |
|---|---|---|
| 1 | 结论式图题 | “24 条舒适或外观正向记录中，14 条仍出现支撑、适配或稳定性问题” |
| 2 | scope + 证据徽章 | “68 independent coded units” + `DIRECTIONAL · PRE-G7` |
| 3 | 图表 | CSS grid 条形图、热力图、瀑布、矩阵 |
| 4 | 三段读图 | Interpretation / Counterevidence / Decision |
| 5 | 人声 | “人工释义，不是原文引语 · `g4_7f02…`” |
| 6 | 来源脚注 + 折叠证据 | Basis / Unit / Limit / Status，加定义与数据表 |

第 4 段是核心。
每个结论强制配一个反向字段。
Interpretation 配 Counterevidence。
Claim 配 Evidence gap。
数字配 Limit。
报告配 Forbidden conclusions。

### 5.2 可信度表达：五件套，不是百分比

两份报告不用脚注、不用编号引用、不给外部 URL。

它们用五件套：

```text
证据等级 + 样本量 + 时间窗 + 来源 artifact + 限制
```

没有数值置信区间。

证据等级是离散状态。

| BumpEase | Medela | 含义 |
|---|---|---|
| Confirmed fact | Verified | 已核实 |
| Directional | Supported | 方向性支持 |
| Supported hypothesis | Hypothesis | 假设 |
| Evidence gap | — | 证据缺口 |
| Blocked claim | Blocked | 门禁阻断 |

报告还把禁止输出写成显式清单。
BumpEase 附录列出 7 类禁止结论。

### 5.3 区块的自动化分类

25 类区块分三档。

| 档 | 含义 | 数量 | 例 |
|---|---|---|---|
| A | 确定性模板，数据驱动 | 约 15 | 门禁条、KPI 条、图表、矩阵、来源脚注、校验记分卡、run ledger |
| B | LLM 起草 + 人工批准 | 约 7 | 首屏主张、SCQA、读图结论、人群叙事、实验卡 |
| C | 必须人工判断 | 约 3 | 战略定位坐标、市场优先级权重、竞品角色、claim/医疗/法务复核、gate 判定 |

至少 8 类判断不能自动化：

1. 决策问题与 owner。
2. 战略定位坐标。
3. 市场优先级权重。
4. 竞品角色。
5. claim / 医疗 / 法务复核。
6. 人群命名与 JTBD。
7. gate PASS/FAIL。
8. 实验资源分配。

我们把这份清单写进产品规格。
它决定“AI 能做什么”的边界，也决定交互里必须有人工批准点。

### 5.4 视觉规格

BumpEase：编辑式咨询简报。

```text
--brand #9b626c · --brand-deep #744650 · --brand-soft #f7ecee
--paper #fbfaf8 · --surface #fff · --surface-2 #f5f2ef
--ink #252321 · --ink-2 #625c58 · --ink-3 #857d78
--line #e3ddd8
--love #547867 · --risk #a55b52 · --amber #a87332 · --blue #4f6f84
--positive #3f6b57 · --negative #a5534b · --candidate #45687d
--qual #756078 · --unknown #8a827d · --chart-grid #ded7d1
--radius 18px · --content 1180px · --nav 68px · --report-width 1220px
h1 clamp(40px, 5.4vw, 64px) · letter-spacing -.045em
h2 clamp(32px, 4.2vw, 48px)
body 16px / 1.66
```

Medela：酒红咨询 deck。

```text
--wine #6c2c3c · --rose #9b626c · --label #7b3446
--ink #261c1e · --muted #716368 · --line #eadcdb
--canvas #fcf8f7 · --paper #fff
--blush #f7ebea · --sand #f3eee9 · --sage #e5eee8
--gold #bd8754 · --good #34705b · --warn #8b4528
--radius 18px · --max 1240px
--shadow 0 16px 46px rgba(70,32,42,.09)
h1 clamp(38px, 5vw, 68px) · line-height .99 · letter-spacing -.066em
```

共同手法：

- 超大标题对 10–12px micro label。
- 白卡片对纸色背景。
- 低饱和主色对语义色。
- 数字用 `tabular-nums`。

图表实现：

| 类型 | 实现 |
|---|---|
| 条形 | 外层 grid + 内层 `width:xx%` |
| 热力图 | CSS grid + 分档背景色 |
| 瀑布 | flex 列 + 固定高度 |
| 矩阵 | grid 单元格 + 边框 |

没有 tooltip，没有排序。这是取舍，不是缺陷。

### 5.5 交互

BumpEase 六类：

1. 锚点导航。
2. 明暗主题。
3. 打印。
4. 全量证据抽屉。
5. aspect family 筛选。
6. 需求象限选择。

Medela 四类：

1. 市场筛选。
2. 人群 tab（支持方向键）。
3. 复制战略一句话。
4. 滚动高亮导航。

共同性质：状态全落 DOM 属性。
`aria-pressed` / `aria-selected` 表示选中。
`hidden` 表示过滤。
`data-theme` 表示主题。
`open` 表示折叠。

没有路由，没有状态库，没有 fetch。

### 5.6 你给的四份产物的实测数字

| 指标 | 值 |
|---|---|
| `siteData` 长度 | 64,467 字符 |
| `siteData` sha256 前 16 位 | `af5607158f0970ed` |
| skills | 14 |
| skillValidation.checks | 177 |
| coverage 键 | 51 |
| Medela run 数 | 109 |
| Medela 成本 | $11.08355 |
| BumpEase 调用数 | 21 |
| BumpEase 成本 | $0.11580 |
| aspect codes | 48 |
| annotations | 212 |
| Medela 市场数 | 7 |
| Medela evidence boundary 条数 | 14 |

注意一处未完成：
siteData 与 HTML 只部分绑定。
只有 `needStates` 与 `skills` 在运行时读取。
多处 headline 数字是构建时写死的。

复刻时要把全部区块绑定到数据合同，否则数字会漂移。

## 6. 可复用判定

### 6.1 直接复用

| 资产 | 用法 |
|---|---|
| 报告六段式 exhibit | 直接作为生成模板的最小单元 |
| 五件套可信度表达 | 作为证据字段的强制集合 |
| 离散证据等级 | 作为 claim 状态机 |
| 一份数据合同、两个渲染器 | 报告与 SOP 同源 |
| 单文件 HTML 交付 | 离线可看、可打印、可归档 |
| 目录骨架与紧凑行 | 目录页布局 |
| 详情页内嵌 playbook | 能力详情页结构 |
| `SKILL.md` 四道机制 | agent 接入包设计 |
| 三个动词 | API 语义 |

### 6.2 不能复用

| 资产 | 原因 |
|---|---|
| 订阅式定位与“kill subscriptions”叙事 | 我们是企业内部工具，不做订阅 |
| 目录的客户端异步加载 | 不可抓、不可分享、SEO 为零 |
| endpoint modal 缺 schema | 是产品缺口，不是设计 |
| 博客 144 篇薄内容 | 我们不做 programmatic SEO 内容库 |
| Mintlify 托管 | 数据留在外部，且品牌不可控 |
| 二进制星号背景与 90px 标题 | 与 B2B 工作台密度冲突 |
| 钱包、promo code、x402 支付 | 内部结算用额度就够 |

### 6.3 建议采用的表现方式

| 维度 | Monid | 本项目 |
|---|---|---|
| 底色 | 纯白 | 暖纸 `#f7f2ed` |
| 主色 | 蓝 `#0016d7` | 玫瑰 `#9b4355` |
| 展示字体 | Outfit | 系统中文字体栈 |
| 说服机制 | 数量与密度 | 证据与可复核 |
| 首页长度 | 5,810px | 4,500–5,500px |
| 目录默认 | 卡片网格 | 行 |
| 报告生成 | 外部 agent | 内置，受门禁约束 |

## 7. 对 DIH 的含义

三条结论。

**第一，执行器不是瓶颈。**
现有 86 个注册采集器已覆盖真实数据源。
缺的是契约层、编排层、证据层、渲染层。
这四层都在我们这边，不在 Monid 那边。

**第二，报告能力要自建，且要比 Monid 强。**
Monid 的报告靠外部 agent 自由生成，没有门禁，没有 claim 模型。
我们可以做成可校验、可复现、可审计的。

**第三，我们必须先修好目录。**
当前 303 条能力视图里有 31 条不可执行条目。
这些 Apify 端点只在 quick-collect，不在目录。
目录不可发现，上层全部失效。

详见 [PRD](../product/【PRD】母婴出海数据洞察Agent工作台.md) 第 1 节与第 5 节。

## 8. 残余限制

本轮未能取到的事项，逐条列出，不编造。

1. `app.monid.ai` 登录态的真实视觉。除侧栏与 Clerk 登录弹窗外，页面结构来自压缩 bundle。
2. `api.monid.ai` 后端源码。公开仓库只是 connector 层。
3. discover 排序模型、分数归一化、候选生成算法。
4. 服务端或 feature flag 注入的隐藏路由。客户端路由表只能证明当前客户端没有它们。
5. 真实延迟与成功率。公开页面不展示。
6. 目录统计口径。官网写 1,700+，README 写 2,000+/72+，app 写 1,700。
7. 价格汇总页。Monid 没有 `/pricing` 页，也没有 changelog。
8. `sitemap` 与目录 API 的差异原因。sitemap 235 个 `/tools`，API 206 个。
9. 博客 readTime 的生成逻辑。132/144 篇标 5 min，疑为默认值。
10. 2026-09-23 两份报告的生成客户端与耗时。HTML 无 generator 元数据。
11. 移动端交互。只验证了布局与字号，未逐项验证触摸行为。
12. Monid 自身的真实可用性。904/1,034 个 fixture 为合成数据，多个 provider 从未用真实 key 验证。

最后一条值得记住：
**Monid 的目录规模是声明值，不是实测值。**
我们不要复制这个错误。
