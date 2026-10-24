---
name: agent-access-governance-design
description: Exa 对齐后的下一批设计：36 个 MCP 工具统一授权、通用异步采集与实时能力真值。定位为 C1/C3/C4/C5/C6/C13 的跨切片设计补充。
---

# Agent 接入正确性设计（N1/N2/N3）

## 1. 定位与范围

本 spec 是 C1/C3/C4/C5/C6/C13 已冻结计划的**跨切片设计补充**。它不建立第二套授权、幂等、账本或执行事实源。

- 表结构、迁移号与文件归属以 `docs/superpowers/plans/2026-10-22-governed-task-platform-master-plan.md`（C0–C14）为准。
- `project_api_keys` 的列扩展归 C3（迁移 059）。
- 预算、额度账户、`tool_prices`、`tool_calls` 归 C5（迁移 061）。
- run 执行收敛归 C6（迁移 062）。
- 客户 MCP 八工具归 C13。
- 本 spec 约束的是**内部 MCP `server.py` 的接线方式**、Console 密钥页的交互，以及 C13 落地时必须采用的默认授权语义。

本批只做以下三件：

1. N1：36 个内部 MCP 工具统一授权、项目绑定与额度。
2. N2：通用异步采集 `start_collect`，并让同步 `collect` 统一产生可查询 run。
3. N3：MCP 发现接口改用实时能力真值，附 14 天 TTL 与开发者契约生成。

## 2. 已确认的产品口径

1. 全部 36 个 MCP 工具显式进入项目密钥白名单；未登记的新工具默认拒绝。
2. 发现与只读合同工具可入白名单但不扣额度；执行工具扣额度。
3. 全局 token 保留运维超级权限，审计标记 `global_operator`；不纳入白名单与日额度。
4. 同步 `collect` 保留，并新增 `start_collect` 异步入口；长任务默认推荐异步。
5. `start_collect` 项目密钥必填幂等键；长度沿用冻结合同 12–200 字符；重放窗口 7 天。
6. 同步 `collect` 也创建 `runs` 行并走 RunExecutor，返回新增 `run_id`。
7. MCP `list_capabilities` 默认只返回「新鲜且当前可执行」的能力；`include_unverified=true` 返回全部与原因。
8. 证据 TTL 14 天；到期只标 stale，不自动复测。
9. Console 密钥页提供五个授权预设加自定义；预设只在客户端展开，不落库。
10. 已有密钥 allowlist 原样保留；不自动扩权。
11. 签发后允许 PATCH 原地更新 allowlist 与日额度，不强制轮换密钥。
12. 监控后续定时运行消耗创建密钥的日额度。
13. A/B 的实时证据独立维护；静态目录 digest 必须一致。
14. 「默认只显示新鲜可执行能力」使用部署级环境开关 `MCP_LIVE_EVIDENCE_FILTER_ENABLED`，A/B 独立控制。
15. 成功指标：零跨项目访问、零白名单绕过、额度重启不丢、幂等并发不重复、异步长任务恢复成功、默认可见工具真实可执行率不低于 95%。

## 3. N1 统一授权

### 3.1 集中式工具策略注册表

新增 `mcp_runtime/tool_registry.py`。每个内部 MCP 工具登记：

```text
tool_name
access_mode        = read | execute | control
requires_project   = true | false
project_scope      = bound_project | workspace | operator
consumes_quota     = none | per_call | per_row_worker | per_scheduled_run
run_mode           = sync | async | both | read_only
cancellable        = true | false
preset_groups      = [...]
```

启动测试必须断言：

1. `mcp_server.list_tools()` 的工具集合与注册表完全相等。
2. `access_mode != read` 的工具必须 `requires_project=true` 且 `consumes_quota != none`（`stop` 除外，`access_mode=control`）。
3. 未登记工具使测试失败。

该注册表同时供给：

- 运行时鉴权。
- `GET /api/settings/mcp-tool-policies`（新增，只读）。
- Console 密钥页复选框与预设。
- 开发者契约生成。

### 3.2 统一执行入口

新增 `governed_mcp_tool(context, tool_name, *, project_id=None, object_ref=None)` 异步上下文管理器，替代各工具手工拼接 `governed_tool` + `enforce_tool_policy` + `enforce_quota` + `_bound_project_id`：

1. 解析身份：`global_operator` 或 `project_key`。
2. 读策略：白名单、项目绑定、额度模式。
3. 校验对象归属：`project_id`、`run_id`、`monitor_id`、`job_id`、`raw_record_id` 追溯到密钥绑定项目。
4. 扣额度（执行型且非重放）。
5. 记录审计元数据：`identity_type`、`key_id`、`workspace_id`、`project_id`、`tool_name`、`quota_consumed`、`outcome`、`duration_ms`。

对象归属失败统一返回稳定的 `*_not_found`，不区分「不存在」与「不属于你」。

### 3.3 全量接线

以下工具全部改走统一入口：

- `collect` 与 16 个 `tiktok_*`：当前未接白名单、额度与 workspace 绑定，必须补齐。
- Exa Pack：`web_search`、`web_fetch`、`answer`、`deep_research`、`deep_research_start/check`、`workspace_answer`。
- Monitor：`create_monitor`、`list_monitors`（list 按 project_scope 过滤）。
- Enrichment：`enrich_list`、`enrichment_check`。
- Run：`get_run`、`list_records`、`stop`。
- Discovery：`list_platforms`、`list_capabilities`、`describe_capability`、`get_playbook`、`balance`。

`collect_capability` 调用必须传 `workspace_id`（项目密钥传 `identity.workspace_id`），禁止回退 demo workspace。

### 3.4 额度模式

| 模式 | 工具 | 计数 |
|---|---|---|
| `per_call` | `collect`、`start_collect`、`web_search`、`web_fetch`、`answer`、`deep_research`、`deep_research_start`、16 个 `tiktok_*` | 每次调用扣 1；幂等重放扣 0 |
| `per_row_worker` | `enrich_list` | 提交扣 0；worker 每行真实外部调用扣 1；`quota_exceeded` 行记失败 |
| `per_scheduled_run` | `create_monitor` | 创建扣 1；每次定时执行前扣 1，不足时不调 provider，run 记 `config_gated` + `quota_exceeded`，并通知所有者 |
| `none` | 发现、合同、playbook、`get_run`、`list_records`、`deep_research_check`、`enrichment_check`、`list_monitors`、`stop`、`balance` | 扣 0 |

`monitors.project_key_id` 记录创建密钥，供定时运行扣额度。列加入 C3 迁移 059 的 scope，不新增第二迁移。

项目密钥的日额度以数据库 `daily_collect_quota` / `quota_used` / `quota_date` 为准；进程内存的 `mcp_daily_collects` 只继续治理全局 token，不作为项目密钥边界。

### 3.5 白名单语义修订

- 空 `tool_allowlist` 表示拒绝全部工具（与模型注释一致；A/B 当前活跃密钥为 0，无兼容负担）。
- 未登记的新工具名默认拒绝。
- Console `MCP_TOOL_OPTIONS` 删除硬编码，改从 `GET /api/settings/mcp-tool-policies` 渲染。
- 五个预设（只读发现、搜索研究、TikTok、运维查询、全部工具）由 Console 端展开为最终工具名数组；后端只存最终数组。
- 已有密钥原样保留；Console 标记「缺少常用依赖工具」。
- 新增 `PATCH /api/projects/{project_id}/api-keys/{key_id}`：仅所有者可更新 `tool_allowlist` 与 `daily_collect_quota`；写结构化审计；不轮换明文密钥。

### 3.6 与 C3/C13 的分工

- C3 拥有 `project_api_keys` 表扩展（迁移 059：`status`、轮换列、`capability_allowlist`、复合外键）与管理路由。
- 本设计拥有 `mcp_runtime` 内部的 enforcement 接线与 `tool_registry.py`。
- C13 客户 MCP 的 capability enforcement 由 C13 按 C1 合同实现，消费 C3 暴露的 `capability_allowlist`；本设计的 `tool_allowlist` 只治理内部 MCP。
- C3 明确「不修改 `mcp_runtime` 白名单实现」；因此本 spec 的 N1 改动登记为 `mcp_runtime` 侧的独立工作包，不并入 C3 计划文件。

## 4. N2 通用异步采集

### 4.1 `start_collect`

入参：`endpoint_type`、`project_id`、`params`、`idempotency_key`（项目密钥必填，12–200 字符，沿用冻结合同）。

行为：

1. 校验 capability 可执行（N3 投影）。
2. 统一授权入口：白名单、项目绑定、`per_call` 扣额度。
3. 幂等摘要：`sha256("mcp.v1:" + tool_name + ":" + project_id + ":" + key_id + ":" + idempotency_key)`；全局 token 用 `global` 替代 `key_id`。
4. 复用 `uq_runs_workspace_idempotency` 部分唯一索引；不建新表、不新增迁移。
5. 命中同摘要返回原 run（`idempotent_replay=true`，不扣额度）。
6. 同键不同摘要返回 `idempotency_conflict`。
7. 入队后立即返回。

响应（最小稳定合同）：

```json
{
  "run_id": "...",
  "task_id": "...",
  "source_id": "...",
  "status": "queued",
  "idempotent_replay": false,
  "check_tool": "get_run"
}
```

### 4.2 同步 collect 统一 run 身份

同步 `collect` 改为在同一线程内走 RunExecutor：

- 创建 `runs` 行（`status=queued` → `running` → 终态）。
- 复用 `run_steps`、`run_ledger_entries` 与 evidence grade。
- 响应保留现有全部字段，新增 `run_id` 与 `idempotent_replay`（全局 token 可选幂等键；未传时为 `false`）。
- `get_run`、`list_records`、`stop` 从此对同步与异步 run 一致可用。

执行行为、超时与状态语义不变；只统一「运行身份」与成本/账本落点。

### 4.3 幂等语义

- 重放窗口 7 天：超龄返回 `idempotency_key_expired`，调用方换 key。
- 同键同摘要返回原 run；同键不同摘要返回 `idempotency_conflict`。
- 摘要从持久化 run 的 task config 重建，不新增第二个摘要列。
- 并发提交依赖部分唯一索引；冲突后重查返回既有 run。
- 已失败/已取消的 run 仍按重放返回原 run；重跑必须换新 key。

### 4.4 run_mode 投影

ToolContract v1 新增向后兼容字段：

```text
run_mode        = sync | async | both | read_only
cancellable     = true | false
recommended_tool = collect | start_collect
```

- `contract_version` 不变；旧客户端忽略未知字段。
- 默认 `both`；已知长任务（Exa Agent、OSINT 长扫描、爬虫类）默认推荐 `start_collect`。
- 例外用显式表维护，不按名称猜测。
- `idempotency_key` 参数进入 `exa_agent` 等执行工具的参数合同。

### 4.5 与 C4/C6 的接缝

- C4 的 `create_run_with_audit` 接缝落地后，`start_collect` 与同步 `collect` 改调该接缝创建 run（获得 `run.created` 审计）；C4 合并前维持现有 `repositories.runs.create_run` 路径。
- C6 的执行收敛开关（`RUN_EXECUTION_CONVERGENCE_ENABLED`）打开后，MCP 不改变行为；C6 Task 10 明确「收敛开关不得改变 MCP 行为」。
- 幂等哈希前缀 `mcp.v1` 与 C4 的 `workbench-submit.v1`、`workbench-task-create.v1` 互不冲突（不同前缀、不同作用域）。

## 5. N3 实时能力真值

### 5.1 真值合成

新增 `services/capability_availability.py`，只读组合：

```text
静态工具目录
+ provider status（最近真实运行）
+ 当前 provider 配置
+ 外访策略阻断
+ ToolContract
→ 单一能力视图
```

REST `/api/platform-packages`、`/api/tools`、MCP 发现工具与 Console 共用该视图。

### 5.2 可见性判定

默认进入列表需全部满足：

```text
availability == verified
executable_now == true
last_test_at 非空且 age <= 14 天
status != disabled
```

### 5.3 证据信任来源

当前证据从 `CollectionTask.name` 的 `[quick] [test] <label>` 前缀派生 endpoint，且 label 由调用方提供，可被普通用户伪造。修复：

1. endpoint_type 从 `task.config.endpoint_type` 读取，不再解析名称。
2. 验证任务带服务端拥有的 `config["verification_source"]="operator"`。
3. 只有全局运维 token 或验证脚本专用入口可写该标记；普通 quick-collect 永不改变全局 verified 状态。
4. 证据记录带 `trust` 字段；N3 默认列表只接受 `trust=operator`。
5. 负向测试：label 指向端点 A、config 实为端点 B 的成功运行，不得把 A 标为 verified。

### 5.4 TTL 与 stale

- TTL 固定 14 天：`age <= 14d` 有效，`age > 14d` stale。
- 不新增 availability 枚举值；stale 用正交字段表达：

```json
{
  "availability": "verified",
  "stale": true,
  "executable_now": false,
  "block_reason": "evidence_stale",
  "evidence_age_hours": 337,
  "evidence_expires_at": "..."
}
```

- 不自动复测。运维用现有 `verify_platform_live.py --only ...` 刷新。
- 每日只读巡检统计「7 天内将过期」与「已 stale」数量；超阈值发飞书告警。
- N3 发布门禁：默认可见工具真实可执行率 ≥ 95%，或附已批准例外清单；不满足时不得打开 `MCP_LIVE_EVIDENCE_FILTER_ENABLED`。

### 5.5 开关与 A/B 差异

- `MCP_LIVE_EVIDENCE_FILTER_ENABLED`：部署级环境开关，A/B 独立控制；关闭时 MCP 行为与现状一致。
- 静态目录 digest A/B 必须一致；实时 `verified_count`、`executable_count_live`、`stale_count`、`blocked_count` 允许不同并明示。
- B 证据未回填前：先部署代码、保持开关关闭；operator 复测达标后打开，无需重建镜像。
- 项目密钥调用方不泄露内部批准域名、密钥名与策略原文；全局 token 可见完整运维诊断。

### 5.6 开发者契约

生成以下材料，不手写计数（CI 检查漂移，沿用 SP-42 思路）：

- MCP 工具列表与 JSON Schema（从注册表生成）。
- Tool Catalog 摘要。
- 授权预设说明。
- 同步/异步调用示例与幂等语义。
- 稳定错误码表。
- A/B 生产版本与 digest。

## 6. 稳定错误码

| 场景 | 错误码 |
|---|---|
| 工具未授权 | `tool_not_allowed` |
| 项目不匹配/对象不属于项目 | 对应稳定 `*_not_found` |
| 日额度用尽 | `quota_exceeded` |
| 能力不可执行 | `capability_not_available` |
| 能力证据过期 | `capability_stale` |
| 项目密钥未传幂等键 | `idempotency_key_required` |
| 幂等键长度错误 | `idempotency_key_invalid` |
| 同键不同请求 | `idempotency_conflict` |
| 幂等键超窗 | `idempotency_key_expired` |
| run 不属于当前项目 | `run_not_found` |

与 C1 registry 的关系：`tool_not_allowed`、`quota_exceeded`、`idempotency_conflict` 已登记；`idempotency_key_required` 已由 C1 登记。`idempotency_key_invalid`、`idempotency_key_expired`、`capability_not_available`、`capability_stale` 需在实施前向 C1 提交登记变更请求；未登记前不得上线返回。

## 7. 测试矩阵

### N1

身份 × 工具组矩阵：全局 token、正确项目密钥、错误项目密钥、白名单缺失、额度充足、额度耗尽、已撤销密钥，覆盖 Discovery、`collect`、Exa Pack、16 个 TikTok、Monitor、Enrichment、Run 查询与 `stop`。

注册表完整性：MCP 注册集合 == 策略集合；执行工具必有项目绑定与额度规则。

隔离负例：跨项目 run/records/monitor/enrichment/answer 全部稳定 not-found；不写任何记录。

额度持久性：API 重启后 `quota_used` 不丢；`per_row_worker` 逐行扣减；`per_scheduled_run` 不足时 run 记 `config_gated` 并通知。

### N2

并发 20 次同键仅 1 run 1 次 provider 调用；同键同 payload replay；同键不同 payload conflict；超窗 expired；worker 重启后 run 恢复；queued/running 的 stop；同步 `collect` 回归不变；长任务（>60 秒）真实端点完成并返回记录与成本。

### N3

固定时钟：14 天整有效、超 1 秒 stale；verified 但缺配置不可执行；config-gated/degraded/empty/untested 默认隐藏；`include_unverified=true` 返回 284 项与原因码；证据伪造负例（label A / config B）；项目密钥与全局 token 诊断字段差异；MCP/REST/Console 聚合一致；A/B digest 一致。

## 8. 发布

三批独立发布，每批：全量测试 → A 备份发布 → 真实验收 → B 备份发布 → 双机对账。

| 批 | 内容 | 迁移 | 回滚 |
|---|---|---|---|
| N1 | 统一授权 + 隔离 + PATCH + 监控 key_id（并入 C3 迁移 059 scope） | 随 C3 059 | 代码回滚；密钥数据不变 |
| N2 | `start_collect` + 同步 run 统一 + ToolContract 扩展 | 无 | 代码回滚；已入队 runs 仍可被旧 worker 消费 |
| N3 | 实时真值投影 + TTL + 契约生成 + 开关 | 无 | 关开关即回旧行为 |

发布门禁：

- N1：隔离矩阵零失败；注册表完整性通过。
- N2：幂等并发零重复；长任务恢复成功。
- N3：默认可见工具真实可执行率 ≥ 95% 或附已批准例外；MCP/REST/Console 真值零漂移。

## 9. 明确不做

- 飞书机器人身份与租户映射（另立批次）。
- Saved Collection、全文/实体搜索、数据集血缘。
- B4 claims/report contract（等 B4 分支消除迁移号冲突后另批）。
- OAuth / keyless MCP、provider 自动降级。
- Typed Contract v2 全量迁移。
- 计费充值与发票。
- 新采集器或扩大端点目录。
- 修改 C3/C5/C6/C13 已冻结的表结构、迁移号与文件所有权。

## 10. 成功指标

1. 跨项目访问：0。
2. 白名单绕过：0。
3. 额度重启丢失：0。
4. 幂等并发重复执行：0。
5. 异步长任务（含 worker 重启）恢复成功率：100%。
6. MCP 默认可见工具真实可执行率 ≥ 95%。
7. MCP / REST / Console 工具真值漂移：0。
