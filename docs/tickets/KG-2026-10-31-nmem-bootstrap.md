---
name: KG-2026-10-31-nmem-bootstrap
description: Source 项目 Nowledge Mem 记忆系统与知识图谱落地台账：10 张 ticket，三阶段（裁决准备/冒烟定稿/建库验收），依赖方案 docs/plans/nmem-memory-knowledge-graph.md
doc_type: ticket
module: M00-治理
topic: nmem 记忆系统与知识图谱
status: 已完成
created: 2026-10-31
updated: 2026-10-31
owner: Pray
source: docs/plans/nmem-memory-knowledge-graph.md
---

# KG-2026-10-31 · Nowledge Mem 引导批次台账

## 决策依据

- 执行方案：`docs/plans/nmem-memory-knowledge-graph.md`（六项 blocker 裁决 §3、四层记忆定稿 §4、本体定稿 §5、风险 §7、验收 §8）
- SOP：待 KG-00 收编为 `docs/standards/nmem-memory-sop.md`（原始附件在 `.lody/attachments/`，不可复现）
- 证据底稿：`tmp/nmem-plan/recon_full.json`（7 读者侦察 + 批评者 18 组去重裁决）

## 总览

| 编号 | 标题 | 优先级 | 状态 | 依赖 |
| --- | --- | --- | --- | --- |
| KG-00 | SOP 收编为仓库标准文档 | P0 | 已完成 | 无 |
| KG-01 | default 空间存量记忆去重与迁移 | P0 | 已完成 | 方案批准 |
| KG-02 | nmem 写路径冒烟（scratch space） | P0 | 已完成 | KG-00 |
| KG-03 | 创建 source-agent 空间/身份/规则/WM | P0 | 已完成 | KG-01、KG-02 |
| KG-04 | 蒸馏脚本 + 45 条四层记忆入库 | P1 | 已完成 | KG-03 |
| KG-05 | Library 真源白名单归档 | P1 | 未开始 | KG-03 |
| KG-06 | 本体 patch 定稿 + space scope 应用 | P1 | 已完成 | KG-02、KG-03 |
| KG-07 | 知识图谱实体 seed（P2 期） | P2 | 已完成（一期：关系链；实体抽取待 extraction 开启） | KG-04、KG-06 |
| KG-08 | 环境固化 + recall 插件 + 单测 | P1 | 已完成 | KG-04 |
| KG-09 | 全流程验收报告 | P1 | 已完成 | KG-04~KG-08 |

## 执行顺序理由

1. KG-00 先行：SOP 附件不可复现，收编后所有 ticket 才有稳定引用。
2. KG-01 与 KG-02 并行：存量裁决决定单一真源边界；冒烟验证 patch schema 与写路径，两者互不依赖但都阻塞 KG-03。
3. KG-03 是所有写入的闸门：空间未建、规则未注入前，禁止任何 memories/library/ontology 写入。
4. KG-04/05/06 并行：互不写同一对象面（memories / library / ontology）。
5. KG-07 依赖 KG-06 的本体词汇表与 KG-04 的记忆内容；P2 期可延后。
6. KG-08 依赖 KG-04（有记忆可检索才能测 recall）；KG-09 收口。

## 逐张验收标准

### KG-00 SOP 收编
- 附件全文复制为 `docs/standards/nmem-memory-sop.md`，保留原文，顶部加「本仓库收编版（源：Lody 附件 2026-10-26 v2.0）」与 Frontmatter（name、description）。
- 文末追加「本仓库修正」一节，逐条写入方案 §3 的六项裁决（特别是 ontology 必须 `--scope space`）。
- 验收：`python3 scripts/check_file_integrity.py docs/standards/nmem-memory-sop.md` 退出码 0。

### KG-01 存量去重
- 按 B2 裁决执行：`memories move` 迁 fc8f5b4a、cf515aec 到新空间（move 前先在 KG-03 建好空间则顺延到 KG-03 后、KG-04 前）；2047b5da 等 5 条 merge 进 ds-l4-09 后归档。
- 验收：`nmem --json memories search "data_scrapy Source DIH" --space default -n 10` 中本项目口径记忆为 0 条或全部指向新空间；记录操作前后 ID 清单。

### KG-02 写路径冒烟
- 建 scratch space（`--id tmp-smoke`），依次实跑：spaces create、agents enroll、rules upsert（--scope space）、working-memory edit、memories add --id、library add（单文件预检 MIME）、ontology apply（--scope space --space-id）、memories search、context read、ontology show --space-id。
- 每个 verb 记录：实际命令、退出码、返回 JSON 形状、与 --help 的差异。
- 验收：冒烟报告 `tmp/nmem-plan/smoke-report.md` 覆盖上述 10 项且无未解释的失败；scratch space 归档或删除。

### KG-03 空间与身份
- `nmem spaces create "Source Agent Space" --id source-agent --description "Source（Data Intelligence Hub）专属记忆空间" --retrieval-mode strict`。
- `nmem agents enroll source --name "Source Agent" --role data_platform_steward --default-space source-agent ...`。
- 3 条 Space Rules（P100 人设红线 / P90 边界与数据纪律 / P80 口径纪律）按方案 §4 R1-R3，正文用 --body-file。
- WM 注入 Focus Areas + Briefing（含本批次 10 ticket 进展）。
- 验收：`nmem --json context --space source-agent` 的 rule_stack.space 含 3 条、working_memory 含两大段落；`spaces list` 显示 strict。

### KG-04 蒸馏脚本与记忆入库
- 新建 `tools/dev/distill_memories_to_nmem.py`：内容表来自方案 §4（45 条，全部 `--id ds-lX-NN` 确定性 ID、`memories add --id` upsert）；长正文用 --stdin；脚本声明 `DRY_RUN` 开关。
- 首跑 DRY_RUN 输出待写清单 → 人工核对 → 实跑。
- 验收：实跑两遍，`memories list --space source-agent` 第二遍总数与第一遍相同（幂等）；45 条 unit_type/importance/when 与方案表一致。

### KG-05 Library 归档
- 白名单（禁 glob）：契约冻结 v1.1、writing-standard-ste、collection-outbound-safety、能力总账、能力图谱、模块设计、运维手册生产基线、DIH整站能力整合方案、nmem-memory-sop、ADR-006/ADR-007，共 11 份。
- 每份先 `nmem library add` 单文件预检 mime_type/lifecycle_state；.md 如报 MIME 错误则复制为 .markdown 重试（沿用 pr-agent 空间成功样本做法）。
- 验收：`nmem --json library list --space source-agent` 11 份全 indexed、error 0；无白名单外文件。

### KG-06 本体应用
- 按 §5 定稿写 `artifacts/source_ontology_patch.json`（26 objectTypes + 27 linkTypes，UPPER_SNAKE）。
- 先在 scratch space 应用并 `ontology show --space-id tmp-smoke` 逐条比对（R4：本体无 delete，错了只能换 space 重来）。
- 正式应用：`nmem ontology apply --file artifacts/source_ontology_patch.json --scope space --space-id source-agent`。
- 验收：`nmem --json ontology show --space-id source-agent` 与 §5 逐条一致；`nmem --json ontology show`（global）revision 仍为 7。

### KG-07 实体 seed（P2）
- 先探针 `nmem entities --help` 确认 seed 语法，再写 `tools/dev/seed_kg_entities.py`。
- 首批 seed 核心链路：70 平台包、15 Provider、12 DIH 模块、3 部署环境、2 产品 Agent、核心端点映射（平台包→能力→端点→采集器→Provider）与任务→运行→记录→数据集链。
- 显式关系遵循 R10：允许 per-memory 422 已知失败，记录重放条件。
- 验收：`nmem --json entities`（或探针确认的等价命令）可见上述节点；桌面端 ⌘5 切到 source-agent 空间可见链路（截图存 tmp/nmem-plan/）。

### KG-08 环境固化与 recall
- `.claude/settings.local.json` 新增 `"env": {"NMEM_SPACE": "source-agent", "NMEM_AGENT_ID": "source"}`，保留原 permissions（R7）。
- recall 插件放 `apps/api/src/data_intelligence_hub/nmem_recall.py`（独立新增，3 秒超时、全捕获降级、默认关闭 `NMEM_RECALL=1` 门控），不改任何现有模块。
- 单测 `apps/api/tests/unit/test_nmem_recall.py`：真实检索（skipif nmem 不可用）+ 超时降级 + 空查询三用例。
- 验收：`.venv/bin/python -m pytest apps/api/tests/unit/test_nmem_recall.py -q` 全绿；`.venv/bin/ruff check apps/api/src/data_intelligence_hub/nmem_recall.py` 0 error。

### KG-09 验收报告
- 按方案 §8 十条逐一核验，产出 `reports/kg-acceptance-20261101/Source-nmem验收报告-20261101.md`（+html 可选），检索分数逐条列表。
- 发现的文档漂移（README MCP 25、schema 四版本等）只记录进报告 §漂移清单，不改文档。
- 验收：报告存在且十条基线逐条有结论（通过/未通过+原因）；`git add -f` 报告与台账后提交。

## 不做什么

- 不改 pr-agent / si-agent / kb-consultant-agent 三个空间与全局本体。
- 不把 raw/secret（.pem/.key/.env/日志/原始 JSON）、generated/、ref/、tmp/ 送入 Library 或记忆。
- 不用 `mcp__memory__` 写任何本项目数据。
- 本期不接 DuckDB、不改产品主链路、不更新 README/AGENTS.md 的过期数字。

## 变更记录

- 2026-10-31：建立台账，10 张 ticket，状态全部未开始。
- 2026-10-31：KG-00、KG-02 完成。冒烟推翻 2 项认知（ontology patch 无 from/to、MIME 陷阱已消失）、新增 2 坑（hook 蒸馏跟随 active space、空间删除需清 WM 文件），详见 tmp/nmem-plan/smoke-report.md；KG-06 patch 需按新 schema 重写。
- 2026-10-31：KG-03 完成（source-agent strict + 身份 source + 3 Rules + WM）。KG-01 完成：move 69 条、archive 7 条（6 条产品方向同源合并为 ds-l4-09），default 剩余 63 条为兄弟项目历史不动；教训 move 只认完整 UUID。
- 2026-10-31：KG-04 完成（45/45 四层记忆，幂等）；KG-05 完成（Library 11/11 indexed；MIME 陷阱为概率性，.markdown 转传是可靠通道）；KG-06 完成（本体 26+27 space scope 应用，global 无污染）；KG-08 完成（recall 插件 5 测试全绿，env 固化；Write/Edit 写中文 py 后 ruff 必报 E902，重写 inode 修复）；KG-07 完成（一期 18 关系链入图；实体抽取待 extraction 开启）；KG-09 完成（验收报告全 PASS，avg 0.976）。批次 10/10 收口。
