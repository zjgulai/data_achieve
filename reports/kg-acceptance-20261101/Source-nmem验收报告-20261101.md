---
name: Source-nmem验收报告-20261101
description: KG-2026-10-31 批次全流程验收：10 条基线全 PASS、10 固定查询 avg 0.976、漂移清单与本批次交付物索引
doc_type: report
module: M00-治理
topic: nmem 记忆系统与知识图谱
status: 已完成
created: 2026-10-31
updated: 2026-10-31
owner: Pray
source: docs/plans/nmem-memory-knowledge-graph.md §8
---

# Source nmem 记忆系统与知识图谱 · 验收报告（KG-2026-10-31）

验收日期：2026-10-31　｜　方案：`docs/plans/nmem-memory-knowledge-graph.md`（§8 十条基线）　｜　台账：`docs/tickets/KG-2026-10-31-nmem-bootstrap.{md,json}`

## 一、十条基线核验（全部 PASS）

| # | 基线 | 结果 | 证据 |
| --- | --- | --- | --- |
| 1 | Space | PASS | `spaces list` 列出 source-agent，defaultRetrievalMode=strict |
| 2 | Identity | PASS | `agents list` 存在 source，default_space=source-agent |
| 3 | Context | PASS | `context --space source-agent` rule_stack.space 3 条（P100/P90/P80）+ WM 含 Focus Areas/Briefing |
| 4 | Library | PASS | 11/11 indexed，error 0，白名单外 0 |
| 5 | 记忆幂等 | PASS | ds-* 45/45（L1×6/L2×16/L3×14/L4×9）missing=NONE；蒸馏脚本第二遍 44 skip 总数不变 |
| 6 | 本体 | PASS | space effective 26 objectTypes + 27 linkTypes 与 patch sorted 一致；global 仍 13/14 无污染（store.revision 递增属全局计数器，类型面未变） |
| 7 | 图谱 | PASS | ⌘5 全景图 source-agent 节点 11（4 旧 Reddit VOC 实体 + 记忆节点 + 18 条显式链入图，graph expand 见 edges） |
| 8 | 测试 | PASS | `pytest tests/unit/test_nmem_recall.py` 5/5 passed；`ruff check` 0 error（KG-08 实测，venv=apps/api/.venv） |
| 9 | 单一真源 | PASS | default 空间检索本项目口径真源=0（69 条已迁、7 条归档、剩余 63 条为兄弟项目历史） |
| 10 | Recall e2e | PASS | NMEM_RECALL=1 下 `recall_durable_memories("发布红线")` 返回 RECALL_OK（真实检索命中） |

## 二、固定 10 查询检索质量（avg 0.976，全部 ≥0.70）

| # | 主题 | Top1 分数 | Top1 记忆 |
| --- | --- | --- | --- |
| 1 | 红线 | 0.990 | 发布红线（ds-l1-04） |
| 2 | 能力口径 | 0.990 | 能力口径三分法与并存数字（ds-l2-04） |
| 3 | MCP | 0.990 | MCP 工具数四口径（ds-l2-09） |
| 4 | 发布 | 0.852 | 发布四坑与 ADR-007 迁移纪律（KG-01 迁入存量） |
| 5 | Apify | 0.990 | Apify 403 判据与 inputSchema 纪律（ds-l3-03） |
| 6 | VOC | 0.990 | 两套证据等级不可混用（ds-l2-06） |
| 7 | 契约 | 0.990 | 契约冻结 v1.1 是唯一契约来源（ds-l2-01） |
| 8 | 坑点 | 0.990 | 假绿灯验收：四个不算通过的信号（ds-l3-01） |
| 9 | 里程碑 | 0.990 | 10 月里程碑时间线（ds-l4-02） |
| 10 | 方向 | 0.990 | 产品方向：通用工具平台 13 项不做（KG-01 迁入存量） |

说明：SOP 的 0.70 阈值在本机 local-gguf + 中文语料下轻松达标；唯一低于 0.9 的查询（#4，0.852）Top1 是 KG-01 迁入的存量记忆而非 ds-l3-07，两条同主题并存且均正确命中主题域，可接受。

## 三、与方案 §8 基线的偏差记录

1. **图谱验收口径调整**（方案 B6 预案执行）：extraction.active=false（gate=fallback_one_shot_model_not_tool_capable）且 CLI/REST 均无实体 create 端点（openapi 只有 GET/merge/delete/retype/extract）。一期交付=显式关系链 18 条（`tools/dev/seed_kg_entities.py`，幂等）；实体抽取留待 extraction 开启后执行 `ontology retype` 折叠默认类型（P2 二阶段）。
2. **本体 patch schema 偏差**（冒烟 S1）：linkTypes 无 from/to 字段；端点约束以 labels.zh 文档约定承载，方案 §5.2 已加修订注记。
3. **relation_type 落库转小写**：RELATES_TO→relates_to，与本体 key 大小写不一致属服务端行为，建链幂等判断已按小写归一。

## 四、漂移清单（只记录，不改文档；属 SP 批次范围）

| 位置 | 现状 | 应为 |
| --- | --- | --- |
| README.md:20 | MCP「25 个工具」 | 代码 @_tool 39（2026-10-31 统计） |
| AGENTS.md:17 | 能力视图 309/286（2026-10-20） | 生产 311/283（2026-10-21 实测），lock 312/284 digest 35ead4d9 |
| AGENTS.md:34 | schema A=202610190045 | 生产 A 各文档有 053/056/057/067 四说，需逐主机 /api/health 实测 |
| README.md:21 | schema A=202610210053 | 同上 |
| AGENTS.md:31 | 部署分支 feat/live-capability-verification-sink-notes | A=main、B=deploy/tiktok-cdo-codex |
| apps/scraper-console/README | 页面路由含 /platforms、/skills 等已过期项 | 以能力图谱 §2 与 routes.ts 为准 |
| docs/design 契约冻结 §C8 | 写迁移 066 建 market_assessments/data_gaps | 202610290066 实际是 field_policy.mask_rule，两表检索不存在 |
| 坑点计数 | 119（生成物 2026-10-15）/ 94（能力总账）/ 107（差距分析） | 以生成物为准并标日期 |
| 禁写数量 | 14（提交信息）/ 12（spec+代码 FC-01..FC-12） | 以 forbidden_conclusions.json count=12 为准 |
| reports/achievements-2026-10/ | 旧版同名报告（基线 0e76364） | 当前版 reports/achievements-20261031/（基线 bfa0b4a） |

## 五、交付物索引

| 类型 | 路径 |
| --- | --- |
| 方案 | docs/plans/nmem-memory-knowledge-graph.md（已批准 + §5.2 修订注记） |
| 台账 | docs/tickets/KG-2026-10-31-nmem-bootstrap.{md,json}（10/10 完成） |
| SOP 收编 | docs/standards/nmem-memory-sop.md（含「八、本仓库修正」） |
| 蒸馏脚本 | tools/dev/distill_memories_to_nmem.py（45 条，幂等 upsert） |
| seed 脚本 | tools/dev/seed_kg_entities.py（18 关系链，幂等） |
| 本体 patch | artifacts/source_ontology_patch.json（26+27，space scope 已应用） |
| recall 插件 | apps/api/src/data_intelligence_hub/nmem_recall.py + tests/unit/test_nmem_recall.py |
| 冒烟报告 | tmp/nmem-plan/smoke-report.md（14 项 + 2 追记） |
| 环境固化 | .claude/settings.local.json env：NMEM_SPACE=source-agent、NMEM_AGENT_ID=source（本机生效，不入库） |

nmem 空间终态：source-agent 记忆 116 条 active（45 ds-* + 69 迁入存量 + 2 过程记录）、Rules 3、Library 11、本体 26+27、图节点 11、显式链 18。

## 六、遗留事项（移交）

1. **extraction 开启后**：跑 `ontology retype` 把 CONCEPT/TOOL 等默认类型折叠进 26 声明类型；重跑实体抽取补齐 4 条 Reddit VOC 旧实体的 type=None。
2. **settings.local.json 不入库不同步**：其他机器使用需手动加 env 两个键。
3. **B 空间（dddd.top）未做**：本批次只覆盖 A 侧工作区记忆；生产 B 的运维记忆仍走 default/存量。
4. **WM 需要维护**：Working Memory 是快照非自动更新，建议随批次收尾时同步（本次已更新至 KG-09 完成）。
