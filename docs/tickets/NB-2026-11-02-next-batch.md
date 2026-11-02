# Source 下一批推荐执行方案（2026-11-02）

## 0. 结论先行

- 本周有真实功能进展，生产可信度没有同步。A 已到 schema 068；发布账本最后 A 记录 `5dbddae`（10-29）是 67 个迁移，差 1 个；B 停在 056，落后 main 250 个提交、12 个迁移。
- B 的 `/api/abi/*` 与 `/api/insight/*` 均为 404（A 为 401）。`origin/deploy/tiktok-cdo-codex` 相对 main 是 **217/0 严格祖先**，0 个独有提交；CDO router 在 main 也存在。先验证这一点，再决定升级或冻结。
- 最贵的坑是写完没跑、跑了没验：ABI 导出曾因 profile 从未启动；`abi-ingest` 只入队不消费；双人审批默认值反向；洞察首份报告没有证据等级。
- 下一批先收口，不先开新功能。P0-A 无外部依赖，48 小时内可做；P0-B 依赖拍板与生产权限，随后做。
- 当前只能说：应用侧 ABI 查询、上传、导出的代码路径与本地测试已打通。生产异步导出终态、T-1 入仓、看板真实数据还没有证据。

## 0.1 已拍板（2026-11-02）

| 决策 | 拍板结果 | 落地动作 |
|---|---|---|
| B 生产 scope | **同意推荐**：先验证祖先；若成立，备份后 fast-forward 升级到 `alembic heads`；做不到备份/回滚就书面冻结并移出「两套生产」口径 | 写 `configs/deploy/scrapy/production-scope.json`；先跑 `preflight-production-b.sh`；升级前备份与回滚包 |
| ABI 数据面 | **ETL 进应用库**；分析型临时查询可读外部仓 | 写 `docs/plans/abi-data-plane-etl.md`；实现 scan consumer 与 ETL |
| `pii_class` 入参 | **先 `extra="forbid"`**，避免静默丢弃；需要写入时另开迁移 | 改 `AbiColumnCreate`；加契约测试 |
| 两前端 | **保留 `apps/web` 为洞察应用，不做合并重构**；ADR-009 放 P2 | 本批不动结构；P2 再写 ADR-009 |

## 0.2 建议节奏

- 第 1 周（P0-A，无外部依赖）：完整性 verify、在途资产提交、密码与审批测试、凭证轮换、账本最小字段。
- 第 2 周（P0-B）：B scope 与升级、ABI `pii` 契约与导出终态、洞察导入口径。
- 第 3 周（P1）：迁移号、integration CI、工单/数字单一源、报告语言闸门、日报、workflow scope。

## 1. P0-A（48 小时，可立即开工）

### P0-A1 在途资产先 verify 再提交

**为什么现在**：工作树有 4 个修改、12 个未跟踪条目，随时可能被并行 workflow 覆盖。先提交，才有回滚锚点。

**任务**：

1. 先跑 `python3 scripts/check_file_integrity.py --path <每个待提交文件>`；有尾洞/坏头/NUL 先处理，再 `git add`。
2. 按文件清单提交，不 `git add -A`。清单：
   - `scripts/extract_retro_sessions.py` + 测试
   - `scripts/check_dual_production_drift.sh` + 测试
   - `scripts/check_migration_numbers.py` + 测试
   - `scripts/check_file_integrity.py` 的 `--path`
   - `scripts/daily-report.sh` 加固
   - `.claude/skills/report-review/`、`.claude/skills/retro/` 更新
   - `apps/api/tests/unit/test_auth_password_policy.py`
   - `.github/workflows/ci.yml` 三条脚本测试
   - `docs/retro/2026-11-02-本周复盘.md`、本文件、OI 与 ASSET 文档
3. 提交前跑 `ruff check`、`ruff format --check`、三套脚本测试、密码测试；提交后跑 CI。
4. 用文件哈希记录提交内容；并行会话不得再改这些路径。

**完成定义**：工作树干净；CI 绿；每项资产有测试输出。

### P0-A2 文件完整性 verify（不做自动 repair）

**为什么现在**：本周至少 2 个文件、ABI 会话约 8-10 次尾洞/乱码头；现有检查器只查 `st_size` 与 NUL，不查严格 UTF-8、mode、垃圾头。

**任务**：

1. `--verify` 增加：严格 UTF-8、原始块哈希、tracked 文件 mode 与 git index 对比。
2. **不做自动 repair**。`repair` 只处理可恢复的尾洞/截断（按读取长度截断）并恢复 mode；非法 UTF-8 与垃圾头标 `quarantine`，要求从 git/备份恢复。
3. 接入 pre-commit、CI、编辑后钩子；`--edited` 扫描 `git status` 的 modified/untracked。
4. 记忆目录用 `--path` 每周扫一次。

**完成定义**：尾洞、NUL、非法 UTF-8、mode 变化四类夹具先 FAIL，修复/隔离后 PASS；正常文本与二进制零误报。

**风险**：repair 可能把损坏源码替换成猜测内容。tracked 源码默认不自动 repair。

### P0-A3 安全下限与凭证轮换

**为什么现在**：密码最小长度 8→3 发布过一次，同日改回；5 个 Apify token 在会话中明文出现；子代理读 `.env` 调付费 TikHub；`reports/mcp-token.txt` 是本地明文。

**任务**：

1. 保留并扩展 `test_auth_password_policy.py`（已 5 passed）。
2. 新增：`APP_ENV=production` 时 cookie `secure=true`、effective demo mode 为 false、ABI 缺省策略 `require_dual_approval=true`。
3. 轮换/撤销 5 个 Apify token 与相关 TikHub token；旧 token 标 retired；确认 `~/.config/apify-lake/tokens.txt` 权限 600。
4. 删除或移入钥匙串 `reports/mcp-token.txt`；`reports/` 保持 gitignore。
5. 加 `gitleaks` 或 `detect-secrets` 到 pre-commit 与 CI；付费调用需批准文件。

**完成定义**：旧 token 已撤销；新增明文为 0；扫描为 0；密码/审批/cookie/demo 测试全过；改回 `min_length=3` 时测试必须红。

### P0-A4 发布账本最小字段

**为什么现在**：`record_release.py` 没有 `schema_revision`、`alembic_head`、`verification`，15 条记录 0 条 schema；A 账本落后生产 1 个迁移。P0 需要账本，但完整 v2 在 P2，顺序倒置。

**任务**：

1. 给 `record_release.py` 增加最小字段：`schema_revision`、`alembic_head`、`verification`、`source`（`deploy-p0` / `backfill_manual` / `probe`）、`deployed_commit`。
2. `verify` 强制这些字段；旧 15 条只追加 `unknown` 标注，不改写。
3. 先确认 `3f889e7` 如何到达 A：
   - 若是正式发布但漏记，用 `backfill_manual` + 公网探针补记；
   - 若是热替换，先重建镜像并按 `deploy-p0.sh` 重新发布，再记账。不能把热替换记成正式发布。
4. 发布门加四项红线：远端分支 HEAD 等于本地 HEAD（先 push 再发布）、edge 固定 IP 172.20.0.16、`provider_call=false`、密钥不入库。

**完成定义**：A 账本含 068 与 `3f889e7`；B 的 scope 有机器可读记录；`check_dual_production_drift.sh --strict` 退出 0 或有 `production_scope` 豁免。

## 2. P0-B（依赖满足后）

### P0-B1 B 生产 scope 与升级/冻结

**任务**：

1. 先验证：`git merge-base --is-ancestor origin/deploy/tiktok-cdo-codex main`、`git rev-list --left-right --count main...origin/deploy/tiktok-cdo-codex`、`git diff --stat`、CDO router 存在性。
2. 写 `configs/deploy/scrapy/production-scope.json`：`a=active`、`b=active|frozen_nonprod|decommissioned`。
3. `active`：实现 `scripts/preflight-production-b.sh`（复用 A 的 branch、edge、备份、回滚检查）；fast-forward 到 `alembic heads`；跑 057-068；账本记录 schema 与 commit。
4. `frozen_nonprod`：从「两套生产」口径移除；drift 只跳过 B schema；保留只读监控。
5. `decommissioned`：保留只读探针与下线记录。

**完成定义**：`production_scope.json` 有值；drift 按 scope 判定；B 升级有备份、回滚包、迁移与健康证据；或冻结有 ADR。

### P0-B2 ABI pii 契约、导出终态与数据面

**任务**：

1. `AbiColumnCreate` 加 `pii_class` 或 `extra="forbid"`；按拍板结果写契约测试。当前 HEAD 必须失败，修复后 PASS。
2. 导出终态验收：一次遮罩/未遮罩导出走完 `queued → awaiting_approval → succeeded`；artifact 可下载；SHA-256 校验通过；probe 断言 `abi-export` running、队列年龄、worker 心跳。
3. 数据面 ADR：本地快照 ETL 进应用库，或应用读外部仓；看板在决策前标 demo。
4. `abi-ingest` scan consumer：分页枚举 dataset、拉 item、写 `raw.apify_item`、按 `createdAt` 分区、幂等、404/429/403 分类。复用 `scripts/apify_lake/rescue.py`。
5. 边界：ingest 是 collector/ETL 层，API 路由与 UI 不得 import Provider SDK；token 只从 env/vault 读；每 T-1 有预算与调用审计。

**完成定义**：`/abi` 看板读真实数据；一次 T-1 成功且重跑不重复；一次导出终态可下载；pii 契约测试 PASS；`provider_call_attempted=false` 断言通过。

### P0-B3 洞察报告生产导入的独立复核与证据标注

**已知**：nmem 记忆 `d80e2201`（2026-10-31T20:31:47Z）记录生产 A 已到 `3f889e7`，迁移 067→068，报告已入库 `report_id=ebe57a63-4241-4ce0-8e13-eb54a9f80f07`，正文 181,984 字节，SHA-256 与契约一致；浏览器实测 1 张报告卡、0 控制台错误、0 外部请求。本次未登录生产，未独立复核。

**任务**：

1. 独立复核：登录生产 `GET /api/insight/reports` 与 detail；确认 `report_count=1`、正文 181,984 字节、SHA-256 一致；`POST` 仍 405。
2. 补 10-31 发布账本（见 P0-A4）；确认 `3f889e7` 是正式发布还是热替换。
3. 报告标「描述性归档」或补 claims/证据等级；口径检查：manifest 增加 `source_dataset_id`、`run_id`、`denominator`、`as_of`、`chart_source`；每个图表数字来自 JSON，或显式标 `illustrative`；百分比 20 字内有分母。
4. 本地 182,450 字节与入库正文 181,984 字节的差异写进口径说明（导入归一化）。
5. 11-01 日报按 `known_gap` 处理：写 `reports/achievements-20261101/MISSING.md`，记录原因、数据截止与 owner；不要为补跑伪造非空报告。

**完成定义**：独立复核通过；账本有 `3f889e7`；报告有等级或描述性归档标记；口径检查 PASS；字节差异有说明。

## 3. P1（与 P0 并行或紧随）

| 编号 | 任务 | 完成定义 | 证据 |
|---|---|---|---|
| P1-1 | 迁移号重基线 | 列出 checker 报的 12 处；逐文件决定历史 allowlist 或新增 addendum；069+ 预留表；checker 对历史计划与现行迁移分开校验；最后 exit 0 | `python3 scripts/check_migration_numbers.py` 当前 FAIL，12 处 |
| P1-2 | integration CI | 34 个 integration 文件进 CI，或书面 allowlist（owner、原因、到期日）；至少加 ABI export、auth 401、insight 路由的 targeted integration | `.github/workflows/ci.yml` 只跑 `pytest tests/unit` |
| P1-3 | 工单与数字单一源 | JSON 单一源生成 MD；每日 diff 飞书；README/能力图谱/总账/基线数字同源；0 冲突 | SP JSON 42/3/2/18 vs 飞书 37/6/1/21 |
| P1-4 | 报告语言闸门 | **已完成（2026-11-03）**：共享实现 `apps/api/src/data_intelligence_hub/report_quality/`，一份 `rules.json`；`tools/insight-report/validate.py --gate` 与导入器共用；删除 `ir_impl/validate.py`；CI 增加闸门步骤；日报 advisory。63 词夹具命中 63；当前报告 PASS。 | 见 `docs/plans/report-language-gate.md` |
| P1-5 | 日报健康检查 | 不用 `flock`/`timeout`（本机没有）；用 `mkdir` 原子锁或 `run_with_timeout`；检查放在 22:15 后或读完成标记；外部 dead-man 检查心跳 | `command -v flock/timeout` 均失败 |
| P1-6 | workflow scope guard | claim/audit 脚本；写集外修改、读 `.env`、未批准付费调用三夹具 FAIL；双 workflow 演练 0 覆盖 | 本次审计期间 NB 文件被并行改写 |
| P1-7 | 身份回归证据 | A/B `/api/tools` 无 token 401；工作区隔离测试；B1/P1 同批门禁记录 | A/B 均含 b75bc3c |

## 4. P2（产品与治理）

| 项 | 完成定义 |
|---|---|
| ADR-009 两前端边界 | 路由归属表；保留/合并决策；不在本批做合并重构 |
| 报告画廊、第二分析类型 | 依赖 P0-B3；先列表与详情，不做推荐算法 |
| PG0 C2-C14 | 依赖 P1-1；每切片迁移、测试、回滚；不跳过 C2 直接做 C13 |
| VOC G7 双盲 | 第二编码员；metric rows > 0 |
| `check_docs_drift.py`、`check_commit_scope.py`、`egress_audit.sh` | 上线并接 CI |
| release ledger v2 | JSON Schema、`migrations_applied`、CI 拒绝缺字段 |

## 5. 不建议现在做

1. ABI 看板扩容或第二分析类型。数据面未定、证据等级未接。
2. B 全量升级。备份、preflight、回滚包未就绪前不碰。
3. 启动 PG0 C2-C14。迁移号未重排，开工断言必然失败。
4. 接真实 LLM 生成。成本、预算、禁写、证据等级未定。
5. 合并两个前端。先定边界，不做结构重构。
6. 把首份洞察报告当六档证据报告对外。先标描述性归档。
7. 未批准预算时让子代理调用付费 API。

## 6. 依赖图

```text
P0-A1 在途资产 verify+提交
  ├─> P0-A2 完整性
  ├─> P0-A3 安全下限与凭证
  └─> P0-A4 账本最小字段
        └─> P0-B1 B scope
              └─> P1-2 integration CI
P0-B1 B scope ──> P1-1 迁移号? 否；P1-1 独立
P0-B2 ABI pii/导出/数据面 ──> 看板真实数据
P0-B3 洞察复核 ──> P2 报告画廊
P1-1 迁移号 ──> P2 C2-C14
```

## 7. 验收门

### 门 1：发布门

- 远端分支 HEAD 等于本地 HEAD（先 push 再发布）。
- `fetch + merge --ff-only`；禁止 `pull` / `reset --hard`。
- 重建 api/console 后 `docker compose restart edge`，断言 edge 在 172.20.0.16。
- 不删除 `lighthouse_ai_video_net`，不 `up -d --force-recreate edge`。
- 业务路由、Agent、UI 的 `provider_call=false` 检查通过。
- 密钥扫描 0 命中；账本含 commit、schema、verification。
- worker running；心跳 < 180 秒；queued 超过 10 分钟为 0（SQL 表、角色、时间列写清）。

### 门 2：提交门

- 先 `verify` 再 `git add`；文件完整性 0 失败。
- ruff、ruff format --check、mypy、相关 pytest 与脚本测试全过。
- 工作树无未跟踪的在途资产；提交按文件清单，不 `git add -A`。
- 文档状态与验收清单已回写。

### 门 3：报告门

- 每个百分比有分母；每个图表有来源与统计范围；数字有 `as_of`。
- 结论有证据等级，或报告明确标描述性归档。
- MD 与 HTML 配对校验；无重复目录。
- 导入器字节与 SHA-256 校验通过。

### 门 4：工单门

- ticket JSON、MD、飞书表状态一致。
- 完成定义已执行，记录命令与输出。
- 文档头 status 与代码存在性一致。

## 8. 事实校正（避免继续引用错数）

| 旧说法 | 校正 | 证据 |
|---|---|---|
| A 账本差 2 个迁移 | 差 1 个：`5dbddae` 是 67，生产 068 是 68 | `git show 5dbddae:apps/api/alembic/versions` 计数；`/api/health` |
| 未跟踪条目 8 个 | 12 个 | `git status --porcelain` |
| B 有独有 CDO 差异 | B 相对 main 为 217/0，严格祖先，0 独有提交；CDO router 在 main 也存在 | `git rev-list --left-right --count main...origin/deploy/tiktok-cdo-codex` |
| `abi-export` 仍有 `profiles:["abi"]` | `abi-export` 已无 profile；`abi-migrate`、`export-init` 才有 | `configs/deploy/scrapy/docker-compose.yml` |
| 726,499 行是当前实测 | 是 SOP 记录，2026-11-02 未复测 | `docs/ops/abi-sop.html` |
| B 目标写死 068 | 用 `alembic heads` 动态读取 | 迁移链会前进 |
| 日报日志最后一行是 RUN_STATUS | 脚本先写 RUN_STATUS，再写 end；健康检查用 `grep '^RUN_STATUS=' \| tail -1` | `scripts/daily-report.sh` |
| 11-01 报告必须补成非空 | 允许 `known_gap`，写 MISSING.md，不伪造内容 | 2026-11-01 空目录 |

## 9. 2026-11-02 已落地（本次，未提交）

| 项 | 证据 |
|---|---|
| `AbiColumnCreate` / `AbiDatasetCreateRequest` 加 `extra="forbid"` | `apps/api/tests/unit/test_abi_pii_contract.py` 4 passed |
| `production-scope.json` + drift 脚本读取 scope | `scripts/tests/test-dual-production-drift.sh` 4 例通过；B `frozen_nonprod` 时 SKIP，`--strict` 仍 PASS |
| B 只读 preflight | `scripts/preflight-production-b.sh` 实跑 PASS：SSH 可达、分支正确、edge `172.20.0.30`、四容器 running、备份存在、45G 空闲 |
| B 升级 | **已完成**：`bf7a2815` → `3f889e7`，schema 056 → 068；A/B 均 068；`abi-export` running；edge 仍在 `172.20.0.30` |
| B 升级 runbook | `docs/workflows/workflow-b-upgrade-2026-11.md`，含备份、fast-forward、构建、迁移、edge、公网验收、回滚与执行记录 |
| ABI ETL 第一切片方案 | `docs/plans/abi-data-plane-etl.md`，5 表 / 186,352 行 / 3 天 |
| B 祖先验证 | `git rev-list --left-right --count main...origin/deploy/tiktok-cdo-codex` = 217/0 |

## 10. 2026-11-02 第二批落地（P1 部分）

| 项 | 证据 |
|---|---|
| P1-1 迁移号 allowlist | `configs/contracts/migration-allowlist.json` 收录 9 条历史引用；`check_migration_numbers.py` 现退出 0；`--no-allowlist` 仍报 12 处。新增计划仍必须用 069+。 |
| P1-2 integration CI | `tests/integration` 本地 397 passed；CI `api` job 增加 `Pytest integration`。 |
| P1-3 文档真值 pass | README、生产环境基线、能力总账、能力图谱、AGENTS.md、SP 台账头、ABI 方案、insight 设计状态已改为 2026-11-02 口径。 |
| P1-5 日报健康检查 | `scripts/check_daily_report_health.sh` + 5 例测试；CI 接入。11-01 允许 `known_gap`。 |
| 账本 v2 | `record_release.py` 写 `schema_revision`、`alembic_head`、`verification`、`deployed_commit`；A/B 最新记录均 v2；`verify` 通过。 |
| 安全下限 | 新增 `test_deployment_security_defaults.py`（7 passed）、`test_abi_export_defaults.py`（4 passed）、`test_abi_pii_contract.py`（4 passed）、`test_auth_password_policy.py`（5 passed）。 |
| mypy 债务清零 | `3f889e7` 起 CI 在 mypy 步骤红；42 个 ABI/洞察类型错误先登记并把 baseline 934→976。2026-11-02 已全部修复，无新增 `type: ignore`；current=baseline=934，signatures 478→459。unit 91 passed、postgres_abi 20 passed。见 [TD-2026-11-02-mypy-abi](./TD-2026-11-02-mypy-abi.md)。 |
| B 应用层 ABI 数据 | **已完成**：B 创建与 A 同名 workspace，复制 owner 与成员关系；ETL 装载 5 表 / 186,352 行 / 0 拒绝；catalog 与物理表当前版本计数一致；当前版本内容哈希与 A 全部一致；读路径 `author_id` 哈希、昵称 `***`、正文明文。 |
| ABI 导出终态 | **A/B 已完成**：未遮罩 `si_metric_snapshot` 走 `awaiting_approval → queued → succeeded`，4,856 行 / 103,721 字节；遮罩 `si_tiktok_video` 同步 `succeeded`，31,366 行 / 1,787,894 字节；A/B 产物字节一致；worker 心跳 < 180 秒。见 `docs/plans/abi-data-plane-etl.md` §6.1。 |
| 洞察报告独立复核 | **已完成**：`report_count=1`；DB 正文 181,984 字节，SHA-256 `f7f7c4f0…`；manifest 归一化规则本地复现同一哈希；`source_status=snapshot_only`，UI 显示「数据快照」；GET 401、POST 405、`/insight` 307。 |
| 日报 11-01 known_gap | 已写 `reports/achievements-20261101/MISSING.md`；健康检查 `KNOWN_GAP` 退出 0；20261102 健康检查 PASS。 |
| 报告语言与数字闸门 | **已完成**：共享包 `data_intelligence_hub.report_quality` + 一份 `rules.json`；`tools/insight-report/validate.py --gate`、导入器、CI 共用；删除 `ir_impl/validate.py`；63 词夹具命中 63；当前报告 PASS（279 个百分比、6 张图）；日报 advisory。 |
| 生产 8ecb28e | **已完成（2026-11-03）**：A/B api/abi-export/abi-ingest 新镜像；A/B schema 068；A 的 media-query edge 热修保留；健康 200、业务端点 401；A/B 账本已记。A 因热修用手动七步发布，`deploy-p0.sh` 仍拒绝脏工作区（OI-45）。 |
| 凭证清理与扫描 | **部分完成**：`scripts/check_secrets.py` + 测试 + CI；1984 个 tracked 文件 0 命中；`reports/mcp-token.txt` 移出仓库；Apify/TikHub 控制台轮换待用户。 |
| ABI 远端备份与恢复 | **部分完成**：A 首次加密备份 69M；Mac 与 B 各一份，sha256 一致；scratch Postgres 恢复 5 表 / 186,352 行，current-version 计数与 catalog 一致；脚本支持远端目标。持久 cron 目标待用户。 |
| Workflow scope guard | **已完成**：`scripts/workflow_scope_guard.py` claim/audit/clean；重叠写集、越界写、secret 读、未批准付费调用均退出 1；测试通过。 |
| 健康检查 schema | **已完成**：默认跟随 `/api/health` 的 `schema_head`，不再写死 048；22 passed。 |
| CI | run `41374327302` 全绿：Platform、API、Web Quality、Web Real Chain、Console E2E、两组 Postgres 全过；API 含新增 `Pytest integration`。 |
| ABI ETL 第一切片 | **生产 A 已装载**：5 表 / 186,352 行 / 0 拒绝；catalog 与物理表逐表一致；B 未装。脚本 `scripts/abi_etl_load.py`，坑点见 `docs/plans/abi-data-plane-etl.md` §6。 |
| ABI T-1 扫描试点 | **A 已跑通**：2026-11-01 目标日 131 dataset / 4,163 item；`raw.apify_dataset` head=local=4,163；`raw.apify_item` 4,163（2026-10 2,609 / 2026-11 1,554）。手动 `--scan-once`。 |
| ABI 自动 scan 队列 | **A/B 已完成**：`drain_scan_queue` 处理 scan job；A/B 各 5 个 token 加密入库；B 回填 2026-11-01 raw 131/4,163；`schedule_state` 两账号 2026-11-01。 |
| ABI actor 归因 | **A 已完成**：9 个 actor 入 `meta.actor_registry`；131 dataset 全部回填；分布 tiktok/post 40、youtube/post 32、x/post 24、instagram/post 16、tiktok/hashtag 16、reddit/post 3；unknown 0。 |
| ABI 多日补扫 | **A 已完成**：`backfill_dates` 按 `schedule_state` 补齐缺失日期，最多 7 天；yueguz 缺口 2 天实测 `days=2 enqueued=1`，补扫 2026-10-31 成功；水位用 `GREATEST` 防回退。 |
