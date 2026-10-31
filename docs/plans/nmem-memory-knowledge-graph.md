---
name: nmem-memory-knowledge-graph
description: 为 Source 项目（data_scrapy）构建 Nowledge Mem 记忆系统与知识图谱的执行方案：六步法改造、六项 blocker 裁决、四层记忆定稿、本体定稿、10 张 ticket 执行序列与验收基线
doc_type: plan
module: M00-治理
topic: nmem 记忆系统与知识图谱
status: 待批准
created: 2026-10-31
updated: 2026-10-31
owner: Pray
source: .lody/attachments/04c87dda-SOP_Nowledge_Mem_智能体记忆系统与知识图谱构建规范.md
---

# Nowledge Mem 记忆系统与知识图谱 · Source 项目执行方案

状态：已批准（2026-10-31 用户批准，自 KG-00/KG-02 起执行）　｜　盘点：2026-10-31　｜　实测方式：7 个并行读者侦察仓库 + nmem 0.10.111 只读探针 + 完整性批评者复核

## §0 先读

- SOP 原文：`.lody/attachments/04c87dda-SOP_Nowledge_Mem_智能体记忆系统与知识图谱构建规范.md`（该路径被 `.git/info/exclude` 忽略，不可复现；KG-00 将其收编为 `docs/standards/nmem-memory-sop.md`）。
- 本方案的证据底稿：`tmp/nmem-plan/recon_full.json`（7 读者结构化侦察 + 批评者结论，349 KB；`tmp/` 不入库，KG-04 生成蒸馏脚本后此文件可删）。
- 关联文档：`AGENTS.md`（仓库红线）、`docs/design/【契约冻结】v1-表名-枚举-接口.md`（口径真源）、`docs/standards/project-workspace-hygiene.md`（ticket 惯例）。

## §1 目标与范围

**做什么**：按 SOP 六步法为本项目建立专属 Nowledge Mem 空间——空间与身份、常驻守门规则、Working Memory、Library 真源归档、四层记忆蒸馏入库、领域本体与知识图谱、环境固化与运行时 recall、验收报告。

**不做什么**：
- 不把 101 条原始候选直接批量入库。去重后目标 45 条（L1×6、L2×16、L3×14、L4×9）+ 3 条 Space Rules。
- 不动 pr-agent / si-agent / kb-consultant-agent 三个既有空间，不写 global 本体。
- 不接入生产数据管线。L4 只用已有报告与文档归纳，本期不接 DuckDB（§7 R12）。
- 不改产品代码。recall 插件是新增独立函数与测试，不改主链路。
- 不用 `mcp__memory__`（会话内另一套 SQLite 知识图谱）写本项目任何数据。nmem 是唯一记忆与图谱后端。

## §2 现状盘点（2026-10-31 实测）

| 项 | 现状 |
| --- | --- |
| nmem 版本 | 0.10.111，local 模式，`http://127.0.0.1:14242`，embedding=local-gguf |
| 既有空间 | default(129)、pr-agent(263)、si-agent(960)、kb-consultant-agent(77)；**无本项目空间** |
| 既有身份 | lody-pray、vicky、social-leader、kb-consultant；**无本项目身份** |
| 全局本体 | revision 7：13 objectTypes + 14 linkTypes，407 实体/374 关系；`extraction.active=false`（gate=fallback_one_shot_model_not_tool_capable） |
| default 空间存量 | 已有本项目相关记忆 ≥7 条（cf515aec 关键数字口径、fc8f5b4a 日报任务、2047b5da 等 5 条产品方向/4P） |
| 仓库落点 | `tools/dev/`、`artifacts/` 不存在；`settings.local.json` 只有 permissions、无 env；`tests/` 根只有 .gitkeep |
| ticket 惯例 | `docs/tickets/<PREFIX>-<日期>-<slug>.md + .json` 成对；状态枚举：未开始/进行中/阻塞/已完成 |

## §3 六项 blocker 裁决（执行前置条件）

| # | 问题 | 裁决 | 依据 |
| --- | --- | --- | --- |
| B1 | L1 红线写成 memories 不会随 Context 注入 | **L1 核心准则同时写两份**：2-3 条 Space Rules（priority 100/90/80，随 context bundle 必定注入）+ memories 中 `decision` 副本（供语义检索）。SOP 第 2 层逻辑按此修正 | 实测 context bundle 只有 rule_stack 与 working_memory，无 memories 键 |
| B2 | default 空间已有本项目记忆，违反单一真源 | **move 到新空间 + 过时者 supersede**：fc8f5b4a（日报任务）、cf515aec（关键数字口径）move 并补日期标注；2047b5da、8a2d81a9、f0df67a7、31a80ce3、1be338d5（产品方向/4P）merge 进 ds-l4-09 后归档。不复制第二份 | SOP「真源唯一性」；nmem 有 `memories move`/`supersede` 子命令 |
| B3 | SOP 示例 `ontology apply --file` 默认 scope=global | **强制修正：必须 `--scope space --space-id <id>`**。且 space scope 是整体替换不是合并，patch 必须自含全部要用的 objectTypes 与 linkTypes | 实测 kb 空间 effective 本体不含全局 BRAND/COMPETITOR |
| B4 | 约 100 个本体候选 key 同义泛滥 | **收敛为 26 objectTypes + 27 linkTypes，统一 UPPER_SNAKE + 领域前缀**，见 §5 定稿表。禁用裸 Project/Platform/Provider/Report/Task/Claim 等通用词 | 与全局及 kb 空间共用命名空间；SOURCE 三义必须拆分 |
| B5 | 数字口径多版本冲突（能力 311/312、schema 053/056/057/067、MCP 39/25/36、禁写 12/14、domain 8/5） | **统一写法**：每个数字带「口径日期 + digest + 计数类型」；冲突值不合并，写「代码 X / 契约 Y，待同步」或「生产 YYYY-MM-DD 实测 = N，lock = M」。生产 schema 以 /api/health 实测为准，入库前实测一次 | 成果总结 §7；批评者 dedupeNotes |
| B6 | extraction.active=false，只 apply 本体不产生图谱实体 | **分两期**：P1 交付本体词汇表（space scope）+ 记忆检索验收；P2（KG-07）显式 seed 核心实体与关系（先探针 `nmem entities` 语法再执行），seed 后才算图谱验收通过 | 全局 extraction 被模型能力门禁关断 |

## §4 四层记忆定稿（45 条 + 3 Rules）

分层与 SOP 一致；`unit_type` 只用 8 枚举；`importance` 按 0-1；`--when` 只取 past/present/future/timeless。确定性 ID 前缀 `ds-`（`memories add --id` upsert 语义，重复运行不产生重复记忆）。

**第一层 核心准则（L1，importance 1.0，decision，when=timeless）** — 6 条 memories + 3 条 Space Rules：

| ID | 标题 |
| --- | --- |
| ds-l1-01 | 产品身份与 provider_call 红线：纯数据采集平台，Provider 调用必经 collector 层 |
| ds-l1-02 | 密钥与敏感文件红线：凭据禁入仓库、禁入记忆、禁入图谱；compose environment 列表同步 |
| ds-l1-03 | 共享基础设施与生产隔离红线：不删 lighthouse_ai_video_net、不重建 edge、生产只读优先 |
| ds-l1-04 | 发布红线：先 push 再发布、fetch+merge --ff-only、重建 api 后必 restart edge、热替换不算发布 |
| ds-l1-05 | 双生产差异纪律：A=main、B=deploy/tiktok-cdo-codex，差异只允许 CDO Agent 一处 |
| ds-l1-06 | 能力边界红线：不加官方 Reddit/YouTube collector，不恢复 Shopee 直连 |

Space Rules：R1（P100）人设与决策优先级 + 四条红线摘要；R2（P90）仓库物理边界与数据纪律（含「nmem 唯一后端、raw/secret 不入记忆」）；R3（P80）口径纪律（数字带日期+digest、契约冻结优先、证据只认 `[test]` label）。

**第二层 业务口径（L2，importance 0.9，fact，when=timeless）** — 16 条：

| ID | 标题 |
| --- | --- |
| ds-l2-01 | 契约冻结 v1.1 是唯一契约来源（冲突时忽略设计文档） |
| ds-l2-02 | 冻结表名与运行语义：runs/run_steps/task_runs/workflow_runs 四表不混；禁 automation_ 前缀 |
| ds-l2-03 | 运行/步骤/结果/健康度/claim/门禁枚举互斥（degraded 只在 health；partial 非法 outcome） |
| ds-l2-04 | 能力口径三分法：平台/能力视图/唯一端点；生产 2026-10-21=70/311/283，lock=70/312/284，digest 35ead4d9 |
| ds-l2-05 | 端点六态词表与 verified 语义（verified=最近一次 [test] 实测成功，非永久承诺） |
| ds-l2-06 | 两套证据等级不可混用（run L0-L4 五级 vs VOC 六级） |
| ds-l2-07 | 采集外访安全硬约束（offline/restricted 两态；一 collector 一配置；hosts≤5；timeout≤60s） |
| ds-l2-08 | 控制台信息架构契约：一级导航四项冻结（routes.ts P0） |
| ds-l2-09 | MCP 工具数四口径：@_tool=39（现行）/ TOOL_POLICIES=23 / README 25 旧 / registry 文档串 36 旧 |
| ds-l2-10 | 整站方案首期 13 项不做（范围已确认、未实施） |
| ds-l2-11 | 迁移链纪律：命名规则、source-only、ADR-007 D1、alembic heads 单行；生产 schema 版本待实测 |
| ds-l2-12 | ABI raw 湖契约：路径模板、归因链、分区、mask_rule 白名单、NUL 剔除 |
| ds-l2-13 | HTTP 错误信封与 Project.domain：代码 8 值 / 契约 5 值，待同步 |
| ds-l2-14 | 新增采集能力七处注册面 + 证据标签精确为 `[test] <endpoint_type>` |
| ds-l2-15 | 双前端分工：console 公网主界面；web 仅 /insight 内部；共享宿主机隔离规则 |
| ds-l2-16 | 写作标准与术语表：ASD-STE100 等效规则；术语以整站方案 §1.1 为准（指向文档，不抄全文） |

**第三层 避坑实证（L3，importance 0.85，learning，when=timeless 或 past）** — 14 条：

| ID | 标题 |
| --- | --- |
| ds-l3-01 | 假绿灯验收：build/curl 200/SUCCEEDED 都不算通过，看 records_count 与真实响应 |
| ds-l3-02 | config-gated ≠ degraded ≠ Connection refused 判据与处置差异 |
| ds-l3-03 | Apify 403 判据（2 秒内=下架/拒号）；inputSchema 为准；占位 ID 禁用 |
| ds-l3-04 | status=success 但 0 条：先取原始响应比对形状，勿反复调参 |
| ds-l3-05 | edge 502 根因：共享网关缓存旧容器 IP（172.20.0.16），重建 api 后必 restart edge |
| ds-l3-06 | .env.production 不生效根因：compose 显式 environment 列表；restart 不重读 env-file |
| ds-l3-07 | 服务器 git 纪律：不 pull、不 reset --hard；管道吞退出码；pgrep 自匹配 |
| ds-l3-08 | 中文文件写坏：+4096 尾洞与 NUL 字节的检测修复；jsonb 拒绝 \u0000 |
| ds-l3-09 | 构建期烧录与国内镜像：NEXT_PUBLIC 烧录、uv.lock 绝对地址、跨环境串台 |
| ds-l3-10 | worktree editable venv / PYTHONPATH 陷阱；GitNexus UNKNOWN ≠ 安全 |
| ds-l3-11 | 坑点库是生成物：只改 notes JSON，target 必须真实存在，改完重建 api |
| ds-l3-12 | ABI 生产暗坑：审批缺省放行、worker 未启动、actual_rows 漏记、export_policy 重复行 |
| ds-l3-13 | quick-collect 落库计费：无 save_records 开关；policy_block 不重试 |
| ds-l3-14 | MCP 生产三事故（空 token、未知 project_id、元键误删）；回填上限与字段漂移 |

**第四层 沉淀纪要（L4，importance 0.7-0.85，context，when=past）** — 9 条：

| ID | 标题 |
| --- | --- |
| ds-l4-01 | Source 项目能力画像 2026-10-31（142 天/926 提交/70 平台/五层能力；注明推导值） |
| ds-l4-02 | 10 月里程碑时间线（10-18 双生产、10-19 TikTok R1、10-29 ABI、10-31 VOC） |
| ds-l4-03 | 32 star 仓库五态结论：11 个「已集成」拿不到干净数据 |
| ds-l4-04 | Apify 十平台选型：按 30 天成功率选主力，官方出品 ≠ 稳定 |
| ds-l4-05 | VOC 管线能力边界：六档证据、禁写 FC-01..FC-12、G7 后指标缺口 |
| ds-l4-06 | 双生产演进与发布事实：账本 15 条只记成功；B 自动发布阻塞 |
| ds-l4-07 | 报告资产与命名约定：Source-项目成果总结-YYYYMMDD；21:07 launchd；reports 需 git add -f |
| ds-l4-08 | 历史快照时效：2026-08 文档与 TODO.md 已被 10 月事实修订 |
| ds-l4-09 | 产品方向：采集平台 → 通用 Agent 工具平台（未实施）+ 业务 4P 视角重构（吸收 default 空间 5 条） |

去重裁决依据：能力口径簇、发布簇、契约簇、写作簇等 18 组重复的取舍见 `tmp/nmem-plan/recon_full.json` 的 critic.dedupeNotes；KG-04 执行时逐条遵守。

## §5 知识图谱本体定稿基线

对象 26 个、关系 27 个。统一 UPPER_SNAKE；`displayName` 中文；每条 `description` 写清承载字段与判定边界。**space scope 整体替换**：本表即完整 patch，不含继承。

### §5.1 objectTypes（26）

| Key | 显示名 | 说明 |
| --- | --- | --- |
| COLLECTION_PROJECT | 采集项目 | Project 表实例，domain 属性 8 值 |
| PROJECT_DOMAIN | 项目业务域 | 代码 8 值枚举节点（osint/ecommerce/social/competitor/agent/platform/governance/mixed），用于跨项目聚合 |
| COLLECTION_SOURCE | 采集数据源 | 数据源配置；与知识来源（kb 的 SOURCE）、产品名 Source 三义分离 |
| COLLECTION_PLATFORM | 采集平台包 | platform_id，70 个 |
| COLLECTION_CAPABILITY | 能力视图 | capability_id，按 catalog 条目计 |
| COLLECTION_ENDPOINT | 唯一采集端点 | endpoint_type 去重 |
| COLLECTION_COLLECTOR | 采集器实现 | collector_type 代码类；与端点（上游接口）是两类节点 |
| COLLECTION_PROVIDER | 采集 Provider | 15 个分组 |
| COLLECTION_TASK | 采集任务 | task_runs 的调度主体（M04） |
| COLLECTION_TASKRUN | 任务运行 | task_runs 表 |
| RUN | 工作台运行 | runs 表（M10 编排），与任务运行区分 |
| RUN_STEP | 运行步骤 | run_steps 表 |
| RAW_RECORD | 原始记录 | 采集落库原子单元 |
| DATASET | 数据集 | 逻辑数据集 |
| DATASET_VERSION | 数据集版本 | 版本化快照 |
| INSIGHT_REPORT | 洞察报告 | 报告产物（M07 唯一报告入口） |
| INSIGHT_CLAIM | 主张 | 主 API claims；与 VOC 主张两套实现不互映射 |
| INSIGHT_EVIDENCE | 运行证据 | 五级 L0-L4 |
| VOC_CLAIM | VOC 主张 | 六级证据；VOC 子域专用 |
| VOC_GATE | VOC 交付门 | PASS/CONDITIONAL/BLOCKED/NOT_STARTED |
| DEPLOY_ENV | 部署环境 | A=scrapy.luteos.com / B=scrapy.lute-tlz-dddd.top / 本地 |
| OPS_RELEASE | 发布记录 | releases.jsonl 条目 |
| DIH_MODULE | 业务模块 | M01-M12 + K0 |
| PRODUCT_AGENT | 产品内 Agent | shusuo、tiktok_cdo（registry.json） |
| PITFALL | 坑点 | 坑点库条目（scope/target/symptom/cause/workaround） |
| DOC_ASSET | 文档资产 | 方案/规范/ADR/复盘/报告统一承载，doc_kind 属性区分；不单建 Runbook/Retrospective 等 |

### §5.2 linkTypes（27）

| Key | 显示名 | from → to |
| --- | --- | --- |
| BELONGS_TO_DOMAIN | 属于业务域 | COLLECTION_PROJECT → PROJECT_DOMAIN |
| HAS_SOURCE | 配置数据源 | COLLECTION_PROJECT → COLLECTION_SOURCE |
| TARGETS_SOURCE | 面向数据源 | COLLECTION_TASK → COLLECTION_SOURCE |
| RUNS_ON_COLLECTOR | 由采集器执行 | COLLECTION_TASK → COLLECTION_COLLECTOR |
| PRODUCES_TASKRUN | 产生任务运行 | COLLECTION_TASK → COLLECTION_TASKRUN |
| DELEGATES_TO_TASKRUN | 委托任务运行 | RUN_STEP → COLLECTION_TASKRUN |
| INVOKES_ENDPOINT | 调用端点 | RUN_STEP → COLLECTION_ENDPOINT |
| EMITS_RECORD | 产出原始记录 | COLLECTION_TASKRUN → RAW_RECORD |
| RESOLVED_BY_COLLECTOR | 由采集器解析 | COLLECTION_ENDPOINT → COLLECTION_COLLECTOR |
| SERVED_BY_PROVIDER | 由 Provider 提供 | COLLECTION_ENDPOINT → COLLECTION_PROVIDER |
| PACKAGED_IN | 打包进平台 | COLLECTION_CAPABILITY → COLLECTION_PLATFORM |
| MAPS_TO_ENDPOINT | 映射到端点 | COLLECTION_CAPABILITY → COLLECTION_ENDPOINT |
| MATERIALIZES_DATASET | 物化为数据集 | RAW_RECORD → DATASET_VERSION |
| HAS_VERSION | 拥有版本 | DATASET → DATASET_VERSION |
| SUPPORTS_CLAIM | 支撑主张 | INSIGHT_EVIDENCE → INSIGHT_CLAIM |
| GROUNDS_IN_RECORD | 落在原始记录 | INSIGHT_EVIDENCE → RAW_RECORD |
| PUBLISHES_CLAIM | 发布主张 | INSIGHT_REPORT → INSIGHT_CLAIM |
| GATED_BY | 受门禁约束 | VOC_CLAIM → VOC_GATE |
| DEPLOYED_TO | 部署到 | OPS_RELEASE → DEPLOY_ENV |
| RUNS_IN_ENV | 运行于 | PRODUCT_AGENT → DEPLOY_ENV |
| OWNED_BY_MODULE | 归属模块 | COLLECTION_TASK → DIH_MODULE（其余类型按需扩 from） |
| DEPENDS_ON_MODULE | 依赖模块 | DIH_MODULE → DIH_MODULE |
| QUERIES_CAPABILITY | 调用能力 | PRODUCT_AGENT → COLLECTION_CAPABILITY |
| AFFECTS_ENDPOINT | 影响端点 | PITFALL → COLLECTION_ENDPOINT |
| AFFECTS_PROVIDER | 影响 Provider | PITFALL → COLLECTION_PROVIDER |
| MITIGATED_BY | 缓解方案在 | PITFALL → DOC_ASSET |
| SUPERSEDES | 取代 | DOC_ASSET → DOC_ASSET |

命名红线（L1 级，写入本空间规则）：禁用裸 Task/Report/Platform/Provider/Dataset/Claim/Gate/Source/Release；不复用全局 MONITORS（品牌监控语义）、COMPETES_WITH（品牌竞争语义）。

> **§5.2 修订（KG-02 冒烟 S1，2026-10-31）**：实测服务端 patch 的 linkTypes **不接受 `from`/`to` 字段**（合法字段仅 key/displayName/labels(map)/inverseDisplayName/directional/domain(字符串数组)/status），objectTypes 的 labels 也是 map 类型。因此上表 from→to 列是**文档级约定**，不入 patch；建边语义由 `memories link add --type <relation>` 的 relation 字符串与 reason 承载。KG-06 的 patch 按实测 schema 生成。

## §6 执行序列与 ticket 映射

三阶段，10 张 ticket（`docs/tickets/KG-2026-10-31-nmem-bootstrap.*`）：

```
阶段 0 裁决与准备        阶段 1 冒烟与定稿           阶段 2 建库与验收
KG-00 SOP收编+方案批准 ─┬─ KG-01 存量去重 ─┐
                        └─ KG-02 写路径冒烟 ┴─ KG-03 空间/身份/规则/WM
                                              ├─ KG-04 蒸馏脚本+45条记忆 ─┐
                                              ├─ KG-05 Library 白名单归档  ├─ KG-08 环境固化+recall+单测
                                              └─ KG-06 本体patch+space应用 ┘        │
                                                    KG-07 实体seed(P2) ────────────┴─ KG-09 验收报告
```

- **串行点**：KG-02 冒烟全绿前不批量写；KG-06 本体定稿前 KG-07 不启动。
- **并行点**：KG-01 与 KG-02 并行；KG-04/05/06 并行。
- 验收基线在 §8，逐条映射 ticket。

## §7 风险与红线

| # | 风险 | 对策 |
| --- | --- | --- |
| R1 | nmem CLI 与 SOP 至少 7 处硬差异（working-memory 无 show、rules list 不收 --space、ontology 只认 --space-id、enroll create-only、update 不支持 --when、--labels 逗号分割、ontology 默认 global） | 所有 ticket 命令以 §3 与探针实测为准，不照抄 SOP |
| R2 | ontology 误写 global 污染全部空间 | 红字规范：一律 `--scope space --space-id`；KG-02 冒烟在 scratch space 先验证 |
| R3 | space 本体整体替换，patch 漏声明即丢关系 | patch 以 §5 完整表为准；应用后 `ontology show --space-id` 逐条比对 |
| R4 | ontology 无 delete 子命令，错类型留在 revision 里 | 先在 scratch space 试错；正式空间 apply 前本地 JSON schema 校验 |
| R5 | 确定性 ID 用 update 触发 422（is_latest=false） | 一律 `memories add --id` upsert；出现 422 用 `delete --force` 后同 ID 重建 |
| R6 | MIME 陷阱在 0.10.111 未复测 | KG-05 先单文件预检 mime_type/lifecycle_state，再决定是否转 `.markdown`；白名单制、禁 glob |
| R7 | settings.local.json 不入库、只影响本机 | 编辑保留原 permissions；文档注明「本机配置，不入库不同步」 |
| R8 | 中文文件 +4096 尾洞 | 每个写文件动作后跑 `scripts/check_file_integrity.py`；提交钩子 `.githooks` 生效（`git config core.hooksPath .githooks`） |
| R9 | default 空间双源 | KG-01 按 B2 裁决 move/supersede，完成后检索验证双源归零 |
| R10 | 显式关系有 per-memory 422 门（kb 经验 10/12 生效） | 验收允许已知失败并记录重放条件，不承诺 100% 建链 |
| R11 | 检索分数受中文语料与 local-gguf 影响，0.70 阈值未验证 | KG-09 用固定 10 查询实测并记录每次分数；低于 0.70 的记录原因，不粉饰 |
| R12 | DuckDB 单写约束 | 本期 L4 不接 DuckDB；如接，只读导出副本（shutil.copy2 后 read_only），不碰源库 |
| R13 | SOP 附件路径不可复现、reports/ 被 gitignore | KG-00 收编 SOP 入 docs/standards；报告入库用 git add -f |
| R14 | nmem 服务 local 模式，重启即失败 | recall 3 秒超时 + 全捕获降级 + 默认关闭（env 门控）；记忆是增强，不是依赖 |

## §8 验收基线（对 SOP 8 条的修正版）

- [ ] Space：`nmem --json spaces list` 列出 `source-agent`，retrieval_mode=strict。
- [ ] Identity：`nmem --json agents list` 存在 `source`，default_space 正确。
- [ ] Context：`nmem --json context --space source-agent` 输出 rule_stack（≥3 条空间规则）+ working_memory（含 Focus Areas/Briefing）。
- [ ] Library：`nmem --json library list --space source-agent` 全部 indexed、错误 0、白名单外文件 0。
- [ ] 记忆：45 条确定性 ID 全部存在，重复执行蒸馏脚本后总数不变（幂等）。
- [ ] 检索：固定 10 查询（红线/能力口径/发布/Apify/VOC/契约/坑点/里程碑/报告/方向）逐条记录 Top1 分数；目标 ≥0.70，不达标写明原因。
- [ ] 本体：`nmem --json ontology show --space-id source-agent` 与 §5 表逐条一致；global 本体 revision 不变。
- [ ] 图谱：KG-07 seed 后，核心链路（平台包→能力视图→端点→采集器→Provider；任务→运行→记录→数据集）在 `nmem entities`/桌面端 ⌘5 可见。
- [ ] 测试：`test_source_nmem_recall.py` 真实检索 + 超时降级用例全绿（落点 apps/api/tests/unit/，见 KG-08）。
- [ ] Git：约定式提交归档；提交前跑 GitNexus `detect-changes --scope all` 与 `check_file_integrity.py`。

## §9 与既有工作的关系

- **SP-Agent-TODO（65 条）**：不并入。本批 KG 独立台账；两者仅共享仓库规范。
- **Feishu 真源**：本批 ticket 仓库文件为工作真源；如需同步飞书由用户另行指派。
- **KB 空间既有经验**（22 条四层记忆、MIME 预检、422 修法、recall 门控）作为执行基线复用，不重新发明。
- **口径修正回写**：KG-09 发现的文档漂移（README MCP 25、AGENTS.md 309/281、schema 四版本）只记录，不擅自改文档；修文档属 SP 批次范围。
