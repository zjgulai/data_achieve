# PG0 C0 基线整合证据

> 执行日期：2026-10-22
> 计划：`docs/superpowers/plans/2026-10-22-governed-task-platform-c0-baseline-integration.md`
> 状态：进行中

## 1. 执行前事实

| 项目 | 值 |
|---|---|
| 起始提交 | `f0560ca652a378ddf9ba65e15284a0311769994b` |
| `feat/p1-identity` 分支 | `feat/p1-identity` @ `5d07eaf4831403733109b1383efdc166c7727bb0`；是 HEAD 的祖先 |
| B5 分支 | `feat/b5-workbench` @ `94d95b24064a4ce2addafb8c50537f0f29aa755c`；领先 13 个提交 |
| B4 分支 | `feat/b4-report-contract` @ `ad968f66570a6738ad122dfef02b1ce4503229d0`；领先 5 个提交；不单独合并 |
| 已批准设计 blob | `052c602942ad8dd42fc80cd38d17c95ac20d2bd2` |
| 已批准设计 SHA-256 | `a648533c80bce42dca385e38347b33b3f666869323f6d34b2e47392a3af1d96f` |
| Alembic head | `202610210055` |
| worktree | 19 条项目记录；4 条 prunable；清理后 15 条项目记录、0 条 prunable；保留 `/private/tmp/b5wt`；新增 C0 worktree |
| RED 清理断言 | `PRUNABLE_PRESENT`；4 条 `dih-*` 元数据待清理 |
| GREEN 清理断言 | `PRUNED`；`WORKTREE_COUNT_OK` |
| 预检结论 | 通过 |

## 2. B5 审查与契约门禁

| 项目 | 值 |
|---|---|
| B5 提交数 | 13 |
| B5 tip | `94d95b24064a4ce2addafb8c50537f0f29aa755c` |
| B5 tip 父提交 | `e7f51c71d1edec71f0298a4d8225319ba9311ebd`、`b02a3a5a1791d17079f202be5cd7f89542b003ae` |
| B5 变更规模 | 57 files changed, 17096 insertions(+), 211 deletions(-) |
| B4 关系 | 已是 B5 祖先（`b4_in_b5=0`）；随 B5 历史进入；未单独合并 B4 分支 |
| B4 迁移 | B4 树有 `202610210052_claims.py`、`202610210053_report_artifacts.py`；B5 树无这两个精确文件；B5 主线的 `202610210052_project_api_key_quota.py`、`202610210053_monitors.py` 不是 B4 迁移 |
| B4→B5 提交数 | 34 |
| B5 迁移 | 056 claims（down 055）、057 report_artifacts（down 056） |
| 迁移列数 | 056：18（claims 14、claim_evidence 4）；057：16 |
| 契约表名 | `claims`、`claim_evidence`、`report_artifacts` 已登记 |
| Claim 五态 | `confirmed · directional · hypothesis · evidence_gap · blocked` 已登记 |
| 新增 REST 路径 | 无（相对 `b02a3a5`） |
| 新 MCP 工具 | `get_run`、`list_records`、`create_report`、`stop`、`balance`；仅内部工具 |
| spec 删除差异 | 仅对 spec 路径检查时 `HEAD..B5` 显示 D；B5 无该路径（`cat-file` 128）；B5 历史没有修改该路径；后续只用标准三方合并，保留 HEAD 的已批准 spec blob，合并后验证 blob；禁止整树 checkout、`-X theirs` 与 squash |
| `git diff --check` | 通过 |
| MERGE_READY | yes |

## 3. B5 合并与 spec 保留

| 项目 | 值 |
|---|---|
| 集成分支 | `feat/pg0-baseline-c0` |
| 合并方式 | `git merge --no-commit --no-ff feat/b5-workbench` |
| 冲突文件 | 无 |
| index spec blob | `052c602942ad8dd42fc80cd38d17c95ac20d2bd2` |
| staged spec 删除 | 无 |
| B4 关系 | 已是 B5 祖先；未单独合并 B4 分支 |
| MERGE_HEAD | `94d95b24064a4ce2addafb8c50537f0f29aa755c` |
| GitNexus staged 分析 | 57 文件、1637 符号、90 流程、critical；计数与风险覆盖全部符号；CLI 仍显示符号列表截断提示 |
| 合并提交 | `4616c8b` |
| 合并后 B5 祖先 | 是（`b5_ancestor=0`） |
| 合并后 B4 祖先 | 是（`b4_ancestor=0`；B4 是 B5 的祖先） |
| 合并后 spec blob | `052c602942ad8dd42fc80cd38d17c95ac20d2bd2` |

## 4. 056/057 迁移验证

| 项目 | 值 |
|---|---|
| 一次性数据库 | Docker `postgres:15`，`127.0.0.1:55432`，库 `c0_migrations` |
| 055 前 claims | `null` |
| upgrade 055 | 通过 |
| upgrade 057 | 通过：055 → 056 → 057 |
| 三张表 | `claims`、`claim_evidence`、`report_artifacts` |
| alembic_version | `202610210057` |
| downgrade 055 | 通过；三张表为 `null` |
| 再次 upgrade 057 | 通过 |
| SCHEMA_HEAD | `202610210057` |


## 4.1 R0 Ruff 清理合回（2026-10-23）

| 项目 | 值 |
|---|---|
| R0 起点 | `8a68069790d9d7c905505892be2968d90f394629` |
| R0 最终提交 | `449860156be5551b749b223dde76aacfa6087340` |
| C0 合并提交 | `72c52648aead926625fc7d55dcb9771e00d06bb4`；`merge(r0): clean inherited Ruff baseline` |
| 合并方式 | `git merge --no-ff feat/pg0-ruff-cleanup`；无冲突 |
| Ruff | `apps/api` 全量真实扫描 748 个文件；exit 0；stderr 空；`All checks passed!` |
| mypy | 命令仍返回 1200 个存量错误；与 C0 起点归一化后均为 498 个唯一诊断签名；新增 0，移除 0；基线非回归通过 |
| 字节完整性 | 合并范围 20 个文件全部满足原生 stat = `os.stat` = read；UTF-8 有效；NUL=0 |
| GitNexus compare | 20 个文件、84 个符号、147 条流程、risk CRITICAL；未使用 `riskSharedAxes` 豁免 |
| CRITICAL 缓解 | 完整 R0 最终审查验证逐任务 AST 等价、目录与 renderer 输出等价、迁移头不变、合同摘要不变、完整测试通过；唯一行为语法变化 `zip(strict=True)` 的等长不变量已验证 |
| 图索引 | 合并后完整 `analyze --force` 成功；45,238 nodes / 76,568 edges / 988 clusters / 901 flows；FTS 构建恢复 |
| 数据库 | `c0-pg15` 保持运行，供 C0 Task 5 integration 使用；未重启或重建 |

R0 不含 migration。C0 schema head 保持 `202610210057`。后续从 Task 5 Step 3 继续，mypy 使用已修订的基线非回归门禁，unit 基线使用 `2493 passed, 2 skipped`。


## 5. 后端测试与目录基线（2026-10-23，R0 合回后续接）

| 项目 | 值 |
|---|---|
| 恢复说明 | resumed after R0；本节为 Task 5 正式证据，接续 4.1，不重复 4.1 |
| 前序事实核对 | Step 1 `uv sync --locked --dev` 已在前序通过（Resolved 207 / Checked 183），锁文件未变；Step 2 Ruff 全量 748 文件 `All checks passed!`；merge evidence commit `38804e5`，工作树 clean |
| Mypy 基线非回归 | 通过；唯一诊断签名 498/498；新增 0，移除 0；命令 exit 1 仍返回 1200 个存量错误（C0 起点 1199，差值 +1，归因：`collectors/tikhub_social.py` 同一 union-attr 签名因 R0 换行多复现 1 次，14→15），不称命令通过，仅基线门禁通过 |
| unit（Step 4） | `2493 passed, 2 skipped`（1 warning：passlib `crypt` DeprecationWarning） |
| integration（Step 5） | `386 passed`（1 warning 同上）；`DATABASE_URL='postgresql+asyncpg://c0:c0@127.0.0.1:55432/c0_migrations'`，使用现有 `c0-pg15` |
| unit 无数据库探针（Step 6） | `2493 passed, 2 skipped`；未设置 `DATABASE_URL`，未运行 `tests/integration` |
| 回归守卫（Step 7） | `OK: 0 failed。` |
| `alembic heads`（Step 8） | `202610210057 (head)` |
| 工具目录（Step 9） | passed；`tool.v1` / `tool-catalog.v1`；284/284/226；digest `35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c`；failures `[]` |
| 平台包生成（Step 10） | 退出码 0；`git status --porcelain -uno` 空输出（生成无 diff） |
| 平台包契约（Step 11） | passed；platform_count=70、capability_count=312、unique_endpoint_count=284 |
| `c0-pg15` 清理（Step 12） | `docker rm -f c0-pg15` 返回 `c0-pg15`；删除后 `docker ps -a` 无该容器 |
| 数量差异记录 | 单元测试总数 2495 = 2493+2：两个目录守卫测试（`test_catalog_digest_parity`、`test_catalog_reconciliation`）以 gitignore 的 `generated/platform-packages.json` 存在为条件 skip；本地存在该生成物时两测试转 passed（2495 passed），移开后按基线条件复现 `2493 passed, 2 skipped`；两轮均记录，未修改证据表 |
| 警告汇总 | unit/integration：passlib `crypt` DeprecationWarning；回归守卫运行（含恢复生成物后的 2495 全量）：另见 `test_demo_data.py` 3 处 aiosqlite `Event loop is closed` 未处理线程异常警告；对判定无影响 |
| 环境缺口 | CI api job 无 PostgreSQL 服务；无数据库时只运行 `tests/unit`，`tests/integration` 必须显式提供 `DATABASE_URL`；`generated/` 在 .gitignore 中，全新 checkout 两个目录守卫测试为 skip |

## 6. 前端测试与构建基线（2026-10-23）

执行环境：Node v26.7.0、pnpm 9.15.4、worktree `data_scrapy-c0`、分支 `feat/pg0-baseline-c0`、起始 HEAD `ec1c300`。

| 项目 | 值 |
|---|---|
| `pnpm install --frozen-lockfile` | 退出码 0；508 个包，全部复用缓存，无下载；锁文件无 diff |
| `pnpm -C apps/scraper-console test` | 220 passed, 0 failed, 0 cancelled, 0 skipped；耗时 282.6ms |
| `pnpm -C apps/scraper-console lint` | 退出码 0；eslint 无输出（无告警、无错误） |
| `next build`（`NEXT_PUBLIC_API_URL=https://scrapy.luteos.com`） | 退出码 0；输出含字面 `Compiled successfully in 3.1s`；TypeScript 检查通过；23 个静态页全部生成 |
| 构建路由表 | 包含 `/workbench`、`/reports`、`/capabilities`（另见 `/capabilities/[toolId]`、`/reports/[artifactId]` 动态路由） |
| 构建后 `git status --porcelain -uno` | 空输出；`.next` 与缓存均为忽略内容，`pnpm-lock.yaml` 无 diff |
| GitNexus impact（编辑前门禁） | 对本文档 upstream impact 返回 UNKNOWN（0 caller，file-node 无 process/module 轴）；文本搜索确认 apps/、scripts/、package.json 无代码引用本文档，属纯证据 markdown |
| 浏览器验收交接 | 延期 C14；grep 证据 `C14_HANDOFF_REQUIRED`；四个判据见下 |
| 构建警告 | Next 16.3.0：`middleware` 文件约定已弃用，建议改用 `proxy`；来源 `apps/scraper-console/src/middleware.ts`（commit `2c1ad41`，pre-existing，Task 6 未改）；不影响本次 build 门禁；迁移风险交 Task 7/8 汇总 |
| 提交前 GitNexus | 证据文档 diff 未命中索引符号；退出码 0；无 `partial`/`truncated`；干净树基线为 `未检测到变更。` |

浏览器验收未在 C0 执行。交接检查结果：`grep -n 'workbench\|reports\|capabilities' apps/scraper-console/e2e/routes.spec.ts` 无匹配，退出码 1，输出 `C14_HANDOFF_REQUIRED`。该文件的 `PAGE_ROUTES` 常量列出的 14 条路由均不含 `/workbench`、`/reports`、`/capabilities`，三个 B5 页面均未覆盖。

C14 必须逐条覆盖以下四个判据：

1. `/workbench`、`/reports`、`/capabilities` 返回 200，页面根节点存在 `<main>`。
2. 三个页面都不出现 5xx 响应。
3. 浏览器控制台没有 `console.error`。
4. `/workbench` 显示五步流程入口；`/reports` 显示报告列表或空态；`/capabilities` 显示能力目录。

风险记录：C0 的合并门禁是后端单元/集成测试、前端单元测试、lint 与生产构建。浏览器验收延期到 C14。若 C14 未在 PG0 验收前执行，风险是 B5 页面在真实 API 下的空态、权限态或控制台错误未被发现。该风险由 C14 的 `e2e/routes.spec.ts` 与 PG0 验收门禁关闭。不得用本节替代 C14 的验收。

## 7. catalog/image/schema 事实快照（2026-10-23）

执行环境：Docker client 29.8.0、server 29.5.2；Docker context `colima`；server `linux/arm64`、主机 `arm64`（aarch64）。worktree `data_scrapy-c0`、分支 `feat/pg0-baseline-c0`。

| 项目 | 值 |
|---|---|
| 镜像构建基座提交 | `29309f5d4941018fa7ead876c2e0c62b1cf5ac2f` |
| 事实证据提交 | `5f639bb2d7c58ac604f881ed4fca073bccc593f1` |
| API 镜像 | `data_achieve_scrapy_api:c0-29309f5`；context `apps/api`；默认 `INSTALL_PLAYWRIGHT=false`、`INSTALL_OSINT=false`，未传 build args |
| API 镜像 ID | `sha256:fb5dbafd3ee8356de42c8b923c8092d47231aa1d3d56601e47bf3edbae1585d8` |
| API RepoDigests | data_achieve_scrapy_api@sha256:fb5dbafd3ee8356de42c8b923c8092d47231aa1d3d56601e47bf3edbae1585d8（本地 build 自指，无 registry 推送来源） |
| Console 镜像 | `data_achieve_scrapy_console:c0-29309f5`；context 仓库根；未传 `NEXT_PUBLIC_API_URL`，镜像内嵌 Dockerfile 默认的生产 B API `https://scrapy.lute-tlz-dddd.top`；生产 compose 默认以 `SCRAPY_PUBLIC_URL` 覆盖为生产 A `https://scrapy.luteos.com` |
| Console 镜像 ID | `sha256:4621204d83bd1bdb217a5a556ab4e75817ad0be68cae596355766475af6703e8` |
| Console RepoDigests | data_achieve_scrapy_console@sha256:4621204d83bd1bdb217a5a556ab4e75817ad0be68cae596355766475af6703e8（本地 build 自指，无 registry 推送来源） |
| 镜像架构 | 两镜像均 `arm64` / `linux`；本地 Colima（aarch64）产物 |
| 生产差异警示 | 本地镜像不可直接视为生产 amd64 产物；生产发布须另行构建 amd64（如 buildx `--platform linux/amd64`） |
| 推送状态 | 未 push；两镜像仅存在于本地 Docker，未进入任何 registry |
| compose 镜像引用 | 默认 profile 解析为 9 行，真实清单见下；不含 `proxy`、`obscura`、`browser_use` 三个 profile 门控服务 |
| `catalog_digest` | `35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c` |
| 工具计数 | 284 / 284 / 226（tool / canonical / executable） |
| 平台包计数 | 70 / 312 / 284（platform / capability / unique endpoint） |
| `tool-catalog.lock.json` SHA-256 | `1e99add62f3d9bf5d43a6bf2fefba2a3596556d50234b63108e6fd64a173dc3e` |
| `platform-packages.lock.json` SHA-256 | `59f5976d5761e2e03c5525b80e53202ffc0dbe56d51def0d21a650a77f1f031e` |
| `SCHEMA_HEAD` | `202610210057`（`uv run alembic heads` 输出） |

compose 镜像引用真实清单：dummy env（`SCRAPY_POSTGRES_USER=x`、`SCRAPY_POSTGRES_PASSWORD=x`、`SCRAPY_POSTGRES_DB=x`、`SCRAPY_JWT_SECRET=x`、`SCRAPY_AUTH_COOKIE_SECURE=true`）解析 `configs/deploy/scrapy/docker-compose.yml` 后 `config --images`，`LC_ALL=C sort -u` 恰好 9 行：

```text
crivellarodiego/spiderfoot:latest
data_achieve_scrapy-tor
data_achieve_scrapy_api:latest
data_achieve_scrapy_console:latest
data_achieve_scrapy_web:latest
nginx:1.27-alpine
postgres:16
soxoj/maigret:latest
spiderfoot_bridge:latest
```

构建警告记录（Task 6 移交风险）：Console build 再次出现 Next 16.3.0 弃用警告 `The "middleware" file convention is deprecated. Please use "proxy" instead.`（修复建议 `npx @next/codemod@canary middleware-to-proxy .`）。来源 `apps/scraper-console/src/middleware.ts`（commit `2c1ad41`，pre-existing，本次未改）。该警告不影响 image build：构建退出码 0，镜像正常产出；迁移决策由 Task 8 汇总。

GitNexus 编辑前门禁：对本文件 upstream impact 返回 UNKNOWN（0 caller；file-node 无 process/module 轴）。文本搜索 `apps/`、`scripts/`、`configs/`、`package.json` 确认无代码引用本文件，属纯证据 markdown，追加安全。build 后 `git status --porcelain -uno` 空输出，锁文件与 tracked 文件无 diff；镜像属 runtime 产物，不提交。

## 8. GitNexus 重建与 pg0-baseline-v1

执行环境（2026-10-23）：worktree `/Users/lute/Project/data_scrapy-c0`；分支 `feat/pg0-baseline-c0`；起始 HEAD `e227070054914f9cbef8cb5d508e5f4aa73d8dcb`；工作树 clean；`pg0-baseline-v1` 创建前不存在（`git rev-parse -q --verify refs/tags/pg0-baseline-v1` 返回非零）。

### 8.1 GitNexus 索引

| 项目 | 值 |
|---|---|
| GitNexus analyze | 退出码 0（首次 `--index-only` 22.0s；`--force` 全量重建 45.8s，复用 1062 / 1063 个文件的解析缓存） |
| 标签创建时 GitNexus `index.commit` | `e227070054914f9cbef8cb5d508e5f4aa73d8dcb` |
| 标签创建时 `index.commit` 与 `git rev-parse HEAD` | 相等；当时同时也是 `current.commit` |
| GitNexus status | `up-to-date`；`incompleteReasons=[]` |
| `contentDrift` | `current`；覆盖 1288 个文件 |
| `runnerIdentityStatus` | 默认 pnpm runner 为 `current`；强制切换 bun runner 会仅因 runner identity 不同显示 `stale`，不表示内容索引漂移 |
| 索引能力 | graph `available`（ladybugdb）；fts `available`（ladybugdb-fts）；vectorSearch `unavailable`（`exactScanLimit` 10000） |
| 标签创建时计数 | 45,243 nodes / 76,573 edges / 988 clusters / 901 flows；files 1290；embeddings 0 |
| 初始证据提交后的交付态索引 | 提交 `88341b400a3faa823ac130774b57cd6700a56c4f` 后重建：`index.commit = current.commit = 88341b4`、`up-to-date`、`incompleteReasons=[]`、45,251 nodes / 76,581 edges / 988 clusters / 901 flows |

状态词表说明：brief 期望的 `fresh` 在 GitNexus 1.6.12 中不是合法取值。`dist/cli/status.js:302` 写的是 `status: isUpToDate ? 'up-to-date' : 'stale'`，中文输出为「状态: ✅ 已是最新」。本节按工具真实输出记录 `up-to-date`，不伪写 `fresh`。

分析器警告（`analyze --index-only --force` 全量日志，68 条 JSON 记录）：

| 类别 | 条数 | 内容 |
|---|---:|---|
| `callable-value-flow` | 66 | `candidate set exceeded the cap; no partial CALLS emitted`（`candidateCount` 33，`cap` 32）；集中在 `agents/shusuo/capabilities.py`、`mcp_runtime/server.py`、`mcp_runtime/runtime.py`；未发出部分 CALLS，因此这些调用边在图中缺失 |
| `scope-resolution` | 1 | 496 个属性读写点命中本工作区字段，但定义锚点在另一种语言，按语言推断拒绝连接；这些字段的查询结果为空，不等于「未使用」 |
| `processes` 截断 | 1 | 报告 901 条 flow，但 `entryPointCandidatesDropped=3002`（3202 个候选入口点中 3002 个未排入），`walksCutByBudget=34`，`calleesDropped=1058`；`entryPointsUnexplored=0`、`processesDropped=0`、`tracesDepthCapped=0`；缺失的 flow 不等于代码路径不存在 |

### 8.2 最终变更分析

| 项目 | 值 |
|---|---|
| 干净树基数 `detect-changes` | `未检测到变更。`；退出码 0（追加第 8 节之前、索引重建之后） |
| 提交前 `detect-changes`（带本文档 diff） | `变更：1 个文件，2 个符号`；`受影响流程：0`；`风险等级：low`；退出码 0 |
| 提交前命中的符号 | 两个 markdown 章节节点：`Section PG0 C0 基线整合证据`、`Section 7. catalog/image/schema 事实快照（2026-10-23）`，均属 `docs/ops/pg0-baseline-c0-2026-10-22.md` |
| `partial` / `truncated` | 未出现 / 未出现；按中文 CLI 注记检查「结果不完整」与「列表已截断」，两轮均无匹配 |
| 追加第 8 节前的编辑门禁 | `impact` 对 `File:docs/ops/pg0-baseline-c0-2026-10-22.md` upstream 返回 `impactedCount 0`、`risk UNKNOWN`（file-node 无 process/module 轴）；文本搜索全仓（排除 `.git`、`.gitnexus`、`node_modules`、`.venv`）只有 `docs/superpowers/plans/2026-10-22-governed-task-platform-c0-baseline-integration.md` 引用本文件，无任何代码、配置或脚本引用，UNKNOWN 已用文本搜索解除 |

### 8.3 标签

| 项目 | 值 |
|---|---|
| 标签 | `pg0-baseline-v1` → `e227070054914f9cbef8cb5d508e5f4aa73d8dcb` |
| ref | `refs/tags/pg0-baseline-v1`；`git cat-file -t` = `tag`（annotated） |
| tag 对象 SHA | `48aaccfa5a3689f23f7517cfb88b59c2533805ab` |
| 标签消息 | `PG0 baseline v1: C0 integration at e227070; B5 94d95b2 merged; spec 052c602 preserved; schema 202610210057` |
| 远端标签 | 未推送；等待人工批准（只检查本地 ref，未访问远端标签） |

### 8.4 最终验收

```text
b5_ancestor=0
b4_ancestor=0
052c602942ad8dd42fc80cd38d17c95ac20d2bd2
TAG_ON_CODE_BASELINE
```

| 断言 | 值 |
|---|---|
| `feat/b5-workbench` 是 HEAD 祖先 | 是（`b5_ancestor=0`） |
| `feat/b4-report-contract` 是 HEAD 祖先 | 是（`b4_ancestor=0`） |
| spec blob `HEAD:docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md` | `052c602942ad8dd42fc80cd38d17c95ac20d2bd2` |
| `pg0-baseline-v1^{commit}` == `HEAD^` | 是（`TAG_ON_CODE_BASELINE`） |
| 提交后 `git status --porcelain -uno` | 空输出 |

标签语义：标签目标 `e227070` 是代码与事实基线。Task 8 的证据提交在标签之后创建，只改文档；标签不指向该证据提交，也不应被移动到它。

### 8.5 Task 5/6/7 门禁事实引用

本节不重跑完整 unit / integration / build。门禁事实以 Task 5/6/7 报告与第 4–7 节为准：

| 任务 | 引用事实 |
|---|---|
| Task 5 | Ruff 全量 748 文件 `All checks passed!`；mypy 唯一诊断签名 498/498 非回归（命令仍返回 1200 个存量错误，不称命令通过）；clean-checkout unit `2493 passed, 2 skipped`；integration `386 passed`；回归守卫 `OK: 0 failed。`；`alembic heads` = `202610210057`；工具目录 284/284/226；平台包 70/312/284 |
| Task 6 | frontend `220 passed / 0 failed / 0 skipped`；eslint 无输出；`next build` 退出码 0，含 `Compiled successfully in 3.1s`，23/23 静态页；`C14_HANDOFF_REQUIRED` |
| Task 7 | 两镜像本地构建退出码 0；compose 默认 profile 9 个镜像；`catalog_digest` `35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c`；`tool-catalog.lock.json` SHA-256 `1e99add62f3d9bf5d43a6bf2fefba2a3596556d50234b63108e6fd64a173dc3e`；`platform-packages.lock.json` SHA-256 `59f5976d5761e2e03c5525b80e53202ffc0dbe56d51def0d21a650a77f1f031e`；`SCHEMA_HEAD` `202610210057` |

本轮 fresh 快速复核（仅必要项，未重跑全量 unit / integration / build）：

| 复核项 | 结果 |
|---|---|
| `uv run ruff check .`（`apps/api`） | `All checks passed!`；退出码 0 |
| `pnpm -C apps/scraper-console test` | 220 passed / 0 failed / 0 cancelled / 0 skipped；261.9ms |
| `configs/tool-catalog.lock.json` SHA-256 | `1e99add62f3d9bf5d43a6bf2fefba2a3596556d50234b63108e6fd64a173dc3e`，与第 7 节一致 |
| `configs/platform-packages.lock.json` SHA-256 | `59f5976d5761e2e03c5525b80e53202ffc0dbe56d51def0d21a650a77f1f031e`，与第 7 节一致 |
| `pytest --collect-only -q`（清空 `DATABASE_URL`、`TEST_DATABASE_URL`） | `2992 tests collected` |


### 8.6 最终风险汇总

| 编号 | 风险 | 状态 | 关闭条件 |
|---|---|---|---|
| R1 | `C14_HANDOFF_REQUIRED`：`/workbench`、`/reports`、`/capabilities` 的浏览器验收未执行；`apps/scraper-console/e2e/routes.spec.ts` 的 14 条 `PAGE_ROUTES` 不含这三个路由 | 未关闭 | C14 按第 6 节四个判据执行 |
| R2 | CI `API Quality Gate` 存量红：该 job（`ubuntu-latest`，无 PostgreSQL 服务）仍运行默认全量 `uv run pytest` 与 `check_pytest_baseline.py`，而后者默认路径为 `tests/unit` + `tests/integration` | 未关闭 | 本轮各项均为本地绿；不得据此宣称 CI 全绿 |
| R3 | integration `386 passed` 的一次性数据库 `c0-pg15` 已删除，当前只有 `--collect-only`（2992）可重放。Task 8 曾在无数据库时运行 integration，得到 385 passed / 1 failed；该命令违反「无数据库时不得运行 integration」的计划口径，只作为环境诊断记录，不属于门禁或基线结果 | 未关闭 | 需要可重放载体时按 `127.0.0.1:55432` 重建 `c0-pg15` |
| R4 | 回归守卫线程警告可能为 10 处（`test_demo_data` 3 + `test_tikhub_param_contract` 7），第 5 节只写了 3 处；另有 passlib `crypt` DeprecationWarning（unit / integration 各 1 处） | 未证实 | 本轮单独运行这两个文件（75 passed）未复现 `Event loop is closed`，10 处仍属「可能」；判据不受影响 |
| R5 | Next 16.3 `middleware` → `proxy` 存量迁移风险；来源 `apps/scraper-console/src/middleware.ts`（`2c1ad41`，pre-existing，本次未改） | 未关闭 | 迁移决策待定；当前不影响 build（退出码 0） |
| R6 | 本地镜像仅 `linux/arm64`（Colima aarch64），不是生产 amd64；Console 镜像已在构建期内嵌生产 B API `https://scrapy.lute-tlz-dddd.top`。生产 compose 的 `SCRAPY_PUBLIC_URL` 只在重新构建时作为 build arg 生成生产 A `https://scrapy.luteos.com` 镜像，不能在运行时覆盖已有 B 镜像；两镜像均未 push | 未关闭 | 生产发布须另行 amd64 构建（buildx `--platform linux/amd64`），显式传入生产目标 API，并走批准流程 |
| R7 | API 镜像存量嵌套 `__pycache__` / `.pyc`：`apps/api/.dockerignore` 的裸 `__pycache__` 规则不覆盖嵌套目录；镜像内 `/app` 下实测 28 个 `__pycache__` 目录、467 个 `.pyc` 文件 | 未关闭 | 改为 `**/__pycache__`、`**/*.pyc` 后重建 |
| R8 | `task-7-report.md` L49 把构建基座 `29309f5d4941018fa7ead876c2e0c62b1cf5ac2f` 裸称「事实提交」 | 已归类 | 语义应称「构建基座」；`29309f5` 是镜像构建所基于的提交，其后 `5f639bb`（冻结事实）与 `e227070`（补充构建边界）才是事实证据提交 |
| R9 | `vectorSearch` 能力 `unavailable`（`exactScanLimit` 10000） | 记录 | 语义检索退回精确扫描；不影响图与全文检索门禁 |

### 8.7 未执行项

未 push 分支、未 push 标签、未创建 PR、未操作生产、未访问远端标签、未启动浏览器。Task 8 只创建本地 annotated tag，只提交本文件。
