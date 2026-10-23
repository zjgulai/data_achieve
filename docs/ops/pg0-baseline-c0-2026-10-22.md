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
