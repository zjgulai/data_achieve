---
name: adr-007-baseline-auth-and-transaction
description: 下一批基线的架构决策记录。固定迁移 045 的去留、读写接口的鉴权分工、demo_mode 推导、事务提交权、quick_collect 服务化、executable 判定与回归守卫基线。当修改鉴权、事务边界、目录执行判定或发布基线时使用。
---

# ADR-007：下一批基线（鉴权、事务与目录执行边界）

> 状态：已采纳
> 日期：2026-10-20
> 决策者：lute
> 相关文档：[下一批迭代计划](../../product/【计划】下一批迭代.md) · [架构设计](../../design/【架构设计】DIH洞察工作台.md)

## 背景

B1 批次修地基。目标有三项：写路径 fail-closed、事务边界回到 service、目录计数可对账。
以下 D1-D7 是本批的固定结论。
后续批次必须按这些结论实施，不得静默偏离。

## D1 迁移 045 保留在主分支

### 背景

`202610190045_tiktok_r1_canonical_tables.py` 已在 `origin/main` 第一父链。
2026-10-20 只读探测 `/api/health`：A `scrapy.luteos.com` 的 `schema_revision` 为 `202610190045`（已应用）；B `scrapy.lute-tlz-dddd.top` 为 `202607280044`（未应用）。
把 045 移到独立分支需要改写 public main 历史。

### 决定

045 保留在 main。
不得改写 main。
不得对 A 执行 downgrade 或 stamp。
B 单列为待升级环境，按独立发布流程处理。
046 的 `down_revision` 必须是 `202610190045`。
`alembic heads` 必须只有一行。

### 后果

A 与 B 的 schema 不同步。
发布检查必须逐主机读取 `/api/health` 的 `schema_revision`。
不得用单一基线覆盖两套生产。
B 在应用 045 前必须完成备份并取得明确授权。
045 文件头的 source-only 说明必须保留。

## D2 写接口用 get_authenticated_context，读接口暂用 get_auth_context

### 背景

`get_auth_context` 在无 token 时回退 demo workspace。
149 个端点使用它。
读接口在本地与测试环境依赖该回退。
一次全部替换会让读接口返回 401。

### 决定

新增 `get_authenticated_context`。
它无有效 token 一律返回 401，从不回退 demo workspace。
写接口必须改用 `get_authenticated_context`。
读接口暂留 `get_auth_context`。
B1-08 已迁移 quick-collect、reports、automation、platform_credentials、workflow_plans、projects 等写路径。
跨 workspace 访问必须返回 403。

### 后果

无 token 写调用不再以 demo owner 身份执行。
读接口仍有 demo 回退，这是已知剩余风险。
迁移必须按路由分批。
后续批次必须继续收敛读接口。

## D3 demo_mode 推导：显式优先，未设置时生产关、开发开

### 背景

本地开发和测试需要 demo workspace 回退。
生产必须 fail-closed。
固定的布尔默认值无法同时满足两者。

### 决定

`demo_mode` 的类型为 `bool | None`，默认 `None`。
显式 `DEMO_MODE=true` 或 `DEMO_MODE=false` 优先。
未设置时由 `effective_demo_mode` 按 `app_env` 推导：`production` 关闭，其他环境开启。

### 后果

生产默认拒绝无 token 请求。
开发环境无需额外配置。
部署必须确认 `APP_ENV=production`。
环境名拼错会打开 demo 回退。
`get_authenticated_context` 不受 `DEMO_MODE` 影响。

## D4 事务提交权在 service，repository 只 flush

### 背景

repository 内直接 `session.commit()` 使事务边界散落。
service 无法组合多个写操作，也无法统一回滚。

### 决定

repository 只执行 `add`、`flush` 和 `refresh`。
repository 不得 `commit`。
service 在业务步骤边界提交。
scheduler 的 tick 记录由 scheduler service 提交。
B1-10 将 9 处 `commit` 改为 `flush`，并在对应调用点补 `commit`。

### 后果

`repositories` 目录中 `session.commit` 必须为 0。
新增 repository 必须遵守同一规则。
service 漏写 `commit` 会让数据在 `session.close()` 时回滚。
每个 repository 调用点必须确认提交归属。
测试必须包含读回断言。

## D5 quick_collect 抽出为服务，MCP 与 agent 走进程内调用

### 背景

quick-collect 执行逻辑原在 `api/routes/quick_collect.py`。
MCP runtime 需要导入 HTTP 路由模块。
服务层依赖 HTTP 会形成反向依赖，也会迫使进程内调用回环 HTTP。

### 决定

抽出 `services/quick_collect_service.py`。
服务不依赖 FastAPI。
服务抛领域异常，由路由映射为 HTTP 状态码。
REST、MCP 与 agent 走同一服务。
MCP 与 agent 使用进程内调用。
`mcp_runtime` 不得再导入 `api.routes.quick_collect`。
workspace 由调用方传入：HTTP 传已鉴权的 `AuthContext.workspace`（fail-closed）；MCP 与 agent 未传时回退 demo workspace。

### 后果

REST 与 MCP 共用一条执行路径。
路由只做鉴权、参数映射与异常转换。
MCP 的 demo 回退仍是既有行为。
后续身份收紧必须覆盖该路径。
新增调用方必须传 workspace，不得复制服务实现。

## D6 executable 排除 unsupported 分类，不看运行时 allowed_now

### 背景

旧 `executable` 只检查 `availability`。
它把 257/258 条标为可执行。
实际有 64 条端点行属于 `unsupported` 策略，无法执行。
`allowed_now` 是运行时状态。
开发环境默认 `offline`，此时 `allowed_now` 恒为假。
用 `allowed_now` 判定目录属性会把全部端点标成不可执行。

### 决定

`executable` 必须同时满足两个条件：`availability` 不是 `disabled` 或 `config-gated`；策略分类不是 `unsupported`。
策略判定必须按 `collector_type` 进行。
不得按 `endpoint_type` 判定。
判定不得读取 `allowed_now`。

### 后果

目录如实反映永久不可执行的端点。
`executable_count` 随策略分类变化。
当前环境可否执行由调用时的策略拒绝回答。
目录不回答该问题。

## D7 回归守卫基线为空集

### 背景

旧回归基线包含 137 条失败。
允许清单会掩盖新增回归。
两套测试应以 0 failed 为唯一通过条件。

### 决定

新建 `scripts/check_pytest_baseline.py`。
基线为空集。
任何 `FAILED` 或 `ERROR` 行必须使脚本退出 1。
pytest 没有汇总行也必须退出 1。
CI 的 Pytest 步骤必须调用该脚本。
旧 `reports/live-sweep/baseline-pytest-failures.txt` 归档，不再作为比对依据。

### 后果

任何失败都必须修复。
不得用基线豁免失败。
CI 失败时必须打印失败清单。
归档文件不得恢复为允许清单。

## 未决事项

- B 应用 045 的时间与备份方案待定。
- 读接口迁移到 `get_authenticated_context` 的分批顺序待定。
- MCP 与 agent 的 demo 回退收紧方案待定。
- 046 迁移落地前，`alembic heads` 必须保持一行。

## 相关证据

- 2026-10-20 `/api/health` 逐主机探测：A=`202610190045`，B=`202607280044`。
- `scripts/reconcile_catalog.py` 当前工作树输出：端点映射 290；生成物 286 视图 / 258 唯一端点 / 70 平台；策略四组 1+4+28+53。
- `apps/api/src/data_intelligence_hub/api/deps.py` 中 `get_authenticated_context` 与 `get_auth_context` 的实现。
- `apps/api/src/data_intelligence_hub/core/config.py` 中 `effective_demo_mode` 的推导。
- B1-10 验证记录：全量 2375 passed / 0 failed；`grep -rn "session.commit" apps/api/src/data_intelligence_hub/repositories` 返回 0。
