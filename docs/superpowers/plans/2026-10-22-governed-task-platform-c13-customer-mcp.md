# 客户 MCP（C13）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在契约路径 `/mcp/customer` 上提供恰好八个工具的客户 MCP server，使用项目密钥 Bearer 鉴权；全局运维 token 继续使用现有内部 `/mcp`。客户链具备统一授权管线、DB 速率并发、输出白名单和全量审计。`create_task` 必须幂等，并且通过 C4 的初始计划版本接缝产生一个 `collect` 可执行的已批准版本。

**Architecture:** 新建独立 `mcp_runtime/customer` 包，与内部 `mcp_runtime/server.py` 完全分离。`/mcp/customer` 直接挂载客户 ASGI app；现有内部 `/mcp` 原样保留，不建 audience router。客户 app 的 ASGI 外层负责 Bearer 鉴权与传输级授权（403/429），MCP server 内层只注册 C1 `customer_mcp.schema.json` 的八个工具，并对 `tools/list` fail-closed。八个工具通过 `CustomerPorts` 调用 C2/C3/C4/C5/C6/C7/C8/C9/C10 的公开服务；`create_task` 与 `collect` 都调用 C4 `create_initial_workflow_version_for_task`，不生成第二套计划事实。C13 不复制业务逻辑，不新增迁移，不执行生产写操作。

**Tech Stack:** Python 3.12、MCP Python SDK 2.3（`mcp>=2.0.0`）、FastAPI/Starlette、SQLAlchemy 2 async、SQLite（单测）与 PostgreSQL（生产）、pytest + anyio、httpx2（MCP Streamable HTTP 测试）。

## Global Constraints

- **隔离 worktree。** 执行分支是 `feat/gov-c13`，worktree 是 `/Users/lute/Project/data_scrapy-gov-c13`。起点分支与主计划 W11 一致：从 `feat/gov-c10` 创建；C13 与 C11 并行，不等待 C11，也不依赖 C12。主工作树 `/Users/lute/Project/data_scrapy` 只用于 Task 0 的 `git worktree add`、只读预检与复制本计划。Task 0 之后所有 Run/Commit 命令都在 worktree 执行。
- 契约优先级：`docs/design/【契约冻结】v1-表名-枚举-接口.md` > 已批准设计 `docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md` > 迁移与代码事实。冲突时以契约为准。
- C13 不修改 `apps/scraper-console/**` 或 `apps/web/**`；浏览器页面归 C14，C13 只提供交接单。
- 功能开关只有一个：`SCRAPY_MCP_CUSTOMER_ENABLED`，默认 `false`。关闭时 `/mcp/customer` 返回 404，内部 `/mcp` 不受影响。回滚点是关闭该开关并回退应用版本；C13 无迁移，不需要 downgrade。**C13 在任何环境都不翻转生产开关；PG0 发布批次负责翻转。** C13 只在共享 compose 的 `api.environment` 增加 `SCRAPY_MCP_CUSTOMER_ENABLED`（默认 `false`）、`SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE`（默认 `60`）与 `SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS`（默认 `4`）三个映射，并新增 compose 事实测试；C13 不写 `.env.production`、不设置生产值、不部署。
- 客户 MCP 路径固定为 C1 登记的 `/mcp/customer`（`mcp.customer.post` / `mcp.customer.get`，audience `customer_key`）。内部 `/mcp` 保持现有行为，只承载全局运维 token 和内部工具。不得新增第三个路径。
- 客户工具恰好八个，名称、输入 schema 和输出 schema 以 `configs/contracts/v1.1.0/customer_mcp.schema.json` 为准：`discover_capabilities`、`estimate_task`、`create_task`、`get_task`、`cancel_task`、`get_delivery_manifest`、`get_evidence`、`collect`。不得增删、改名或重排。
- 请求检查顺序固定，不得重排：Bearer 鉴权 → 密钥状态 → 工作区与项目绑定 → 工具白名单 → 能力白名单 → Cookie 隔离 → 日额度 → 速率与并发 → 预算 → 执行与审计。
- 错误码只用 C1 登记值：`authentication_required`、`project_key_invalid`、`project_key_revoked`、`tool_not_allowed`、`capability_not_allowed`、`cookie_not_accepted`、`quota_exceeded`、`rate_limited`、`approval_required`、`tool_not_executable`、`tool_not_priced`、`market_unsupported`、`task_not_found`、`manifest_not_found`、`claim_not_found`、`evidence_not_found`、`idempotency_conflict`、`state_conflict`、`package_type_invalid`、`comparison_markets_exceeded`、`acceptance_contact_not_member`、`budget_invalid`。白名单失败返回 403；日额度、速率或并发失败返回 429；预算不足返回 `approval_required` 并进入待批准状态。
- 客户请求不能携带 `workspace_id`、`project_id`、`provider`、`endpoint_type`、分页、重试、降级链、Cookie 或 Seller Center 登录态。工作区与项目只从项目密钥解析。`create_task` 的 `acceptance_contact_id` 只能是当前工作区 owner 或 admin；普通 member 返回 `acceptance_contact_not_member`，由 C4 校验，C13 不复制角色规则。
- `create_task` 必须把 `idempotency_key`、`package_type`、`primary_market`、`compare_markets`、`seed_products`、`target_price_band`、`budget`、`acceptance_contact_id` 映射到 C4：`idempotency_key` 传给 `create_workbench_task(..., idempotency_key=...)`；`compare_markets` 映射为 `comparison_markets`；`seed_products` 与 `target_price_band` 原样传递，不得静默丢弃；`budget` 展开为 `max_cost_usd/max_pages/max_records`。C4 负责持久化、幂等摘要、Quick 最多 1 个/Standard 最多 3 个对比市场、种子商品 3–10 项与价格带校验。C13 不复制市场档位或产品阈值，不写 `workbench_tasks` 或 `runs`。
- **模板能力白名单 fail-closed。** C8 的模板侧唯一能力白名单由模块函数 `template_capability_ids(template_id)` 读取；`TaskTemplate.capability_allowlist` 只是该函数背后的 dataclass 字段，C13 不直接依赖模板属性。`discover_capabilities` 只返回 `project_api_keys.capability_allowlist ∩ template_capability_ids(template_id)`；`collect` 的 `capability_id` 必须同时在密钥白名单与模板白名单内，否则返回 `capability_not_allowed`。模板白名单缺失、为空或 C8 未提供该函数时一律 fail-closed：`collect` 返回 `capability_not_allowed`，`discover_capabilities` 返回空清单。不得回退为“全部非 Cookie 工具”，不得用 `core_domains`、工具目录 `category` 或 provider 自行推导模板白名单。C8 尚未提供 `template_capability_ids(template_id)` 或其返回为空时，C13 记为 `BLOCKED: c8_template_capability_ids_missing`，由 C8 所有者补函数；C13 不自行新增函数、字段或契约对象。
- **取消幂等。** `cancel_task` 的 `idempotency_key` 与 `reason_code` 必须原样传给 C6 取消服务，不得 `del`、不得本地改写。同键同 `reason_code` 为幂等重放；同键不同 `reason_code`（或不同任务）返回 `idempotency_conflict`；并发同键只有一个执行者，其余重放或返回 `idempotency_conflict`，不得重复写取消副作用。任务或运行已进入终态且没有同键重放记录时返回 `state_conflict`。C6 取消服务是唯一写 `run.cancelled`、释放预算预留的地方；C13 不删除 step、attempt、`task_runs` 或账本，不直接循环 `cancel_run` 复制幂等语义。
- **证据可发布门禁。** `get_evidence` 只返回通过 C7 可发布门禁的 Claim：`review_status=approved`、`reviewed_content_version=content_version`，且该 Claim 的合同行通过 `validate_claim_bundle`。`draft`、`pending`、`rejected`、`stale` Claim 一律返回 `claim_not_found`，不返回草稿内容；证据缺字段、证据行不完整或证据等级不一致返回 `evidence_not_found`。C13 不自行判定 Claim 是否可发布，也不把 pending/stale 当作可读草稿返回。
- 客户链出现 `creator_cookie` 的次数必须为 0。内部 `collect(endpoint_type, project_id, params)` 与 `tiktok.creator_cookie` 工具保留，但只能留在内部 `/mcp` 和内部控制台，保留至少一个迁移周期。
- C3 只存储、展示、审计 `capability_allowlist`；C13 负责 enforcement。C13 不修改 C3 的存储与 API。
- C13 不新增 Alembic 迁移，也不新增表。只使用 C1 已登记的 `project_api_keys.capability_allowlist`、`project_api_keys.status`、`project_api_keys.expires_at`、`audit_events`、`tool_calls` 与 `/mcp/customer` 路径。`apps/api/alembic/versions/` 在本计划执行期间必须零改动。C1 registry 的 `mcp_customer_request_leases` 必须删除或标 `deferred`；C13 不实现租约表。C13 不设置租约过期开关；stale 判定使用 `rate_limit.STALE_AFTER_SECONDS` 内部常量（300 秒），不进入配置、`.env.example` 或产品阈值。
- 速率与并发计数必须落库，不能用进程内计数器；使用 C2 `audit_events` 的 `mcp.tool_call.started` / `mcp.tool_call.finished` 事件计数，不新建租约表。金额一律 `Decimal`，不得用 `float`。账本 `run_ledger_entries` 八列与六种 `entry_kind` 不得改变。
- 审计只追加，覆盖允许、拒绝、成功和失败；不得记录明文密钥、Cookie、盐、原始个人数据。审计链由 C2 `services.audit_log` 统一实现，本计划只调用 `append_audit_event`。审计 `result` 只用 `success`、`denied`、`failed`。
- `tools/list` 只返回密钥 `tool_allowlist` 与八个客户工具的交集。内部端点级工具不得出现在客户 `tools/list`、文档或 SDK 中。
- MCP 工具只增不改。破坏性变化必须使用新工具名，旧工具至少保留一个迁移周期。任何新工具名或路径必须先登记到冻结契约。
- 修改任何已有函数前必须运行 GitNexus `impact`；每个 commit 前必须运行 `detect-changes --scope all`。`partial: true`、`truncated: true` 或 `risk: UNKNOWN` 都不是通过。
- 测试命令统一在 `apps/api` 下执行：`uv run pytest ...`。基线是 0 failed；任何新失败都是回归，不得用「已知失败」豁免。
- **PG0 前只读。** C13 在 PG0 前不翻转任何生产开关、不写 `.env.production`、不签发真实客户密钥、不写生产数据库；C13 只提交共享 compose 的默认映射与测试，不部署。认证协议测试只使用本地 ASGI fixture 或 staging 夹具。生产检查只有 `GET /api/health` 与未带 Bearer 的 `POST /mcp/customer`；未带 Bearer 返回 `401` 才通过，返回 `404` 记为 `BLOCKED: customer_switch_not_enabled_pre_pg0`，由 PG0 批次翻开关，不由 C13 修复。首个真实客户密钥的签发属于 PG1（PG0 之后）；C13 不执行。
- 生产 A/B 门禁：`https://scrapy.luteos.com` 与 `https://scrapy.lute-tlz-dddd.top` 的 `/api/health` 必须 200；未带 Bearer 的 `/mcp/customer` 在 PG0 后必须 401；内部 `/mcp` 与全局 token 工具必须仍可用。B 落后时记录 `BLOCKED`，不要求 C13 先升级 B。`/connectors` 浏览器验收由 C14 只读执行；C13 只提供交接单。生产备份、迁移、`.env.production` 变更、部署、重启与开关切换只属于 PG0 发布批次；C13 提交的共享 compose 映射不构成部署。

---

## Dependency Contracts (C2/C3/C4/C5/C6/C7/C8/C9/C10)

C13 只依赖下表的符号。任何名称或参数不一致，必须先改对应 C 计划或 C1 契约，不能在 C13 里写第二套实现。

| 依赖 | 必须提供的符号 |
|---|---|
| C2 身份与审计 | `services.audit_log.append_audit_event(session, *, workspace_id, project_id=None, actor_user_id=None, actor_type="user", action, resource_type, resource_id=None, request_id=None, result="success", details=None, occurred_at=None)`；`AuditEvent` 的 `result` 只有 `success`、`denied`、`failed`。C2 的 `api.authz.require_project_access` 供同一工作区/项目复核复用 |
| C3 身份与密钥 | `models.project_api_key.ProjectApiKey.capability_allowlist`、`status`、`expires_at`；`ProjectApiKeyIdentity.capability_allowlist` 与 `allows_capability`；`authenticate_key`、`find_by_hash`、`consume_daily_quota` |
| C4 任务单 | `services.workbench.tasks.create_workbench_task(session, *, workspace_id, project_id, created_by_user_id, payload, idempotency_key)` 返回 `(task, idempotent_replay)`、`get_workbench_task_detail(session, *, workspace_id, task_id)`；`services.workbench.initial_version.create_initial_workflow_version_for_task(session, *, workspace_id, project_id, created_by_user_id, workbench_task_id, idempotency_key, request_id=None) -> uuid.UUID`；`services.workbench.markets.market_role_for(*, primary_market, comparison_markets, market_code)`；`repositories.workbench_tasks.get_workbench_task(session, *, workspace_id, task_id, project_id=None)`、`list_runs_for_task(session, *, workspace_id, task_id)`、`update_workbench_task_fields(session, *, workspace_id, task_id, values)`；`services.workbench.submission.submit_workbench_task(session, *, workspace_id, project_id, workbench_task_id, workflow_version_id, idempotency_key)`；`schemas.workbench.WorkbenchTaskCreateRequest`（含 `package_type`、`primary_market`、`comparison_markets`、`seed_products`、`target_price_band`、`acceptance_contact_id`、`max_cost_usd/max_pages/max_records`）、`WorkbenchTaskResponse`、`WorkbenchWindow` |
| C5 价格与预算 | `services.pricing.quote(tool_id, *, records_count=0)`、`price_book_fingerprint()`、`ToolNotPricedError`；`services.budget_service.estimate_run_budget(session, *, run_id, endpoint_type, records_count)`；`services.run_budget.OrmRunBudget.cancel(run)` 由 C6 取消服务内部消费，C13 不直接调用 |
| C5 额度 | `repositories.quota_accounts.get_or_create_quota_account(session, *, workspace_id, project_id, period_start)`；`QuotaAccount.remaining_usd`；`core.config.Settings.budget_enforcement_enabled` |
| C6 执行取消 | `services.run_service.cancel_task_runs(session, *, workspace_id, project_id, task_id, idempotency_key, reason_code) -> RunCancellationResult` 是 `cancel_task` 唯一入口；`RunCancellationResult` 至少含 `cancelled_run_ids: tuple[uuid.UUID, ...]`、`preserved_artifact_ids: tuple[str, ...]`、`cancelled_at: datetime`、`replayed: bool`；`services.run_service.CancellationError.code` 只使用 `idempotency_conflict`、`state_conflict`；C6 内部对每个可取消 run 调用 `repositories.runs.cancel_run(session, *, workspace_id, run_id)` 并调用 C5 `OrmRunBudget.cancel(run)`；`services.run_queue.enqueue_run(...)` 只在 `collect` 需要直接入队时使用 |
| C7 Claim 与证据 | `repositories.claims.get_claim(session, *, workspace_id, claim_id)`、`list_evidence(session, *, claim_id)`、`load_evidence_rows(session, *, workspace_id, project_id, evidence_ids)`；`services.claims.load_publishable_claim_rows(session, *, workspace_id, project_id) -> ClaimContractBundle`、`validate_claim_bundle(bundle) -> list[str]`、`ClaimContractBundle.claims/evidences`、`ClaimContractRow.claim_id/claim_status/evidence_grade/review_status/evidence_ids` |
| C8 模板与质量 | `services.workbench_templates.get_task_template(template_id)`、`list_task_templates()`、`template_capability_ids(template_id)`；`TaskTemplate.capability_allowlist: tuple[str, ...]`（字段，C13 只经函数读取）；`tool_catalog.evidence_thresholds.package_threshold_for(tier)`、`PACKAGE_TIER_THRESHOLDS`；`repositories.dataset_quality.get_market_assessment(session, *, task_id, market)`、`list_data_gaps(session, *, task_id, market)` |
| C9 报告查询 | `repositories.report_artifacts.get_latest_artifact(session, *, workspace_id, report_id)`；`services.report_publication.get_current_contract(session, *, workspace, report_id)`；`report_artifacts.run_id`、`status`、`delivery_status`、`manifest_sha256`、`delivered_at` 只读字段 |
| C10 交付 | `services.delivery.store.DeliveryStore(root)`；`services.delivery.service.load_delivery_manifest(session, *, workspace_id, artifact_id, store)`、`open_delivery_zip(...)` |
| 能力目录 | `tool_catalog.service.get_tool_catalog(session)`、`find_tool(catalog, tool_id)`；`tool_catalog.markets.FORMAL_MARKETS`（C7） |

如果某个依赖函数尚未提供，C13 的 `mcp_runtime/customer/ports.py` 只写薄投影并调用该依赖的公开仓储/服务；不得复制预算、Claim、报告或采集逻辑，不得在 C13 中新建 `services.customer_task_gateway`、`services.customer_budget`、`services.customer_capabilities`、`services.governed_collect` 或 `services.delivery_manifest`。

**C6 取消服务前置（必须由 C6 所有者先落地，C13 不自行实现）：** `services/run_service.py` 必须提供 `cancel_task_runs(...)` 与 `RunCancellationResult`、`CancellationError`，签名与语义同上表。`CancellationError(code)` 把 `code` 暴露为 `.code`，只接受 `idempotency_conflict`、`state_conflict`。C6 用 C2 `audit_events` 的 `run.cancelled` 记录幂等键摘要与 `reason_code`，不新建表；同键同 `reason_code` 重放，同键不同 payload 抛 `CancellationError("idempotency_conflict")`，并发同键只执行一次。若 C6 未提供该服务，C13 Task 7 记为 `BLOCKED: c6_cancel_task_service_missing`；C13 不得在适配器里 `del` 参数、循环 `cancel_run` 或复制取消幂等逻辑。

**C7 可发布门禁前置：** `services/claims.py` 必须提供上表的 `load_publishable_claim_rows` 与 `validate_claim_bundle`。C13 只用这两个函数判定 Claim 是否可发布，不复制 `review_status`、`reviewed_content_version` 或证据完整性规则。若缺失，C13 Task 7 记为 `BLOCKED: c7_publishable_gate_missing`。

**C8 模板能力函数前置（必须由 C8 所有者先落地，C13 不自行新增函数或字段）：** `apps/api/src/data_intelligence_hub/services/workbench_templates.py` 必须导出 `template_capability_ids(template_id: str) -> tuple[str, ...]`，由它读取 `TaskTemplate.capability_allowlist` 字段；C13 只导入并调用该函数，不读取 `TaskTemplate` 上不存在的同名属性。若执行 C13 时该函数不存在或返回空元组，C13 记为 `BLOCKED: c8_template_capability_ids_missing`，由 C8 所有者补齐。该函数是代码注册表接口，不是表列，不需要 C1 新登记列；C13 不新增任何列、路径或错误码。若 C1 决定把模板能力白名单冻结为契约对象，C1 必须先登记 `template_capability_ids`，C13 只读消费，不自行改契约。

---

## File Structure

### 新建

| 文件 | 责任 |
|---|---|
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/__init__.py` | 导出客户 server、app 与身份类型 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/tool_names.py` | 冻结的八个工具名，唯一来源 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/errors.py` | 稳定错误码与 HTTP 状态映射 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/auth.py` | 客户 Bearer 鉴权、身份解析、工作区/项目绑定 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/policy.py` | 工具/能力白名单判定与 Cookie 扫描 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/schemas.py` | 客户输入合同（任务包、预算） |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/ports.py` | 端口协议、传输数据类与薄生产适配器；只做字段映射和只读查询 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/authorize.py` | 统一授权管线、授权上下文、审计 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/rate_limit.py` | 基于 `audit_events` 的速率与并发计数 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/middleware.py` | 传输级授权与 `tools/list` 过滤 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/redaction.py` | 客户输出白名单，丢弃内部字段 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/server.py` | 八个客户工具与 MCP server |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/app.py` | Streamable HTTP app、传输安全、ASGI 组合 |
| `apps/api/tests/unit/test_customer_mcp_contract.py` | 契约登记与八个工具名守卫 |
| `apps/api/tests/unit/test_customer_mcp_auth.py` | Bearer、撤销、绑定、禁用开关 |
| `apps/api/tests/unit/test_customer_mcp_policy.py` | Cookie 扫描、能力白名单 |
| `apps/api/tests/unit/test_customer_mcp_authorize.py` | 授权顺序、审计、错误码 |
| `apps/api/tests/unit/test_customer_mcp_rate_limit.py` | 基于审计事件的 DB 速率与并发 |
| `apps/api/tests/unit/test_customer_mcp_tools.py` | 八个工具、tools/list 过滤、参数边界 |
| `apps/api/tests/unit/test_customer_mcp_ports.py` | 端口协议、生产适配器的字段映射、`create_task → collect` 共享初始版本 E2E |
| `apps/api/tests/unit/test_customer_mcp_mount.py` | 挂载顺序、传输安全 |
| `apps/api/tests/integration/test_customer_mcp_protocol.py` | 本地 ASGI fixture 的 MCP 协议、HTTP 401/403/429；不使用生产密钥 |
| `apps/api/tests/unit/test_customer_mcp_scripts.py` | curl 脚本内容与语法 |
| `apps/api/tests/unit/test_deploy_customer_mcp_facts.py` | 共享 compose 与 `.env.example` 的客户 MCP 配置事实；断言不存在租约过期开关 |
| `scripts/verify-customer-mcp.sh` | 生产/预发 curl 验证脚本 |
| `docs/ops/customer-mcp-connectors-handoff.md` | `/connectors` 浏览器交接单 |

### 修改

| 文件 | 改动 |
|---|---|
| `apps/api/src/data_intelligence_hub/core/config.py` | 客户 MCP 开关、速率与并发；不设租约过期开关 |
| `apps/api/.env.example` | 增加 `SCRAPY_MCP_CUSTOMER_ENABLED=false`、速率与并发示例 |
| `configs/deploy/scrapy/docker-compose.yml` | 生产 A/B 共用 compose；只在 `api.environment` 增加三个客户 MCP 映射，默认关闭；不部署 |
| `apps/api/src/data_intelligence_hub/main.py` | 在现有内部 `/mcp` 之前挂载 `/mcp/customer`；不替换内部 app |
| `apps/api/tests/unit/test_mcp_transport_security.py` | 只运行现有断言，证明内部传输安全未变（不改文件） |

### 明确不改

- `apps/api/alembic/versions/`：零改动。
- `apps/api/src/data_intelligence_hub/mcp_runtime/server.py`：内部工具一律不动。
- `apps/api/src/data_intelligence_hub/mcp_runtime/auth.py`：内部 Bearer 中间件一律不动。
- `apps/api/src/data_intelligence_hub/models/__init__.py`：C13 不新增模型，不改。
- `docs/design/【契约冻结】v1-表名-枚举-接口.md`：由 C1 修改；C13 只读校验。

---

### Task 0: 隔离 worktree 初始化

**Files:**
- 只读：`/Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c13-customer-mcp.md`（主工作树的计划文件，复制源）
- Create: `/Users/lute/Project/data_scrapy-gov-c13`（worktree 根）

**Interfaces:**
- Consumes: 前置分支 `feat/gov-c10`（主计划 W11：C13 与 C11 并行，不等待 C11，也不依赖 C12）；主工作树的计划文件。
- Produces: 分支 `feat/gov-c13` 与 worktree `/Users/lute/Project/data_scrapy-gov-c13`；Task 0 之后所有 Run/Commit 都在该 worktree 执行。

- [ ] **Step 0: 主工作树只读预检**

Run:

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
git rev-parse --verify feat/gov-c10^{commit}
git rev-parse --verify --quiet refs/heads/feat/gov-c13 || echo "C13_BRANCH_ABSENT"
test ! -e /Users/lute/Project/data_scrapy-gov-c13 && echo "worktree_path_free"
```

Expected: `git worktree prune` 退出码 0；`git rev-parse` 输出 C10 提交 SHA；输出 `C13_BRANCH_ABSENT` 与 `worktree_path_free`。`feat/gov-c10` 不存在或 worktree 路径已存在时停止，先审查旧分支与旧 worktree，不得复用或删除。

- [ ] **Step 1: 创建 worktree 并同步依赖**

Run:

```bash
cd /Users/lute/Project/data_scrapy
git worktree add /Users/lute/Project/data_scrapy-gov-c13 -b feat/gov-c13 feat/gov-c10
cd /Users/lute/Project/data_scrapy-gov-c13
test "$(git branch --show-current)" = feat/gov-c13 && echo "branch=feat/gov-c13"
git merge-base --is-ancestor feat/gov-c10 HEAD; echo "c10_ancestor=$?"
mkdir -p docs/superpowers/plans
cp /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c13-customer-mcp.md docs/superpowers/plans/
cd apps/api && uv sync
```

Expected: `branch=feat/gov-c13`；`c10_ancestor=0`；`uv sync` 退出码 0。本计划的 Markdown 不在 `feat/gov-c10` 内，必须先从主工作树复制到 worktree。主工作树只用于本 Step 的 `git worktree add`、只读预检与 `cp` 源。不得从 C12 分支创建或断言其祖先关系；C12 依赖 C11，与 C13 是并行分支。

- [ ] **Step 2: 固定执行路径**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
git rev-parse --show-toplevel
git status --short
```

Expected: 输出 `/Users/lute/Project/data_scrapy-gov-c13`；工作区干净。后续 Run/Commit 块必须在该 worktree 内执行。

---

### Task 1: 契约门禁与八个工具名

**Files:**
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/__init__.py`
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/tool_names.py`
- Test: `apps/api/tests/unit/test_customer_mcp_contract.py`

**Interfaces:**
- Consumes: C1 已登记的 `/mcp/customer`、`configs/contracts/v1.1.0/customer_mcp.schema.json`、`project_api_keys.capability_allowlist`。
- Produces: `CUSTOMER_TOOL_NAMES: tuple[str, ...]`，后续所有任务用它判定工具集合。

- [ ] **Step 1: 写失败测试**

```python
"""客户 MCP 契约门禁。

C13 不修改契约。契约缺任何一项，本测试失败，计划停止执行。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from data_intelligence_hub.mcp_runtime.customer.tool_names import CUSTOMER_TOOL_NAMES

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = REPO_ROOT / "docs" / "design" / "【契约冻结】v1-表名-枚举-接口.md"
REGISTRY_PATH = REPO_ROOT / "configs" / "contracts" / "v1.1.0" / "registry.json"
SCHEMA_PATH = REPO_ROOT / "configs" / "contracts" / "v1.1.0" / "customer_mcp.schema.json"

EXPECTED_TOOLS = (
    "discover_capabilities",
    "estimate_task",
    "create_task",
    "get_task",
    "cancel_task",
    "get_delivery_manifest",
    "get_evidence",
    "collect",
)

EXPECTED_DEFS = {
    "DiscoverCapabilitiesInput",
    "DiscoverCapabilitiesOutput",
    "EstimateTaskInput",
    "EstimateTaskOutput",
    "CreateTaskInput",
    "CreateTaskOutput",
    "GetTaskInput",
    "GetTaskOutput",
    "CancelTaskInput",
    "CancelTaskOutput",
    "GetDeliveryManifestInput",
    "GetDeliveryManifestOutput",
    "GetEvidenceInput",
    "GetEvidenceOutput",
    "CollectInput",
    "CollectOutput",
    "BudgetInput",
}


def test_customer_tool_names_are_exactly_eight() -> None:
    assert CUSTOMER_TOOL_NAMES == EXPECTED_TOOLS
    assert len(set(CUSTOMER_TOOL_NAMES)) == 8


def test_contract_registers_customer_mcp_surface() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert '"/mcp/customer"' in text or "`/mcp/customer`" in text
    assert not re.search(r'"/mcp"\s*,', text), "C1 不得把客户入口登记为 /mcp"
    assert "capability_allowlist" in text
    assert "customer_mcp.schema.json" in text
    missing = [name for name in CUSTOMER_TOOL_NAMES if name not in text]
    assert missing == [], f"C1 未登记客户工具：{missing}"


def test_registry_has_no_customer_lease_table() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    c13 = next(item for item in registry["phases"] if item["id"] == "C13")
    assert "table:mcp_customer_request_leases" not in c13["objects"]
    table_names = {table["name"] for table in registry["tables"]}
    assert "mcp_customer_request_leases" not in table_names


def test_customer_mcp_schema_has_all_tool_defs() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert EXPECTED_DEFS <= set(schema["$defs"])
    for tool_name, suffix in (
        ("discover_capabilities", "DiscoverCapabilities"),
        ("estimate_task", "EstimateTask"),
        ("create_task", "CreateTask"),
        ("get_task", "GetTask"),
        ("cancel_task", "CancelTask"),
        ("get_delivery_manifest", "GetDeliveryManifest"),
        ("get_evidence", "GetEvidence"),
        ("collect", "Collect"),
    ):
        assert f"{suffix}Input" in schema["$defs"], tool_name
        assert f"{suffix}Output" in schema["$defs"], tool_name


def test_c13_migrations_create_no_lease_table() -> None:
    versions = REPO_ROOT / "apps" / "api" / "alembic" / "versions"
    migration_text = "\n".join(
        path.read_text(encoding="utf-8") for path in versions.glob("*.py")
    )
    assert "capability_allowlist" in migration_text
    assert "mcp_customer_request_leases" not in migration_text


def test_create_task_input_registers_seed_products_and_price_band() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    properties = schema["$defs"]["CreateTaskInput"]["properties"]
    assert properties["seed_products"] == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert properties["target_price_band"] == {"type": "object"}
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    create_path = next(
        item for item in registry["paths"] if item["id"] == "workbench.tasks.create"
    )
    assert create_path["idempotent"] is True
    assert "idempotency_conflict" in create_path["error_codes"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_contract.py -q`

Expected: `FAILED` with `ModuleNotFoundError: No module named 'data_intelligence_hub.mcp_runtime.customer'`.

- [ ] **Step 3: Create the package marker**

`apps/api/src/data_intelligence_hub/mcp_runtime/customer/__init__.py`:

```python
"""客户 MCP 入口。内部 `/mcp` 不在此包内。"""
```

- [ ] **Step 4: Create the frozen tool names**

`apps/api/src/data_intelligence_hub/mcp_runtime/customer/tool_names.py`:

```python
"""客户 MCP 的八个稳定工具名。

顺序就是 C1 `customer_mcp.schema.json` 的顺序，也是 `tools/list` 的注册顺序。
不得在此增加内部工具、端点级工具或临时工具。
"""

from __future__ import annotations

CUSTOMER_TOOL_NAMES: tuple[str, ...] = (
    "discover_capabilities",
    "estimate_task",
    "create_task",
    "get_task",
    "cancel_task",
    "get_delivery_manifest",
    "get_evidence",
    "collect",
)

__all__ = ["CUSTOMER_TOOL_NAMES"]
```

- [ ] **Step 5: 运行契约门禁**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_contract.py -q`

Expected: `6 passed`。若 `test_registry_has_no_customer_lease_table` 失败，C13 状态记为 `BLOCKED`；C1 所有者必须从 registry 删除 `mcp_customer_request_leases` 或标 `deferred`。C13 不自行改 registry。若 `test_create_task_input_registers_seed_products_and_price_band` 失败，C13 状态记为 `BLOCKED`；C1 必须登记 `seed_products`、`target_price_band`、`workbench.tasks.create` 的幂等标记与 `idempotency_conflict`。

If the failure is `C1 未登记 /mcp/customer`、`capability_allowlist`、`customer_mcp.schema.json` 或任一工具名，立即停止。C13 不修改契约，不放大断言。若 registry 或迁移出现 `mcp_customer_request_leases`，停止并回退；由 C1 所有者删除或标 `deferred`。

- [ ] **Step 6: Record GitNexus impact for symbols this plan will modify**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
node .gitnexus/run.cjs impact "create_app" --direction upstream --repo .
node .gitnexus/run.cjs impact "BearerTokenMiddleware" --direction upstream --repo .
node .gitnexus/run.cjs impact "ProjectApiKeyIdentity" --direction upstream --repo .
node .gitnexus/run.cjs impact "authenticate_key" --direction upstream --repo .
```

Expected: each command prints callers, processes and `risk`. Record the output in the commit body. If any risk is `HIGH` or `CRITICAL`, report it before editing. If `risk` is `UNKNOWN`, confirm with `rg -n "create_app|BearerTokenMiddleware|ProjectApiKeyIdentity|authenticate_key" apps/api/src apps/api/tests` before proceeding.

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/mcp_runtime/customer/__init__.py \
        apps/api/src/data_intelligence_hub/mcp_runtime/customer/tool_names.py \
        apps/api/tests/unit/test_customer_mcp_contract.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(customer-mcp): add contract gate and frozen tool names"
```

---

### Task 2: 客户 Bearer 鉴权与配置

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/core/config.py`（`mcp_daily_collects` 之后）
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/errors.py`
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/auth.py`
- Test: `apps/api/tests/unit/test_customer_mcp_auth.py`

**Interfaces:**
- Consumes: `repositories.project_api_keys.find_by_hash`、`repositories.projects.get_project`、`repositories.workspaces.get_workspace_by_id`、`services.project_api_keys.hash_key`。
- Produces: `CustomerIdentity(key_id, workspace_id, project_id, key_prefix, label, tool_allowlist, capability_allowlist, daily_collect_quota)`；`resolve_customer_identity(session, token) -> tuple[CustomerIdentity | None, CustomerAuthFailure | None]`；`CustomerBearerMiddleware`；`customer_identity(context)`；`customer_identity_from_scope(scope)`；`customer_identity_from_request(request)`。

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/test_customer_mcp_auth.py`:

```python
"""客户 MCP Bearer 鉴权。

客户入口只接受 dih_ 项目密钥。全局运维 token、开发放行和 demo 回退都不适用。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from starlette.types import Receive, Scope, Send

from data_intelligence_hub.core import config
from data_intelligence_hub.mcp_runtime.customer import auth as auth_module
from data_intelligence_hub.mcp_runtime.customer.auth import (
    CUSTOMER_STATE_KEY,
    CustomerAuthFailure,
    CustomerBearerMiddleware,
    CustomerIdentity,
)


async def _ok_app(scope: Scope, receive: Receive, send: Send) -> None:
    del receive
    state = scope.setdefault("state", {})
    state["seen_identity"] = state.get(CUSTOMER_STATE_KEY)
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


@asynccontextmanager
async def _null_session():
    yield SimpleNamespace()


IDENTITY = CustomerIdentity(
    key_id=uuid.uuid4(),
    workspace_id=uuid.uuid4(),
    project_id=uuid.uuid4(),
    key_prefix="dih_test",
    label="test",
    tool_allowlist=("discover_capabilities", "get_task"),
    capability_allowlist=("cap-1",),
    daily_collect_quota=10,
)


def _settings(**overrides: object) -> config.Settings:
    values = {
        "app_env": "production",
        "SCRAPY_MCP_TOKEN": SecretStr("ops-token"),
        "SCRAPY_MCP_CUSTOMER_ENABLED": True,
    }
    values.update(overrides)
    return config.Settings(**values)


def _transport(monkeypatch: pytest.MonkeyPatch, **overrides: object):
    settings = _settings(**overrides)
    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    return ASGITransport(
        app=CustomerBearerMiddleware(_ok_app, session_factory=_null_session)
    )


@pytest.mark.asyncio
async def test_customer_mcp_rejects_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = _transport(monkeypatch)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/")

    assert response.status_code == 401
    assert response.json()["detail"] == "project_key_invalid"


@pytest.mark.asyncio
async def test_customer_mcp_rejects_global_operator_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = _transport(monkeypatch)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/", headers={"Authorization": "Bearer ops-token"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_customer_mcp_accepts_project_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_resolve(session: object, token: str):
        del session
        if token == "dih_valid":
            return IDENTITY, None
        return None, CustomerAuthFailure("project_key_invalid")

    monkeypatch.setattr(auth_module, "resolve_customer_identity", fake_resolve)
    transport = _transport(monkeypatch)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/", headers={"Authorization": "Bearer dih_valid"}
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_customer_mcp_rejects_revoked_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_resolve(session: object, token: str):
        del session, token
        return None, CustomerAuthFailure(
            "project_key_revoked",
            key_id=IDENTITY.key_id,
            workspace_id=IDENTITY.workspace_id,
            project_id=IDENTITY.project_id,
        )

    monkeypatch.setattr(auth_module, "resolve_customer_identity", fake_resolve)
    transport = _transport(monkeypatch)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/", headers={"Authorization": "Bearer dih_revoked"}
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_customer_mcp_rejects_broken_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_resolve(session: object, token: str):
        del session, token
        return None, CustomerAuthFailure(
            "permission_denied",
            key_id=IDENTITY.key_id,
            workspace_id=IDENTITY.workspace_id,
            project_id=IDENTITY.project_id,
        )

    monkeypatch.setattr(auth_module, "resolve_customer_identity", fake_resolve)
    transport = _transport(monkeypatch)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/", headers={"Authorization": "Bearer dih_broken"}
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "permission_denied"


@pytest.mark.asyncio
async def test_customer_mcp_is_404_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = _transport(monkeypatch, SCRAPY_MCP_CUSTOMER_ENABLED=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/", headers={"Authorization": "Bearer dih_valid"}
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "customer_mcp_disabled"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_auth.py -q`

Expected: `FAILED` with `ModuleNotFoundError: No module named 'data_intelligence_hub.mcp_runtime.customer.errors'` or `auth`.

- [ ] **Step 3: Add configuration**

在 `core/config.py` 的 `mcp_daily_collects` 字段之后加入：

```python
    # 客户 MCP 默认关闭。打开前必须完成 PG0 与 C2/C3/C4/C5/C6/C7/C8/C9/C10 依赖。
    mcp_customer_enabled: bool = Field(
        default=False,
        validation_alias="SCRAPY_MCP_CUSTOMER_ENABLED",
    )
    mcp_customer_rate_per_minute: int = Field(
        default=60,
        ge=1,
        validation_alias="SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE",
    )
    mcp_customer_concurrent_calls: int = Field(
        default=4,
        ge=1,
        validation_alias="SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS",
    )
```

不增加租约过期配置项（总索引 §6 规则 7：C13 不建租约表，因此不设置租约过期开关）。stale 判定在 `mcp_runtime/customer/rate_limit.py` 使用内部常量 `STALE_AFTER_SECONDS = 300`；它不进入 `Settings`、`.env.example`、compose 或产品阈值。

同时修改 `apps/api/.env.example`，在文件末尾追加：

```dotenv
# SCRAPY_MCP_CUSTOMER_ENABLED: 客户 MCP 总开关。默认关闭；关闭时 /mcp/customer 返回 404。
SCRAPY_MCP_CUSTOMER_ENABLED=false
# 客户 MCP 速率与并发。按试点容量设置；默认值与 Settings 一致。
SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE=60
SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS=4
```

- [ ] **Step 4: Create error codes**

`mcp_runtime/customer/errors.py`:

```python
"""客户 MCP 的稳定错误码。

错误消息就是错误码，不含请求参数、密钥、Cookie 或上游原文。
"""

from __future__ import annotations

HTTP_STATUS_BY_CODE: dict[str, int] = {
    "authentication_required": 401,
    "project_key_invalid": 401,
    "project_key_revoked": 401,
    "permission_denied": 403,
    "tool_not_allowed": 403,
    "capability_not_allowed": 403,
    "cookie_not_accepted": 403,
    "quota_exceeded": 429,
    "rate_limited": 429,
    "approval_required": 409,
    "state_conflict": 409,
    "idempotency_conflict": 409,
    "task_not_found": 404,
    "claim_not_found": 404,
    "evidence_not_found": 404,
    "manifest_not_found": 404,
    "tool_not_executable": 422,
    "tool_not_priced": 422,
    "market_unsupported": 422,
    "package_type_invalid": 422,
    "comparison_markets_exceeded": 422,
    "acceptance_contact_not_member": 422,
    "budget_invalid": 422,
}


class CustomerToolError(ValueError):
    """带稳定错误码的客户工具错误。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def http_status_for(code: str) -> int:
    return HTTP_STATUS_BY_CODE.get(code, 400)


__all__ = ["CustomerToolError", "HTTP_STATUS_BY_CODE", "http_status_for"]
```

- [ ] **Step 5: Create customer auth**

`mcp_runtime/customer/auth.py`:

```python
"""客户 MCP 的 Bearer 鉴权与工作区/项目绑定。

与内部 `/mcp` 的区别：
- 只接受 `dih_` 项目密钥；全局运维 token 一律拒绝。
- 没有开发放行、demo 回退或空 token 分支。
- 身份写入 ASGI `scope['state']`，供传输级授权读取。
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import UTC, datetime

import structlog
from mcp.server.mcpserver import Context
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import ASGIApp, Receive, Scope, Send

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.repositories.project_api_keys import find_by_hash
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.workspaces import get_workspace_by_id
from data_intelligence_hub.services.project_api_keys import hash_key

logger = structlog.get_logger(__name__)

CUSTOMER_STATE_KEY = "mcp_customer_identity"
CUSTOMER_FAILURE_STATE_KEY = "mcp_customer_auth_failure"
PROJECT_KEY_MARKER = "dih_"
BEARER_PREFIX = "Bearer "


@dataclasses.dataclass(frozen=True, slots=True)
class CustomerIdentity:
    """项目密钥通过鉴权后的客户调用身份。它不含明文。"""

    key_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    key_prefix: str
    label: str
    tool_allowlist: tuple[str, ...]
    capability_allowlist: tuple[str, ...]
    daily_collect_quota: int


@dataclasses.dataclass(frozen=True, slots=True)
class CustomerAuthFailure:
    """一次鉴权失败。仅用于返回固定错误码与审计定位。"""

    reason: str
    key_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None


def _bearer_value(scope: Scope) -> str:
    headers = dict(scope.get("headers") or [])
    value = headers.get(b"authorization", b"").decode()
    if value.startswith(BEARER_PREFIX):
        return value.removeprefix(BEARER_PREFIX).strip()
    return ""


async def resolve_customer_identity(
    session: AsyncSession,
    token: str,
) -> tuple[CustomerIdentity | None, CustomerAuthFailure | None]:
    """解析项目密钥并校验绑定。

    返回二元组：成功时 `(identity, None)`，失败时 `(None, failure)`。
    已撤销的密钥与不存在的密钥都不返回身份；区别只在 failure.reason 与审计。
    """
    if not token.startswith(PROJECT_KEY_MARKER):
        return None, CustomerAuthFailure("project_key_invalid")
    record = await find_by_hash(session, hash_key(token))
    if record is None:
        return None, CustomerAuthFailure("project_key_invalid")
    expired = record.expires_at is not None and record.expires_at <= datetime.now(UTC)
    if record.revoked_at is not None or record.status != "active" or expired:
        return None, CustomerAuthFailure(
            "project_key_revoked",
            key_id=record.id,
            workspace_id=record.workspace_id,
            project_id=record.project_id,
        )
    if await get_workspace_by_id(session, record.workspace_id) is None:
        return None, CustomerAuthFailure(
            "permission_denied",
            key_id=record.id,
            workspace_id=record.workspace_id,
            project_id=record.project_id,
        )
    if await get_project(session, record.workspace_id, record.project_id) is None:
        return None, CustomerAuthFailure(
            "permission_denied",
            key_id=record.id,
            workspace_id=record.workspace_id,
            project_id=record.project_id,
        )
    capability_allowlist = tuple(
        str(item) for item in (getattr(record, "capability_allowlist", ()) or ())
    )
    return (
        CustomerIdentity(
            key_id=record.id,
            workspace_id=record.workspace_id,
            project_id=record.project_id,
            key_prefix=record.key_prefix,
            label=record.label,
            tool_allowlist=tuple(str(item) for item in (record.tool_allowlist or ())),
            capability_allowlist=capability_allowlist,
            daily_collect_quota=record.daily_collect_quota,
        ),
        None,
    )


def _scope_state(scope: Scope) -> dict[str, object]:
    state = scope.get("state")
    if not isinstance(state, dict):
        state = {}
        scope["state"] = state
    return state


def _attach_identity(scope: Scope, identity: CustomerIdentity) -> None:
    _scope_state(scope)[CUSTOMER_STATE_KEY] = identity


def _attach_failure(scope: Scope, failure: CustomerAuthFailure) -> None:
    _scope_state(scope)[CUSTOMER_FAILURE_STATE_KEY] = failure


def _identity_from_scope(scope: object) -> CustomerIdentity | None:
    if not isinstance(scope, dict):
        return None
    state = scope.get("state")
    if not isinstance(state, dict):
        return None
    identity = state.get(CUSTOMER_STATE_KEY)
    return identity if isinstance(identity, CustomerIdentity) else None


def customer_identity_from_scope(scope: object) -> CustomerIdentity | None:
    """从 ASGI scope 读取客户身份。"""
    return _identity_from_scope(scope)


def customer_identity_from_request(request: object | None) -> CustomerIdentity | None:
    """从 Starlette Request 读取客户身份。`tools/list` 过滤使用。"""
    if request is None:
        return None
    return _identity_from_scope(getattr(request, "scope", None))


def customer_identity(context: Context) -> CustomerIdentity | None:
    """从 MCP Context 读取客户身份。"""
    try:
        request = context.request_context.request
    except (AttributeError, ValueError):
        return None
    return _identity_from_scope(getattr(request, "scope", None))


def customer_auth_failure(context: Context) -> CustomerAuthFailure | None:
    try:
        request = context.request_context.request
    except (AttributeError, ValueError):
        return None
    scope = getattr(request, "scope", None)
    if not isinstance(scope, dict):
        return None
    state = scope.get("state")
    if not isinstance(state, dict):
        return None
    failure = state.get(CUSTOMER_FAILURE_STATE_KEY)
    return failure if isinstance(failure, CustomerAuthFailure) else None


async def _send_json(
    send: Send,
    status: int,
    payload: dict[str, object],
    *,
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    headers.extend(extra_headers or [])
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class CustomerBearerMiddleware:
    """客户入口的 Bearer 鉴权。只接受项目密钥。"""

    def __init__(
        self,
        app: ASGIApp,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._app = app
        self._session_factory = session_factory or async_session_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        if not get_settings().mcp_customer_enabled:
            await _send_json(send, 404, {"detail": "customer_mcp_disabled"})
            return
        token = _bearer_value(scope)
        try:
            async with self._session_factory() as session:
                identity, failure = await resolve_customer_identity(session, token)
        except Exception as exc:
            logger.warning(
                "customer_mcp_identity_lookup_failed",
                error_type=type(exc).__name__,
            )
            identity, failure = None, CustomerAuthFailure("lookup_failed")
        if identity is None:
            failure = failure or CustomerAuthFailure("project_key_invalid")
            _attach_failure(scope, failure)
            if failure.reason == "permission_denied":
                await _send_json(
                    send,
                    403,
                    {"detail": "permission_denied"},
                )
                return
            detail = (
                "project_key_revoked"
                if failure.reason == "project_key_revoked"
                else "project_key_invalid"
            )
            await _send_json(
                send,
                401,
                {"detail": detail},
                extra_headers=[(b"www-authenticate", b"Bearer")],
            )
            return
        _attach_identity(scope, identity)
        await self._app(scope, receive, send)


__all__ = [
    "CUSTOMER_FAILURE_STATE_KEY",
    "CUSTOMER_STATE_KEY",
    "CustomerAuthFailure",
    "CustomerBearerMiddleware",
    "CustomerIdentity",
    "customer_auth_failure",
    "customer_identity",
    "customer_identity_from_request",
    "customer_identity_from_scope",
    "resolve_customer_identity",
]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_auth.py -q`

Expected: `6 passed`.

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
git add apps/api/src/data_intelligence_hub/core/config.py \
        apps/api/.env.example \
        apps/api/src/data_intelligence_hub/mcp_runtime/customer/errors.py \
        apps/api/src/data_intelligence_hub/mcp_runtime/customer/auth.py \
        apps/api/tests/unit/test_customer_mcp_auth.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(customer-mcp): add project-key bearer auth and config"
```

---

### Task 2b: 共用 compose 的客户 MCP 配置事实（默认关闭）

**Files:**
- Modify: `configs/deploy/scrapy/docker-compose.yml`（生产 A 与 B 共用）
- Test: `apps/api/tests/unit/test_deploy_customer_mcp_facts.py`

**Interfaces:**
- 生产 A/B 共用 `configs/deploy/scrapy/docker-compose.yml`；**不修改 `configs/deploy/scrapy-new/**`**。
- `api.environment` 新增 `SCRAPY_MCP_CUSTOMER_ENABLED`（默认 `false`）、`SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE`（默认 `60`）与 `SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS`（默认 `4`）。
- 不增加 `SCRAPY_MCP_CUSTOMER_LEASE_STALE_SECONDS`；stale 使用 `rate_limit.STALE_AFTER_SECONDS` 内部常量。
- 不改 edge、网络、volume、端口。本任务不写 `.env.production`、不部署、不重启容器；发布与开关翻转由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_deploy_customer_mcp_facts.py`:

```python
"""共享生产 compose 的客户 MCP 配置事实。"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE = REPO_ROOT / "configs/deploy/scrapy/docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / "apps/api/.env.example"
CONFIG = REPO_ROOT / "apps/api/src/data_intelligence_hub/core/config.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_customer_mcp_switch_is_off_by_default() -> None:
    text = _text(COMPOSE)
    assert "SCRAPY_MCP_CUSTOMER_ENABLED: ${SCRAPY_MCP_CUSTOMER_ENABLED:-false}" in text


def test_customer_mcp_limits_are_mapped() -> None:
    text = _text(COMPOSE)
    assert (
        "SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE: "
        "${SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE:-60}"
    ) in text
    assert (
        "SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS: "
        "${SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS:-4}"
    ) in text


def test_internal_mcp_limits_are_unchanged() -> None:
    text = _text(COMPOSE)
    assert "SCRAPY_MCP_RATE_PER_MINUTE: ${SCRAPY_MCP_RATE_PER_MINUTE:-120}" in text
    assert "SCRAPY_MCP_CONCURRENT_CALLS: ${SCRAPY_MCP_CONCURRENT_CALLS:-8}" in text


def test_no_lease_stale_switch_is_exposed() -> None:
    for path in (COMPOSE, ENV_EXAMPLE, CONFIG):
        assert "SCRAPY_MCP_CUSTOMER_LEASE_STALE_SECONDS" not in _text(path)


def test_scrapy_new_is_not_used() -> None:
    assert "scrapy-new" not in _text(COMPOSE)


def test_env_example_documents_customer_mcp_keys() -> None:
    text = _text(ENV_EXAMPLE)
    for expected in (
        "SCRAPY_MCP_CUSTOMER_ENABLED=false",
        "SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE=60",
        "SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS=4",
    ):
        assert expected in text
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13/apps/api
uv run pytest tests/unit/test_deploy_customer_mcp_facts.py -q
```

Expected: FAIL。共享 compose 尚未映射客户 MCP 的键。

- [ ] **Step 3: 修改共享 compose**

在 `configs/deploy/scrapy/docker-compose.yml` 的 `api.environment` 中、内部 `SCRAPY_MCP_*` 段之后追加：

```yaml
      # C13：默认关闭。PG0 发布批次在 C13 通过后由 .env.production 显式打开。
      SCRAPY_MCP_CUSTOMER_ENABLED: ${SCRAPY_MCP_CUSTOMER_ENABLED:-false}
      SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE: ${SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE:-60}
      SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS: ${SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS:-4}
```

不要新增 `SCRAPY_MCP_CUSTOMER_LEASE_STALE_SECONDS`；不要改 `edge`、网络、volume 或端口。

- [ ] **Step 4: 校验 compose 与测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
docker compose -f configs/deploy/scrapy/docker-compose.yml config --quiet
cd apps/api
uv run pytest tests/unit/test_deploy_customer_mcp_facts.py -q
```

Expected: `docker compose config` 退出码 0；6 passed。若本机缺少生产必填变量，只运行测试，并在 C14 的 A/B 环境执行 `config --quiet`。

- [ ] **Step 5: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add configs/deploy/scrapy/docker-compose.yml \
  apps/api/tests/unit/test_deploy_customer_mcp_facts.py
git commit -m "ops(customer-mcp): map default-off customer MCP settings"
```

Expected: `detect-changes` 不含 `partial: true` / `truncated: true`；没有 `configs/deploy/scrapy-new/**` 改动。

---

### Task 3: 输入合同、Cookie 隔离与能力白名单

**Files:**
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/schemas.py`
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/policy.py`
- Test: `apps/api/tests/unit/test_customer_mcp_policy.py`

**Interfaces:**
- Consumes: `errors.CustomerToolError`、`tool_names.CUSTOMER_TOOL_NAMES`、`auth.CustomerIdentity`。
- Produces: `BudgetInput`、`EstimateTaskInput`、`CreateTaskInput`；`find_credential_material(value) -> str | None`；`find_forbidden_argument(value) -> str | None`；`requested_capability_ids(tool_name, arguments) -> tuple[str, ...]`；`assert_capability_allowed(identity, capability_id, template_ids)`。

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/test_customer_mcp_policy.py`:

```python
"""客户输入边界：Cookie 隔离、能力白名单、预算与窗口。"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from data_intelligence_hub.mcp_runtime.customer.auth import CustomerIdentity
from data_intelligence_hub.mcp_runtime.customer.policy import (
    assert_capability_allowed,
    find_credential_material,
    find_forbidden_argument,
    requested_capability_ids,
)
from data_intelligence_hub.mcp_runtime.customer.schemas import (
    BudgetInput,
    CreateTaskInput,
    EstimateTaskInput,
    validate_window,
)

IDENTITY = CustomerIdentity(
    key_id=uuid.uuid4(),
    workspace_id=uuid.uuid4(),
    project_id=uuid.uuid4(),
    key_prefix="dih_test",
    label="test",
    tool_allowlist=("collect",),
    capability_allowlist=("cap-product",),
    daily_collect_quota=10,
)


def test_cookie_material_is_rejected_recursively() -> None:
    assert (
        find_credential_material({"params": {"creator_cookie": "sessionid=abc"}})
        == "arguments.params.creator_cookie"
    )
    assert (
        find_credential_material({"params": {"headers": {"Cookie": "a=b"}}})
        == "arguments.params.headers.cookie"
    )
    assert find_credential_material({"params": {"query": "hello"}}) is None


def test_cookie_value_is_rejected_even_when_key_is_innocent() -> None:
    assert (
        find_credential_material({"params": {"note": "Cookie: sessionid=abc"}})
        == "arguments.params.note"
    )


def test_provider_and_endpoint_arguments_are_rejected() -> None:
    assert (
        find_forbidden_argument({"params": {"provider": "exa"}})
        == "arguments.params.provider"
    )
    assert (
        find_forbidden_argument({"params": {"endpoint_type": "tikhub_x"}})
        == "arguments.params.endpoint_type"
    )
    assert find_forbidden_argument({"params": {"query": "baby"}}) is None
    assert (
        find_forbidden_argument({"params": {"limit": 10}})
        == "arguments.params.limit"
    )
    assert (
        find_forbidden_argument({"params": {"page_size": 50}})
        == "arguments.params.page_size"
    )
    assert (
        find_forbidden_argument({"params": {"tool_id": "tikhub_x"}})
        == "arguments.params.tool_id"
    )


def test_requested_capability_ids_only_reads_collect() -> None:
    assert requested_capability_ids(
        "collect", {"capability_id": "cap-product", "params": {}}
    ) == ("cap-product",)
    assert requested_capability_ids("get_task", {"capability_id": "cap-product"}) == ()


def test_capability_must_be_in_key_and_template() -> None:
    assert_capability_allowed(IDENTITY, "cap-product", {"cap-product"})

    with pytest.raises(ValueError) as exc:
        assert_capability_allowed(IDENTITY, "cap-other", {"cap-other"})
    assert str(exc.value) == "capability_not_allowed"

    with pytest.raises(ValueError) as exc:
        assert_capability_allowed(IDENTITY, "cap-product", {"cap-template-only"})
    assert str(exc.value) == "capability_not_allowed"

    with pytest.raises(ValueError) as exc:
        assert_capability_allowed(IDENTITY, "cap-product", set())
    assert str(exc.value) == "capability_not_allowed"


def test_budget_uses_decimal_and_c1_minimum() -> None:
    budget = BudgetInput(max_cost_usd="120.50", max_pages=10, max_records=500)
    assert budget.max_cost_usd == Decimal("120.50")
    assert BudgetInput(max_cost_usd="0").max_cost_usd == Decimal("0")

    with pytest.raises(ValidationError):
        BudgetInput(max_cost_usd="-1")

    with pytest.raises(ValidationError):
        BudgetInput(max_cost_usd="Infinity")


def test_window_rejects_future_and_reversed_dates() -> None:
    with pytest.raises(ValueError):
        validate_window(date(2099, 1, 1), date(2099, 1, 2))

    with pytest.raises(ValueError):
        validate_window(date(2026, 9, 30), date(2026, 9, 1))


def test_task_inputs_match_c1_required_fields() -> None:
    estimate = EstimateTaskInput(
        template_id="maternal-new-entry",
        package_type="quick",
        primary_market="US",
        compare_markets=(),
        category_id="feeding",
        window_start=date(2026, 9, 1),
        window_end=date(2026, 9, 30),
        budget=BudgetInput(max_cost_usd="20"),
    )
    assert estimate.package_type == "quick"

    create = CreateTaskInput(
        idempotency_key="idem-1",
        template_id="maternal-new-entry",
        package_type="quick",
        primary_market="US",
        compare_markets=(),
        category_id="feeding",
        brand="Brand",
        competitors=(),
        window_start=date(2026, 9, 1),
        window_end=date(2026, 9, 30),
        decision_question="是否值得进入？",
        does_not_answer=(),
        seed_products=("https://example.com/1", "https://example.com/2", "ID-3"),
        target_price_band={"currency": "USD", "min_amount": "10", "max_amount": "30"},
        budget=BudgetInput(max_cost_usd="20"),
        acceptance_contact_id=str(uuid.uuid4()),
    )
    assert create.idempotency_key == "idem-1"
    assert create.seed_products == (
        "https://example.com/1",
        "https://example.com/2",
        "ID-3",
    )
    assert create.target_price_band == {
        "currency": "USD",
        "min_amount": "10",
        "max_amount": "30",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_policy.py -q`

Expected: `FAILED` with `ModuleNotFoundError: No module named 'data_intelligence_hub.mcp_runtime.customer.policy'`.

- [ ] **Step 3: Create the input schemas**

`mcp_runtime/customer/schemas.py`:

```python
"""客户 MCP 的输入合同。

字段与 C1 `configs/contracts/v1.1.0/customer_mcp.schema.json` 对齐。
金额用 Decimal；MCP 传入数字时 pydantic 直接转 Decimal，不经过 float 计算。
工作区、项目、provider、端点、分页、重试和 Cookie 都不在输入里。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class BudgetInput(BaseModel):
    """C1 `BudgetInput`。max_cost_usd 是非负 USD 金额。"""

    max_cost_usd: Decimal = Field(ge=0)
    max_pages: int | None = Field(default=None, ge=0)
    max_records: int | None = Field(default=None, ge=0)

    @field_validator("max_cost_usd")
    @classmethod
    def _finite_decimal(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("invalid_request")
        return value


@dataclass(frozen=True, slots=True)
class EstimateTaskInput:
    template_id: str
    package_type: str
    primary_market: str
    compare_markets: tuple[str, ...]
    category_id: str
    window_start: date
    window_end: date
    budget: BudgetInput


@dataclass(frozen=True, slots=True)
class CreateTaskInput:
    idempotency_key: str
    template_id: str
    package_type: str
    primary_market: str
    compare_markets: tuple[str, ...]
    category_id: str
    brand: str
    competitors: tuple[str, ...]
    window_start: date
    window_end: date
    decision_question: str
    does_not_answer: tuple[str, ...]
    seed_products: tuple[str, ...]
    target_price_band: dict[str, object] | None
    budget: BudgetInput
    acceptance_contact_id: str


def validate_window(window_start: date, window_end: date) -> None:
    """C1 窗口规则：顺序、未来、最长 365 天。"""
    if window_end < window_start:
        raise ValueError("window_order_invalid")
    if window_end > date.today():
        raise ValueError("window_future")
    if (window_end - window_start).days > 365:
        raise ValueError("window_too_long")


__all__ = [
    "BudgetInput",
    "CreateTaskInput",
    "EstimateTaskInput",
    "validate_window",
]
```

- [ ] **Step 4: Create the policy module**

`mcp_runtime/customer/policy.py`:

```python
"""客户请求的白名单与 Cookie 隔离。

判定只返回稳定错误码，不回显被拒绝的值。
"""

from __future__ import annotations

from collections.abc import Mapping

from data_intelligence_hub.mcp_runtime.customer.auth import CustomerIdentity
from data_intelligence_hub.mcp_runtime.customer.errors import CustomerToolError

_COOKIE_KEY_EXACT = frozenset(
    {
        "cookie",
        "cookies",
        "creator_cookie",
        "seller_center",
        "seller_center_cookie",
        "sessionid",
        "session_id",
        "csrftoken",
        "csrf_token",
        "ttwid",
        "authorization",
        "proxy_authorization",
        "set_cookie",
        "bearer",
        "access_token",
        "refresh_token",
        "token",
        "auth",
        "credential",
        "credentials",
        "api_key",
        "apikey",
        "secret",
        "client_secret",
        "password",
    }
)
_COOKIE_KEY_FRAGMENTS = (
    "cookie",
    "sessionid",
    "session_id",
    "csrf",
    "authorization",
)
_COOKIE_VALUE_MARKERS = ("sessionid=", "cookie:", "bearer ")
_FORBIDDEN_ARGUMENT_KEYS = frozenset(
    {
        "provider",
        "providers",
        "endpoint_type",
        "endpoint",
        "project_id",
        "workspace_id",
        "pagination",
        "page_token",
        "limit",
        "offset",
        "page",
        "page_size",
        "cursor",
        "tool_id",
        "endpoint_id",
        "provider_id",
        "retry",
        "retries",
        "fallback_chain",
        "degrade_chain",
    }
)


def find_credential_material(value: object, path: str = "arguments") -> str | None:
    """递归查找 Cookie、登录态或凭据字段。命中返回字段路径。"""
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            child_path = f"{path}.{normalized}"
            if normalized in _COOKIE_KEY_EXACT:
                return child_path
            if any(fragment in normalized for fragment in _COOKIE_KEY_FRAGMENTS):
                return child_path
            found = find_credential_material(item, child_path)
            if found is not None:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = find_credential_material(item, f"{path}[{index}]")
            if found is not None:
                return found
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if any(marker in lowered for marker in _COOKIE_VALUE_MARKERS):
            return path
    return None


def find_forbidden_argument(value: object, path: str = "arguments") -> str | None:
    """查找客户不能指定的 provider、端点、分页、重试或租户字段。"""
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            child_path = f"{path}.{normalized}"
            if normalized in _FORBIDDEN_ARGUMENT_KEYS:
                return child_path
            found = find_forbidden_argument(item, child_path)
            if found is not None:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = find_forbidden_argument(item, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def requested_capability_ids(
    tool_name: str,
    arguments: Mapping[str, object],
) -> tuple[str, ...]:
    """只有 `collect` 接受能力标识。"""
    if tool_name != "collect":
        return ()
    value = arguments.get("capability_id")
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    return ()


def assert_capability_allowed(
    identity: CustomerIdentity,
    capability_id: str,
    template_capability_ids: set[str],
) -> None:
    """能力必须同时在密钥白名单与模板白名单内。

    模板白名单为空或 C8 未提供时 fail-closed，不回退到工具目录。
    """
    allowed = set(identity.capability_allowlist) & set(template_capability_ids)
    if capability_id not in allowed:
        raise CustomerToolError("capability_not_allowed")


__all__ = [
    "assert_capability_allowed",
    "find_credential_material",
    "find_forbidden_argument",
    "requested_capability_ids",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_policy.py -q`

Expected: `8 passed`.

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
git add apps/api/src/data_intelligence_hub/mcp_runtime/customer/schemas.py \
        apps/api/src/data_intelligence_hub/mcp_runtime/customer/policy.py \
        apps/api/tests/unit/test_customer_mcp_policy.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(customer-mcp): align customer input policy with contract v1.1"
```

---

### Task 4: 统一授权管线与端口协议

**Files:**
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/ports.py`
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/authorize.py`
- Test: `apps/api/tests/unit/test_customer_mcp_authorize.py`

**Interfaces:**
- Consumes: `auth.customer_identity`、`auth.CustomerIdentity`、`policy.find_credential_material`、`policy.requested_capability_ids`、`policy.assert_capability_allowed`、`errors.CustomerToolError`。
- Produces:
  - 数据类：`CapabilityView`、`CapabilityCatalogView`、`TaskEstimateView`、`TaskView`、`BudgetDecision`、`AuditEvent`、`CustomerPorts`。
  - 协议：`KeyStatusPort`、`QuotaPort`、`CapabilityPort`、`BudgetPort`、`TaskPort`、`CollectPort`、`AuditPort`、`RequestLimiterPort`。
  - 函数：`authorize_before_rate(...)`、`authorized_call_for_identity(...)`、`authorized_call(...)`、`ensure_customer_call(...)`、`customer_authorized_call(...)`。

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/test_customer_mcp_authorize.py`:

```python
"""统一授权管线的顺序与审计。

顺序固定：身份 → 密钥状态 → 绑定 → 工具白名单 → 能力白名单 →
Cookie 隔离 → 日额度 → 速率并发 → 执行。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from data_intelligence_hub.mcp_runtime.customer.auth import CustomerIdentity
from data_intelligence_hub.mcp_runtime.customer.authorize import (
    authorized_call_for_identity,
)
from data_intelligence_hub.mcp_runtime.customer.errors import CustomerToolError
from data_intelligence_hub.mcp_runtime.customer.ports import (
    AuditEvent,
    BudgetDecision,
    CapabilityCatalogView,
    CapabilityView,
    CustomerPorts,
    TaskEstimateView,
    TaskView,
)

IDENTITY = CustomerIdentity(
    key_id=uuid.uuid4(),
    workspace_id=uuid.uuid4(),
    project_id=uuid.uuid4(),
    key_prefix="dih_test",
    label="test",
    tool_allowlist=("collect", "get_task"),
    capability_allowlist=("cap-product",),
    daily_collect_quota=10,
)


class _KeyStatus:
    def __init__(self, log: list[str], active: bool = True, bound: bool = True) -> None:
        self.log = log
        self.active = active
        self.bound = bound

    async def is_active(self, key_id: uuid.UUID) -> bool:
        self.log.append("key_active")
        return self.active

    async def validate_binding(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> bool:
        self.log.append("binding")
        return self.bound


class _Quota:
    def __init__(self, log: list[str], allowed: bool = True) -> None:
        self.log = log
        self.allowed = allowed

    async def consume(self, key_id: uuid.UUID) -> bool:
        self.log.append("quota")
        return self.allowed


class _Capabilities:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    async def template_capability_ids(self) -> tuple[str, ...]:
        self.log.append("template")
        return ("cap-product",)

    async def list_capabilities(self, **kwargs: object) -> CapabilityCatalogView:
        return CapabilityCatalogView(catalog_digest="d", capabilities=())

    async def resolve_capability(self, **kwargs: object) -> CapabilityView | None:
        return None


class _Budget:
    def __init__(self) -> None:
        self.calls = 0

    async def check(self, **kwargs: object) -> BudgetDecision:
        self.calls += 1
        return BudgetDecision(allowed=True, approval_required=False, remaining_usd=Decimal("10"))


class _Tasks:
    async def estimate_task(self, **kwargs: object) -> TaskEstimateView:
        raise AssertionError("not used")

    async def create_task(self, **kwargs: object) -> TaskView:
        raise AssertionError("not used")

    async def get_task(self, **kwargs: object) -> TaskView | None:
        return None

    async def cancel_task(self, **kwargs: object) -> TaskView | None:
        return None

    async def get_delivery_manifest(self, **kwargs: object) -> dict[str, object] | None:
        return None

    async def get_evidence(self, **kwargs: object) -> dict[str, object] | None:
        return None


class _Collect:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, **kwargs: object) -> dict[str, object]:
        self.calls += 1
        return {"run_id": "run-1"}


class _Audit:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> None:
        self.events.append(event)


class _Limiter:
    def __init__(self, log: list[str], error: CustomerToolError | None = None) -> None:
        self.log = log
        self.error = error

    @asynccontextmanager
    async def acquire(self, *, identity: CustomerIdentity, tool_name: str, request_id: str):
        self.log.append("limiter_enter")
        if self.error is not None:
            raise self.error
        try:
            yield
        finally:
            self.log.append("limiter_exit")


@dataclass
class _Ports:
    log: list[str] = field(default_factory=list)
    quota_allowed: bool = True
    limiter_error: CustomerToolError | None = None
    active: bool = True
    bound: bool = True

    def build(self) -> CustomerPorts:
        self.audit = _Audit()
        self.collect = _Collect()
        return CustomerPorts(
            keys=_KeyStatus(self.log, self.active, self.bound),
            quota=_Quota(self.log, self.quota_allowed),
            capabilities=_Capabilities(self.log),
            budget=_Budget(),
            tasks=_Tasks(),
            collect=self.collect,
            audit=self.audit,
            limiter=_Limiter(self.log, self.limiter_error),
        )


async def _run(ports: CustomerPorts, arguments: dict[str, object], tool_name: str = "collect"):
    async with authorized_call_for_identity(
        IDENTITY,
        tool_name=tool_name,
        arguments=arguments,
        ports=ports,
    ) as call:
        return call


@pytest.mark.asyncio
async def test_authorization_order_is_fixed() -> None:
    fake = _Ports()
    call = await _run(
        fake.build(),
        {"capability_id": "cap-product", "params": {}, "idempotency_key": "k"},
    )
    assert call.request_id
    assert fake.log == [
        "key_active",
        "binding",
        "template",
        "quota",
        "limiter_enter",
        "limiter_exit",
    ]
    assert len(fake.audit.events) == 1
    assert fake.audit.events[0].outcome == "success"


@pytest.mark.asyncio
async def test_tool_allowlist_fails_before_capability() -> None:
    fake = _Ports()
    with pytest.raises(CustomerToolError) as exc:
        await _run(
            fake.build(),
            {"capability_id": "cap-product", "params": {}, "idempotency_key": "k"},
            tool_name="create_task",
        )
    assert exc.value.code == "tool_not_allowed"
    assert fake.log == ["key_active", "binding"]


@pytest.mark.asyncio
async def test_capability_allowlist_fails_before_cookie_and_quota() -> None:
    fake = _Ports()
    with pytest.raises(CustomerToolError) as exc:
        await _run(
            fake.build(),
            {"capability_id": "cap-other", "params": {}, "idempotency_key": "k"},
        )
    assert exc.value.code == "capability_not_allowed"
    assert fake.log == ["key_active", "binding", "template"]


@pytest.mark.asyncio
async def test_cookie_fails_before_quota_and_limiter() -> None:
    fake = _Ports()
    with pytest.raises(CustomerToolError) as exc:
        await _run(
            fake.build(),
            {
                "capability_id": "cap-product",
                "params": {"creator_cookie": "x"},
                "idempotency_key": "k",
            },
        )
    assert exc.value.code == "cookie_not_accepted"
    assert fake.log == ["key_active", "binding", "template"]


@pytest.mark.asyncio
async def test_quota_fails_before_limiter() -> None:
    fake = _Ports(quota_allowed=False)
    with pytest.raises(CustomerToolError) as exc:
        await _run(
            fake.build(),
            {"capability_id": "cap-product", "params": {}, "idempotency_key": "k"},
        )
    assert exc.value.code == "quota_exceeded"
    assert fake.log == ["key_active", "binding", "template", "quota"]


@pytest.mark.asyncio
async def test_rate_limit_is_audited_as_denied() -> None:
    fake = _Ports(limiter_error=CustomerToolError("rate_limited"))
    with pytest.raises(CustomerToolError) as exc:
        await _run(
            fake.build(),
            {"capability_id": "cap-product", "params": {}, "idempotency_key": "k"},
        )
    assert exc.value.code == "rate_limited"
    assert fake.audit.events[-1].outcome == "denied"
    assert fake.audit.events[-1].error_code == "rate_limited"


@pytest.mark.asyncio
async def test_unexpected_tool_error_is_audited_as_failed() -> None:
    fake = _Ports()
    with pytest.raises(RuntimeError):
        async with authorized_call_for_identity(
            IDENTITY,
            tool_name="get_task",
            arguments={"task_id": str(uuid.uuid4())},
            ports=fake.build(),
        ):
            raise RuntimeError("boom")
    assert fake.audit.events[-1].outcome == "failed"
    assert fake.audit.events[-1].error_code == "internal_error"


@pytest.mark.asyncio
async def test_revoked_key_fails_before_tool_allowlist() -> None:
    fake = _Ports(active=False)
    with pytest.raises(CustomerToolError) as exc:
        await _run(
            fake.build(),
            {"capability_id": "cap-product", "params": {}, "idempotency_key": "k"},
        )
    assert exc.value.code == "project_key_revoked"
    assert fake.log == ["key_active"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_authorize.py -q`

Expected: `FAILED` with `ModuleNotFoundError: No module named 'data_intelligence_hub.mcp_runtime.customer.ports'`.

- [ ] **Step 3: Create the port protocols**

`mcp_runtime/customer/ports.py`:

```python
"""客户 MCP 的端口协议。

工具只依赖这些协议；C2/C3/C4/C5/C6/C7/C8/C9/C10 的薄生产适配器在 Task 7 追加到本模块。
测试用内存假实现，不触碰数据库与网络。
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from data_intelligence_hub.mcp_runtime.customer.auth import CustomerIdentity
from data_intelligence_hub.mcp_runtime.customer.schemas import (
    BudgetInput,
    CreateTaskInput,
    EstimateTaskInput,
)


@dataclass(frozen=True, slots=True)
class CapabilityView:
    capability_id: str
    display_name: str
    data_domain: str
    markets: tuple[str, ...]
    why_this: str
    cost_estimate_usd: Decimal
    executable: bool
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CapabilityCatalogView:
    catalog_digest: str
    capabilities: tuple[CapabilityView, ...]


@dataclass(frozen=True, slots=True)
class TaskEstimateView:
    estimate_id: str
    max_cost_usd: Decimal
    currency: str
    price_book_version: str
    expires_at: datetime
    breakdown: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class TaskView:
    task_id: uuid.UUID
    status: str
    package_type: str
    markets: tuple[Mapping[str, Any], ...] = ()
    plan_version_id: uuid.UUID | None = None
    run_ids: tuple[uuid.UUID, ...] = ()
    quote_id: str | None = None
    delivery_manifest_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    cancelled_runs: tuple[uuid.UUID, ...] = ()
    preserved_artifacts: tuple[str, ...] = ()
    cancelled_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    allowed: bool
    approval_required: bool
    remaining_usd: Decimal | None


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_type: str
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    key_id: uuid.UUID
    request_id: str
    tool_name: str
    outcome: str
    error_code: str | None
    capability_id: str | None
    duration_ms: int


@runtime_checkable
class KeyStatusPort(Protocol):
    async def is_active(self, key_id: uuid.UUID) -> bool: ...

    async def validate_binding(
        self, workspace_id: uuid.UUID, project_id: uuid.UUID
    ) -> bool: ...


@runtime_checkable
class QuotaPort(Protocol):
    async def consume(self, key_id: uuid.UUID) -> bool: ...


@runtime_checkable
class CapabilityPort(Protocol):
    async def template_capability_ids(self) -> tuple[str, ...]:
        """只读投影 C8 `template_capability_ids(template_id)`；空集合 fail-closed。

        `TaskTemplate.capability_allowlist` 是 C8 dataclass 字段，C13 不直接读属性。
        """
        ...

    async def list_capabilities(
        self,
        *,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        capability_ids: tuple[str, ...],
        query: str | None,
        markets: tuple[str, ...],
        data_domains: tuple[str, ...],
        limit: int,
    ) -> CapabilityCatalogView: ...

    async def resolve_capability(
        self,
        *,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        capability_id: str,
    ) -> CapabilityView | None: ...


@runtime_checkable
class BudgetPort(Protocol):
    async def check(
        self,
        *,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        estimated_cost_usd: Decimal,
    ) -> BudgetDecision: ...


@runtime_checkable
class TaskPort(Protocol):
    async def estimate_task(
        self, *, identity: CustomerIdentity, request: EstimateTaskInput
    ) -> TaskEstimateView: ...

    async def create_task(
        self,
        *,
        identity: CustomerIdentity,
        request: CreateTaskInput,
        quote_id: str,
        budget: BudgetDecision,
    ) -> TaskView: ...

    async def get_task(
        self, *, identity: CustomerIdentity, task_id: uuid.UUID
    ) -> TaskView | None: ...

    async def cancel_task(
        self,
        *,
        identity: CustomerIdentity,
        task_id: uuid.UUID,
        idempotency_key: str,
        reason_code: str,
    ) -> TaskView | None: ...

    async def get_delivery_manifest(
        self,
        *,
        identity: CustomerIdentity,
        task_id: uuid.UUID,
        manifest_version: int | None,
    ) -> Mapping[str, Any] | None: ...

    async def get_evidence(
        self,
        *,
        identity: CustomerIdentity,
        claim_id: str,
    ) -> Mapping[str, Any] | None: ...


@runtime_checkable
class CollectPort(Protocol):
    async def run(
        self,
        *,
        identity: CustomerIdentity,
        capability: CapabilityView,
        params: Mapping[str, Any],
        idempotency_key: str,
        budget: BudgetInput,
        request_id: str,
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class AuditPort(Protocol):
    async def record(self, event: AuditEvent) -> None: ...


@runtime_checkable
class RequestLimiterPort(Protocol):
    def acquire(
        self,
        *,
        identity: CustomerIdentity,
        tool_name: str,
        request_id: str,
    ) -> AbstractAsyncContextManager[None]: ...


@dataclass(frozen=True, slots=True)
class CustomerPorts:
    keys: KeyStatusPort
    quota: QuotaPort
    capabilities: CapabilityPort
    budget: BudgetPort
    tasks: TaskPort
    collect: CollectPort
    audit: AuditPort
    limiter: RequestLimiterPort


__all__ = [
    "AuditEvent",
    "AuditPort",
    "BudgetDecision",
    "BudgetPort",
    "CapabilityCatalogView",
    "CapabilityPort",
    "CapabilityView",
    "CollectPort",
    "CustomerPorts",
    "KeyStatusPort",
    "QuotaPort",
    "RequestLimiterPort",
    "TaskEstimateView",
    "TaskPort",
    "TaskView",
]
```

- [ ] **Step 4: Create the authorization pipeline**

`mcp_runtime/customer/authorize.py`:

```python
"""客户 MCP 的统一授权管线。

所有工具都必须经过 `ensure_customer_call`。传输层中间件也调用同一套函数，
因此 HTTP 与进程内调用不会出现两套判定。

顺序固定，不得重排：
身份 → 密钥状态 → 工作区/项目绑定 → 工具白名单 → 能力白名单 →
Cookie 隔离 → 日额度 → 速率与并发 → 执行 → 审计。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import perf_counter

import structlog
from mcp.server.mcpserver import Context

from data_intelligence_hub.mcp_runtime.customer.auth import (
    CustomerIdentity,
    customer_identity,
)
from data_intelligence_hub.mcp_runtime.customer.errors import CustomerToolError
from data_intelligence_hub.mcp_runtime.customer.policy import (
    assert_capability_allowed,
    find_credential_material,
    find_forbidden_argument,
    requested_capability_ids,
)
from data_intelligence_hub.mcp_runtime.customer.ports import (
    AuditEvent,
    CustomerPorts,
)
from data_intelligence_hub.mcp_runtime.customer.tool_names import CUSTOMER_TOOL_NAMES

logger = structlog.get_logger(__name__)

AUTHORIZED_STATE_KEY = "mcp_customer_authorized_call"


@dataclass(frozen=True, slots=True)
class PendingCall:
    identity: CustomerIdentity
    tool_name: str
    capability_ids: tuple[str, ...]
    template_capability_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AuthorizedCall:
    identity: CustomerIdentity
    request_id: str
    tool_name: str
    capability_id: str | None
    ports: CustomerPorts
    template_capability_ids: tuple[str, ...] = ()


def _scope_from_context(context: Context | None) -> dict[str, object] | None:
    if context is None:
        return None
    try:
        request = context.request_context.request
    except (AttributeError, ValueError):
        return None
    scope = getattr(request, "scope", None)
    return scope if isinstance(scope, dict) else None


def _request_id_for_context(context: Context | None) -> str:
    if context is not None:
        try:
            return str(context.request_id)
        except (AttributeError, ValueError):
            pass
    return uuid.uuid4().hex


def _request_id_for_scope(scope: dict[str, object] | None) -> str:
    if scope is not None:
        raw_headers = scope.get("headers")
        if raw_headers:
            headers = {
                key.decode("latin-1").lower(): value.decode("latin-1")
                for key, value in dict(raw_headers).items()
            }
            value = headers.get("x-request-id")
            if isinstance(value, str) and 0 < len(value) <= 64:
                return value
    return uuid.uuid4().hex


async def _authorize_before_rate(
    identity: CustomerIdentity | None,
    *,
    tool_name: str,
    arguments: Mapping[str, object],
    ports: CustomerPorts,
) -> PendingCall:
    if identity is None:
        raise CustomerToolError("authentication_required")
    if not await ports.keys.is_active(identity.key_id):
        raise CustomerToolError("project_key_revoked")
    if not await ports.keys.validate_binding(identity.workspace_id, identity.project_id):
        raise CustomerToolError("permission_denied")
    if tool_name not in CUSTOMER_TOOL_NAMES or tool_name not in identity.tool_allowlist:
        raise CustomerToolError("tool_not_allowed")
    if find_forbidden_argument(arguments) is not None:
        raise CustomerToolError("invalid_request")
    capability_ids = requested_capability_ids(tool_name, arguments)
    template_capability_ids: tuple[str, ...] = ()
    if tool_name in ("collect", "discover_capabilities"):
        # C8 `template_capability_ids(template_id)` 是模板侧唯一白名单读取入口；
        # `TaskTemplate.capability_allowlist` 只是其 dataclass 字段。
        # 空集合为 fail-closed：collect 在下一步返回 capability_not_allowed，
        # discover 只返回空清单；不得回退到工具目录。
        template_capability_ids = tuple(
            str(item) for item in await ports.capabilities.template_capability_ids()
        )
    for capability_id in capability_ids:
        assert_capability_allowed(
            identity,
            capability_id,
            set(template_capability_ids),
        )
    if find_credential_material(arguments) is not None:
        raise CustomerToolError("cookie_not_accepted")
    if not await ports.quota.consume(identity.key_id):
        raise CustomerToolError("quota_exceeded")
    return PendingCall(
        identity=identity,
        tool_name=tool_name,
        capability_ids=capability_ids,
        template_capability_ids=template_capability_ids,
    )


def _first_capability_id(tool_name: str, arguments: Mapping[str, object]) -> str | None:
    ids = requested_capability_ids(tool_name, arguments)
    return ids[0] if ids else None


async def _record_audit(
    ports: CustomerPorts,
    identity: CustomerIdentity | None,
    *,
    request_id: str,
    tool_name: str,
    outcome: str,
    error_code: str | None,
    capability_id: str | None,
    started: float,
) -> None:
    if identity is None:
        return
    event = AuditEvent(
        event_type="mcp.tool_call",
        workspace_id=identity.workspace_id,
        project_id=identity.project_id,
        key_id=identity.key_id,
        request_id=request_id,
        tool_name=tool_name,
        outcome=outcome,
        error_code=error_code,
        capability_id=capability_id,
        duration_ms=int((perf_counter() - started) * 1000),
    )
    try:
        await ports.audit.record(event)
    except Exception as exc:
        logger.warning(
            "customer_mcp_audit_failed",
            error_type=type(exc).__name__,
            tool_name=tool_name,
            outcome=outcome,
        )


@asynccontextmanager
async def authorized_call_for_identity(
    identity: CustomerIdentity | None,
    *,
    tool_name: str,
    arguments: Mapping[str, object],
    ports: CustomerPorts,
    scope: dict[str, object] | None = None,
    request_id: str | None = None,
) -> AsyncIterator[AuthorizedCall]:
    """执行完整授权管线，并在调用期间持有数据库租约。"""
    started = perf_counter()
    resolved_request_id = request_id or _request_id_for_scope(scope)
    capability_id = _first_capability_id(tool_name, arguments)
    try:
        pending = await _authorize_before_rate(
            identity,
            tool_name=tool_name,
            arguments=arguments,
            ports=ports,
        )
    except CustomerToolError as exc:
        await _record_audit(
            ports,
            identity,
            request_id=resolved_request_id,
            tool_name=tool_name,
            outcome="denied",
            error_code=exc.code,
            capability_id=capability_id,
            started=started,
        )
        raise

    call = AuthorizedCall(
        identity=pending.identity,
        request_id=resolved_request_id,
        tool_name=tool_name,
        capability_id=capability_id,
        ports=ports,
        template_capability_ids=pending.template_capability_ids,
    )
    if scope is not None:
        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state[AUTHORIZED_STATE_KEY] = call

    outcome = "failed"
    error_code: str | None = "internal_error"
    try:
        async with ports.limiter.acquire(
            identity=pending.identity,
            tool_name=tool_name,
            request_id=resolved_request_id,
        ):
            try:
                yield call
            except CustomerToolError as exc:
                outcome, error_code = "denied", exc.code
                raise
            except Exception:
                outcome, error_code = "failed", "internal_error"
                raise
            else:
                outcome, error_code = "success", None
    except CustomerToolError as exc:
        if error_code == "internal_error":
            outcome, error_code = "denied", exc.code
        raise
    finally:
        if scope is not None:
            state = scope.get("state")
            if isinstance(state, dict) and state.get(AUTHORIZED_STATE_KEY) is call:
                state.pop(AUTHORIZED_STATE_KEY, None)
        await _record_audit(
            ports,
            pending.identity,
            request_id=resolved_request_id,
            tool_name=tool_name,
            outcome=outcome,
            error_code=error_code,
            capability_id=capability_id,
            started=started,
        )


def customer_authorized_call(context: Context) -> AuthorizedCall | None:
    scope = _scope_from_context(context)
    if scope is None:
        return None
    state = scope.get("state")
    if not isinstance(state, dict):
        return None
    call = state.get(AUTHORIZED_STATE_KEY)
    return call if isinstance(call, AuthorizedCall) else None


@asynccontextmanager
async def authorized_call(
    context: Context,
    *,
    tool_name: str,
    arguments: Mapping[str, object],
    ports: CustomerPorts | None = None,
    scope: dict[str, object] | None = None,
) -> AsyncIterator[AuthorizedCall]:
    from data_intelligence_hub.mcp_runtime.customer.ports import get_ports

    resolved_ports = ports or get_ports()
    async with authorized_call_for_identity(
        customer_identity(context),
        tool_name=tool_name,
        arguments=arguments,
        ports=resolved_ports,
        scope=scope or _scope_from_context(context),
        request_id=_request_id_for_context(context),
    ) as call:
        yield call


@asynccontextmanager
async def ensure_customer_call(
    context: Context,
    *,
    tool_name: str,
    arguments: Mapping[str, object],
    ports: CustomerPorts | None = None,
) -> AsyncIterator[AuthorizedCall]:
    """复用传输层已经完成的授权；进程内调用则现场执行管线。"""
    existing = customer_authorized_call(context)
    if existing is not None and existing.tool_name == tool_name:
        yield existing
        return
    async with authorized_call(
        context,
        tool_name=tool_name,
        arguments=arguments,
        ports=ports,
    ) as call:
        yield call


__all__ = [
    "AUTHORIZED_STATE_KEY",
    "AuthorizedCall",
    "PendingCall",
    "authorized_call",
    "authorized_call_for_identity",
    "customer_authorized_call",
    "ensure_customer_call",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_authorize.py -q`

Expected: `8 passed`.

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
git add apps/api/src/data_intelligence_hub/mcp_runtime/customer/ports.py \
        apps/api/src/data_intelligence_hub/mcp_runtime/customer/authorize.py \
        apps/api/tests/unit/test_customer_mcp_authorize.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(customer-mcp): add unified authorization pipeline and ports"
```

---

### Task 5: 基于审计事件的数据库速率与并发

**Files:**
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/rate_limit.py`
- Test: `apps/api/tests/unit/test_customer_mcp_rate_limit.py`

**Interfaces:**
- Consumes: C2 `models.audit_event.AuditEvent`、`services.audit_log.append_audit_event`；`auth.CustomerIdentity`；`errors.CustomerToolError`。
- Produces: `STALE_AFTER_SECONDS = 300`；`LeasePolicy(per_minute, concurrent, stale_after_seconds=STALE_AFTER_SECONDS)`；`AuditRequestLimiter(session_factory, policy, now=None)`；其 `acquire(identity, tool_name, request_id)` 是异步上下文管理器。

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/test_customer_mcp_rate_limit.py`:

```python
"""基于审计事件的速率与并发。

不新建租约表。每次调用写 `mcp.tool_call.started`，结束时写
`mcp.tool_call.finished` 或 `mcp.tool_call.denied`。计数全部落库。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.mcp_runtime.customer.auth import CustomerIdentity
from data_intelligence_hub.mcp_runtime.customer.errors import CustomerToolError
from data_intelligence_hub.mcp_runtime.customer.rate_limit import (
    STALE_AFTER_SECONDS,
    AuditRequestLimiter,
    LeasePolicy,
)
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace

IDENTITY = CustomerIdentity(
    key_id=uuid.uuid4(),
    workspace_id=uuid.uuid4(),
    project_id=uuid.uuid4(),
    key_prefix="dih_test",
    label="test",
    tool_allowlist=("collect",),
    capability_allowlist=("cap-1",),
    daily_collect_quota=100,
)


@pytest_asyncio.fixture()
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        owner = User(email="rate@example.com", password_hash="x", name="Rate")
        session.add(owner)
        await session.flush()
        session.add(
            Workspace(
                id=IDENTITY.workspace_id,
                name="Rate WS",
                slug="rate-ws",
                owner_id=owner.id,
            )
        )
        await session.commit()
    yield factory
    await engine.dispose()


async def _start(
    limiter: AuditRequestLimiter,
    request_id: str,
    *,
    tool_name: str = "get_task",
) -> None:
    async with limiter.acquire(
        identity=IDENTITY,
        tool_name=tool_name,
        request_id=request_id,
    ):
        pass


@pytest.mark.asyncio
async def test_rate_limit_rejects_second_call_in_window(session_factory) -> None:
    limiter = AuditRequestLimiter(
        session_factory,
        LeasePolicy(per_minute=1, concurrent=10, stale_after_seconds=300),
    )
    await _start(limiter, "r1")

    with pytest.raises(CustomerToolError) as exc:
        await _start(limiter, "r2")
    assert exc.value.code == "rate_limited"


@pytest.mark.asyncio
async def test_concurrency_limit_blocks_unfinished_start(session_factory) -> None:
    limiter = AuditRequestLimiter(
        session_factory,
        LeasePolicy(per_minute=10, concurrent=1, stale_after_seconds=300),
    )
    await _start(limiter, "r1")

    with pytest.raises(CustomerToolError) as exc:
        await _start(limiter, "r2")
    assert exc.value.code == "rate_limited"


@pytest.mark.asyncio
async def test_finished_event_frees_concurrency_slot(session_factory) -> None:
    from data_intelligence_hub.services.audit_log import append_audit_event

    limiter = AuditRequestLimiter(
        session_factory,
        LeasePolicy(per_minute=10, concurrent=1, stale_after_seconds=300),
    )
    await _start(limiter, "r1")
    async with session_factory() as session:
        await append_audit_event(
            session,
            workspace_id=IDENTITY.workspace_id,
            project_id=IDENTITY.project_id,
            actor_type="project_key",
            action="mcp.tool_call.finished",
            resource_type="mcp_tool",
            resource_id="r1",
            request_id="r1",
            result="success",
            details={"tool_name": "get_task"},
        )
        await session.commit()

    await _start(limiter, "r2")


@pytest.mark.asyncio
async def test_stale_start_does_not_block_forever(session_factory) -> None:
    base = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
    clock = [base]
    limiter = AuditRequestLimiter(
        session_factory,
        LeasePolicy(per_minute=10, concurrent=1, stale_after_seconds=30),
        now=lambda: clock[0],
    )
    await _start(limiter, "r1")
    clock[0] = base + timedelta(seconds=31)
    await _start(limiter, "r2")


@pytest.mark.asyncio
async def test_different_workspaces_do_not_share_limits(session_factory) -> None:
    other = CustomerIdentity(
        key_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        key_prefix="dih_other",
        label="other",
        tool_allowlist=("get_task",),
        capability_allowlist=(),
        daily_collect_quota=10,
    )
    limiter = AuditRequestLimiter(
        session_factory,
        LeasePolicy(per_minute=1, concurrent=1, stale_after_seconds=300),
    )
    await _start(limiter, "a")
    async with limiter.acquire(
        identity=other,
        tool_name="get_task",
        request_id="b",
    ):
        pass


def test_default_policy_uses_internal_stale_constant() -> None:
    policy = LeasePolicy(per_minute=10, concurrent=2)
    assert STALE_AFTER_SECONDS == 300
    assert policy.stale_after_seconds == STALE_AFTER_SECONDS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_rate_limit.py -q`

Expected: `FAILED` with `ModuleNotFoundError: No module named 'data_intelligence_hub.mcp_runtime.customer.rate_limit'`.

- [ ] **Step 3: Create the audit-backed limiter**

`mcp_runtime/customer/rate_limit.py`:

```python
"""基于 `audit_events` 的速率与并发。

C1 没有登记客户租约表，因此不新建表。一次允许的调用写
`mcp.tool_call.started`；结束由审计管线写 `mcp.tool_call.finished`
或 `mcp.tool_call.denied`。并发只统计没有终态事件的 started 行。

计数前锁工作区行，保证同一工作区的“计数 + 写入”原子。
审计写入失败向外抛出；调用方必须 fail-closed。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from data_intelligence_hub.mcp_runtime.customer.auth import CustomerIdentity
from data_intelligence_hub.mcp_runtime.customer.errors import CustomerToolError
from data_intelligence_hub.models.audit_event import AuditEvent
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.audit_log import append_audit_event

STARTED_ACTION = "mcp.tool_call.started"
FINISHED_ACTION = "mcp.tool_call.finished"
DENIED_ACTION = "mcp.tool_call.denied"
TERMINAL_ACTIONS = (FINISHED_ACTION, DENIED_ACTION)
# 内部常量，不是产品阈值，也不暴露为配置或环境变量。
STALE_AFTER_SECONDS = 300


@dataclass(frozen=True, slots=True)
class LeasePolicy:
    """并发/速率策略值对象。它不是数据库租约表，也不持久化。"""

    per_minute: int
    concurrent: int
    stale_after_seconds: int = STALE_AFTER_SECONDS


class AuditRequestLimiter:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        policy: LeasePolicy,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._policy = policy
        self._now = now or (lambda: datetime.now(UTC))

    @asynccontextmanager
    async def acquire(
        self,
        *,
        identity: CustomerIdentity,
        tool_name: str,
        request_id: str,
    ) -> AsyncIterator[None]:
        await self._start(identity=identity, tool_name=tool_name, request_id=request_id)
        yield

    async def _start(
        self,
        *,
        identity: CustomerIdentity,
        tool_name: str,
        request_id: str,
    ) -> None:
        now = self._now()
        window_start = now - timedelta(minutes=1)
        stale_start = now - timedelta(seconds=self._policy.stale_after_seconds)
        async with self._session_factory() as session:
            async with session.begin():
                # 同一工作区串行计数与追加，避免并发请求同时通过。
                await session.execute(
                    select(Workspace.id)
                    .where(Workspace.id == identity.workspace_id)
                    .with_for_update()
                )
                rate_count = await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.workspace_id == identity.workspace_id,
                        AuditEvent.project_id == identity.project_id,
                        AuditEvent.action == STARTED_ACTION,
                        AuditEvent.occurred_at > window_start,
                    )
                )
                if int(rate_count or 0) >= self._policy.per_minute:
                    raise CustomerToolError("rate_limited")
                terminal = select(AuditEvent.resource_id).where(
                    AuditEvent.workspace_id == identity.workspace_id,
                    AuditEvent.project_id == identity.project_id,
                    AuditEvent.action.in_(TERMINAL_ACTIONS),
                    AuditEvent.resource_id.is_not(None),
                )
                active_count = await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.workspace_id == identity.workspace_id,
                        AuditEvent.project_id == identity.project_id,
                        AuditEvent.action == STARTED_ACTION,
                        AuditEvent.occurred_at > stale_start,
                        AuditEvent.resource_id.is_not(None),
                        AuditEvent.resource_id.not_in(terminal),
                    )
                )
                if int(active_count or 0) >= self._policy.concurrent:
                    raise CustomerToolError("rate_limited")
                await append_audit_event(
                    session,
                    workspace_id=identity.workspace_id,
                    project_id=identity.project_id,
                    actor_type="project_key",
                    action=STARTED_ACTION,
                    resource_type="mcp_tool",
                    resource_id=request_id,
                    request_id=request_id,
                    result="success",
                    details={"tool_name": tool_name},
                    occurred_at=now,
                )


__all__ = [
    "AuditRequestLimiter",
    "DENIED_ACTION",
    "FINISHED_ACTION",
    "LeasePolicy",
    "STALE_AFTER_SECONDS",
    "STARTED_ACTION",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_rate_limit.py -q`

Expected: `6 passed`.

- [ ] **Step 5: Verify no migration and no new table**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
git status --short apps/api/alembic/versions
rg -n "mcp_customer_request_leases" apps/api/src apps/api/alembic docs/design
```

Expected:

- `git status --short apps/api/alembic/versions` 无输出。
- `rg` 无命中。若出现命中，说明违反“不新增表”，停止并回退。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
git add apps/api/src/data_intelligence_hub/mcp_runtime/customer/rate_limit.py \
        apps/api/tests/unit/test_customer_mcp_rate_limit.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(customer-mcp): add db-backed rate limiting on audit events"
```

---

### Task 6: 恰好八个客户工具与 tools/list 过滤

**Files:**
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/server.py`
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/middleware.py`
- Test: `apps/api/tests/unit/test_customer_mcp_tools.py`

**Interfaces:**
- Consumes: `ensure_customer_call`、`AuthorizedCall`、`CustomerPorts`、`BudgetInput`、`EstimateTaskInput`、`CreateTaskInput`、`validate_window`、`CustomerToolError`、`CUSTOMER_TOOL_NAMES`。
- Produces: `customer_mcp_server: MCPServer`；八个工具函数；`CustomerToolListMiddleware`；`CustomerAuthorizationMiddleware`；`filter_tools_result(result, allowed_names)`。

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/test_customer_mcp_tools.py`:

```python
"""八个客户工具与 tools/list 过滤。

工具名、输入字段和输出字段以 C1 `customer_mcp.schema.json` 为准。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from mcp.client import Client

from data_intelligence_hub.mcp_runtime.customer import ports as ports_module
from data_intelligence_hub.mcp_runtime.customer import authorize as authorize_module
from data_intelligence_hub.mcp_runtime.customer.auth import CustomerIdentity
from data_intelligence_hub.mcp_runtime.customer.middleware import filter_tools_result
from data_intelligence_hub.mcp_runtime.customer.ports import (
    AuditEvent,
    BudgetDecision,
    CapabilityCatalogView,
    CapabilityView,
    CustomerPorts,
    TaskEstimateView,
    TaskView,
)
from data_intelligence_hub.mcp_runtime.customer.server import customer_mcp_server
from data_intelligence_hub.mcp_runtime.customer.tool_names import CUSTOMER_TOOL_NAMES

IDENTITY = CustomerIdentity(
    key_id=uuid.uuid4(),
    workspace_id=uuid.uuid4(),
    project_id=uuid.uuid4(),
    key_prefix="dih_test",
    label="test",
    tool_allowlist=CUSTOMER_TOOL_NAMES,
    capability_allowlist=("cap-product",),
    daily_collect_quota=100,
)
TASK_ID = uuid.uuid4()
RUN_ID = uuid.uuid4()


class _KeyStatus:
    async def is_active(self, key_id: uuid.UUID) -> bool:
        return True

    async def validate_binding(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> bool:
        return True


class _Quota:
    async def consume(self, key_id: uuid.UUID) -> bool:
        return True


class _Capabilities:
    def __init__(self) -> None:
        self.list_calls: list[dict[str, object]] = []
        self.template_calls = 0
        self.template_ids: tuple[str, ...] = ("cap-product",)

    async def template_capability_ids(self) -> tuple[str, ...]:
        self.template_calls += 1
        return self.template_ids

    async def list_capabilities(self, **kwargs: object) -> CapabilityCatalogView:
        self.list_calls.append(dict(kwargs))
        allowed = set(kwargs["capability_ids"])
        capabilities = (_capability(),) if "cap-product" in allowed else ()
        return CapabilityCatalogView(
            catalog_digest="digest-1",
            capabilities=capabilities,
        )

    async def resolve_capability(self, **kwargs: object) -> CapabilityView | None:
        if kwargs["capability_id"] == "cap-product":
            return _capability()
        return None


class _Budget:
    def __init__(self) -> None:
        self.allowed = True
        self.calls: list[dict[str, object]] = []

    async def check(self, **kwargs: object) -> BudgetDecision:
        self.calls.append(dict(kwargs))
        return BudgetDecision(
            allowed=self.allowed,
            approval_required=not self.allowed,
            remaining_usd=Decimal("0") if not self.allowed else Decimal("10"),
        )


class _Tasks:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, object]] = []
        self.cancel_calls: list[dict[str, object]] = []

    async def estimate_task(self, **kwargs: object) -> TaskEstimateView:
        return TaskEstimateView(
            estimate_id="est-1",
            max_cost_usd=Decimal("20"),
            currency="USD",
            price_book_version="price-book.v1",
            expires_at=datetime(2026, 10, 23, tzinfo=UTC),
            breakdown=({"label": "商品", "amount_usd": Decimal("7.50")},),
        )

    async def create_task(self, **kwargs: object) -> TaskView:
        self.create_calls.append(dict(kwargs))
        budget = kwargs["budget"]
        request = kwargs["request"]
        markets = tuple(
            {
                "market_code": code,
                "market_role": "primary" if code == request.primary_market else "compare",
            }
            for code in (request.primary_market, *request.compare_markets)
        )
        return TaskView(
            task_id=TASK_ID,
            status="queued" if budget.allowed else "pending_approval",
            package_type=request.package_type,
            markets=markets,
            plan_version_id=uuid.uuid4(),
            run_ids=(RUN_ID,) if budget.allowed else (),
            quote_id=kwargs["quote_id"],
            created_at=datetime(2026, 10, 22, tzinfo=UTC),
        )

    async def get_task(self, **kwargs: object) -> TaskView | None:
        if kwargs["task_id"] != TASK_ID:
            return None
        return TaskView(
            task_id=TASK_ID,
            status="running",
            package_type="quick",
            markets=(
                {"market_code": "US", "market_role": "primary"},
                {"market_code": "GB", "market_role": "compare"},
            ),
            delivery_manifest_id=None,
            updated_at=datetime(2026, 10, 22, tzinfo=UTC),
        )

    async def cancel_task(self, **kwargs: object) -> TaskView | None:
        self.cancel_calls.append(dict(kwargs))
        if kwargs["task_id"] != TASK_ID:
            return None
        return TaskView(
            task_id=TASK_ID,
            status="cancelled",
            package_type="quick",
            cancelled_runs=(RUN_ID,),
            preserved_artifacts=("artifact-1",),
            cancelled_at=datetime(2026, 10, 22, tzinfo=UTC),
        )

    async def get_delivery_manifest(self, **kwargs: object) -> dict[str, object] | None:
        if kwargs["task_id"] != TASK_ID:
            return None
        return {
            "manifest_id": "manifest-1",
            "task_id": str(TASK_ID),
            "report_artifact_id": "artifact-1",
            "manifest_sha256": "a" * 64,
            "files": [],
            "access_scope": ["project"],
            "retention_class": "formal_report_24m",
            "published_at": "2026-10-22T00:00:00Z",
        }

    async def get_evidence(self, **kwargs: object) -> dict[str, object] | None:
        if kwargs["claim_id"] != "claim-1":
            return None
        return {
            "claim_id": "claim-1",
            "claim_status": "directional",
            "evidence_grade": "L3_live_single",
            "items": [],
        }


class _Collect:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def run(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(dict(kwargs))
        return {
            "run_id": str(RUN_ID),
            "task_id": str(TASK_ID),
            "status": "queued",
            "accepted_at": "2026-10-22T00:00:00Z",
        }


class _Audit:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> None:
        self.events.append(event)


class _Limiter:
    @asynccontextmanager
    async def acquire(self, **kwargs: object):
        yield


@dataclass
class _Ports:
    capabilities: _Capabilities = field(default_factory=_Capabilities)
    budget: _Budget | None = None
    tasks: _Tasks = field(default_factory=_Tasks)
    collect: _Collect = field(default_factory=_Collect)
    audit: _Audit = field(default_factory=_Audit)

    def build(self) -> CustomerPorts:
        self.budget = _Budget()
        return CustomerPorts(
            keys=_KeyStatus(),
            quota=_Quota(),
            capabilities=self.capabilities,
            budget=self.budget,
            tasks=self.tasks,
            collect=self.collect,
            audit=self.audit,
            limiter=_Limiter(),
        )


def _capability() -> CapabilityView:
    return CapabilityView(
        capability_id="cap-product",
        display_name="商品搜索",
        data_domain="product",
        markets=("US", "GB"),
        why_this="覆盖公开商品与价格",
        cost_estimate_usd=Decimal("1.20"),
        executable=True,
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object"},
    )


@pytest.fixture()
def ports(monkeypatch: pytest.MonkeyPatch) -> _Ports:
    fake = _Ports()
    resolved = fake.build()
    monkeypatch.setattr(authorize_module, "customer_identity", lambda context: IDENTITY)
    monkeypatch.setattr(ports_module, "get_ports", lambda: resolved)
    return fake


@pytest.mark.asyncio
async def test_customer_server_registers_exactly_eight_tools() -> None:
    tools = await customer_mcp_server.list_tools()
    assert tuple(tool.name for tool in tools) == CUSTOMER_TOOL_NAMES


@pytest.mark.asyncio
async def test_customer_tools_do_not_expose_internal_parameters() -> None:
    tools = await customer_mcp_server.list_tools()
    forbidden = {"project_id", "workspace_id", "provider", "endpoint_type", "cookie"}
    for tool in tools:
        properties = set((tool.input_schema or {}).get("properties", {}))
        assert properties.isdisjoint(forbidden), tool.name


@pytest.mark.asyncio
async def test_discover_capabilities_uses_key_allowlist(ports: _Ports) -> None:
    async with Client(customer_mcp_server) as client:
        result = await client.call_tool(
            "discover_capabilities",
            {"query": "商品", "markets": ["US"], "limit": 10},
        )

    assert result.is_error is False
    assert result.structured_content["catalog_digest"] == "digest-1"
    assert result.structured_content["items"][0]["capability_id"] == "cap-product"
    call = ports.capabilities.list_calls[0]
    assert call["capability_ids"] == IDENTITY.capability_allowlist


@pytest.mark.asyncio
async def test_discover_capabilities_returns_only_template_key_intersection(
    ports: _Ports,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """密钥白名单里但模板外的能力不能出现在 discover 结果或下游查询中。"""
    monkeypatch.setattr(
        authorize_module,
        "customer_identity",
        lambda context: replace(
            IDENTITY,
            capability_allowlist=("cap-product", "cap-outside-template"),
        ),
    )
    async with Client(customer_mcp_server) as client:
        result = await client.call_tool(
            "discover_capabilities",
            {"query": "商品", "markets": ["US"], "limit": 10},
        )

    assert result.is_error is False
    assert [item["capability_id"] for item in result.structured_content["items"]] == [
        "cap-product"
    ]
    call = ports.capabilities.list_calls[0]
    assert call["capability_ids"] == ("cap-product",)
    assert ports.capabilities.template_calls == 1


@pytest.mark.asyncio
async def test_discover_capabilities_empty_template_returns_empty_without_fallback(
    ports: _Ports,
) -> None:
    """C8 模板白名单为空时不得回退为全部非 Cookie 工具。"""
    ports.capabilities.template_ids = ()
    async with Client(customer_mcp_server) as client:
        result = await client.call_tool(
            "discover_capabilities",
            {"query": "商品", "markets": ["US"], "limit": 10},
        )

    assert result.is_error is False
    assert result.structured_content["items"] == []
    call = ports.capabilities.list_calls[0]
    assert call["capability_ids"] == ()


@pytest.mark.asyncio
async def test_estimate_task_returns_c1_fields(ports: _Ports) -> None:
    async with Client(customer_mcp_server) as client:
        result = await client.call_tool(
            "estimate_task",
            {
                "template_id": "maternal-new-entry",
                "package_type": "quick",
                "primary_market": "US",
                "compare_markets": ["GB"],
                "category_id": "feeding",
                "window_start": "2026-09-01",
                "window_end": "2026-09-30",
                "budget": {"max_cost_usd": 20, "max_pages": 10, "max_records": 100},
            },
        )

    assert result.is_error is False
    assert result.structured_content["estimate_id"] == "est-1"
    assert result.structured_content["price_book_version"] == "price-book.v1"


@pytest.mark.asyncio
async def test_create_task_returns_pending_approval_when_budget_fails(
    ports: _Ports,
) -> None:
    assert ports.budget is not None
    ports.budget.allowed = False
    async with Client(customer_mcp_server) as client:
        result = await client.call_tool(
            "create_task",
            {
                "idempotency_key": "idem-1",
                "template_id": "maternal-new-entry",
                "package_type": "quick",
                "primary_market": "US",
                "compare_markets": [],
                "category_id": "feeding",
                "brand": "Brand",
                "competitors": [],
                "window_start": "2026-09-01",
                "window_end": "2026-09-30",
                "decision_question": "是否值得进入？",
                "does_not_answer": [],
                "seed_products": [],
                "budget": {"max_cost_usd": 20},
                "acceptance_contact_id": str(uuid.uuid4()),
            },
        )

    assert result.is_error is False
    assert result.structured_content["status"] == "pending_approval"
    assert result.structured_content["run_ids"] == []
    assert ports.tasks.create_calls


@pytest.mark.asyncio
async def test_create_task_maps_package_markets_and_budget(ports: _Ports) -> None:
    async with Client(customer_mcp_server) as client:
        result = await client.call_tool(
            "create_task",
            {
                "idempotency_key": "idem-2",
                "template_id": "maternal-new-entry",
                "package_type": "standard",
                "primary_market": "US",
                "compare_markets": ["GB", "DE"],
                "category_id": "feeding",
                "brand": "Brand",
                "competitors": [],
                "window_start": "2026-09-01",
                "window_end": "2026-09-30",
                "decision_question": "是否值得进入？",
                "does_not_answer": [],
                "seed_products": [
                    "https://example.com/1",
                    "https://example.com/2",
                    "ID-3",
                ],
                "target_price_band": {
                    "currency": "USD",
                    "min_amount": "10",
                    "max_amount": "30",
                },
                "budget": {"max_cost_usd": 20, "max_pages": 10, "max_records": 100},
                "acceptance_contact_id": str(uuid.uuid4()),
            },
        )

    assert result.is_error is False
    request = ports.tasks.create_calls[0]["request"]
    assert request.package_type == "standard"
    assert request.primary_market == "US"
    assert request.compare_markets == ("GB", "DE")
    assert request.seed_products == (
        "https://example.com/1",
        "https://example.com/2",
        "ID-3",
    )
    assert request.target_price_band == {
        "currency": "USD",
        "min_amount": "10",
        "max_amount": "30",
    }
    assert request.budget.max_cost_usd == Decimal("20")
    assert request.budget.max_pages == 10
    assert request.budget.max_records == 100


@pytest.mark.asyncio
async def test_collect_unknown_capability_is_rejected(ports: _Ports) -> None:
    async with Client(customer_mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "collect",
            {
                "capability_id": "cap-other",
                "params": {},
                "idempotency_key": "idem-1",
                "budget": {"max_cost_usd": 10},
            },
        )

    assert result.is_error is True
    assert "capability_not_allowed" in str(result.content)


@pytest.mark.asyncio
async def test_collect_rejects_key_capability_outside_template(
    ports: _Ports,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """密钥白名单允许但 C8 模板不允许的能力必须返回 capability_not_allowed。"""
    monkeypatch.setattr(
        authorize_module,
        "customer_identity",
        lambda context: replace(
            IDENTITY,
            capability_allowlist=("cap-product", "cap-outside-template"),
        ),
    )
    async with Client(customer_mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "collect",
            {
                "capability_id": "cap-outside-template",
                "params": {},
                "idempotency_key": "idem-1",
                "budget": {"max_cost_usd": 10},
            },
        )

    assert result.is_error is True
    assert "capability_not_allowed" in str(result.content)
    assert ports.capabilities.template_calls == 1


@pytest.mark.asyncio
async def test_collect_requires_budget(ports: _Ports) -> None:
    assert ports.budget is not None
    ports.budget.allowed = False
    async with Client(customer_mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "collect",
            {
                "capability_id": "cap-product",
                "params": {"query": "baby"},
                "idempotency_key": "idem-1",
                "budget": {"max_cost_usd": 10},
            },
        )

    assert result.is_error is True
    assert "approval_required" in str(result.content)
    assert ports.collect.calls == []


@pytest.mark.asyncio
async def test_cancel_task_passes_idempotency_key_and_reason_code(
    ports: _Ports,
) -> None:
    async with Client(customer_mcp_server) as client:
        result = await client.call_tool(
            "cancel_task",
            {
                "task_id": str(TASK_ID),
                "idempotency_key": "cancel-1",
                "reason_code": "user_request",
            },
        )

    assert result.is_error is False
    call = ports.tasks.cancel_calls[0]
    assert call["idempotency_key"] == "cancel-1"
    assert call["reason_code"] == "user_request"
    assert call["task_id"] == TASK_ID


@pytest.mark.asyncio
async def test_get_task_cross_project_is_not_found(ports: _Ports) -> None:
    async with Client(customer_mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool("get_task", {"task_id": str(uuid.uuid4())})

    assert result.is_error is True
    assert "task_not_found" in str(result.content)


@pytest.mark.asyncio
async def test_manifest_and_evidence_tools_return_c1_fields(ports: _Ports) -> None:
    async with Client(customer_mcp_server) as client:
        manifest = await client.call_tool(
            "get_delivery_manifest", {"task_id": str(TASK_ID)}
        )
        evidence = await client.call_tool("get_evidence", {"claim_id": "claim-1"})

    assert manifest.structured_content["manifest_id"] == "manifest-1"
    assert evidence.structured_content["claim_status"] == "directional"


def test_tools_list_filter_keeps_only_allowed_names() -> None:
    result = {"tools": [{"name": "get_task"}, {"name": "collect"}]}
    filtered = filter_tools_result(result, ("get_task",))
    assert [tool["name"] for tool in filtered["tools"]] == ["get_task"]


def test_tools_list_unknown_shape_fails_closed() -> None:
    assert filter_tools_result(object(), ("get_task",)) == {"tools": []}
    assert filter_tools_result(None, ("get_task",)) == {"tools": []}
    assert filter_tools_result([], ("get_task",)) == {"tools": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_tools.py -q`

Expected: `FAILED` with `ModuleNotFoundError: No module named 'data_intelligence_hub.mcp_runtime.customer.server'`.

- [ ] **Step 3: Create the tools/list filter and transport authorization middleware**

`mcp_runtime/customer/middleware.py`:

```python
"""客户 MCP 的传输层中间件。

两层职责：
1. `CustomerAuthorizationMiddleware` 在 MCP 处理器之前执行统一授权管线，
   让白名单失败返回真正的 403、额度或限流返回真正的 429。
2. `CustomerToolListMiddleware` 在 `tools/list` 结果上按密钥白名单过滤。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from mcp_types import ListToolsResult
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from data_intelligence_hub.mcp_runtime.customer.auth import (
    customer_identity_from_request,
    customer_identity_from_scope,
)
from data_intelligence_hub.mcp_runtime.customer.authorize import (
    authorized_call_for_identity,
)
from data_intelligence_hub.mcp_runtime.customer.errors import (
    CustomerToolError,
    http_status_for,
)
from data_intelligence_hub.mcp_runtime.customer.ports import CustomerPorts
from data_intelligence_hub.mcp_runtime.customer.tool_names import CUSTOMER_TOOL_NAMES


async def _read_body(receive: Receive) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _replay_receive(body: bytes, receive: Receive) -> Receive:
    sent = False

    async def replay() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay


def _jsonrpc_tool_call(body: bytes) -> tuple[str, dict[str, object]] | None:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, list):
        return "__batch__", {}
    if not isinstance(payload, dict) or payload.get("method") != "tools/call":
        return None
    params = payload.get("params")
    if not isinstance(params, dict):
        return None
    name = params.get("name")
    if not isinstance(name, str):
        return None
    arguments = params.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
    return name, arguments


async def _send_json(send: Send, status: int, payload: dict[str, object]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class CustomerAuthorizationMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        ports_provider: Callable[[], CustomerPorts] | None = None,
    ) -> None:
        self._app = app
        if ports_provider is None:
            # Task 7 才在 ports.py 追加 get_ports；这里惰性导入，
            # 让 Task 6 的 middleware 模块可以先独立导入与测试。
            from data_intelligence_hub.mcp_runtime.customer.ports import get_ports

            ports_provider = get_ports
        self._ports_provider = ports_provider

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await self._app(scope, receive, send)
            return
        body = await _read_body(receive)
        replay = _replay_receive(body, receive)
        parsed = _jsonrpc_tool_call(body)
        if parsed is None:
            await self._app(scope, replay, send)
            return
        tool_name, arguments = parsed
        if tool_name == "__batch__":
            await _send_json(send, 400, {"detail": "invalid_request"})
            return
        identity = customer_identity_from_scope(scope)
        try:
            async with authorized_call_for_identity(
                identity,
                tool_name=tool_name,
                arguments=arguments,
                ports=self._ports_provider(),
                scope=scope,
            ):
                await self._app(scope, replay, send)
        except CustomerToolError as exc:
            await _send_json(send, http_status_for(exc.code), {"detail": exc.code})


def filter_tools_result(result: Any, allowed_names: tuple[str, ...]) -> Any:
    """按白名单过滤 `tools/list` 结果。支持模型与字典两种形态。"""
    allowed = set(allowed_names)
    if isinstance(result, ListToolsResult):
        return result.model_copy(
            update={"tools": [tool for tool in result.tools if tool.name in allowed]}
        )
    if isinstance(result, dict):
        tools = result.get("tools")
        if isinstance(tools, list):
            return {
                **result,
                "tools": [
                    tool
                    for tool in tools
                    if isinstance(tool, dict) and tool.get("name") in allowed
                ],
            }
    return {"tools": []}


class CustomerToolListMiddleware:
    async def __call__(self, ctx: Any, call_next: Any) -> Any:
        result = await call_next(ctx)
        if ctx.method != "tools/list":
            return result
        identity = customer_identity_from_request(ctx.request)
        if identity is None:
            # HTTP 请求缺身份时 fail-closed；进程内测试没有 request，保留完整清单。
            allowed = () if ctx.request is not None else CUSTOMER_TOOL_NAMES
        else:
            allowed = tuple(
                name for name in CUSTOMER_TOOL_NAMES if name in identity.tool_allowlist
            )
        return filter_tools_result(result, allowed)


__all__ = [
    "CustomerAuthorizationMiddleware",
    "CustomerToolListMiddleware",
    "filter_tools_result",
]
```

- [ ] **Step 4: Create the eight customer tools**

`mcp_runtime/customer/server.py`:

```python
"""客户 MCP server。

只注册 C1 `customer_mcp.schema.json` 的八个客户工具。
内部端点级工具、provider 原始调用和 `creator_cookie` 工具都不在本 server。
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import ToolAnnotations

from data_intelligence_hub.mcp_runtime.customer.authorize import ensure_customer_call
from data_intelligence_hub.mcp_runtime.customer.errors import CustomerToolError
from data_intelligence_hub.mcp_runtime.customer.middleware import (
    CustomerToolListMiddleware,
)
from data_intelligence_hub.mcp_runtime.customer.ports import (
    CapabilityView,
    TaskEstimateView,
    TaskView,
)
from data_intelligence_hub.mcp_runtime.customer.schemas import (
    BudgetInput,
    CreateTaskInput,
    EstimateTaskInput,
    validate_window,
)


def _annotations(
    *,
    read_only: bool,
    open_world: bool,
    destructive: bool = False,
    idempotent: bool = False,
) -> ToolAnnotations:
    return ToolAnnotations(
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )


customer_mcp_server = MCPServer(
    "Data Intelligence Hub Customer",
    instructions=(
        "Customer task tools only. Discover allowed capabilities first. "
        "Never send cookies, provider names or endpoint names."
    ),
    middleware=[CustomerToolListMiddleware()],
)


def _capability_payload(capability: CapabilityView) -> dict[str, object]:
    return {
        "capability_id": capability.capability_id,
        "display_name": capability.display_name,
        "data_domain": capability.data_domain,
        "markets": list(capability.markets),
        "why_this": capability.why_this,
        "cost_estimate_usd": float(capability.cost_estimate_usd),
    }


def _estimate_payload(estimate: TaskEstimateView) -> dict[str, object]:
    return {
        "estimate_id": estimate.estimate_id,
        "max_cost_usd": float(estimate.max_cost_usd),
        "currency": estimate.currency,
        "price_book_version": estimate.price_book_version,
        "expires_at": estimate.expires_at.isoformat(),
        "breakdown": [
            {key: (float(value) if isinstance(value, Decimal) else value) for key, value in item.items()}
            for item in estimate.breakdown
        ],
    }


def _create_task_payload(task: TaskView) -> dict[str, object]:
    return {
        "task_id": str(task.task_id),
        "status": task.status,
        "plan_version_id": str(task.plan_version_id) if task.plan_version_id else "",
        "run_ids": [str(item) for item in task.run_ids],
        "quote_id": task.quote_id or "",
        "created_at": task.created_at.isoformat() if task.created_at else "",
    }


def _get_task_payload(task: TaskView) -> dict[str, object]:
    return {
        "task_id": str(task.task_id),
        "status": task.status,
        "package_type": task.package_type,
        "markets": [dict(item) for item in task.markets],
        "delivery_manifest_id": task.delivery_manifest_id or "",
        "updated_at": task.updated_at.isoformat() if task.updated_at else "",
    }


def _cancel_task_payload(task: TaskView) -> dict[str, object]:
    return {
        "task_id": str(task.task_id),
        "status": task.status,
        "cancelled_runs": [str(item) for item in task.cancelled_runs],
        "preserved_artifacts": list(task.preserved_artifacts),
        "cancelled_at": task.cancelled_at.isoformat() if task.cancelled_at else "",
    }


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise CustomerToolError("invalid_request") from exc


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CustomerToolError("invalid_request") from exc


@customer_mcp_server.tool(
    description="List the capabilities allowed by both this project key and the task template.",
    annotations=_annotations(read_only=True, open_world=False, idempotent=True),
    structured_output=True,
)
async def discover_capabilities(
    context: Context,
    query: str,
    markets: list[str] | None = None,
    data_domains: list[str] | None = None,
    limit: int = 20,
) -> dict[str, object]:
    if limit < 1 or limit > 50:
        raise CustomerToolError("invalid_request")
    arguments: dict[str, object] = {
        "query": query,
        "markets": markets,
        "data_domains": data_domains,
        "limit": limit,
    }
    async with ensure_customer_call(
        context,
        tool_name="discover_capabilities",
        arguments=arguments,
    ) as call:
        template_ids = set(call.template_capability_ids)
        capability_ids = tuple(
            capability_id
            for capability_id in call.identity.capability_allowlist
            if capability_id in template_ids
        )
        catalog = await call.ports.capabilities.list_capabilities(
            workspace_id=call.identity.workspace_id,
            project_id=call.identity.project_id,
            capability_ids=capability_ids,
            query=query,
            markets=tuple(markets or ()),
            data_domains=tuple(data_domains or ()),
            limit=limit,
        )
        return {
            "catalog_digest": catalog.catalog_digest,
            "items": [_capability_payload(item) for item in catalog.capabilities],
        }


@customer_mcp_server.tool(
    description="Estimate one task package without creating it.",
    annotations=_annotations(read_only=True, open_world=False, idempotent=True),
    structured_output=True,
)
async def estimate_task(
    context: Context,
    template_id: str,
    package_type: str,
    primary_market: str,
    category_id: str,
    window_start: str,
    window_end: str,
    budget: BudgetInput,
    compare_markets: list[str] | None = None,
) -> dict[str, object]:
    if package_type not in ("quick", "standard"):
        raise CustomerToolError("invalid_request")
    start = _parse_date(window_start)
    end = _parse_date(window_end)
    validate_window(start, end)
    request = EstimateTaskInput(
        template_id=template_id,
        package_type=package_type,
        primary_market=primary_market,
        compare_markets=tuple(compare_markets or ()),
        category_id=category_id,
        window_start=start,
        window_end=end,
        budget=budget,
    )
    async with ensure_customer_call(
        context,
        tool_name="estimate_task",
        arguments={
            "template_id": template_id,
            "package_type": package_type,
            "primary_market": primary_market,
            "compare_markets": compare_markets,
            "category_id": category_id,
            "window_start": window_start,
            "window_end": window_end,
            "budget": budget.model_dump(mode="json"),
        },
    ) as call:
        estimate = await call.ports.tasks.estimate_task(
            identity=call.identity,
            request=request,
        )
        return _estimate_payload(estimate)


@customer_mcp_server.tool(
    description="Create one governed task package. Idempotency key is required.",
    annotations=_annotations(read_only=False, open_world=True, idempotent=True),
    structured_output=True,
)
async def create_task(
    context: Context,
    idempotency_key: str,
    template_id: str,
    package_type: str,
    primary_market: str,
    category_id: str,
    brand: str,
    window_start: str,
    window_end: str,
    decision_question: str,
    budget: BudgetInput,
    acceptance_contact_id: str,
    compare_markets: list[str] | None = None,
    competitors: list[str] | None = None,
    does_not_answer: list[str] | None = None,
    seed_products: list[str] | None = None,
    target_price_band: dict[str, Any] | None = None,
) -> dict[str, object]:
    if package_type not in ("quick", "standard"):
        raise CustomerToolError("invalid_request")
    start = _parse_date(window_start)
    end = _parse_date(window_end)
    validate_window(start, end)
    request = CreateTaskInput(
        idempotency_key=idempotency_key,
        template_id=template_id,
        package_type=package_type,
        primary_market=primary_market,
        compare_markets=tuple(compare_markets or ()),
        category_id=category_id,
        brand=brand,
        competitors=tuple(competitors or ()),
        window_start=start,
        window_end=end,
        decision_question=decision_question,
        does_not_answer=tuple(does_not_answer or ()),
        seed_products=tuple(seed_products or ()),
        target_price_band=target_price_band,
        budget=budget,
        acceptance_contact_id=acceptance_contact_id,
    )
    async with ensure_customer_call(
        context,
        tool_name="create_task",
        arguments={
            "idempotency_key": idempotency_key,
            "template_id": template_id,
            "package_type": package_type,
            "primary_market": primary_market,
            "compare_markets": compare_markets,
            "category_id": category_id,
            "brand": brand,
            "competitors": competitors,
            "window_start": window_start,
            "window_end": window_end,
            "decision_question": decision_question,
            "does_not_answer": does_not_answer,
            "seed_products": seed_products,
            "target_price_band": target_price_band,
            "budget": budget.model_dump(mode="json"),
            "acceptance_contact_id": acceptance_contact_id,
        },
    ) as call:
        decision = await call.ports.budget.check(
            workspace_id=call.identity.workspace_id,
            project_id=call.identity.project_id,
            estimated_cost_usd=budget.max_cost_usd,
        )
        estimate = await call.ports.tasks.estimate_task(
            identity=call.identity,
            request=EstimateTaskInput(
                template_id=template_id,
                package_type=package_type,
                primary_market=primary_market,
                compare_markets=request.compare_markets,
                category_id=category_id,
                window_start=start,
                window_end=end,
                budget=budget,
            ),
        )
        task = await call.ports.tasks.create_task(
            identity=call.identity,
            request=request,
            quote_id=estimate.estimate_id,
            budget=decision,
        )
        return _create_task_payload(task)


@customer_mcp_server.tool(
    description="Read one task in this project.",
    annotations=_annotations(read_only=True, open_world=False, idempotent=True),
    structured_output=True,
)
async def get_task(context: Context, task_id: str) -> dict[str, object]:
    async with ensure_customer_call(
        context,
        tool_name="get_task",
        arguments={"task_id": task_id},
    ) as call:
        task = await call.ports.tasks.get_task(
            identity=call.identity,
            task_id=_parse_uuid(task_id),
        )
        if task is None:
            raise CustomerToolError("task_not_found")
        return _get_task_payload(task)


@customer_mcp_server.tool(
    description="Cancel one task in this project. Idempotency key is required.",
    annotations=_annotations(
        read_only=False,
        open_world=False,
        destructive=True,
        idempotent=True,
    ),
    structured_output=True,
)
async def cancel_task(
    context: Context,
    task_id: str,
    idempotency_key: str,
    reason_code: str,
) -> dict[str, object]:
    async with ensure_customer_call(
        context,
        tool_name="cancel_task",
        arguments={
            "task_id": task_id,
            "idempotency_key": idempotency_key,
            "reason_code": reason_code,
        },
    ) as call:
        task = await call.ports.tasks.cancel_task(
            identity=call.identity,
            task_id=_parse_uuid(task_id),
            idempotency_key=idempotency_key,
            reason_code=reason_code,
        )
        if task is None:
            raise CustomerToolError("task_not_found")
        return _cancel_task_payload(task)


@customer_mcp_server.tool(
    description="Return the immutable delivery manifest for one task.",
    annotations=_annotations(read_only=True, open_world=False, idempotent=True),
    structured_output=True,
)
async def get_delivery_manifest(
    context: Context,
    task_id: str,
    manifest_version: int | None = None,
) -> dict[str, object]:
    async with ensure_customer_call(
        context,
        tool_name="get_delivery_manifest",
        arguments={"task_id": task_id, "manifest_version": manifest_version},
    ) as call:
        manifest = await call.ports.tasks.get_delivery_manifest(
            identity=call.identity,
            task_id=_parse_uuid(task_id),
            manifest_version=manifest_version,
        )
        if manifest is None:
            raise CustomerToolError("manifest_not_found")
        return {
            "manifest_id": str(manifest.get("manifest_id", "")),
            "task_id": str(manifest.get("task_id", task_id)),
            "report_artifact_id": str(manifest.get("report_artifact_id", "")),
            "manifest_sha256": str(manifest.get("manifest_sha256", "")),
            "files": list(manifest.get("files", [])),
            "access_scope": list(manifest.get("access_scope", [])),
            "retention_class": str(manifest.get("retention_class", "")),
            "published_at": str(manifest.get("published_at", "")),
        }


@customer_mcp_server.tool(
    description="Return one claim with its evidence items.",
    annotations=_annotations(read_only=True, open_world=False, idempotent=True),
    structured_output=True,
)
async def get_evidence(context: Context, claim_id: str) -> dict[str, object]:
    async with ensure_customer_call(
        context,
        tool_name="get_evidence",
        arguments={"claim_id": claim_id},
    ) as call:
        evidence = await call.ports.tasks.get_evidence(
            identity=call.identity,
            claim_id=claim_id,
        )
        if evidence is None:
            raise CustomerToolError("claim_not_found")
        return {
            "claim_id": str(evidence.get("claim_id", claim_id)),
            "claim_status": str(evidence.get("claim_status", "")),
            "evidence_grade": str(evidence.get("evidence_grade", "")),
            "items": list(evidence.get("items", [])),
        }


@customer_mcp_server.tool(
    description="Run one template-whitelisted capability under governance.",
    annotations=_annotations(read_only=False, open_world=True, idempotent=True),
    structured_output=True,
)
async def collect(
    context: Context,
    capability_id: str,
    params: dict[str, Any],
    idempotency_key: str,
    budget: BudgetInput,
) -> dict[str, object]:
    async with ensure_customer_call(
        context,
        tool_name="collect",
        arguments={
            "capability_id": capability_id,
            "params": params,
            "idempotency_key": idempotency_key,
            "budget": budget.model_dump(mode="json"),
        },
    ) as call:
        if (
            capability_id not in call.identity.capability_allowlist
            or capability_id not in set(call.template_capability_ids)
        ):
            raise CustomerToolError("capability_not_allowed")
        capability = await call.ports.capabilities.resolve_capability(
            workspace_id=call.identity.workspace_id,
            project_id=call.identity.project_id,
            capability_id=capability_id,
        )
        if capability is None:
            raise CustomerToolError("capability_not_allowed")
        if not capability.executable:
            raise CustomerToolError("tool_not_executable")
        decision = await call.ports.budget.check(
            workspace_id=call.identity.workspace_id,
            project_id=call.identity.project_id,
            estimated_cost_usd=capability.cost_estimate_usd,
        )
        if not decision.allowed:
            raise CustomerToolError("approval_required")
        result = await call.ports.collect.run(
            identity=call.identity,
            capability=capability,
            params=params,
            idempotency_key=idempotency_key,
            budget=budget,
            request_id=call.request_id,
        )
        return {
            "run_id": str(result.get("run_id", "")),
            "task_id": str(result.get("task_id", "")),
            "status": str(result.get("status", "")),
            "accepted_at": str(result.get("accepted_at", "")),
        }


__all__ = [
    "cancel_task",
    "collect",
    "create_task",
    "customer_mcp_server",
    "discover_capabilities",
    "estimate_task",
    "get_delivery_manifest",
    "get_evidence",
    "get_task",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_tools.py -q`

Expected: `16 passed`.

- [ ] **Step 6: Verify the internal server is unchanged**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13 && git diff --exit-code -- apps/api/src/data_intelligence_hub/mcp_runtime/server.py apps/api/src/data_intelligence_hub/mcp_runtime/auth.py`

Expected: no output.

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
git add apps/api/src/data_intelligence_hub/mcp_runtime/customer/server.py \
        apps/api/src/data_intelligence_hub/mcp_runtime/customer/middleware.py \
        apps/api/tests/unit/test_customer_mcp_tools.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(customer-mcp): add exactly eight contract-aligned customer tools"
```

---

### Task 6b: 客户输出白名单

**Files:**
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/redaction.py`
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/server.py`
- Test: `apps/api/tests/unit/test_customer_mcp_redaction.py`

**Interfaces:**
- Consumes: `estimate_task`、`get_evidence`、`get_delivery_manifest`、`cancel_task` 的原始下游字典。
- Produces:
  - `FORBIDDEN_OUTPUT_KEYS: frozenset[str]`
  - `public_estimate(payload) -> dict[str, object]`
  - `public_evidence(payload) -> dict[str, object]`
  - `public_manifest(payload) -> dict[str, object]`
  - `public_cancel(payload) -> dict[str, object]`
  - `assert_no_internal_keys(payload) -> None`

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_customer_mcp_redaction.py`:

```python
from __future__ import annotations

import json

from data_intelligence_hub.mcp_runtime.customer.redaction import (
    assert_no_internal_keys,
    public_cancel,
    public_estimate,
    public_evidence,
    public_manifest,
)

FORBIDDEN = {
    "source_tool_id",
    "provider_id",
    "raw_record_id",
    "endpoint_type",
    "storage_path",
    "cookie",
    "unit_price",
    "tool_id",
}


def test_estimate_drops_internal_breakdown_fields() -> None:
    payload = {
        "estimate_id": "est-1",
        "max_cost_usd": "20.0",
        "currency": "USD",
        "price_book_version": "v1",
        "expires_at": "2026-10-23T00:00:00Z",
        "breakdown": [
            {
                "capability_id": "cap-1",
                "label": "商品",
                "amount_usd": "10.0",
                "tool_id": "tikhub_product",
                "unit_price": "0.01",
                "provider_id": "tikhub",
                "endpoint_type": "product_detail",
            }
        ],
    }
    result = public_estimate(payload)
    text = json.dumps(result, ensure_ascii=False).lower()
    for key in FORBIDDEN:
        assert key not in text, key
    assert result["breakdown"][0]["capability_id"] == "cap-1"
    assert result["breakdown"][0]["amount_usd"] == "10.0"


def test_evidence_items_drop_raw_and_provider_ids() -> None:
    payload = {
        "claim_id": "claim-1",
        "claim_status": "confirmed",
        "evidence_grade": "A",
        "items": [
            {
                "evidence_id": "ev-1",
                "title": "公开评论",
                "source_url": "https://example.com/post/1?utm_source=x",
                "excerpt": "text",
                "source_tool_id": "tikhub_comments",
                "provider_id": "tikhub",
                "raw_record_id": "raw-1",
                "endpoint_type": "comments",
            }
        ],
    }
    result = public_evidence(payload)
    text = json.dumps(result, ensure_ascii=False).lower()
    for key in FORBIDDEN:
        assert key not in text, key
    assert result["items"][0]["evidence_id"] == "ev-1"


def test_manifest_drops_storage_paths_and_internal_scope() -> None:
    payload = {
        "manifest_id": "m-1",
        "task_id": "task-1",
        "report_artifact_id": "art-1",
        "manifest_sha256": "a" * 64,
        "files": [
            {
                "path": "report.zh.html",
                "sha256": "b" * 64,
                "storage_path": "/srv/bundles/ws/art/report.zh.html",
                "content_type": "text/html",
            }
        ],
        "access_scope": ["internal", "workspace:ws"],
        "retention_class": "report_delivery",
        "published_at": "2026-10-22T00:00:00Z",
    }
    result = public_manifest(payload)
    text = json.dumps(result, ensure_ascii=False).lower()
    for key in FORBIDDEN:
        assert key not in text, key
    assert result["files"][0]["path"] == "report.zh.html"
    assert result["access_scope"] == ["project"]


def test_cancel_drops_preserved_artifact_internal_names() -> None:
    payload = {
        "task_id": "task-1",
        "status": "cancelled",
        "cancelled_runs": ["run-1"],
        "preserved_artifacts": ["/srv/bundles/ws/art.zip", "s3://bucket/key"],
        "cancelled_at": "2026-10-22T00:00:00Z",
    }
    result = public_cancel(payload)
    text = json.dumps(result, ensure_ascii=False).lower()
    for key in FORBIDDEN:
        assert key not in text, key
    assert result["preserved_artifacts"] == ["artifact-preserved"]


def test_assert_no_internal_keys_rejects_nested_leak() -> None:
    try:
        assert_no_internal_keys({"items": [{"provider_id": "x"}]})
    except ValueError as exc:
        assert "provider_id" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c13/apps/api
uv run pytest tests/unit/test_customer_mcp_redaction.py -q
```
Expected: FAIL，模块不存在。

- [ ] **Step 3: 写白名单实现**

Create `apps/api/src/data_intelligence_hub/mcp_runtime/customer/redaction.py`:

```python
"""客户可见输出白名单。

下游字典可能含内部字段。客户响应只保留白名单键，其他键全部丢弃。
禁止把本模块用于内部审计；它只负责客户出口。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

FORBIDDEN_OUTPUT_KEYS: frozenset[str] = frozenset(
    {
        "source_tool_id",
        "provider_id",
        "raw_record_id",
        "endpoint_type",
        "storage_path",
        "cookie",
        "unit_price",
        "tool_id",
        "workspace_id",
        "project_id",
        "salt",
        "salt_b64",
        "key_hash",
        "credential_id",
    }
)

_ESTIMATE_KEYS = {
    "estimate_id",
    "max_cost_usd",
    "currency",
    "price_book_version",
    "expires_at",
    "breakdown",
}
_BREAKDOWN_KEYS = {"capability_id", "label", "amount_usd", "currency"}
_EVIDENCE_KEYS = {"claim_id", "claim_status", "evidence_grade", "items"}
_EVIDENCE_ITEM_KEYS = {
    "evidence_id",
    "title",
    "source_url",
    "published_at",
    "excerpt",
    "grade",
    "role",
}
_MANIFEST_KEYS = {
    "manifest_id",
    "task_id",
    "report_artifact_id",
    "manifest_sha256",
    "files",
    "access_scope",
    "retention_class",
    "published_at",
}
_MANIFEST_FILE_KEYS = {"path", "sha256", "bytes", "content_type"}
_CANCEL_KEYS = {
    "task_id",
    "status",
    "cancelled_runs",
    "preserved_artifacts",
    "cancelled_at",
}


def _pick(value: Mapping[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {key: value[key] for key in allowed if key in value}


def assert_no_internal_keys(value: Any, path: str = "output") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_OUTPUT_KEYS:
                raise ValueError(f"customer_output_internal_key:{path}.{normalized}")
            assert_no_internal_keys(item, f"{path}.{normalized}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_no_internal_keys(item, f"{path}[{index}]")


def public_estimate(payload: Mapping[str, Any]) -> dict[str, object]:
    result = _pick(payload, _ESTIMATE_KEYS)
    result["breakdown"] = [
        _pick(item, _BREAKDOWN_KEYS)
        for item in payload.get("breakdown", [])
        if isinstance(item, Mapping)
    ]
    assert_no_internal_keys(result)
    return result


def public_evidence(payload: Mapping[str, Any]) -> dict[str, object]:
    result = _pick(payload, _EVIDENCE_KEYS)
    result["items"] = [
        _pick(item, _EVIDENCE_ITEM_KEYS)
        for item in payload.get("items", [])
        if isinstance(item, Mapping)
    ]
    assert_no_internal_keys(result)
    return result


def public_manifest(payload: Mapping[str, Any]) -> dict[str, object]:
    result = _pick(payload, _MANIFEST_KEYS)
    result["files"] = [
        _pick(item, _MANIFEST_FILE_KEYS)
        for item in payload.get("files", [])
        if isinstance(item, Mapping)
    ]
    result["access_scope"] = ["project"]
    assert_no_internal_keys(result)
    return result


def public_cancel(payload: Mapping[str, Any]) -> dict[str, object]:
    result = _pick(payload, _CANCEL_KEYS)
    if result.get("preserved_artifacts"):
        result["preserved_artifacts"] = ["artifact-preserved"]
    assert_no_internal_keys(result)
    return result
```

- [ ] **Step 4: 接入四个工具**

在 `server.py` 中替换返回值：

```python
# get_delivery_manifest
return public_manifest(manifest)

# get_evidence
return public_evidence(evidence)

# cancel_task
return public_cancel(_cancel_task_payload(task))

# estimate_task
return public_estimate(_estimate_payload(estimate))
```

`_estimate_payload`、`_cancel_task_payload` 可以保留；对外只返回白名单结果。

- [ ] **Step 5: 运行测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c13/apps/api
uv run pytest tests/unit/test_customer_mcp_redaction.py tests/unit/test_customer_mcp_tools.py -q
```
Expected: PASS。`test_customer_mcp_tools.py` 必须断言响应 JSON 不含 `source_tool_id`、`provider_id`、`raw_record_id`、`endpoint_type`、`storage_path`、`cookie`、`unit_price`、`tool_id`。

- [ ] **Step 6: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/mcp_runtime/customer/redaction.py \
        apps/api/src/data_intelligence_hub/mcp_runtime/customer/server.py \
        apps/api/tests/unit/test_customer_mcp_redaction.py \
        apps/api/tests/unit/test_customer_mcp_tools.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(customer-mcp): whitelist customer output fields"
```

---

### Task 7: 生产适配器连接 C2/C3/C4/C5/C6/C7/C8/C9/C10

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/ports.py`（在端口协议之后追加薄生产适配器）
- Test: `apps/api/tests/unit/test_customer_mcp_ports.py`

**Interfaces:**
- Consumes:
  - C2：`services.audit_log.append_audit_event`。
  - C3：`repositories.project_api_keys.find_by_id`、`consume_daily_quota`、`repositories.workspaces.get_workspace_by_id`、`repositories.projects.get_project`。
  - C4：`services.workbench.tasks.create_workbench_task`、`services.workbench.initial_version.create_initial_workflow_version_for_task`、`repositories.workbench_tasks.get_workbench_task`、`list_runs_for_task`、`update_workbench_task_fields`、`services.workbench.submission.submit_workbench_task`、`services.workbench.markets.market_role_for`。
  - C5：`services.pricing.quote`、`price_book_fingerprint`、`services.budget_service.estimate_run_budget`、`repositories.quota_accounts.get_or_create_quota_account`。
  - C6：`services.run_service.cancel_task_runs`、`CancellationError`、`RunCancellationResult`。C13 不直接调用 `repositories.runs.cancel_run` 或 `OrmRunBudget.cancel`；二者只属于 C6 取消服务内部。
  - C7：`repositories.claims.get_claim`、`list_evidence`、`load_evidence_rows`；`services.claims.load_publishable_claim_rows`、`validate_claim_bundle`、`ClaimContractBundle`。
  - C8：`services.workbench_templates.get_task_template`、`list_task_templates`、`template_capability_ids(template_id)`、`TaskTemplate.capability_allowlist`、`tool_catalog.evidence_thresholds.package_threshold_for`、`repositories.dataset_quality.get_market_assessment`、`list_data_gaps`。
  - C9/C10：`report_artifacts` 只读字段、`services.delivery.store.DeliveryStore`、`services.delivery.service.load_delivery_manifest`。
- Produces: `get_ports() -> CustomerPorts`；`SqlAlchemyKeyStatus`、`SqlAlchemyQuota`、`ToolCatalogCapabilityAdapter`、`QuotaBudgetAdapter`、`WorkbenchTaskAdapter`、`WorkbenchCollectAdapter`、`SqlAlchemyAuditSink`。

上游文件所有权（C13 只读消费，不创建、不改写）：

| 文件 | 所有者 | C13 使用的符号 |
|---|---|---|
| `apps/api/src/data_intelligence_hub/services/workbench/tasks.py` | C4 | `create_workbench_task`、`get_workbench_task_detail` |
| `apps/api/src/data_intelligence_hub/repositories/workbench_tasks.py` | C4 | `get_workbench_task`、`list_runs_for_task`、`update_workbench_task_fields` |
| `apps/api/src/data_intelligence_hub/services/workbench/initial_version.py` | C4 | `create_initial_workflow_version_for_task` |
| `apps/api/src/data_intelligence_hub/services/workbench/submission.py` | C4 | `submit_workbench_task` |
| `apps/api/src/data_intelligence_hub/services/workbench/markets.py` | C4 | `market_role_for` |
| `apps/api/src/data_intelligence_hub/schemas/workbench.py` | C4 | `WorkbenchTaskCreateRequest`、`WorkbenchWindow` |
| `apps/api/src/data_intelligence_hub/services/pricing.py` | C5 | `quote`、`price_book_fingerprint`、`ToolNotPricedError` |
| `apps/api/src/data_intelligence_hub/services/budget_service.py` | C5 | `estimate_run_budget` |
| `apps/api/src/data_intelligence_hub/repositories/quota_accounts.py` | C5 | `get_or_create_quota_account` |
| `apps/api/src/data_intelligence_hub/services/run_service.py` | C6 | `cancel_task_runs`、`CancellationError`、`RunCancellationResult` |
| `apps/api/src/data_intelligence_hub/repositories/claims.py` | C7 | `get_claim`、`list_evidence`、`load_evidence_rows` |
| `apps/api/src/data_intelligence_hub/services/claims.py` | C7 | `load_publishable_claim_rows`、`validate_claim_bundle`、`ClaimContractBundle` |
| `apps/api/src/data_intelligence_hub/services/workbench_templates.py` | C8 | `get_task_template`、`list_task_templates`、`template_capability_ids`、`TaskTemplate.capability_allowlist`（字段） |
| `apps/api/src/data_intelligence_hub/tool_catalog/evidence_thresholds.py` | C8 | `package_threshold_for`、`PACKAGE_TIER_THRESHOLDS` |
| `apps/api/src/data_intelligence_hub/repositories/dataset_quality.py` | C8 | `get_market_assessment`、`list_data_gaps` |
| `apps/api/src/data_intelligence_hub/repositories/report_artifacts.py` | C9 | `report_artifacts` 只读查询 |
| `apps/api/src/data_intelligence_hub/services/delivery/store.py` | C10 | `DeliveryStore` |
| `apps/api/src/data_intelligence_hub/services/delivery/service.py` | C10 | `load_delivery_manifest`、`open_delivery_zip` |

C13 不在 `services/` 下新建 `customer_task_gateway`、`customer_budget`、`customer_capabilities`、`governed_collect` 或 `delivery_manifest` 模块；这些名称不存在于 C4/C5/C8/C10 的计划，不得作为依赖。`ports.py` 只做字段映射、只读查询和公开服务调用；预算、Claim、报告与采集规则仍归上游所有者。

`create_task` 与 `collect` 都通过 C4 `create_initial_workflow_version_for_task` 取得可执行的已批准当前版本；计划生成、批准与持久化只属于 C4 既有 workflow planner，C13 只消费返回的版本 ID。该接缝已有版本时只复用，不建第二个。`create_task` 返回非空 `plan_version_id` 与 `run_ids`，`collect` 用同一接缝取得同一版本后提交 run。

`WorkbenchTaskAdapter.create_task` 必须按以下映射构造 C4 `WorkbenchTaskCreateRequest`。映射只做字段改名与装箱，不复制 Quick/Standard 上限或任何产品阈值：

| `CreateTaskInput` / `BudgetInput` | C4 目标 |
|---|---|
| `request.idempotency_key` | `create_workbench_task(..., idempotency_key=request.idempotency_key)`；不写入任务单字段 |
| `request.package_type` | `package_type` |
| `request.primary_market` | `primary_market` |
| `request.compare_markets` | `comparison_markets`（`tuple` 转 `list`） |
| `request.category_id` | `category` |
| `request.brand` | `brand` |
| `request.competitors` | `competitors` |
| `request.window_start` / `window_end` | `window.start` / `window.end` |
| `request.decision_question` | `decision_question` |
| `request.does_not_answer` | `does_not_answer` |
| `request.seed_products` | `seed_products`（`tuple` 转 `list`；不得丢弃） |
| `request.target_price_band` | `target_price_band`（原样传递 `dict`；不得丢弃） |
| `request.budget.max_cost_usd` | `max_cost_usd` |
| `request.budget.max_pages` | `max_pages` |
| `request.budget.max_records` | `max_records` |
| `request.acceptance_contact_id` | `acceptance_contact_id`（转 UUID；C4 校验 owner/admin） |

`markets` 与 `locale_by_market` 由适配器派生：`markets = [primary_market, *comparison_markets]`，`locale_by_market = {market: "en" for market in markets}`；请求不单独携带这两个派生值。`workbench_tasks` 与 `runs` 的写入只发生在 C4。`TaskView.markets` 的 `market_role` 也由 C4 `market_role_for()` 派生，C13 不写 `runs.market_role`。

`collect` 的 `params` 可带 `package_type`、`markets`、`seed_products`、`target_price_band`；缺省 `package_type=quick`，首个市场为主市场，其余为对比市场。市场数量上限、种子商品 3–10 项与价格带规则仍由 C4 校验，C13 不复制阈值。

`WorkbenchTaskAdapter.cancel_task` 必须委托 `services.run_service.cancel_task_runs(...)`，原样传 `idempotency_key` 与 `reason_code`，不得 `del`、改写或本地重算幂等摘要。`TaskView.cancelled_runs`、`preserved_artifacts`、`cancelled_at` 只取自 `RunCancellationResult`；`replayed=True` 时不重复写任务状态。`CancellationError.code` 只映射为 C1 已登记的 `idempotency_conflict` 或 `state_conflict`。

`WorkbenchTaskAdapter.get_evidence` 必须先调用 C7 `load_publishable_claim_rows` 和 `validate_claim_bundle`。Claim 不在 publishable bundle 中（`draft`/`pending`/`rejected`/`stale` 或同工作区其他项目）返回 `claim_not_found`；bundle 行存在但证据缺字段、证据行不完整或证据等级不一致时抛 `evidence_not_found`。C13 不自行判断 `review_status`。

- [ ] **Step 0: 上游接口导入预检**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c13/apps/api
uv run python - <<'PY'
from data_intelligence_hub.repositories.claims import get_claim, list_evidence, load_evidence_rows
from data_intelligence_hub.repositories.dataset_quality import get_market_assessment, list_data_gaps
from data_intelligence_hub.repositories.project_api_keys import consume_daily_quota, find_by_id
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.quota_accounts import get_or_create_quota_account
from data_intelligence_hub.repositories.report_artifacts import get_latest_artifact
from data_intelligence_hub.repositories.workspaces import get_workspace_by_id
from data_intelligence_hub.repositories.workbench_tasks import (
    get_workbench_task,
    list_runs_for_task,
    update_workbench_task_fields,
)
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.budget_service import estimate_run_budget
from data_intelligence_hub.services.claims import (
    ClaimContractBundle,
    load_publishable_claim_rows,
    validate_claim_bundle,
)
from data_intelligence_hub.services.delivery.service import load_delivery_manifest
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.pricing import (
    ToolNotPricedError,
    price_book_fingerprint,
    quote,
)
from data_intelligence_hub.services.run_service import (
    CancellationError,
    RunCancellationResult,
    cancel_task_runs,
)
from data_intelligence_hub.services.workbench.errors import WorkbenchError
from data_intelligence_hub.services.workbench.initial_version import (
    create_initial_workflow_version_for_task,
)
from data_intelligence_hub.services.workbench.markets import market_role_for
from data_intelligence_hub.services.workbench.submission import submit_workbench_task
from data_intelligence_hub.services.workbench.tasks import (
    create_workbench_task,
    get_workbench_task_detail,
)
from data_intelligence_hub.services.workbench_templates import (
    get_task_template,
    list_task_templates,
    template_capability_ids,
)
from data_intelligence_hub.tool_catalog.evidence_thresholds import package_threshold_for
from data_intelligence_hub.tool_catalog.markets import FORMAL_MARKETS
from data_intelligence_hub.tool_catalog.service import find_tool, get_tool_catalog

for template in list_task_templates():
    assert template_capability_ids(template.template_id), template.template_id
print("customer_upstream_services_ok")
PY
```

Expected: `customer_upstream_services_ok`。任一 `ImportError` 或 `AssertionError` 时停止，C13 状态记为 `BLOCKED`；先由 C4/C5/C6/C7/C8/C9/C10 所有者落地文件与函数，不得用 mock 单测代替预检。C6 缺 `cancel_task_runs` 记为 `BLOCKED: c6_cancel_task_service_missing`；C7 缺 `load_publishable_claim_rows` / `validate_claim_bundle` 记为 `BLOCKED: c7_publishable_gate_missing`；C8 缺 `template_capability_ids(template_id)` 或返回空元组记为 `BLOCKED: c8_template_capability_ids_missing`。

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/test_customer_mcp_ports.py`:

```python
"""端口到上游公开接口的薄映射。

C13 不复制业务。测试只断言字段映射、调用参数与白名单边界。
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from data_intelligence_hub.mcp_runtime.customer import ports as ports_module
from data_intelligence_hub.mcp_runtime.customer.auth import CustomerIdentity
from data_intelligence_hub.mcp_runtime.customer.errors import CustomerToolError
from data_intelligence_hub.mcp_runtime.customer.ports import (
    AuditEvent,
    BudgetDecision,
    QuotaBudgetAdapter,
    SqlAlchemyAuditSink,
    ToolCatalogCapabilityAdapter,
    WorkbenchCollectAdapter,
    WorkbenchTaskAdapter,
)
from data_intelligence_hub.mcp_runtime.customer.schemas import (
    BudgetInput,
    CreateTaskInput,
)

IDENTITY = CustomerIdentity(
    key_id=uuid.uuid4(),
    workspace_id=uuid.uuid4(),
    project_id=uuid.uuid4(),
    key_prefix="dih_test",
    label="test",
    tool_allowlist=("collect",),
    capability_allowlist=("cap-1",),
    daily_collect_quota=10,
)
TASK_ID = uuid.uuid4()
VERSION_ID = uuid.uuid4()
RUN_ID = uuid.uuid4()
CLAIM_ID = uuid.uuid4()
EVIDENCE_ID = uuid.uuid4()


class _Session:
    async def commit(self) -> None:
        return None

    async def refresh(self, instance: object, *args: object, **kwargs: object) -> None:
        del instance, args, kwargs
        return None


@asynccontextmanager
async def _null_session():
    yield _Session()


def _create_input() -> CreateTaskInput:
    return CreateTaskInput(
        idempotency_key="idem-1",
        template_id="maternal-new-entry",
        package_type="quick",
        primary_market="US",
        compare_markets=(),
        category_id="feeding",
        brand="Brand",
        competitors=(),
        window_start=date(2026, 9, 1),
        window_end=date(2026, 9, 30),
        decision_question="这个类目是否值得进入？",
        does_not_answer=(),
        seed_products=("https://example.com/1", "https://example.com/2", "ID-3"),
        target_price_band={"currency": "USD", "min_amount": "10", "max_amount": "30"},
        budget=BudgetInput(max_cost_usd="20"),
        acceptance_contact_id=str(uuid.uuid4()),
    )


@pytest.mark.asyncio
async def test_capability_adapter_projects_tool_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = SimpleNamespace(
        tool_id="cap-1",
        label="商品",
        description="公开商品",
        category="product",
        executable=True,
        availability_view=SimpleNamespace(availability="verified"),
        parameters=(),
    )
    catalog = SimpleNamespace(catalog_digest="digest-1", tools=(tool,))
    template = SimpleNamespace(
        template_id="tiktok_shop_maternal_newborn",
        capability_allowlist=("cap-1",),
        core_domains=("product",),
        markets=("US",),
        package_tiers=("quick", "standard"),
    )

    async def fake_catalog(session: object) -> object:
        del session
        return catalog

    monkeypatch.setattr(ports_module, "get_tool_catalog", fake_catalog)
    monkeypatch.setattr(ports_module, "list_task_templates", lambda: (template,))
    monkeypatch.setattr(
        ports_module,
        "template_capability_ids",
        lambda template_id: ("cap-1",),
    )
    monkeypatch.setattr(
        ports_module,
        "quote",
        lambda tool_id, records_count=0: SimpleNamespace(
            total_cost_usd=Decimal("1.50")
        ),
    )

    adapter = ToolCatalogCapabilityAdapter(session_factory=_null_session)
    view = await adapter.list_capabilities(
        workspace_id=IDENTITY.workspace_id,
        project_id=IDENTITY.project_id,
        capability_ids=("cap-1",),
        query=None,
        markets=(),
        data_domains=(),
        limit=20,
    )
    assert view.catalog_digest == "digest-1"
    assert view.capabilities[0].capability_id == "cap-1"
    assert view.capabilities[0].cost_estimate_usd == Decimal("1.50")
    assert view.capabilities[0].markets == ("US",)


@pytest.mark.asyncio
async def test_capability_adapter_uses_c8_template_capability_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模板白名单只经 C8 `template_capability_ids(template_id)` 读取。"""

    def _tool(tool_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            tool_id=tool_id,
            label=tool_id,
            description=tool_id,
            category="product",
            executable=True,
            availability_view=SimpleNamespace(availability="verified"),
            parameters=(),
        )

    catalog = SimpleNamespace(
        catalog_digest="digest-1",
        tools=(_tool("cap-1"), _tool("cap-2")),
    )
    template = SimpleNamespace(
        template_id="tiktok_shop_maternal_newborn",
        capability_allowlist=("cap-1",),
        core_domains=("product",),
        markets=("US",),
        package_tiers=("quick", "standard"),
    )
    seen_template_ids: list[str] = []

    def fake_template_capability_ids(template_id: str) -> tuple[str, ...]:
        seen_template_ids.append(template_id)
        return ("cap-1",)

    async def fake_catalog(session: object) -> object:
        del session
        return catalog

    monkeypatch.setattr(ports_module, "get_tool_catalog", fake_catalog)
    monkeypatch.setattr(ports_module, "list_task_templates", lambda: (template,))
    monkeypatch.setattr(
        ports_module,
        "template_capability_ids",
        fake_template_capability_ids,
    )
    monkeypatch.setattr(
        ports_module,
        "quote",
        lambda tool_id, records_count=0: SimpleNamespace(
            total_cost_usd=Decimal("1.50")
        ),
    )

    adapter = ToolCatalogCapabilityAdapter(session_factory=_null_session)
    assert await adapter.template_capability_ids() == ("cap-1",)
    assert seen_template_ids == ["tiktok_shop_maternal_newborn"]
    view = await adapter.list_capabilities(
        workspace_id=IDENTITY.workspace_id,
        project_id=IDENTITY.project_id,
        capability_ids=("cap-1", "cap-2"),
        query=None,
        markets=(),
        data_domains=(),
        limit=20,
    )
    assert [item.capability_id for item in view.capabilities] == ["cap-1"]


@pytest.mark.asyncio
async def test_capability_adapter_empty_template_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C8 模板白名单为空时不得回退为全部非 Cookie 工具。"""
    tool = SimpleNamespace(
        tool_id="cap-1",
        label="商品",
        description="公开商品",
        category="product",
        executable=True,
        availability_view=SimpleNamespace(availability="verified"),
        parameters=(),
    )
    catalog = SimpleNamespace(catalog_digest="digest-1", tools=(tool,))
    template = SimpleNamespace(
        template_id="tiktok_shop_maternal_newborn",
        capability_allowlist=(),
        markets=("US",),
        package_tiers=("quick", "standard"),
    )

    async def fake_catalog(session: object) -> object:
        del session
        return catalog

    monkeypatch.setattr(ports_module, "get_tool_catalog", fake_catalog)
    monkeypatch.setattr(ports_module, "list_task_templates", lambda: (template,))
    monkeypatch.setattr(
        ports_module,
        "template_capability_ids",
        lambda template_id: (),
    )

    adapter = ToolCatalogCapabilityAdapter(session_factory=_null_session)
    assert await adapter.template_capability_ids() == ()
    view = await adapter.list_capabilities(
        workspace_id=IDENTITY.workspace_id,
        project_id=IDENTITY.project_id,
        capability_ids=("cap-1",),
        query=None,
        markets=(),
        data_domains=(),
        limit=20,
    )
    assert view.capabilities == ()
    assert (
        await adapter.resolve_capability(
            workspace_id=IDENTITY.workspace_id,
            project_id=IDENTITY.project_id,
            capability_id="cap-1",
        )
        is None
    )


@pytest.mark.asyncio
async def test_budget_adapter_reads_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_account(session: object, **kwargs: object) -> object:
        del session
        assert kwargs["workspace_id"] == IDENTITY.workspace_id
        return SimpleNamespace(remaining_usd=Decimal("5"))

    monkeypatch.setattr(ports_module, "get_or_create_quota_account", fake_account)
    adapter = QuotaBudgetAdapter(session_factory=_null_session, enforce=True)
    decision = await adapter.check(
        workspace_id=IDENTITY.workspace_id,
        project_id=IDENTITY.project_id,
        estimated_cost_usd=Decimal("20"),
    )
    assert decision == BudgetDecision(
        allowed=False,
        approval_required=True,
        remaining_usd=Decimal("5"),
    )


@pytest.mark.asyncio
async def test_task_adapter_creates_initial_version_and_submits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_create(session: object, **kwargs: object) -> object:
        del session
        calls.append(("create", dict(kwargs)))
        return (
            SimpleNamespace(
                id=TASK_ID,
                status="draft",
                markets=["US"],
                primary_market="US",
                comparison_markets=[],
                created_at=datetime(2026, 10, 22, tzinfo=UTC),
                updated_at=datetime(2026, 10, 22, tzinfo=UTC),
            ),
            False,
        )

    async def fake_seam(session: object, **kwargs: object) -> uuid.UUID:
        del session
        calls.append(("seam", dict(kwargs)))
        return VERSION_ID

    async def fake_submit(session: object, **kwargs: object) -> object:
        del session
        calls.append(("submit", dict(kwargs)))
        return SimpleNamespace(
            workbench_task_id=TASK_ID,
            workflow_version_id=VERSION_ID,
            runs=(SimpleNamespace(id=RUN_ID, status="queued", market_code="US"),),
            gaps=(),
            idempotent_replay=False,
        )

    monkeypatch.setattr(ports_module, "create_workbench_task", fake_create)
    monkeypatch.setattr(
        ports_module, "create_initial_workflow_version_for_task", fake_seam
    )
    monkeypatch.setattr(ports_module, "submit_workbench_task", fake_submit)
    monkeypatch.setattr(
        ports_module,
        "get_task_template",
        lambda template_id: SimpleNamespace(
            markets=("US",),
            package_tiers=("quick", "standard"),
        ),
    )
    monkeypatch.setattr(ports_module, "package_threshold_for", lambda tier: SimpleNamespace())

    adapter = WorkbenchTaskAdapter(session_factory=_null_session)
    request = _create_input()
    task = await adapter.create_task(
        identity=IDENTITY,
        request=request,
        quote_id="est-1",
        budget=BudgetDecision(
            allowed=True,
            approval_required=False,
            remaining_usd=Decimal("10"),
        ),
    )
    assert task.status == "submitted"
    assert task.package_type == "quick"
    assert task.plan_version_id == VERSION_ID
    assert task.run_ids == (RUN_ID,)
    create_kwargs = calls[0][1]
    assert create_kwargs["workspace_id"] == IDENTITY.workspace_id
    assert create_kwargs["idempotency_key"] == "idem-1"
    payload = create_kwargs["payload"]
    assert payload.package_type == "quick"
    assert payload.primary_market == "US"
    assert payload.comparison_markets == []
    assert payload.seed_products == [
        "https://example.com/1",
        "https://example.com/2",
        "ID-3",
    ]
    assert payload.target_price_band is not None
    assert payload.target_price_band.currency == "USD"
    assert str(payload.acceptance_contact_id) == request.acceptance_contact_id
    assert payload.max_cost_usd == Decimal("20")
    seam_kwargs = calls[1][1]
    assert seam_kwargs["workbench_task_id"] == TASK_ID
    assert seam_kwargs["idempotency_key"] == "idem-1"
    assert calls[2][1]["workflow_version_id"] == VERSION_ID
    assert calls[2][1]["idempotency_key"] == "idem-1"


@pytest.mark.asyncio
async def test_create_task_then_collect_reuses_same_initial_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """客户 create_task 后 collect 必须命中同一任务与同一初始版本。"""
    created: dict[str, uuid.UUID] = {}
    versions: dict[uuid.UUID, uuid.UUID] = {}
    seam_calls: list[uuid.UUID] = []

    async def fake_create(session: object, **kwargs: object) -> object:
        del session
        key = str(kwargs["idempotency_key"])
        task_id = created.setdefault(key, uuid.uuid4())
        return (
            SimpleNamespace(
                id=task_id,
                status="draft",
                markets=["US"],
                primary_market="US",
                comparison_markets=[],
                created_at=datetime(2026, 10, 22, tzinfo=UTC),
                updated_at=datetime(2026, 10, 22, tzinfo=UTC),
            ),
            False,
        )

    async def fake_seam(session: object, **kwargs: object) -> uuid.UUID:
        del session
        task_id = kwargs["workbench_task_id"]
        seam_calls.append(task_id)
        return versions.setdefault(task_id, uuid.uuid4())

    async def fake_submit(session: object, **kwargs: object) -> object:
        del session
        return SimpleNamespace(
            workbench_task_id=kwargs["workbench_task_id"],
            workflow_version_id=kwargs["workflow_version_id"],
            runs=(
                SimpleNamespace(
                    id=uuid.uuid4(),
                    status="queued",
                    market_code="US",
                ),
            ),
            gaps=(),
            idempotent_replay=False,
        )

    async def fake_estimate(session: object, **kwargs: object) -> object:
        del session, kwargs
        return SimpleNamespace()

    monkeypatch.setattr(ports_module, "create_workbench_task", fake_create)
    monkeypatch.setattr(
        ports_module, "create_initial_workflow_version_for_task", fake_seam
    )
    monkeypatch.setattr(ports_module, "submit_workbench_task", fake_submit)
    monkeypatch.setattr(ports_module, "estimate_run_budget", fake_estimate)
    monkeypatch.setattr(
        ports_module,
        "get_task_template",
        lambda template_id: SimpleNamespace(
            markets=("US",),
            package_tiers=("quick", "standard"),
        ),
    )
    monkeypatch.setattr(ports_module, "package_threshold_for", lambda tier: SimpleNamespace())

    request = _create_input()
    task_adapter = WorkbenchTaskAdapter(session_factory=_null_session)
    collect_adapter = WorkbenchCollectAdapter(session_factory=_null_session)
    created_view = await task_adapter.create_task(
        identity=IDENTITY,
        request=request,
        quote_id="est-1",
        budget=BudgetDecision(
            allowed=True,
            approval_required=False,
            remaining_usd=Decimal("10"),
        ),
    )
    collected = await collect_adapter.run(
        identity=IDENTITY,
        capability=SimpleNamespace(capability_id="cap-1"),
        params={
            "brand": "Brand",
            "category_id": "feeding",
            "markets": ["US"],
            "window_start": "2026-09-01",
            "window_end": "2026-09-30",
            "decision_question": "这个类目是否值得进入？",
            "acceptance_contact_id": request.acceptance_contact_id,
            "package_type": "quick",
            "seed_products": [
                "https://example.com/1",
                "https://example.com/2",
                "ID-3",
            ],
            "target_price_band": {
                "currency": "USD",
                "min_amount": "10",
                "max_amount": "30",
            },
        },
        idempotency_key=request.idempotency_key,
        budget=request.budget,
        request_id="req-1",
    )

    assert collected["task_id"] == str(created_view.task_id)
    assert seam_calls == [created_view.task_id, created_view.task_id]
    assert len(set(versions.values())) == 1


def test_workbench_error_maps_to_registered_customer_code() -> None:
    """C4 的验收联系人/幂等错误必须原码透传，未知错误收敛为 state_conflict。"""
    for code in ("acceptance_contact_not_member", "idempotency_conflict"):
        error = ports_module._customer_error_for(SimpleNamespace(code=code))
        assert error.code == code
    assert (
        ports_module._customer_error_for(SimpleNamespace(code="unmapped")).code
        == "state_conflict"
    )


def _cancel_result(*, replayed: bool) -> SimpleNamespace:
    return SimpleNamespace(
        cancelled_run_ids=(RUN_ID,),
        preserved_artifact_ids=("artifact-1",),
        cancelled_at=datetime(2026, 10, 22, tzinfo=UTC),
        replayed=replayed,
    )


async def _fake_task_row(session: object, **kwargs: object) -> object:
    del session, kwargs
    return SimpleNamespace(
        id=TASK_ID,
        status="submitted",
        markets=["US"],
        primary_market="US",
        comparison_markets=[],
        package_type="quick",
        created_at=datetime(2026, 10, 22, tzinfo=UTC),
        updated_at=datetime(2026, 10, 22, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_cancel_task_replays_same_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同键同 reason_code 重放同一结果，且只写一次任务状态。"""
    calls: list[dict[str, object]] = []
    results = (_cancel_result(replayed=False), _cancel_result(replayed=True))
    updates: list[dict[str, object]] = []

    async def fake_cancel(session: object, **kwargs: object) -> object:
        del session
        calls.append(dict(kwargs))
        return results[len(calls) - 1]

    async def fake_update(session: object, **kwargs: object) -> object:
        del session
        updates.append(dict(kwargs))
        return None

    monkeypatch.setattr(ports_module, "get_workbench_task", _fake_task_row)
    monkeypatch.setattr(ports_module, "cancel_task_runs", fake_cancel)
    monkeypatch.setattr(ports_module, "update_workbench_task_fields", fake_update)

    adapter = WorkbenchTaskAdapter(session_factory=_null_session)
    first = await adapter.cancel_task(
        identity=IDENTITY,
        task_id=TASK_ID,
        idempotency_key="cancel-1",
        reason_code="user_request",
    )
    second = await adapter.cancel_task(
        identity=IDENTITY,
        task_id=TASK_ID,
        idempotency_key="cancel-1",
        reason_code="user_request",
    )

    assert first is not None and second is not None
    assert first.cancelled_runs == (RUN_ID,)
    assert second.cancelled_runs == (RUN_ID,)
    assert calls[0]["idempotency_key"] == "cancel-1"
    assert calls[0]["reason_code"] == "user_request"
    assert calls[0] == calls[1]
    assert len(updates) == 1


@pytest.mark.asyncio
async def test_cancel_task_same_key_different_reason_is_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同键不同 reason_code 必须由 C6 返回 idempotency_conflict。"""
    updates: list[dict[str, object]] = []

    async def fake_cancel(session: object, **kwargs: object) -> object:
        del session, kwargs
        raise ports_module.CancellationError("idempotency_conflict")

    async def fake_update(session: object, **kwargs: object) -> object:
        del session
        updates.append(dict(kwargs))
        return None

    monkeypatch.setattr(ports_module, "get_workbench_task", _fake_task_row)
    monkeypatch.setattr(ports_module, "cancel_task_runs", fake_cancel)
    monkeypatch.setattr(ports_module, "update_workbench_task_fields", fake_update)

    adapter = WorkbenchTaskAdapter(session_factory=_null_session)
    with pytest.raises(CustomerToolError) as exc:
        await adapter.cancel_task(
            identity=IDENTITY,
            task_id=TASK_ID,
            idempotency_key="cancel-1",
            reason_code="ops_cleanup",
        )

    assert exc.value.code == "idempotency_conflict"
    assert updates == []


@pytest.mark.asyncio
async def test_cancel_task_concurrent_same_key_cancels_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """并发同键只产生一次取消副作用，另一个调用重放。"""
    state = {"calls": 0, "cancelled": False}
    updates: list[dict[str, object]] = []
    lock = asyncio.Lock()

    async def fake_cancel(session: object, **kwargs: object) -> object:
        del session, kwargs
        async with lock:
            state["calls"] += 1
            if state["cancelled"]:
                return _cancel_result(replayed=True)
            state["cancelled"] = True
            return _cancel_result(replayed=False)

    async def fake_update(session: object, **kwargs: object) -> object:
        del session
        updates.append(dict(kwargs))
        return None

    monkeypatch.setattr(ports_module, "get_workbench_task", _fake_task_row)
    monkeypatch.setattr(ports_module, "cancel_task_runs", fake_cancel)
    monkeypatch.setattr(ports_module, "update_workbench_task_fields", fake_update)

    adapter = WorkbenchTaskAdapter(session_factory=_null_session)
    first, second = await asyncio.gather(
        adapter.cancel_task(
            identity=IDENTITY,
            task_id=TASK_ID,
            idempotency_key="cancel-1",
            reason_code="user_request",
        ),
        adapter.cancel_task(
            identity=IDENTITY,
            task_id=TASK_ID,
            idempotency_key="cancel-1",
            reason_code="user_request",
        ),
    )

    assert first is not None and second is not None
    assert state["calls"] == 2
    assert first.cancelled_runs == second.cancelled_runs == (RUN_ID,)
    assert len(updates) == 1


def _publishable_claim_row() -> SimpleNamespace:
    return SimpleNamespace(
        claim_id=str(CLAIM_ID),
        claim_status="directional",
        evidence_grade="L3_live_single",
        review_status="approved",
        evidence_ids=(str(EVIDENCE_ID),),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("review_status", ["pending", "stale"])
async def test_get_evidence_rejects_pending_or_stale_claim(
    monkeypatch: pytest.MonkeyPatch,
    review_status: str,
) -> None:
    """C7 可发布门禁过滤 pending/stale，客户只能得到 claim_not_found。"""

    async def fake_claim(session: object, **kwargs: object) -> object:
        del session, kwargs
        return SimpleNamespace(
            id=CLAIM_ID,
            state="directional",
            evidence_grade="L3_live_single",
            review_status=review_status,
        )

    async def fake_bundle(session: object, **kwargs: object) -> object:
        del session, kwargs
        return SimpleNamespace(claims=(), evidences=())

    monkeypatch.setattr(ports_module, "get_claim", fake_claim)
    monkeypatch.setattr(
        ports_module, "load_publishable_claim_rows", fake_bundle
    )

    adapter = WorkbenchTaskAdapter(session_factory=_null_session)
    assert (
        await adapter.get_evidence(
            identity=IDENTITY,
            claim_id=str(CLAIM_ID),
        )
        is None
    )


@pytest.mark.asyncio
async def test_get_evidence_rejects_unpublishable_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """approved Claim 但证据不完整时返回 evidence_not_found。"""

    async def fake_claim(session: object, **kwargs: object) -> object:
        del session, kwargs
        return SimpleNamespace(
            id=CLAIM_ID,
            state="directional",
            evidence_grade="L3_live_single",
            review_status="approved",
        )

    async def fake_bundle(session: object, **kwargs: object) -> object:
        del session, kwargs
        return SimpleNamespace(
            claims=(_publishable_claim_row(),),
            evidences=(SimpleNamespace(claim_id=str(CLAIM_ID)),),
        )

    monkeypatch.setattr(ports_module, "get_claim", fake_claim)
    monkeypatch.setattr(
        ports_module, "load_publishable_claim_rows", fake_bundle
    )
    monkeypatch.setattr(
        ports_module,
        "validate_claim_bundle",
        lambda bundle: ["claim missing counter evidence"],
    )

    adapter = WorkbenchTaskAdapter(session_factory=_null_session)
    with pytest.raises(CustomerToolError) as exc:
        await adapter.get_evidence(
            identity=IDENTITY,
            claim_id=str(CLAIM_ID),
        )

    assert exc.value.code == "evidence_not_found"


@pytest.mark.asyncio
async def test_get_evidence_returns_only_publishable_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """通过 C7 门禁后才读取证据行并返回客户白名单字段。"""

    async def fake_claim(session: object, **kwargs: object) -> object:
        del session, kwargs
        return SimpleNamespace(
            id=CLAIM_ID,
            state="directional",
            evidence_grade="L3_live_single",
            review_status="approved",
        )

    async def fake_bundle(session: object, **kwargs: object) -> object:
        del session, kwargs
        return SimpleNamespace(
            claims=(_publishable_claim_row(),),
            evidences=(SimpleNamespace(claim_id=str(CLAIM_ID)),),
        )

    async def fake_links(session: object, **kwargs: object) -> list[object]:
        del session, kwargs
        return [
            SimpleNamespace(
                evidence_id=EVIDENCE_ID,
                evidence_grade="L3_live_single",
                role="support",
            )
        ]

    async def fake_rows(session: object, **kwargs: object) -> list[object]:
        del session, kwargs
        return [
            SimpleNamespace(
                id=EVIDENCE_ID,
                title="公开评论",
                source_url="https://example.com/post/1",
                published_at=datetime(2026, 10, 1, tzinfo=UTC),
                excerpt="text",
                evidence_grade="L3_live_single",
            )
        ]

    monkeypatch.setattr(ports_module, "get_claim", fake_claim)
    monkeypatch.setattr(
        ports_module, "load_publishable_claim_rows", fake_bundle
    )
    monkeypatch.setattr(ports_module, "validate_claim_bundle", lambda bundle: [])
    monkeypatch.setattr(ports_module, "list_evidence", fake_links)
    monkeypatch.setattr(ports_module, "load_evidence_rows", fake_rows)

    adapter = WorkbenchTaskAdapter(session_factory=_null_session)
    payload = await adapter.get_evidence(
        identity=IDENTITY,
        claim_id=str(CLAIM_ID),
    )

    assert payload is not None
    assert payload["claim_id"] == str(CLAIM_ID)
    assert payload["claim_status"] == "directional"
    assert payload["evidence_grade"] == "L3_live_single"
    assert payload["items"][0]["evidence_id"] == str(EVIDENCE_ID)
    assert payload["items"][0]["source_url"] == "https://example.com/post/1"


@pytest.mark.asyncio
async def test_task_adapter_maps_delivery_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_id = uuid.uuid4()
    artifact = SimpleNamespace(
        id=artifact_id,
        delivered_at=datetime(2026, 10, 22, tzinfo=UTC),
    )
    manifest = SimpleNamespace(
        payload={
            "manifest_id": "m-1",
            "task_id": str(TASK_ID),
            "report_artifact_id": str(artifact_id),
            "files": [],
            "access_scope": ["project"],
            "retention_class": "standard_24m",
        },
        sha256="c" * 64,
    )

    async def fake_task(session: object, **kwargs: object) -> object:
        del session, kwargs
        return SimpleNamespace(
            id=TASK_ID,
            status="submitted",
            markets=["US"],
            package_type="quick",
            task_type=None,
        )

    async def fake_runs(session: object, **kwargs: object) -> list[object]:
        del session, kwargs
        return [SimpleNamespace(id=RUN_ID, status="completed")]

    async def fake_artifact(session: object, *, workspace_id: object, run_ids: object) -> object:
        del session, workspace_id
        assert list(run_ids) == [RUN_ID]
        return artifact

    async def fake_manifest(session: object, **kwargs: object) -> object:
        del session
        assert kwargs["artifact_id"] == artifact_id
        return manifest

    monkeypatch.setattr(ports_module, "get_workbench_task", fake_task)
    monkeypatch.setattr(ports_module, "list_runs_for_task", fake_runs)
    monkeypatch.setattr(ports_module, "_latest_delivered_artifact", fake_artifact)
    monkeypatch.setattr(ports_module, "load_delivery_manifest", fake_manifest)
    monkeypatch.setattr(ports_module, "DeliveryStore", lambda root: SimpleNamespace(root=root))
    monkeypatch.setattr(
        ports_module,
        "get_settings",
        lambda: SimpleNamespace(delivery_export_dir="/tmp/delivery"),
    )

    adapter = WorkbenchTaskAdapter(session_factory=_null_session)
    payload = await adapter.get_delivery_manifest(
        identity=IDENTITY,
        task_id=TASK_ID,
        manifest_version=None,
    )
    assert payload["manifest_id"] == "m-1"
    assert payload["manifest_sha256"] == "c" * 64
    assert payload["published_at"].startswith("2026-10-22")


@pytest.mark.asyncio
async def test_audit_adapter_never_sends_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[dict[str, object]] = []

    async def fake_audit(session: object, **kwargs: object) -> None:
        del session
        recorded.append(dict(kwargs))

    monkeypatch.setattr(ports_module, "append_audit_event", fake_audit)
    sink = SqlAlchemyAuditSink(session_factory=_null_session)
    await sink.record(
        AuditEvent(
            event_type="mcp.tool_call",
            workspace_id=IDENTITY.workspace_id,
            project_id=IDENTITY.project_id,
            key_id=IDENTITY.key_id,
            request_id="req-1",
            tool_name="get_task",
            outcome="success",
            error_code=None,
            capability_id=None,
            duration_ms=12,
        )
    )
    details = recorded[0]["details"]
    assert set(details) == {"tool_name", "capability_id", "error_code", "duration_ms"}
    assert recorded[0]["result"] == "success"
    assert recorded[0]["actor_type"] == "project_key"
    assert "dih_" not in str(recorded[0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_ports.py -q`

Expected: `FAILED` with `ImportError` or `AttributeError`，因为 `ports.py` 还没有生产适配器。

- [ ] **Step 3: Add the thin production adapters to `ports.py`**

在 `apps/api/src/data_intelligence_hub/mcp_runtime/customer/ports.py` 的 `__all__` 之前追加以下代码，并用代码块末尾的 `__all__` 替换 Task 4 的 `__all__`。不新建 `adapters.py`，不新建任何 `services.customer_*` 模块。

```python
# ---------------------------------------------------------------------------
# 生产适配器（Task 7）
#
# 只做字段映射、只读查询与公开服务调用。预算、Claim、报告与采集规则仍属于
# C4/C5/C6/C7/C8/C9/C10。任何上游函数缺失时，Step 0 的导入预检先失败。
# ---------------------------------------------------------------------------

import uuid as _uuid
from collections.abc import Mapping as _Mapping
from datetime import UTC as _UTC, date as _date, datetime as _datetime, timedelta as _timedelta
from decimal import Decimal as _Decimal
from functools import lru_cache as _lru_cache
from typing import Any as _Any

from sqlalchemy import select as _select
from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession, async_sessionmaker as _async_sessionmaker

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.mcp_runtime.customer.errors import CustomerToolError
from data_intelligence_hub.mcp_runtime.customer.rate_limit import (
    AuditRequestLimiter,
    LeasePolicy,
)
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.repositories.claims import (
    get_claim,
    list_evidence,
    load_evidence_rows,
)
from data_intelligence_hub.repositories.dataset_quality import (
    get_market_assessment,
    list_data_gaps,
)
from data_intelligence_hub.repositories.project_api_keys import (
    consume_daily_quota,
    find_by_id,
)
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.quota_accounts import (
    get_or_create_quota_account,
)
from data_intelligence_hub.repositories.workspaces import get_workspace_by_id
from data_intelligence_hub.repositories.workbench_tasks import (
    get_workbench_task,
    list_runs_for_task,
    update_workbench_task_fields,
)
from data_intelligence_hub.schemas.workbench import (
    WorkbenchTaskCreateRequest,
    WorkbenchWindow,
)
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.budget_service import (
    BudgetApprovalRequiredError,
    estimate_run_budget,
)
from data_intelligence_hub.services.claims import (
    ClaimContractBundle,
    load_publishable_claim_rows,
    validate_claim_bundle,
)
from data_intelligence_hub.services.delivery.service import load_delivery_manifest
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.pricing import (
    ToolNotPricedError,
    price_book_fingerprint,
    quote,
)
from data_intelligence_hub.services.run_service import (
    CancellationError,
    RunCancellationResult,
    cancel_task_runs,
)
from data_intelligence_hub.services.workbench.errors import WorkbenchError
from data_intelligence_hub.services.workbench.initial_version import (
    create_initial_workflow_version_for_task,
)
from data_intelligence_hub.services.workbench.markets import market_role_for
from data_intelligence_hub.services.workbench.submission import submit_workbench_task
from data_intelligence_hub.services.workbench.tasks import create_workbench_task
from data_intelligence_hub.services.workbench_templates import (
    get_task_template,
    list_task_templates,
    template_capability_ids,
)
from data_intelligence_hub.tool_catalog.evidence_thresholds import package_threshold_for
from data_intelligence_hub.tool_catalog.markets import FORMAL_MARKETS
from data_intelligence_hub.tool_catalog.service import find_tool, get_tool_catalog


def _attr(item: object, name: str, default: _Any = None) -> _Any:
    if isinstance(item, _Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


_CUSTOMER_WORKBENCH_CODES = frozenset(
    {
        "idempotency_conflict",
        "acceptance_contact_not_member",
        "package_type_invalid",
        "comparison_markets_exceeded",
        "budget_invalid",
        "market_unsupported",
        "task_not_found",
    }
)


def _customer_error_for(exc: WorkbenchError) -> CustomerToolError:
    """把 C4 领域错误映射为客户 MCP 已登记错误码；未知码收敛为 state_conflict。"""
    code = exc.code if exc.code in _CUSTOMER_WORKBENCH_CODES else "state_conflict"
    return CustomerToolError(code)


def _decimal(value: object) -> _Decimal:
    return _Decimal(str(value))


def _iso(value: object) -> str:
    if isinstance(value, _datetime):
        return value.isoformat()
    return "" if value is None else str(value)


def _enum_value(value: object) -> str:
    """把 C7 的枚举或字符串统一为输出字符串。"""
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def _is_creator_cookie_tool(tool: object) -> bool:
    if "creator_cookie" in str(_attr(tool, "tool_id", "")):
        return True
    return any(
        str(_attr(parameter, "name", "")) == "creator_cookie"
        for parameter in (_attr(tool, "parameters", ()) or ())
    )


def _tool_input_schema(tool: object) -> dict[str, object]:
    properties: dict[str, object] = {}
    required: list[str] = []
    for parameter in _attr(tool, "parameters", ()) or ():
        name = str(_attr(parameter, "name", ""))
        if not name:
            continue
        properties[name] = {
            "type": str(_attr(parameter, "value_type", "string") or "string"),
            "description": str(_attr(parameter, "description", "") or ""),
        }
        if bool(_attr(parameter, "required", False)):
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}


def _quote_cost(tool_id: str) -> _Decimal:
    try:
        return _decimal(quote(tool_id).total_cost_usd)
    except ToolNotPricedError:
        return _Decimal("0")


def _capability_view(tool: object, *, markets: tuple[str, ...]) -> CapabilityView:
    availability = _attr(_attr(tool, "availability_view"), "availability", "")
    return CapabilityView(
        capability_id=str(_attr(tool, "tool_id")),
        display_name=str(_attr(tool, "label", "")),
        data_domain=str(_attr(tool, "category", "")),
        markets=markets,
        why_this=str(_attr(tool, "description", "")),
        cost_estimate_usd=_quote_cost(str(_attr(tool, "tool_id"))),
        executable=bool(_attr(tool, "executable", False)) and str(availability) != "disabled",
        input_schema=_tool_input_schema(tool),
        output_schema={},
    )


class SqlAlchemyKeyStatus:
    async def is_active(self, key_id: uuid.UUID) -> bool:
        async with async_session_factory() as session:
            record = await find_by_id(session, key_id)
            if record is None or record.revoked_at is not None or record.status != "active":
                return False
            if record.expires_at is not None and record.expires_at <= _datetime.now(_UTC):
                return False
            return True

    async def validate_binding(
        self,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> bool:
        async with async_session_factory() as session:
            if await get_workspace_by_id(session, workspace_id) is None:
                return False
            return await get_project(session, workspace_id, project_id) is not None


class SqlAlchemyQuota:
    async def consume(self, key_id: uuid.UUID) -> bool:
        async with async_session_factory() as session:
            allowed = await consume_daily_quota(session, key_id)
            await session.commit()
            return allowed


class ToolCatalogCapabilityAdapter:
    """只读投影 `tool_catalog.service` 与 C8 模板，不复制目录。"""

    def __init__(
        self,
        *,
        session_factory: _async_sessionmaker[_AsyncSession] = async_session_factory,
    ) -> None:
        self._session_factory = session_factory

    async def _catalog(
        self,
    ) -> tuple[object, tuple[str, ...], tuple[str, ...]]:
        async with self._session_factory() as session:
            catalog = await get_tool_catalog(session)
        templates = tuple(list_task_templates())
        # C8 `template_capability_ids(template_id)` 是模板侧唯一白名单读取入口；
        # `TaskTemplate.capability_allowlist` 只是它的 dataclass 字段。
        # 函数返回空时保持空集合，调用方 fail-closed；不得用 core_domains
        # 或工具目录 category 推导第二套模板白名单。
        template_ids = tuple(
            dict.fromkeys(
                str(capability_id)
                for template in templates
                for capability_id in template_capability_ids(
                    str(_attr(template, "template_id", ""))
                )
            )
        )
        markets = tuple(
            dict.fromkeys(
                str(market)
                for template in templates
                for market in (_attr(template, "markets", ()) or ())
            )
        )
        return catalog, template_ids, markets or tuple(FORMAL_MARKETS)

    async def template_capability_ids(self) -> tuple[str, ...]:
        _catalog, template_ids, _markets = await self._catalog()
        return template_ids

    async def list_capabilities(
        self,
        *,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        capability_ids: tuple[str, ...],
        query: str | None,
        markets: tuple[str, ...],
        data_domains: tuple[str, ...],
        limit: int,
    ) -> CapabilityCatalogView:
        del workspace_id, project_id
        catalog, template_ids, catalog_markets = await self._catalog()
        requested_markets = tuple(str(market) for market in markets)
        if requested_markets and not set(requested_markets).issubset(
            set(catalog_markets)
        ):
            return CapabilityCatalogView(
                catalog_digest=str(_attr(catalog, "catalog_digest", "")),
                capabilities=(),
            )
        view_markets = requested_markets or catalog_markets
        allowed = {str(item) for item in capability_ids} & set(template_ids)
        if not allowed:
            # 空交集是 fail-closed：不返回工具目录中的任何能力。
            return CapabilityCatalogView(
                catalog_digest=str(_attr(catalog, "catalog_digest", "")),
                capabilities=(),
            )
        catalog_tools = tuple(_attr(catalog, "tools", ()) or ())
        known_categories = {
            str(_attr(tool, "category", "")) for tool in catalog_tools
        }
        # data_domains 与工具 category 不是同一命名空间；只有实际命中时才过滤。
        domain_filter = {str(domain) for domain in data_domains} & known_categories
        selected: list[CapabilityView] = []
        for tool in catalog_tools:
            tool_id = str(_attr(tool, "tool_id"))
            if tool_id not in allowed:
                continue
            if _is_creator_cookie_tool(tool):
                continue
            if domain_filter and str(_attr(tool, "category", "")) not in domain_filter:
                continue
            if query:
                haystack = (
                    f"{tool_id} {_attr(tool, 'label', '')} {_attr(tool, 'description', '')}"
                ).lower()
                if query.lower() not in haystack:
                    continue
            selected.append(_capability_view(tool, markets=view_markets))
            if len(selected) >= limit:
                break
        return CapabilityCatalogView(
            catalog_digest=str(_attr(catalog, "catalog_digest", "")),
            capabilities=tuple(selected),
        )

    async def resolve_capability(
        self,
        *,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        capability_id: str,
    ) -> CapabilityView | None:
        del workspace_id, project_id
        catalog, template_ids, catalog_markets = await self._catalog()
        if capability_id not in template_ids:
            return None
        try:
            tool = find_tool(catalog, capability_id)
        except KeyError:
            return None
        if _is_creator_cookie_tool(tool):
            return None
        return _capability_view(tool, markets=catalog_markets)


class QuotaBudgetAdapter:
    """C5 额度只读判定。影子模式不阻断，但保留计算值。"""

    def __init__(
        self,
        *,
        session_factory: _async_sessionmaker[_AsyncSession] = async_session_factory,
        enforce: bool | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._enforce = enforce

    async def check(
        self,
        *,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        estimated_cost_usd: _Decimal,
    ) -> BudgetDecision:
        async with self._session_factory() as session:
            account = await get_or_create_quota_account(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                period_start=_date.today(),
            )
            await session.commit()
        remaining = _decimal(_attr(account, "remaining_usd", "0") or "0")
        enforce = (
            get_settings().budget_enforcement_enabled
            if self._enforce is None
            else self._enforce
        )
        allowed = (not enforce) or remaining >= estimated_cost_usd
        return BudgetDecision(
            allowed=allowed,
            approval_required=not allowed,
            remaining_usd=remaining,
        )


def _validate_template_request(request: EstimateTaskInput | CreateTaskInput) -> object:
    try:
        template = get_task_template(request.template_id)
    except KeyError as exc:
        raise CustomerToolError("tool_not_executable") from exc
    allowed_markets = {
        str(market) for market in (_attr(template, "markets", ()) or ())
    }
    if allowed_markets and (
        request.primary_market not in allowed_markets
        or any(
            market not in allowed_markets for market in request.compare_markets
        )
    ):
        raise CustomerToolError("market_unsupported")
    tiers = {str(tier) for tier in (_attr(template, "package_tiers", ()) or ())}
    if tiers and request.package_type not in tiers:
        raise CustomerToolError("tool_not_executable")
    package_threshold_for(request.package_type)
    return template


def _package_type_for(task: object) -> str:
    for field in ("package_type", "task_type"):
        value = str(_attr(task, field, "") or "")
        if value in ("quick", "standard"):
            return value
    return "standard"


def _market_role(task: object, market_code: object) -> str:
    """字段映射到 C4 的 `market_role_for`；角色规则归 C4。"""
    return market_role_for(
        primary_market=str(_attr(task, "primary_market", "") or ""),
        comparison_markets=tuple(
            str(market)
            for market in (_attr(task, "comparison_markets", ()) or ())
        ),
        market_code=str(market_code),
    )


def _base_task_view(
    task: object,
    *,
    package_type: str,
    runs: tuple[object, ...] = (),
    markets: tuple[dict[str, object], ...] | None = None,
    quote_id: str | None = None,
) -> TaskView:
    if markets is None:
        markets = tuple(
            {"market_code": str(market)}
            for market in (_attr(task, "markets", ()) or ())
        )
    return TaskView(
        task_id=_attr(task, "id"),
        status=str(_attr(task, "status", "draft")),
        package_type=package_type,
        markets=markets,
        plan_version_id=None,
        run_ids=tuple(_attr(run, "id") for run in runs),
        quote_id=quote_id,
        created_at=_attr(task, "created_at"),
        updated_at=_attr(task, "updated_at"),
    )


def _submission_task_view(
    task: object,
    result: object,
    *,
    package_type: str,
    quote_id: str,
) -> TaskView:
    runs = tuple(_attr(result, "runs", ()) or ())
    return TaskView(
        task_id=_attr(result, "workbench_task_id", _attr(task, "id")),
        status="submitted" if runs else str(_attr(task, "status", "draft")),
        package_type=package_type,
        markets=tuple(
            {
                "market_code": str(_attr(run, "market_code", "")),
                "market_role": _market_role(
                    task, _attr(run, "market_code", "")
                ),
                "run_id": str(_attr(run, "id")),
                "status": str(_attr(run, "status", "")),
            }
            for run in runs
        ),
        plan_version_id=_attr(result, "workflow_version_id"),
        run_ids=tuple(_attr(run, "id") for run in runs),
        quote_id=quote_id,
        created_at=_attr(task, "created_at"),
        updated_at=_attr(task, "updated_at"),
    )


class WorkbenchTaskAdapter:
    """C4 任务单、C5 预算、C6 取消、C7 证据门禁、C8 模板与质量、C9/C10 交付的薄组合。"""

    def __init__(
        self,
        *,
        session_factory: _async_sessionmaker[_AsyncSession] = async_session_factory,
    ) -> None:
        self._session_factory = session_factory

    async def estimate_task(
        self,
        *,
        identity: CustomerIdentity,
        request: EstimateTaskInput,
    ) -> TaskEstimateView:
        _validate_template_request(request)
        breakdown: list[dict[str, object]] = []
        total = _Decimal("0")
        for capability_id in identity.capability_allowlist:
            try:
                price = quote(
                    capability_id,
                    records_count=request.budget.max_records or 0,
                )
            except ToolNotPricedError as exc:
                raise CustomerToolError("tool_not_priced") from exc
            amount = _decimal(price.total_cost_usd)
            total += amount
            breakdown.append(
                {
                    "capability_id": capability_id,
                    "label": capability_id,
                    "amount_usd": str(amount),
                    "currency": "USD",
                }
            )
        if not breakdown:
            total = request.budget.max_cost_usd
        return TaskEstimateView(
            estimate_id=f"est-{_uuid.uuid4().hex}",
            max_cost_usd=min(total, request.budget.max_cost_usd),
            currency="USD",
            price_book_version=price_book_fingerprint(),
            expires_at=_datetime.now(_UTC) + _timedelta(minutes=30),
            breakdown=tuple(breakdown),
        )

    async def create_task(
        self,
        *,
        identity: CustomerIdentity,
        request: CreateTaskInput,
        quote_id: str,
        budget: BudgetDecision,
    ) -> TaskView:
        if not budget.allowed:
            raise CustomerToolError("approval_required")
        _validate_template_request(request)
        markets = (request.primary_market, *request.compare_markets)
        try:
            # 客户链没有人类会话；用验收联系人作为任务创建者，C4 复核其为 owner/admin。
            creator = _uuid.UUID(request.acceptance_contact_id)
        except ValueError as exc:
            raise CustomerToolError("invalid_request") from exc
        payload = WorkbenchTaskCreateRequest(
            brand=request.brand,
            category=request.category_id,
            competitors=list(request.competitors),
            package_type=request.package_type,
            primary_market=request.primary_market,
            comparison_markets=list(request.compare_markets),
            seed_products=list(request.seed_products),
            target_price_band=request.target_price_band,
            acceptance_contact_id=creator,
            max_cost_usd=request.budget.max_cost_usd,
            max_pages=request.budget.max_pages,
            max_records=request.budget.max_records,
            locale_by_market={market: "en" for market in markets},
            window=WorkbenchWindow(
                start=request.window_start,
                end=request.window_end,
            ),
            decision_question=request.decision_question,
            does_not_answer=list(request.does_not_answer),
        )
        try:
            async with self._session_factory() as session:
                task, _replayed = await create_workbench_task(
                    session,
                    workspace_id=identity.workspace_id,
                    project_id=identity.project_id,
                    created_by_user_id=creator,
                    payload=payload,
                    idempotency_key=request.idempotency_key,
                )
                # 计划版本只由 C4 的既有 planner 接缝生成或复用，C13 不复制计划逻辑。
                workflow_version_id = await create_initial_workflow_version_for_task(
                    session,
                    workspace_id=identity.workspace_id,
                    project_id=identity.project_id,
                    created_by_user_id=creator,
                    workbench_task_id=_attr(task, "id"),
                    idempotency_key=request.idempotency_key,
                )
                result = await submit_workbench_task(
                    session,
                    workspace_id=identity.workspace_id,
                    project_id=identity.project_id,
                    workbench_task_id=_attr(task, "id"),
                    workflow_version_id=workflow_version_id,
                    idempotency_key=request.idempotency_key,
                )
                await session.refresh(task)
                return _submission_task_view(
                    task,
                    result,
                    package_type=request.package_type,
                    quote_id=quote_id,
                )
        except WorkbenchError as exc:
            raise _customer_error_for(exc) from exc

    async def get_task(
        self,
        *,
        identity: CustomerIdentity,
        task_id: uuid.UUID,
    ) -> TaskView | None:
        async with self._session_factory() as session:
            task = await get_workbench_task(
                session,
                workspace_id=identity.workspace_id,
                task_id=task_id,
                project_id=identity.project_id,
            )
            if task is None:
                return None
            runs = await list_runs_for_task(
                session,
                workspace_id=identity.workspace_id,
                task_id=task_id,
            )
            market_rows: list[dict[str, object]] = []
            for market in _attr(task, "markets", ()) or ():
                assessment = await get_market_assessment(
                    session,
                    task_id=task_id,
                    market=str(market),
                )
                gaps = await list_data_gaps(
                    session,
                    task_id=task_id,
                    market=str(market),
                )
                market_rows.append(
                    {
                        "market_code": str(market),
                        "market_role": _market_role(task, market),
                        "quality_status": _attr(
                            assessment,
                            "quality_status",
                            _attr(assessment, "status", None),
                        ),
                        "data_gaps": [
                            {
                                "data_domain": _attr(gap, "data_domain"),
                                "reason_code": _attr(gap, "reason_code"),
                                "severity": _attr(gap, "severity"),
                            }
                            for gap in gaps
                        ],
                    }
                )
            return _base_task_view(
                task,
                package_type=_package_type_for(task),
                runs=tuple(runs),
                markets=tuple(market_rows),
            )

    async def cancel_task(
        self,
        *,
        identity: CustomerIdentity,
        task_id: uuid.UUID,
        idempotency_key: str,
        reason_code: str,
    ) -> TaskView | None:
        async with self._session_factory() as session:
            task = await get_workbench_task(
                session,
                workspace_id=identity.workspace_id,
                task_id=task_id,
                project_id=identity.project_id,
            )
            if task is None:
                return None
            try:
                # 取消幂等与取消副作用归 C6；C13 只透传两个参数并映射结果。
                result = await cancel_task_runs(
                    session,
                    workspace_id=identity.workspace_id,
                    project_id=identity.project_id,
                    task_id=task_id,
                    idempotency_key=idempotency_key,
                    reason_code=reason_code,
                )
            except CancellationError as exc:
                code = (
                    exc.code
                    if exc.code in ("idempotency_conflict", "state_conflict")
                    else "state_conflict"
                )
                raise CustomerToolError(code) from exc
            if not result.replayed:
                await update_workbench_task_fields(
                    session,
                    workspace_id=identity.workspace_id,
                    task_id=task_id,
                    values={"status": "cancelled"},
                )
            await session.commit()
            return TaskView(
                task_id=task_id,
                status="cancelled",
                package_type=_package_type_for(task),
                markets=tuple(
                    {
                        "market_code": str(market),
                        "market_role": _market_role(task, market),
                    }
                    for market in (_attr(task, "markets", ()) or ())
                ),
                cancelled_runs=tuple(result.cancelled_run_ids),
                preserved_artifacts=tuple(result.preserved_artifact_ids),
                cancelled_at=result.cancelled_at,
            )

    async def get_delivery_manifest(
        self,
        *,
        identity: CustomerIdentity,
        task_id: uuid.UUID,
        manifest_version: int | None,
    ) -> Mapping[str, _Any] | None:
        async with self._session_factory() as session:
            task = await get_workbench_task(
                session,
                workspace_id=identity.workspace_id,
                task_id=task_id,
                project_id=identity.project_id,
            )
            if task is None:
                return None
            runs = await list_runs_for_task(
                session,
                workspace_id=identity.workspace_id,
                task_id=task_id,
            )
            artifact = await _latest_delivered_artifact(
                session,
                workspace_id=identity.workspace_id,
                run_ids=[_attr(run, "id") for run in runs],
            )
            if artifact is None:
                return None
            store = DeliveryStore(get_settings().delivery_export_dir)
            manifest = await load_delivery_manifest(
                session,
                workspace_id=identity.workspace_id,
                artifact_id=_attr(artifact, "id"),
                store=store,
            )
            payload = dict(_attr(manifest, "payload", {}) or {})
            if manifest_version is not None:
                current = str(payload.get("report_version", ""))
                if current.isdigit() and int(current) != manifest_version:
                    return None
            payload["manifest_sha256"] = str(_attr(manifest, "sha256", ""))
            payload["published_at"] = _iso(_attr(artifact, "delivered_at"))
            return payload

    async def get_evidence(
        self,
        *,
        identity: CustomerIdentity,
        claim_id: str,
    ) -> Mapping[str, _Any] | None:
        try:
            parsed = _uuid.UUID(claim_id)
        except ValueError as exc:
            raise CustomerToolError("invalid_request") from exc
        async with self._session_factory() as session:
            claim = await get_claim(
                session,
                workspace_id=identity.workspace_id,
                claim_id=parsed,
            )
            if claim is None:
                return None
            # C7 可发布门禁：只返回 approved 且内容版本一致的 Claim。
            # pending/stale/draft/rejected 或同工作区其他项目的 Claim 都不在
            # bundle 中，统一按 claim_not_found 处理，不泄露草稿内容。
            bundle = await load_publishable_claim_rows(
                session,
                workspace_id=identity.workspace_id,
                project_id=identity.project_id,
            )
            claim_row = next(
                (
                    item
                    for item in bundle.claims
                    if str(item.claim_id) == str(parsed)
                ),
                None,
            )
            if claim_row is None:
                return None
            issues = validate_claim_bundle(
                ClaimContractBundle(
                    claims=(claim_row,),
                    evidences=tuple(
                        evidence
                        for evidence in bundle.evidences
                        if str(evidence.claim_id) == str(parsed)
                    ),
                )
            )
            if issues:
                raise CustomerToolError("evidence_not_found")
            links = await list_evidence(session, claim_id=_attr(claim, "id"))
            evidence_ids = [_attr(link, "evidence_id") for link in links]
            rows = await load_evidence_rows(
                session,
                workspace_id=identity.workspace_id,
                project_id=identity.project_id,
                evidence_ids=evidence_ids,
            )
            by_id = {
                str(_attr(row, "id", _attr(row, "evidence_id"))): row
                for row in rows
            }
            items: list[dict[str, object]] = []
            for link in links:
                row = by_id.get(str(_attr(link, "evidence_id")))
                if row is None:
                    continue
                items.append(
                    {
                        "evidence_id": str(_attr(link, "evidence_id")),
                        "title": _attr(row, "title", ""),
                        "source_url": _attr(
                            row,
                            "source_url",
                            _attr(row, "url", ""),
                        ),
                        "published_at": _iso(_attr(row, "published_at", None)),
                        "excerpt": _attr(row, "excerpt", ""),
                        "grade": _attr(
                            link,
                            "evidence_grade",
                            _attr(row, "evidence_grade", ""),
                        ),
                        "role": _attr(link, "role", ""),
                    }
                )
            return {
                "claim_id": str(claim_row.claim_id),
                "claim_status": _enum_value(claim_row.claim_status),
                "evidence_grade": _enum_value(claim_row.evidence_grade),
                "items": items,
            }


async def _latest_delivered_artifact(
    session: _AsyncSession,
    *,
    workspace_id: uuid.UUID,
    run_ids: list[uuid.UUID],
) -> object | None:
    """只读定位任务最新交付产物。manifest 语义仍由 C10 实现。"""
    if not run_ids:
        return None
    result = await session.execute(
        _select(ReportArtifact)
        .where(
            ReportArtifact.workspace_id == workspace_id,
            ReportArtifact.run_id.in_(tuple(run_ids)),
            ReportArtifact.delivery_status == "delivered",
        )
        .order_by(ReportArtifact.delivered_at.desc(), ReportArtifact.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


def _collect_task_request(
    params: Mapping[str, _Any],
    capability: CapabilityView,
    budget: BudgetInput,
) -> tuple[uuid.UUID, WorkbenchTaskCreateRequest]:
    required = (
        "brand",
        "category_id",
        "markets",
        "window_start",
        "window_end",
        "decision_question",
        "acceptance_contact_id",
    )
    if any(not params.get(key) for key in required):
        raise CustomerToolError("invalid_request")
    markets_value = params["markets"]
    if isinstance(markets_value, str) or not isinstance(
        markets_value, (list, tuple)
    ):
        raise CustomerToolError("invalid_request")
    markets = tuple(str(market) for market in markets_value)
    if not markets:
        raise CustomerToolError("market_unsupported")
    package_type = str(params.get("package_type", "quick"))
    if package_type not in ("quick", "standard"):
        raise CustomerToolError("package_type_invalid")
    seed_products_value = params.get("seed_products", ())
    if isinstance(seed_products_value, str) or not isinstance(
        seed_products_value, (list, tuple)
    ):
        raise CustomerToolError("invalid_request")
    target_price_band_value = params.get("target_price_band")
    if target_price_band_value is not None and not isinstance(
        target_price_band_value, _Mapping
    ):
        raise CustomerToolError("invalid_request")
    try:
        window = WorkbenchWindow(
            start=_date.fromisoformat(str(params["window_start"])),
            end=_date.fromisoformat(str(params["window_end"])),
        )
        creator = _uuid.UUID(str(params["acceptance_contact_id"]))
    except (TypeError, ValueError) as exc:
        raise CustomerToolError("invalid_request") from exc
    payload = WorkbenchTaskCreateRequest(
        brand=str(params["brand"]),
        category=str(params["category_id"]),
        competitors=[str(item) for item in params.get("competitors", ())],
        package_type=package_type,
        primary_market=markets[0],
        comparison_markets=list(markets[1:]),
        seed_products=[str(item) for item in seed_products_value],
        target_price_band=(
            dict(target_price_band_value)
            if target_price_band_value is not None
            else None
        ),
        acceptance_contact_id=creator,
        max_cost_usd=budget.max_cost_usd,
        max_pages=budget.max_pages,
        max_records=budget.max_records,
        locale_by_market={
            market: str(params.get("locale", "en")) for market in markets
        },
        window=window,
        decision_question=str(params["decision_question"]),
        does_not_answer=[
            str(item) for item in params.get("does_not_answer", ())
        ],
    )
    del capability
    return creator, payload


class WorkbenchCollectAdapter:
    """C4 建单与提交、C5 预算估算的薄组合；不实例化 collector。"""

    def __init__(
        self,
        *,
        session_factory: _async_sessionmaker[_AsyncSession] = async_session_factory,
    ) -> None:
        self._session_factory = session_factory

    async def run(
        self,
        *,
        identity: CustomerIdentity,
        capability: CapabilityView,
        params: Mapping[str, _Any],
        idempotency_key: str,
        budget: BudgetInput,
        request_id: str,
    ) -> Mapping[str, _Any]:
        del request_id
        creator, payload = _collect_task_request(params, capability, budget)
        try:
            async with self._session_factory() as session:
                task, _replayed = await create_workbench_task(
                    session,
                    workspace_id=identity.workspace_id,
                    project_id=identity.project_id,
                    created_by_user_id=creator,
                    payload=payload,
                    idempotency_key=idempotency_key,
                )
                workflow_version_id = await create_initial_workflow_version_for_task(
                    session,
                    workspace_id=identity.workspace_id,
                    project_id=identity.project_id,
                    created_by_user_id=creator,
                    workbench_task_id=_attr(task, "id"),
                    idempotency_key=idempotency_key,
                )
                result = await submit_workbench_task(
                    session,
                    workspace_id=identity.workspace_id,
                    project_id=identity.project_id,
                    workbench_task_id=_attr(task, "id"),
                    workflow_version_id=workflow_version_id,
                    idempotency_key=idempotency_key,
                )
                await session.refresh(task)
                runs = tuple(_attr(result, "runs", ()) or ())
                if not runs:
                    raise CustomerToolError("market_unsupported")
                run = runs[0]
                try:
                    await estimate_run_budget(
                        session,
                        run_id=_attr(run, "id"),
                        endpoint_type=capability.capability_id,
                        records_count=budget.max_records or 0,
                    )
                except ToolNotPricedError as exc:
                    raise CustomerToolError("tool_not_priced") from exc
                except BudgetApprovalRequiredError as exc:
                    raise CustomerToolError("approval_required") from exc
                await session.commit()
                return {
                    "run_id": str(_attr(run, "id")),
                    "task_id": str(_attr(task, "id")),
                    "status": str(_attr(run, "status", "queued")),
                    "accepted_at": _iso(
                        _attr(task, "created_at", _datetime.now(_UTC))
                    ),
                }
        except WorkbenchError as exc:
            raise _customer_error_for(exc) from exc


class SqlAlchemyAuditSink:
    def __init__(
        self,
        *,
        session_factory: _async_sessionmaker[_AsyncSession] = async_session_factory,
    ) -> None:
        self._session_factory = session_factory

    async def record(self, event: AuditEvent) -> None:
        action = (
            "mcp.tool_call.denied"
            if event.outcome == "denied"
            else "mcp.tool_call.finished"
        )
        async with self._session_factory() as session:
            await append_audit_event(
                session,
                workspace_id=event.workspace_id,
                project_id=event.project_id,
                actor_user_id=None,
                actor_type="project_key",
                action=action,
                resource_type="mcp_tool",
                resource_id=event.request_id,
                request_id=event.request_id,
                result=event.outcome,
                details={
                    "tool_name": event.tool_name,
                    "capability_id": event.capability_id,
                    "error_code": event.error_code,
                    "duration_ms": event.duration_ms,
                },
            )
            await session.commit()


@_lru_cache(maxsize=1)
def get_ports() -> CustomerPorts:
    settings = get_settings()
    return CustomerPorts(
        keys=SqlAlchemyKeyStatus(),
        quota=SqlAlchemyQuota(),
        capabilities=ToolCatalogCapabilityAdapter(),
        budget=QuotaBudgetAdapter(enforce=settings.budget_enforcement_enabled),
        tasks=WorkbenchTaskAdapter(),
        collect=WorkbenchCollectAdapter(),
        audit=SqlAlchemyAuditSink(),
        limiter=AuditRequestLimiter(
            async_session_factory,
            LeasePolicy(
                per_minute=settings.mcp_customer_rate_per_minute,
                concurrent=settings.mcp_customer_concurrent_calls,
            ),
        ),
    )


__all__ = [
    "AuditEvent",
    "AuditPort",
    "BudgetDecision",
    "BudgetPort",
    "CapabilityCatalogView",
    "CapabilityPort",
    "CapabilityView",
    "CollectPort",
    "CustomerPorts",
    "KeyStatusPort",
    "QuotaBudgetAdapter",
    "QuotaPort",
    "RequestLimiterPort",
    "SqlAlchemyAuditSink",
    "SqlAlchemyKeyStatus",
    "SqlAlchemyQuota",
    "TaskEstimateView",
    "TaskPort",
    "TaskView",
    "ToolCatalogCapabilityAdapter",
    "WorkbenchCollectAdapter",
    "WorkbenchTaskAdapter",
    "get_ports",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_ports.py -q`

Expected: `16 passed`（新增 C8 模板白名单、取消同键/异键/并发、get_evidence pending/stale 与 C7 门禁用例）。

再跑 Task 6 的工具测试，确认 `get_ports` 的新位置没有破坏工具注册：

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_tools.py -q`

Expected: PASS。若失败，检查 `mcp_runtime/customer/ports.py` 的 `__all__` 是否包含 `get_ports`，以及 `authorize.py`、`middleware.py` 是否都从 `ports` 导入。

- [ ] **Step 5: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
git add apps/api/src/data_intelligence_hub/mcp_runtime/customer/ports.py \
        apps/api/tests/unit/test_customer_mcp_ports.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(customer-mcp): wire ports to C4 C5 C6 C7 C8 C9 C10 public services"
```

---

### Task 8: `/mcp/customer` 挂载、传输安全与生命周期

**Files:**
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/app.py`
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/customer/__init__.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py`
- Test: `apps/api/tests/unit/test_customer_mcp_mount.py`

**Interfaces:**
- Consumes: `customer_mcp_app`、现有内部 `mcp_app` 与 `BearerTokenMiddleware`。
- Produces: `CUSTOMER_MCP_TRANSPORT_SECURITY`、`customer_mcp_app`、`customer_asgi_app`、挂载常量 `CUSTOMER_MCP_PATH = "/mcp/customer"`。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/unit/test_customer_mcp_mount.py`:

```python
from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.mcp_runtime.customer.app import (
    CUSTOMER_MCP_PATH,
    CUSTOMER_MCP_TRANSPORT_SECURITY,
    customer_asgi_app,
)


def test_customer_path_is_contract_path() -> None:
    assert CUSTOMER_MCP_PATH == "/mcp/customer"


def test_transport_security_does_not_allow_wildcard_hosts() -> None:
    assert "*" not in CUSTOMER_MCP_TRANSPORT_SECURITY.allowed_hosts
    assert "scrapy.luteos.com" in CUSTOMER_MCP_TRANSPORT_SECURITY.allowed_hosts
    assert "scrapy.lute-tlz-dddd.top" in CUSTOMER_MCP_TRANSPORT_SECURITY.allowed_hosts


def test_customer_app_requires_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAPY_MCP_CUSTOMER_ENABLED", "true")
    get_settings.cache_clear()
    try:
        app = Starlette(routes=[Mount(CUSTOMER_MCP_PATH, app=customer_asgi_app)])
        client = TestClient(app)
        response = client.post(
            CUSTOMER_MCP_PATH,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
    finally:
        get_settings.cache_clear()
    assert response.status_code == 401
    assert response.json() == {"detail": "project_key_invalid"}


def test_internal_mcp_mount_is_not_replaced() -> None:
    source = (
        __import__("pathlib").Path(__file__)
        .resolve()
        .parents[4]
        / "apps"
        / "api"
        / "src"
        / "data_intelligence_hub"
        / "main.py"
    ).read_text(encoding="utf-8")
    assert 'app.mount("/mcp/customer"' in source
    assert 'app.mount("/mcp",' in source
    assert "McpAudienceRouter" not in source
    assert "audience" not in source
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_mount.py -q`

Expected: FAIL，模块不存在或 `CUSTOMER_MCP_PATH` 不存在。

- [ ] **Step 3: 写客户 app**

`apps/api/src/data_intelligence_hub/mcp_runtime/customer/app.py`:

```python
"""客户 MCP 的 ASGI app 与传输安全。

客户入口固定 `/mcp/customer`。内部 `/mcp` 不经过本模块。
"""

from __future__ import annotations

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from data_intelligence_hub.mcp_runtime.customer.auth import CustomerBearerMiddleware
from data_intelligence_hub.mcp_runtime.customer.server import customer_mcp_server

CUSTOMER_MCP_PATH = "/mcp/customer"

CUSTOMER_MCP_TRANSPORT_SECURITY = TransportSecuritySettings(
    allowed_hosts=[
        "scrapy.luteos.com",
        "scrapy.luteos.com:*",
        "scrapy.lute-tlz-dddd.top",
        "scrapy.lute-tlz-dddd.top:*",
        "127.0.0.1",
        "127.0.0.1:*",
        "localhost",
        "localhost:*",
        "test",
        "test:*",
    ],
    allowed_origins=[
        "https://scrapy.luteos.com",
        "https://scrapy.lute-tlz-dddd.top",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://test",
    ],
)


customer_mcp_app = customer_mcp_server.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
    transport_security=CUSTOMER_MCP_TRANSPORT_SECURITY,
)


def build_customer_mcp_app() -> Starlette:
    """Return the contract Streamable HTTP app."""

    return customer_mcp_app


# 客户入口只复用 `CustomerBearerMiddleware`，不写第二套 Bearer 解析。
customer_asgi_app = CustomerBearerMiddleware(customer_mcp_app)
```

- [ ] **Step 4: 挂载客户 app，保留内部 `/mcp`**

在 `main.py` 中：

1. 保留现有 `app.mount("/mcp", BearerTokenMiddleware(mcp_app))`。
2. 在它之前加入：

```python
from data_intelligence_hub.mcp_runtime.customer.app import (
    CUSTOMER_MCP_PATH,
    customer_asgi_app,
)

app.mount(CUSTOMER_MCP_PATH, customer_asgi_app)
```

顺序必须是先 `/mcp/customer`，后 `/mcp`。Starlette 按注册顺序匹配；`/mcp` 会吞掉子路径。

3. 不创建 `audience.py`，不创建 `McpAudienceRouter`，不替换内部 `BearerTokenMiddleware`。
4. 在 `main.py` 的 `lifespan` 中同时启动两个 session manager：

```python
async with mcp_server.session_manager.run():
    async with customer_mcp_server.session_manager.run():
        yield
```

内部 `mcp_server` 与客户 `customer_mcp_server` 的生命周期互相独立；任一启动失败时 API 启动失败。

- [ ] **Step 5: 运行挂载测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c13/apps/api
uv run pytest tests/unit/test_customer_mcp_mount.py tests/unit/test_mcp_transport_security.py -q
```
Expected: PASS。内部 `/mcp` 的现有断言不变。

- [ ] **Step 6: 确认没有 audience router**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c13
rg -n "McpAudienceRouter|mcp_runtime/customer/audience.py" apps/api/src apps/api/tests
```
Expected: 无输出。

- [ ] **Step 7: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/mcp_runtime/customer/app.py \
        apps/api/src/data_intelligence_hub/mcp_runtime/customer/__init__.py \
        apps/api/src/data_intelligence_hub/main.py \
        apps/api/tests/unit/test_customer_mcp_mount.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(customer-mcp): mount customer app at contract path"
```

---

### Task 9: MCP 协议测试与 curl 验证脚本

**Files:**
- Create: `apps/api/tests/integration/test_customer_mcp_protocol.py`
- Create: `scripts/verify-customer-mcp.sh`
- Test: `apps/api/tests/unit/test_customer_mcp_scripts.py`

**Interfaces:**
- Consumes: `customer_mcp_server`、`customer_mcp_app`、`CustomerBearerMiddleware`、`CustomerAuthorizationMiddleware`、`CUSTOMER_TOOL_NAMES`。
- Produces: 可复现的 MCP 协议测试与 curl 脚本；脚本退出码 0 表示 8 工具、401、403、429 全部符合预期。

- [ ] **Step 1: Write the failing protocol test**

`apps/api/tests/integration/test_customer_mcp_protocol.py`:

```python
"""客户 MCP 的 Streamable HTTP 协议测试。

覆盖：
- 无 Bearer 401；
- 全局 token 401；
- tools/list 按密钥白名单过滤；
- 能力白名单 403；
- 日额度 429；
- Cookie 参数 403；
- 八个工具名。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from starlette.applications import Starlette
from starlette.routing import Mount

from data_intelligence_hub.core import config
from data_intelligence_hub.mcp_runtime.customer import auth as auth_module
from data_intelligence_hub.mcp_runtime.customer.app import customer_mcp_app
from data_intelligence_hub.mcp_runtime.customer.auth import (
    CustomerBearerMiddleware,
    CustomerIdentity,
)
from data_intelligence_hub.mcp_runtime.customer.middleware import (
    CustomerAuthorizationMiddleware,
)
from data_intelligence_hub.mcp_runtime.customer.server import customer_mcp_server
from data_intelligence_hub.mcp_runtime.customer.tool_names import CUSTOMER_TOOL_NAMES
from data_intelligence_hub.services.project_api_keys import hash_key

TOKEN = "dih_aaaaaaaa_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
IDENTITY = CustomerIdentity(
    key_id=uuid.uuid4(),
    workspace_id=uuid.uuid4(),
    project_id=uuid.uuid4(),
    key_prefix="dih_aaaaaaaa",
    label="protocol-test",
    tool_allowlist=CUSTOMER_TOOL_NAMES,
    capability_allowlist=("cap-product",),
    daily_collect_quota=10,
)


@asynccontextmanager
async def _session_factory():
    yield SimpleNamespace()


@asynccontextmanager
async def _lifespan(app: Starlette):
    async with customer_mcp_server.session_manager.run():
        yield


def _record(**overrides: object) -> SimpleNamespace:
    values = {
        "id": IDENTITY.key_id,
        "workspace_id": IDENTITY.workspace_id,
        "project_id": IDENTITY.project_id,
        "key_prefix": IDENTITY.key_prefix,
        "label": IDENTITY.label,
        "tool_allowlist": list(IDENTITY.tool_allowlist),
        "capability_allowlist": list(IDENTITY.capability_allowlist),
        "daily_collect_quota": IDENTITY.daily_collect_quota,
        "status": "active",
        "expires_at": None,
        "revoked_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _FakePorts:
    def __init__(self) -> None:
        self.quota_allowed = True

    def build(self):
        from data_intelligence_hub.mcp_runtime.customer.ports import (
            BudgetDecision,
            CapabilityCatalogView,
            CustomerPorts,
        )

        outer = self

        class Keys:
            async def is_active(self, key_id: uuid.UUID) -> bool:
                return True

            async def validate_binding(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> bool:
                return True

        class Quota:
            async def consume(self, key_id: uuid.UUID) -> bool:
                return outer.quota_allowed

        class Capabilities:
            async def template_capability_ids(self) -> tuple[str, ...]:
                return ("cap-product",)

            async def list_capabilities(self, **kwargs: object) -> CapabilityCatalogView:
                return CapabilityCatalogView(catalog_digest="d", capabilities=())

            async def resolve_capability(self, **kwargs: object):
                return None

        class Budget:
            async def check(self, **kwargs: object) -> BudgetDecision:
                return BudgetDecision(True, False, None)

        class Tasks:
            async def get_task(self, **kwargs: object):
                return None

            async def estimate_task(self, **kwargs: object):
                raise AssertionError

            async def create_task(self, **kwargs: object):
                raise AssertionError

            async def cancel_task(self, **kwargs: object):
                return None

            async def get_delivery_manifest(self, **kwargs: object):
                return None

            async def get_evidence(self, **kwargs: object):
                return None

        class Collect:
            async def run(self, **kwargs: object):
                return {"run_id": "run-1"}

        class Audit:
            async def record(self, event: object) -> None:
                return None

        from contextlib import asynccontextmanager as _acm

        class Limiter:
            @_acm
            async def acquire(self, **kwargs: object):
                yield

        return CustomerPorts(
            keys=Keys(),
            quota=Quota(),
            capabilities=Capabilities(),
            budget=Budget(),
            tasks=Tasks(),
            collect=Collect(),
            audit=Audit(),
            limiter=Limiter(),
        )


def _build_app(monkeypatch: pytest.MonkeyPatch, record: SimpleNamespace):
    fake_ports = _FakePorts()
    resolved_ports = fake_ports.build()

    async def fake_find_by_hash(session: object, key_hash: str):
        del session
        return record if key_hash == hash_key(TOKEN) else None

    async def fake_workspace(session: object, workspace_id: uuid.UUID):
        del session, workspace_id
        return object()

    async def fake_project(session: object, workspace_id: uuid.UUID, project_id: uuid.UUID):
        del session, workspace_id, project_id
        return object()

    monkeypatch.setattr(auth_module, "find_by_hash", fake_find_by_hash)
    monkeypatch.setattr(auth_module, "get_workspace_by_id", fake_workspace)
    monkeypatch.setattr(auth_module, "get_project", fake_project)
    monkeypatch.setattr(
        auth_module,
        "get_settings",
        lambda: config.Settings(SCRAPY_MCP_CUSTOMER_ENABLED=True),
    )

    inner = CustomerAuthorizationMiddleware(
        customer_mcp_app,
        ports_provider=lambda: resolved_ports,
    )
    wrapped = CustomerBearerMiddleware(inner, session_factory=_session_factory)
    app = Starlette(
        routes=[Mount("/mcp/customer", app=wrapped)],
        lifespan=_lifespan,
    )
    return app, fake_ports


async def _raw_post(app: Starlette, payload: dict[str, object], token: str | None):
    headers = {"content-type": "application/json"}
    if token is not None:
        headers["authorization"] = f"Bearer {token}"
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers=headers,
    ) as client:
        return await client.post("/mcp/customer", json=payload)


def _tools_call(tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }


@pytest.mark.asyncio
async def test_customer_endpoint_requires_project_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = _build_app(monkeypatch, _record())
    response = await _raw_post(app, _tools_call("get_task", {"task_id": str(uuid.uuid4())}), None)
    assert response.status_code == 401
    assert response.json()["detail"] == "project_key_invalid"


@pytest.mark.asyncio
async def test_global_token_does_not_work_on_customer_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = _build_app(monkeypatch, _record())
    response = await _raw_post(
        app,
        _tools_call("get_task", {"task_id": str(uuid.uuid4())}),
        "ops-global-token",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_tools_list_omits_tools_outside_key_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record(tool_allowlist=["discover_capabilities", "get_task"])
    app, _ = _build_app(monkeypatch, record)

    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://test",
            headers={"authorization": f"Bearer {TOKEN}"},
        ) as http_client:
            transport = streamable_http_client(
                "http://test/mcp/customer",
                http_client=http_client,
            )
            async with Client(transport) as client:
                tools = await client.list_tools()

    assert [tool.name for tool in tools] == ["discover_capabilities", "get_task"]


@pytest.mark.asyncio
async def test_capability_not_allowed_returns_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = _build_app(monkeypatch, _record())
    response = await _raw_post(
        app,
        _tools_call(
            "collect",
            {
                "capability_id": "cap-other",
                "params": {},
                "idempotency_key": "idem-1",
                "budget": {"max_cost_usd": 10},
            },
        ),
        TOKEN,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "capability_not_allowed"


@pytest.mark.asyncio
async def test_capability_outside_template_returns_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """密钥允许但 C8 模板不允许的能力同样返回 403。"""
    app, _ = _build_app(
        monkeypatch,
        _record(capability_allowlist=["cap-product", "cap-outside-template"]),
    )
    response = await _raw_post(
        app,
        _tools_call(
            "collect",
            {
                "capability_id": "cap-outside-template",
                "params": {},
                "idempotency_key": "idem-1",
                "budget": {"max_cost_usd": 10},
            },
        ),
        TOKEN,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "capability_not_allowed"


@pytest.mark.asyncio
async def test_quota_exceeded_returns_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, fake = _build_app(monkeypatch, _record())
    fake.quota_allowed = False
    response = await _raw_post(
        app,
        _tools_call("get_task", {"task_id": str(uuid.uuid4())}),
        TOKEN,
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "quota_exceeded"


@pytest.mark.asyncio
async def test_cookie_argument_returns_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = _build_app(monkeypatch, _record())
    response = await _raw_post(
        app,
        _tools_call(
            "collect",
            {
                "capability_id": "cap-product",
                "params": {"creator_cookie": "sessionid=abc"},
                "idempotency_key": "idem-1",
                "budget": {"max_cost_usd": 10},
            },
        ),
        TOKEN,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "cookie_not_accepted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/integration/test_customer_mcp_protocol.py -q`

Expected: `FAILED` with `ModuleNotFoundError: No module named 'data_intelligence_hub.mcp_runtime.customer.app'` 或 `httpx2` 导入失败。若 `httpx2` 不可用，检查 `apps/api/uv.lock` 中 `mcp` 的依赖；不得改用同步 `httpx` 伪造 Streamable HTTP。

- [ ] **Step 3: Create the curl verification script**

`scripts/verify-customer-mcp.sh`:

```bash
#!/usr/bin/env bash
# 客户 MCP 只读/认证验证。
#
# PG0 前（不带密钥）：scripts/verify-customer-mcp.sh https://scrapy.luteos.com
#   只检查 health 与未带 Bearer 的 401。404 表示开关未由 PG0 翻起，脚本返回 2 并打印 BLOCKED。
# PG1 后（带测试密钥）：DIH_CUSTOMER_MCP_KEY='dih_...' scripts/verify-customer-mcp.sh https://scrapy.luteos.com
#   首次真实客户密钥签发属于 PG1；C13 不签发、不写入仓库。
set -euo pipefail

BASE_URL="${1:-https://scrapy.luteos.com}"
KEY="${DIH_CUSTOMER_MCP_KEY:-}"
ENDPOINT="${BASE_URL%/}/mcp/customer"
HEALTH_URL="${BASE_URL%/}/api/health"

health_code="$(curl -sS -o /dev/null -w '%{http_code}' "$HEALTH_URL")"
if [ "$health_code" != "200" ]; then
  echo "expected health 200, got $health_code" >&2
  exit 1
fi
echo "health status: ${health_code}"

status_without_auth() {
  curl -sS -o /dev/null -w '%{http_code}' -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    --data '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
}

if [ -z "$KEY" ]; then
  code="$(status_without_auth)"
  case "$code" in
    401)
      echo "unauthenticated status: 401"
      exit 0
      ;;
    404)
      echo "BLOCKED: customer_switch_not_enabled_pre_pg0" >&2
      exit 2
      ;;
    *)
      echo "expected 401 without Bearer, got $code" >&2
      exit 1
      ;;
  esac
fi

AUTH_HEADER="Authorization: Bearer ${KEY}"

post_auth() {
  curl -sS -X POST "$ENDPOINT" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    --data "$1"
}

post_auth '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2026-07-28","capabilities":{},"clientInfo":{"name":"dih-curl","version":"0.1.0"}}}' >/tmp/dih-customer-mcp-initialize.json
post_auth '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null || true

tools_json="$(post_auth '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}')"
printf '%s' "$tools_json" >/tmp/dih-customer-mcp-tools.json

python3 - "$tools_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
tools = payload["result"]["tools"]
names = [tool["name"] for tool in tools]
expected = [
    "discover_capabilities",
    "estimate_task",
    "create_task",
    "get_task",
    "cancel_task",
    "get_delivery_manifest",
    "get_evidence",
    "collect",
]
missing = [name for name in expected if name not in names]
forbidden = [name for name in names if name not in expected]
if missing or forbidden:
    raise SystemExit(f"tools mismatch missing={missing} forbidden={forbidden}")
print(f"customer MCP tools: {len(names)}")
PY

code="$(status_without_auth)"
if [ "$code" != "401" ]; then
  echo "expected 401 without Bearer, got $code" >&2
  exit 1
fi
echo "unauthenticated status: ${code}"
```

- [ ] **Step 4: Create the script tests**

`apps/api/tests/unit/test_customer_mcp_scripts.py`:

```python
"""curl 验证脚本的静态门禁。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from data_intelligence_hub.mcp_runtime.customer.tool_names import CUSTOMER_TOOL_NAMES

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "verify-customer-mcp.sh"


def test_script_exists_and_is_executable() -> None:
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & 0o111


def test_script_names_all_eight_tools_and_contract_path() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "/mcp/customer" in text
    assert "/mcp/customer" in text.split("ENDPOINT=")[1]
    for name in CUSTOMER_TOOL_NAMES:
        assert name in text


def test_script_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_script_supports_pre_pg0_readonly_mode() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "DIH_CUSTOMER_MCP_KEY:-" in text
    assert ":?set DIH_CUSTOMER_MCP_KEY" not in text
    assert "customer_switch_not_enabled_pre_pg0" in text
    assert "BLOCKED" in text
    assert "exit 2" in text
    assert "/api/health" in text
```

- [ ] **Step 5: Make the script executable and run tests**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
chmod +x scripts/verify-customer-mcp.sh
cd apps/api && uv run pytest tests/integration/test_customer_mcp_protocol.py tests/unit/test_customer_mcp_scripts.py -q
```

Expected: `11 passed`（7 个协议测试 + 4 个脚本测试）。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
git add apps/api/tests/integration/test_customer_mcp_protocol.py \
        apps/api/tests/unit/test_customer_mcp_scripts.py \
        scripts/verify-customer-mcp.sh
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "test(customer-mcp): add streamable http protocol and curl verification"
```

---

### Task 10: `/connectors` 浏览器交接

**Files:**
- Create: `docs/ops/customer-mcp-connectors-handoff.md`
- Test: `apps/api/tests/unit/test_customer_mcp_contract.py`（追加文档存在性与八工具断言）

**Interfaces:**
- Consumes: 前九个任务产出的 endpoint、八个工具名、错误码、curl 脚本。
- Produces: 一份可直接交给 C14/前端/验收人的 `/connectors` 浏览器交接单。

- [ ] **Step 1: Add the failing documentation test**

在 `apps/api/tests/unit/test_customer_mcp_contract.py` 末尾追加：

```python
def test_connectors_handoff_documents_the_customer_surface() -> None:
    handoff = REPO_ROOT / "docs" / "ops" / "customer-mcp-connectors-handoff.md"
    text = handoff.read_text(encoding="utf-8")
    assert "/mcp/customer" in text
    assert "/connectors" in text
    assert "dih_" in text
    for name in CUSTOMER_TOOL_NAMES:
        assert name in text
    assert "creator_cookie" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_contract.py::test_connectors_handoff_documents_the_customer_surface -q`

Expected: `FAILED` with `FileNotFoundError` for `docs/ops/customer-mcp-connectors-handoff.md`.

- [ ] **Step 3: Create the handoff document**

`docs/ops/customer-mcp-connectors-handoff.md`:

```markdown
# 客户 MCP /connectors 浏览器交接

| 字段 | 内容 |
|---|---|
| 交接对象 | C14 控制台、前端、验收人 |
| 后端入口 | `https://<host>/mcp/customer` |
| 鉴权 | `Authorization: Bearer dih_...` 项目密钥 |
| 协议 | MCP Streamable HTTP，`json_response=true`，`stateless_http=true` |
| 状态 | 后端已实现；页面由 C14 只读验收；PG0 批次翻开关；首个真实客户密钥签发属于 PG1（PG0 之后） |
| 写操作边界 | C13 只提交共享 compose 的默认关闭映射与测试，不部署；C13 与 C14 都不翻转生产开关、不写 `.env.production` 或生产数据；部署与开关切换只属于 PG0 发布批次 |

## 1. 页面必须展示的事实

`/connectors` 页面只展示以下客户事实，不展示 provider、端点、内部单价或运维 token。

1. 客户 MCP 地址：`https://<host>/mcp/customer`。
2. 项目密钥前缀与标签；完整明文只在签发时显示一次。
3. 八个工具的名称与一句话说明。
4. 当前密钥的工具白名单与能力白名单。
5. 日额度、速率和并发限制的客户可见口径。
6. 撤销按钮与撤销后的即时失效说明。
7. MCP 客户端配置 JSON。

PG0 前页面只读验收，不创建或撤销真实密钥。密钥创建、明文展示一次与撤销验证属于 PG1（PG0 之后）。

## 2. 八个工具

| 工具 | 用途 | 是否只读 |
|---|---|---|
| `discover_capabilities` | 列出模板白名单与密钥白名单的交集 | 是 |
| `estimate_task` | 估算任务包成本 | 是 |
| `create_task` | 创建受治理任务包，必须带幂等键 | 否 |
| `get_task` | 读取本项目任务 | 是 |
| `cancel_task` | 取消本项目任务；必须带幂等键与 `reason_code`，同键重放、异键返回 `idempotency_conflict` | 否 |
| `get_delivery_manifest` | 读取不可变交付清单 | 是 |
| `get_evidence` | 只读通过 C7 可发布门禁的 approved Claim 与证据；pending/stale 返回 `claim_not_found` | 是 |
| `collect` | 执行模板白名单与密钥白名单交集内的能力 | 否 |

页面不得出现 `web_search`、`tiktok_product_search`、`endpoint_type`、`provider` 或任何端点级工具。

## 3. 错误码

| HTTP | 错误码 | 页面文案 |
|---:|---|---|
| 401 | `project_key_invalid` | 密钥不存在或格式错误 |
| 401 | `project_key_revoked` | 密钥已撤销或过期 |
| 403 | `tool_not_allowed` | 该密钥未授权此工具 |
| 403 | `permission_denied` | 密钥与工作区/项目绑定不一致 |
| 403 | `capability_not_allowed` | 该能力不在模板或项目白名单 |
| 403 | `cookie_not_accepted` | 客户链不接受 Cookie 或登录态 |
| 404 | `claim_not_found` | Claim 不存在或尚未通过审核 |
| 404 | `evidence_not_found` | Claim 证据不完整 |
| 429 | `quota_exceeded` | 今日额度已用完 |
| 429 | `rate_limited` | 请求过快 |
| 429 | `rate_limited` | 并发调用过多 |
| 409 | `approval_required` | 预算不足，等待 owner/admin 批准 |
| 409 | `idempotency_conflict` | 幂等键已用于不同请求内容 |
| 409 | `state_conflict` | 任务状态不允许当前操作 |

## 4. curl 验证

PG0 前只读检查（不带密钥）：

```bash
scripts/verify-customer-mcp.sh https://scrapy.luteos.com
```

期望 health 200 与 `unauthenticated status: 401`。若未带 Bearer 返回 404，脚本打印 `BLOCKED: customer_switch_not_enabled_pre_pg0` 并退出 2；这不是 C13 的缺陷，由 PG0 批次翻开关，C13 不修复。

PG1 后带测试密钥：

```bash
DIH_CUSTOMER_MCP_KEY='dih_...' scripts/verify-customer-mcp.sh https://scrapy.luteos.com
```

手工检查未带 Bearer：

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
  https://scrapy.luteos.com/mcp/customer \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

期望 `401`。

## 5. MCP 客户端配置

```json
{
  "mcpServers": {
    "dih-customer": {
      "type": "streamable-http",
      "url": "https://scrapy.luteos.com/mcp/customer",
      "headers": {
        "Authorization": "Bearer ${DIH_CUSTOMER_MCP_KEY}"
      }
    }
  }
}
```

## 6. 浏览器验收清单

### 6.1 PG0 前只读验收（C14）

在 `https://scrapy.luteos.com/login` 以 owner 登录后执行，不创建或撤销密钥，不修改开关：

1. 打开 `/connectors`，页面 200 且无控制台 error。
2. “客户 MCP”区块显示 `/mcp/customer`。
3. 工具清单恰好八项，逐项与第 2 节一致。
4. 页面任何位置都没有 Cookie、Seller Center 登录态或 `creator_cookie` 输入框。
5. 截图保存到 `reports/customer-mcp/connectors.png`。

### 6.2 PG1 密钥生命周期验收（PG0 之后）

1. 创建密钥后，明文只出现一次；刷新后只剩前缀。
2. 复制配置 JSON，`url` 与 `${DIH_CUSTOMER_MCP_KEY}` 正确。
3. 撤销密钥；同一密钥的下一次 `/mcp/customer` 请求返回 401。

页面未实现时，本清单标记 `BLOCKED`，不得声称完成。C13 不执行 PG1 密钥签发；交接人必须在 C14 页面合并且 PG0 完成后重跑 6.2。
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lute/Project/data_scrapy-gov-c13/apps/api && uv run pytest tests/unit/test_customer_mcp_contract.py -q`

Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
git add docs/ops/customer-mcp-connectors-handoff.md \
        apps/api/tests/unit/test_customer_mcp_contract.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(customer-mcp): hand off connectors browser verification"
```

---

### Task 11: 全量门禁、只读生产 A/B 与 GitNexus 变更分析

**Files:**
- Modify: 无（只运行门禁；若失败，回到对应任务修复）
- Test: 全量 `apps/api/tests/unit` 与 `apps/api/tests/integration`

**Interfaces:**
- Consumes: 前十个任务的全部产物。
- Produces: 可提交、可发布、可复核的证据链；任何一项失败都不得宣称完成。

- [ ] **Step 1: Run the full API test suites**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c13/apps/api
uv run pytest -q tests/unit
uv run pytest -q tests/integration
```

Expected: both commands end with `0 failed`. 计数可以比契约 §7.1 的 1980/384 多，但失败数必须是 0。

- [ ] **Step 2: Verify the migration invariant**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c13/apps/api
uv run alembic heads
uv run alembic current
cd /Users/lute/Project/data_scrapy-gov-c13
git diff --name-only -- apps/api/alembic/versions
```

Expected:

- `alembic heads` 恰好一行。
- `alembic current` 与唯一 head 相同。
- `git diff --name-only -- apps/api/alembic/versions` 无输出。C13 不新增迁移。

- [ ] **Step 3: Run GitNexus change analysis**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `partial: false` and `truncated: false`. If either is true, re-run until both are false. A zero result with `partial: true` is not a clean check.

再跑：

```bash
node .gitnexus/run.cjs impact "customer_mcp_server" --direction upstream --repo .
node .gitnexus/run.cjs impact "customer_asgi_app" --direction upstream --repo .
node .gitnexus/run.cjs impact "ensure_customer_call" --direction upstream --repo .
node .gitnexus/run.cjs impact "cancel_task_runs" --direction upstream --repo .
node .gitnexus/run.cjs impact "load_publishable_claim_rows" --direction upstream --repo .
```

Expected: no `risk: HIGH` or `risk: CRITICAL`. If any is `UNKNOWN`, confirm with `rg -n "customer_mcp_server|customer_asgi_app|ensure_customer_call|cancel_task_runs|load_publishable_claim_rows" apps/api/src apps/api/tests` and report what the graph could not resolve.

- [ ] **Step 4: Verify production A health and unauthenticated boundary (read-only)**

C13 不设置生产开关值、不写 `.env.production`、不部署。共享 compose 只提交默认关闭映射；PG0 前只允许只读检查：health 与未带 Bearer 的 `POST /mcp/customer`。开关由 PG0 发布批次翻转。

Run:

```bash
curl -fsS https://scrapy.luteos.com/api/health
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
  https://scrapy.luteos.com/mcp/customer \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Expected: health 200。未带 Bearer 的 `/mcp/customer` 在 PG0 开关翻起后返回 `401`；返回 `404` 记为 `BLOCKED: customer_switch_not_enabled_pre_pg0`，由 PG0 批次翻开关，C13 不修复、不记为 C13 失败。返回 `200` 说明鉴权门禁失效，立即停止并报告。

- [ ] **Step 5: Verify production B health and unauthenticated boundary (read-only)**

B 被 `202610190045` 的目标授权与备份门禁挡住时，不升级、不打开客户 MCP 开关。记录 `BLOCKED`，只跑只读健康检查。

Run:

```bash
curl -fsS https://scrapy.lute-tlz-dddd.top/api/health
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
  https://scrapy.lute-tlz-dddd.top/mcp/customer \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Expected: health 200。B 落后时记录 `BLOCKED`，不要求 C13 先升级 B，也不阻断 A。B 的 `/mcp/customer` 返回 404 属于 PG0 前已知状态，记为 `BLOCKED: customer_switch_not_enabled_pre_pg0`，不是 C13 失败。

- [ ] **Step 6: Run authenticated protocol tests on local/staging fixtures only**

C13 在 PG0 前不签发真实客户密钥，也不对生产执行带 Bearer 的认证调用。认证协议测试只使用本地 ASGI fixture：

```bash
cd /Users/lute/Project/data_scrapy-gov-c13/apps/api
uv run pytest tests/integration/test_customer_mcp_protocol.py tests/unit/test_customer_mcp_ports.py -q
```

Expected: 全部 PASS，0 failed；覆盖八个工具、401/403/429、模板∩密钥能力白名单、Cookie 隔离、`create_task → collect` 共享初始版本、取消同键/异键/并发幂等、`get_evidence` 的 C7 pending/stale 门禁。

首个真实客户密钥的签发属于 PG1（PG0 之后）。PG1 才允许执行：

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
DIH_CUSTOMER_MCP_KEY='<PG1 由 owner 在工作区签发的测试密钥>' \
  scripts/verify-customer-mcp.sh https://scrapy.luteos.com
```

不得把测试密钥写进仓库、日志、工单或报告。C13 不执行这一条；它只是交接说明。

- [ ] **Step 7: Browser handoff gate (read-only)**

C13 does not run Playwright and does not modify `apps/scraper-console`. The browser gate belongs to C14 and is read-only.

C13 only verifies the handoff document and marks the browser gate `BLOCKED` until C14 lands:

```bash
cd /Users/lute/Project/data_scrapy-gov-c13
test -f docs/ops/customer-mcp-connectors-handoff.md
git diff --exit-code -- apps/scraper-console
```
Expected: handoff file exists; console diff is empty. If C14 has landed, C14 runs the read-only browser checks and writes the result. C13 must not claim the browser gate passed. PG1 key lifecycle checks are not part of this gate.

- [ ] **Step 8: Record gate evidence without a new commit**

Do not create a new commit for this task. Paste the exact last line of every command in Steps 1-7 into the pull request description. Do not summarize or round numbers. The evidence must show:

- `pytest` unit and integration each end with `0 failed`.
- `alembic heads` and `alembic current` show the same single head.
- `git diff --name-only -- apps/api/alembic/versions` prints nothing.
- `detect-changes` prints `partial: false` and `truncated: false`.
- Both production health endpoints print `200`.
- Both `/mcp/customer` unauthenticated calls print `401`, or print `404` accompanied by `BLOCKED: customer_switch_not_enabled_pre_pg0`.
- Authenticated protocol tests ran on local/staging fixtures with `0 failed`; no production customer key was issued.
- `/connectors` is marked `BLOCKED` with the reason `owned_by_c14` until C14 lands; PG1 key lifecycle is marked `BLOCKED: pg1_after_pg0`.
- No production switch was flipped and no `.env.production`, migration, deployment or restart was executed by C13; only the default-off shared compose mapping and its test were committed.

若 Step 1-7 任一失败，不要填写通过结论。修复失败项后从对应任务的测试重新开始。

---

## Self-Review

- **契约覆盖**：`/mcp/customer` 路径、八个工具、`capability_allowlist`、`customer_mcp.schema.json` 全部由 Task 1 守卫；C13 不修改契约、不新增迁移、不新增表。
- **包型、市场与输入字段**：Task 3 固定 `CreateTaskInput` 字段；Task 7 把 `idempotency_key`、`package_type`、`primary_market`、`compare_markets`、`seed_products`、`target_price_band`、预算与 `acceptance_contact_id` 映射到 C4，`compare_markets` 改名为 `comparison_markets`。C13 不丢弃种子商品或目标价格带；Quick 1 / Standard 3、种子商品 3–10、价格带与 `market_role` 派生都归 C4。
- **创建幂等与可执行性**：Task 7 把 `idempotency_key` 传给 C4 `create_workbench_task`，同摘要重放已有任务、异摘要返回 `idempotency_conflict`；`create_task` 与 `collect` 都调用 C4 `create_initial_workflow_version_for_task`，共享同一已批准版本。Task 7 的 `test_create_task_then_collect_reuses_same_initial_version` 断言同一 task 与同一版本。
- **模板能力交集**：Task 4/6/7 只经 C8 `template_capability_ids(template_id)` 读取模板白名单（`TaskTemplate.capability_allowlist` 是字段，不直接读属性）；`discover_capabilities` 与 `collect` 都使用模板白名单 ∩ 密钥 `capability_allowlist`。模板缺失或为空时 `collect` 返回 `capability_not_allowed`、`discover_capabilities` 返回空清单；`ToolCatalogCapabilityAdapter` 已删除“全部非 Cookie 工具”回退，并由 Task 7 的空模板与目录不回落用例守卫。
- **取消幂等**：Task 6 工具把 `idempotency_key`、`reason_code` 原样传给端口；Task 7 适配器委托 C6 `cancel_task_runs`，不再 `del` 参数、不直接循环 `cancel_run`。Task 7 覆盖同键同 reason 重放、同键异 reason `idempotency_conflict`、并发同键只取消一次。
- **证据可发布门禁**：Task 7 `get_evidence` 先调用 C7 `load_publishable_claim_rows` 与 `validate_claim_bundle`；pending/stale 返回 `claim_not_found`，证据不完整返回 `evidence_not_found`；测试覆盖两类拒绝与一个通过用例。
- **验收联系人**：Global Constraints 与 Task 7 映射要求 owner/admin；C4 负责角色校验，普通 member 返回 `acceptance_contact_not_member`。
- **请求顺序**：Task 4 用调用日志逐段断言身份 → 密钥 → 绑定 → 工具 → 能力 → Cookie → 额度 → 限流 → 执行；Task 6/9 在 HTTP 层验证 403/429。
- **八个工具**：Task 6 断言 tuple 等于 `CUSTOMER_TOOL_NAMES`，并断言不存在 `project_id`、`workspace_id`、`provider`、`endpoint_type`、`cookie` 参数。
- **Cookie 隔离**：Task 3 递归扫描键名与值；Task 9 在 `collect.params` 中放 `creator_cookie` 断言 403。
- **旧内部 MCP**：Task 6 与 Task 8 断言 `mcp_runtime/server.py`、`auth.py` 零 diff；Task 8 断言内部 `/mcp` 挂载保持不变，客户入口只在 `/mcp/customer` 挂载一次，并复用 `CustomerBearerMiddleware`。
- **DB 速率并发**：Task 5 只测 `audit_events` 计数，覆盖速率、并发、终态释放、stale 与工作区隔离；无进程内计数器、无租约表。stale 使用内部常量 `STALE_AFTER_SECONDS = 300`，不设置租约过期开关，不进入 Settings、`.env.example`、compose 或产品阈值。
- **共享 compose**：Task 2b 在 `configs/deploy/scrapy/docker-compose.yml` 的 `api.environment` 增加 `SCRAPY_MCP_CUSTOMER_ENABLED=false`、`SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE=60`、`SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS=4` 三个默认映射，并用 `test_deploy_customer_mcp_facts.py` 断言；C13 不部署、不写 `.env.production`。
- **审计**：Task 4 断言允许/拒绝/成功/失败四类事件；Task 7 断言 audit metadata 只有四个字段，不含参数、密钥或 Cookie。
- **依赖接口**：Task 7 明确列出 C2/C3/C4/C5/C6/C7/C8/C9/C10 的真实函数名与参数；`ports.py` 只做字段映射、只读查询和公开服务调用，不复制预算、Claim、报告或采集逻辑。不存在 `services.customer_task_gateway`、`services.customer_budget`、`services.customer_capabilities`、`services.governed_collect`、`services.delivery_manifest` 依赖；导入预检失败即记为 `BLOCKED`。
- **PG0 前后边界**：Task 11 的 Step 4/5 只读 health 与未带 Bearer 的 401；404 记为 `BLOCKED`，C13 不翻开关。Task 11 Step 6 的认证测试只用本地/staging fixture；首个真实客户密钥属于 PG1。C14 只读浏览器验收；生产写操作属于 PG0 发布批次。
- **验证命令**：每个任务都有 `uv run pytest` 命令与预期结果；Task 11 覆盖全量测试、迁移、GitNexus、只读生产 A/B 与 `/connectors` 交接门禁。
