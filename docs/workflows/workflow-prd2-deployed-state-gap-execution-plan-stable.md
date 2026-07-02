---
title: PRD2 Deployed State Gap Audit And Execution Plan
doc_type: workflow
module: automation
topic: prd2-deployed-state-gap
status: stable
created: 2026-06-21
updated: 2026-07-02
owner: self
source: human+ai
---

# PRD2 Deployed State Gap Audit And Execution Plan

## 0. Evidence Boundary

本文件盘点的是 2026-06-21 M3 GitHub API-first 深化发布后的“线上当前状态 vs PRD2/本地工作树目标”。2026-06-22 增补 M4 源码分支状态：PR #6 已把 M4-1/M4-2 合并到 `main@67f611e`；PR #7 已把 M4-3 合并到 `main@8cd3e8f` 且 main CI 通过。2026-06-23 已完成一次小范围 M3 GitHub API-first 生产 package gate：`topic=web-scraping`、`max_repositories=3`、允许 Source/Task write、一次 GitHub API TaskRun、Dataset save、report asset、drift snapshot，并按 `cleanup_after_evidence` 清理。同日已完成 M5 Public Web/RSS/Docs production package smoke：允许一次公开 RSS TaskRun、`public_content_update` DatasetVersion save、read-only drift/report preview，并按 exact-ID 与 generic E2E cleanup 清理；随后已完成 M5 Public Content Report asset gate，允许创建一个 `public_content` Report asset 并清理；之后已完成 M5 Public Content Dataset export gate，允许创建一个 CSV DatasetExportJob、写出一个受控导出文件、下载校验并清理 scoped fixtures 与导出文件；随后已完成 M5 Public Content retained lifecycle gate，保留一组 production canary 资产并验证重登录后的 Dataset/Report/Export 可见性与 export artifact 存在。2026-06-24 先本地补齐 public-content drift event 专用持久化路径，随后部署 production SHA `68c27e0f9c62d542149eedc5b18439938103b4bb` 并完成一个 scoped production drift-event gate：创建 `public_content_drift` DatasetDriftEvent、重复提交复用同一 ID，并在取证后清理为零；retained canary inventory 的 `dataset_drift_events=0` 历史事实不代表 retained canary 已更新。同日继续部署 production SHA `af23cefc92aa9fec336f632a5b1561623811c2fd` 并完成一个 scoped production docs/page gate：`generic_web` 公开 docs/page 进入 `public_content_update` DatasetVersion、read-only drift、`public_content_drift` 事件和 `public_content` Report asset，并在取证后清理为零。随后部署 production SHA `a81154426fd4e942fc9439de3dcbd9c816122562` 并完成一个 scoped public-content scheduler approval gate：针对 `public_feed` DatasetVersion 批准 `manual_refresh_only` schedule metadata，验证 `run_started=false`、`scheduler_tick_started=false` 且 approval 前后 TaskRun 不变，并在取证后清理为零。随后本地完成 retained public-content TTL/cleanup policy slice，并在同日部署到 production SHA `d11d5a477ea3125649f7674495bfca5b93148e32` 完成 production retained cleanup dry-run gate：首次 dry-run 暴露 member workspace lineage 覆盖不足后停止 execute，修复后 dry-run 命中 retained canary 的 Source/Task/TaskRun/Dataset/Version/Report/Export asset，`export_artifact_path_violations=0`；默认 168 小时 TTL dry-run 全 0。本文的生产写入证据只覆盖这些授权包；scheduler approval 只证明任务配置 mutation，不证明 scheduler tick 或 recurring monitoring；retained cleanup dry-run 只证明计划和安全边界，不证明 cleanup execute 或 canary deletion；不覆盖 provider call、邮件发送、生产浏览器运行或浏览器 artifact 写入。

2026-06-24 进一步完成 scoped scheduler tick gate 和 retained canary scheduler/drift refresh gate。前者证明一个临时 scoped `public_feed` Task 可由 background scheduler tick 执行并在取证后清理；后者直接更新 retained canary，新增 retained TaskRun `fb2dc909-f125-402e-8759-7443e0214e55` 和 retained `public_content_drift` event `73fbce88-ea11-4cc6-8c61-c6088d1ccaec`，随后恢复 `manual_refresh_only` / `schedule_cron=null`。post-refresh cleanup dry-run 暴露 later scheduler TaskRun lineage gap 后，已修复并部署 production SHA `3c92fcbf2230e1b0b4eef71afea2b8e7547d3331`；最终 retained cleanup dry-run 返回 `task_runs=2`、`dataset_drift_events=1`、`cleanup_ready=true`、`export_artifact_path_violations=0`。同日 retained TTL observation baseline 证明默认 168h dry-run 仍为 0、24h dry-run 已命中完整 retained canary graph。后续 deploy marker diagnosis 确认 active app marker `/opt/data-achieve-scrapy/app/.deploy-sha` 与 app `HEAD=3c92fcbf2230e1b0b4eef71afea2b8e7547d3331` 匹配；父级 `/opt/data-achieve-scrapy/.deploy-sha=dda2786638d4aac8647bbff8b3694b05113678f3` 和 `current` symlink 是旧 release-directory 路径残留，不应作为当前 compose 部署身份来源。2026-06-25 已将未来生产身份核验标准写入 `.codex/commands.md` 和 R0 release boundary log：当前 compose 布局以 `/opt/data-achieve-scrapy/app/.deploy-sha` 为准，父级 marker/current symlink 只在单独 housekeeping gate 中处理。同日 retained TTL midpoint observation 证明 canary 仍保持 `manual_refresh_only` / `schedule_cron=null`，default 168h 与 48h dry-run 均为 0，0h dry-run 仍覆盖完整 retained graph。2026-07-01 retained TTL final 168h observation 证明 retained canary 已超过 `2026-06-30T12:38:16Z` 默认 168h threshold，default 168h dry-run 命中完整 retained graph 且 `cleanup_ready=true`、`export_artifact_path_violations=0`。当前仍不证明 cleanup execute、canary deletion、provider/email、production browser run 或 browser artifact write。

2026-07-02 当前生产只读核验显示：`GET https://scrapy.lute-tlz-dddd.top/api/health` 返回 `environment=production`、`status=ok`、`database=connected`、`schema=current`、`schema_revision=202606110026`、`schema_head=202606110026`、`scheduler_enabled=true`；active app working tree `/opt/data-achieve-scrapy/app` 的 `HEAD` 与 `/opt/data-achieve-scrapy/app/.deploy-sha` 均为 `b81a4be2a47f387d381293db7c4b2932128f6708`；API/Web compose working directory 仍为 `/opt/data-achieve-scrapy/app/configs/deploy/scrapy`；本地 `codex/release-3b-on-428` 与 `origin/codex/release-3b-on-428` 同为 `b81a4be2a47f387d381293db7c4b2932128f6708`，`main` 与 `origin/main` 仍为 `42851929d59d82708c9380d36347ca721979297d`。Loop 35 source-control read-only check 进一步确认 remote refs 与本地一致，`main`/`origin/main` 均为 release branch 祖先，release branch 领先 1 个提交，当前没有 `codex/release-3b-on-428 -> main` GitHub PR。本次核验为 L3 production read-only/source-control read-only，不执行 production write、provider call、email send、cleanup execute、scheduler mutation、production browser run、browser artifact write、PR creation 或 merge。

| Evidence | Current fact | Boundary |
|---|---|---|
| Production health | `GET https://scrapy.lute-tlz-dddd.top/api/health` 返回 `environment=production`、`status=ok`、`database=connected`、`schema=current`、`schema_revision=202606110026`、`schema_head=202606110026`、`scheduler_enabled=true` | L3 production read-only smoke；证明 current production release 已对齐到 PRD2 R0 schema `202606110026` |
| Production deploy identity | 2026-07-02 read-only probe: active app `HEAD=b81a4be2a47f387d381293db7c4b2932128f6708` and `/opt/data-achieve-scrapy/app/.deploy-sha=b81a4be2a47f387d381293db7c4b2932128f6708`; running API/Web compose working directory is `/opt/data-achieve-scrapy/app/configs/deploy/scrapy`; parent marker/current symlink remain separate housekeeping evidence, not current compose identity | L3 deployment evidence；当前 compose 部署身份应读取 app marker，不应读取父级旧 marker |
| Production identity probe standard | 2026-06-25 `.codex/commands.md` standardizes future probes on `cd /opt/data-achieve-scrapy/app`, `git rev-parse HEAD`, `cat .deploy-sha`, API/Web compose working directory inspect, and health check | Docs-only standardization；未改写生产 marker，未更新 symlink，未 restart 或 deploy |
| Public content retained TTL final 168h observation | 2026-07-01 production read-only/dry-run pass confirmed the retained canary crossed threshold `2026-06-30T12:38:16Z`; active app `HEAD` and `.deploy-sha` both equal `42851929d59d82708c9380d36347ca721979297d`; retained task remains `manual_refresh_only` with `schedule_cron=null`; default 168h dry-run matched the full retained graph with `task_runs=2`, `dataset_drift_events=1`, `dataset_export_jobs=1`, `reports=1`, `report_audit_events=1`, `export_artifact_files=1`, `cleanup_ready=true`, and `export_artifact_path_violations=0`; 0h dry-run matched the same graph | L4 production read-only/dry-run；证明 default 168h threshold 和 cleanup graph readiness；不证明 cleanup execute、canary deletion、provider/email/browser/export |
| Production pages | `/dashboard`、`/automation`、`/datasets`、`/tasks`、`/sources`、`/raw-records`、`/reports`、`/alerts`、`/notifications`、`/projects`、`/signals`、`/entities`、`/toolkit` 均返回 `200` | L3 production read-only smoke；不证明页面内写入链路可用 |
| Production auth boundary | 未认证访问 `/api/automation/platform-packages` 和 `/api/sources` 返回 `401 application/json` | L3 production read-only smoke；符合业务接口需要登录态的 API 合同 |
| Authenticated read-only API smoke | 既有 demo 账号读取 session、dashboard、tasks、reports、alert events、notifications 均通过 | L3 production read-only；没有创建或修改业务数据 |
| GitHub API-first package | 真实生产 API Playwright gate `PLAYWRIGHT_REAL_API=true ... --grep "renders automation platform packages"` 返回 `2 passed`；scope 为 `topic=web-scraping`、`max_repositories=3` | L4 authorized live；证明小范围 GitHub package write-through、Dataset save、report asset、drift snapshot 和 cleanup 链路，不证明大规模或定时采集 |
| GitHub cleanup register | cleanup dry-run 发现 scoped E2E residue：`users=8`、`workspaces=8`、`workspace_members=16`、`notifications=8`、`dataset_versions=2`、`dataset_drift_events=2`、`report_audit_events=2`；execute 后 recount 全为 0 | L4 cleanup evidence；保留证据，不保留测试资产 |
| Public content package | 公开 RSS `https://hnrss.org/frontpage` 生产 TaskRun `success`，采集 5 条 feed entries，保存 `public_content_update` DatasetVersion `row_count=5`，read-only drift/report preview 通过，后续 gate 创建 `public_content` Report asset，在 export gate 创建 CSV DatasetExportJob、写入 4900-byte export artifact 且下载校验通过，在 retained gate 保留一组 canary Dataset/Report/Export asset，并在 2026-06-24 drift-event gate 创建/复用一个 `public_content_drift` DatasetDriftEvent；docs/page gate 使用 `generic_web` 采集 `https://www.iana.org/help/example-domains`，保存 `public_content_update` DatasetVersion `row_count=1`、`collector_schema_versions=["generic_web.v1"]`，创建/复用 `public_content_drift` DatasetDriftEvent 并创建 `public_content` Report asset；scheduler approval gate、scheduler tick gate、retained canary scheduler/drift refresh gate、post-refresh cleanup dry-run lineage fix、retained TTL observation baseline/midpoint/final 168h observation 均已完成 | L4 authorized live + dry-run evidence；证明小范围 public_feed 与 generic_web write-through、Dataset save、read-only drift/report preview、Report asset、Dataset export、DatasetDriftEvent persistence、schedule approval mutation、scheduler tick execution、retained canary refresh、cleanup-after-evidence、retained-no-cleanup 生命周期、retained cleanup dry-run 计划、24h threshold 和 default 168h threshold；不证明 production cleanup execute、canary deletion、provider/email 或 browser runtime |
| Public content retention register | retained lifecycle gate 保留 `retained-public-content-20260623123816-90w0q7@example.com` 资产链：Source `c86b280c`、Task `b8a4cb3f`、original TaskRun `1f684c04`、Dataset `ee4a4a7a`、Version `6e2cbc17`、Report `38a0f8ce`、ExportJob `3f43b866`；2026-06-24 retained refresh 新增 scheduler TaskRun `fb2dc909-f125-402e-8759-7443e0214e55` 和 `public_content_drift` DatasetDriftEvent `73fbce88-ea11-4cc6-8c61-c6088d1ccaec`；post-fix retained preflight 返回 `task_runs=2`、`dataset_drift_events=1`、`schedule_policy=manual_refresh_only`、`schedule_cron=null` | L4 retained evidence；保留测试资产，未来清理必须按 retained cleanup policy，不走 generic E2E cleanup |
| Public content drift event production gate | 2026-06-24 部署 SHA `68c27e0f9c62d542149eedc5b18439938103b4bb` 后，新建 scoped public RSS fixture，保存 `public_content_drift` DatasetDriftEvent `6acbd871-e0f8-4580-a7c7-b3d2459962f1`，重复提交复用同一 ID，exact-ID cleanup 和 generic cleanup dry-run 全 0 | L4 authorized live；证明生产 save/list/reuse 与 cleanup-after-evidence；不证明 retained canary 已更新或 scheduler recurring drift 已启用 |
| Public content docs/page production gate | 2026-06-24 部署 SHA `af23cefc92aa9fec336f632a5b1561623811c2fd` 后，新建 scoped generic_web docs/page fixture，保存 `public_content_update` DatasetVersion `9f4d3da5-2d87-45bd-8d15-5ef3d8b7a73d`，创建/复用 `public_content_drift` DatasetDriftEvent `05847c1a-5013-4fc8-8d1f-5bec747d0408`，创建 `public_content` Report asset `9b2ec052-0ba8-482f-9902-209da8c51885`，exact-ID cleanup 和 generic cleanup dry-run 全 0 | L4 authorized live；证明 `generic_web` docs/page 小范围生产链路；不证明 content hash 已在生产发生变化、retained canary 已更新或 scheduler recurring drift 已启用 |
| Public content scheduler approval production gate | 2026-06-24 部署 SHA `a81154426fd4e942fc9439de3dcbd9c816122562` 后，新建 scoped public RSS fixture，保存 `public_content_update` DatasetVersion `1a9ce0f2-b7e3-4437-bb4e-a1c45c1a78b7`，批准 Task `6338d234-554d-4527-9f51-5f695e646bdf` 的 `manual_refresh_only` schedule metadata，审计事件 `public_content_schedule_approved`，`run_started=false`，`scheduler_tick_started=false`，approval 前后 TaskRun 数量和 ID 不变，exact-ID cleanup 和 generic cleanup dry-run 全 0 | L4 authorized live；证明 public-content schedule approval mutation；不证明 scheduler tick execution、recurring monitoring、retained canary schedule refresh 或 cron execution |
| Public content retained cleanup dry-run gate | SHA `c321a52` 首次 production dry-run 暴露 shared/member workspace lineage 未覆盖 Source/Task/Run/Dataset/Report，未执行 cleanup；修复 SHA `d11d5a4` 后 `--older-than-hours 0` dry-run 返回 `users=1`、`workspaces=1`、`workspace_members=2`、`sources=1`、`collection_tasks=1`、`task_runs=1`、`datasets=1`、`dataset_versions=1`、`dataset_export_jobs=1`、`reports=1`、`report_audit_events=1`、`notifications=1`、`export_artifact_files=1`、`export_artifact_path_violations=0`；默认 168 小时 TTL dry-run 全 0 | L4 production dry-run；证明 cleanup plan、artifact root safety 和 TTL cutoff；不证明 cleanup execute、retained canary deletion、scheduler tick 或 recurring monitoring |
| Public content scheduler tick production gate | 2026-06-24 在 SHA `d11d5a4` 上用 scoped `public_feed` fixture 临时批准 `auto_freshness` + `* * * * *`，background tick `47356df1-8f5e-442c-883b-f46ec51c6bbc` 返回 `due=1`、`started=1`，TaskRun `258b2265-5f5a-4505-a9f7-400aee863259` finished `success`，read-only drift check 返回 `checked_tasks=1`，随后 exact cleanup 到零 | L4 authorized live；证明一条 scoped scheduler tick execution 和 read-only recurring monitoring signal；不证明 retained canary refresh 或多租户长期 SLA |
| Public content retained refresh drift scheduler gate | 2026-06-24 在 retained canary Task `b8a4cb3f` 上临时批准 `auto_freshness` + `* * * * *`，background tick `b1fa40d1-215a-469c-b2b7-f841fb8edcab` 返回 `due=1`、`started=1`，retained TaskRun `fb2dc909-f125-402e-8759-7443e0214e55` finished `success`，随后恢复 `manual_refresh_only`/`schedule_cron=null`，保存 retained `public_content_drift` event `73fbce88-ea11-4cc6-8c61-c6088d1ccaec`；发现并修复 cleanup dry-run 未覆盖 later scheduler TaskRun 的 lineage gap，生产 SHA 升至 `3c92fcbf2230e1b0b4eef71afea2b8e7547d3331`，post-fix dry-run 返回 `task_runs=2`、`dataset_drift_events=1`、`cleanup_ready=true`、`export_artifact_path_violations=0` | L4 authorized live + production dry-run；证明 retained canary scheduler refresh、retained drift event persistence 和 cleanup dry-run graph 覆盖；不证明 cleanup execute、multi-day TTL、provider/email/browser/export |
| Public content retained TTL observation baseline | 2026-06-24 retained preflight 确认 Task `b8a4cb3f` 仍为 `manual_refresh_only`、`schedule_cron=null`、`task_runs=2`、`dataset_drift_events=1`；default 168h dry-run 全 0；24h dry-run 和 0h dry-run 均命中完整 retained canary graph：`users=1`、`sources=1`、`collection_tasks=1`、`task_runs=2`、`datasets=1`、`dataset_versions=1`、`dataset_drift_events=1`、`dataset_export_jobs=1`、`reports=1`、`report_audit_events=1`、`export_artifact_files=1`、`cleanup_ready=true`、`export_artifact_path_violations=0` | L4 production read-only/dry-run；证明 24h observation threshold 和 cleanup graph coverage；不证明 cleanup execute、canary deletion、default 168h multi-day TTL、provider/email/browser/export |
| Public content retained TTL midpoint observation | 2026-06-25 retained preflight 确认 retained account/source/task/dataset/version 均仍存在，Task `b8a4cb3f` 仍为 `manual_refresh_only`、`schedule_cron=null`、`task_runs=2`、`dataset_drift_events=1`、`dataset_export_jobs=1`、`reports=1`；default 168h dry-run 全 0；48h dry-run 全 0；0h dry-run 命中完整 retained graph：`task_runs=2`、`dataset_drift_events=1`、`dataset_export_jobs=1`、`export_artifact_files=1`、`cleanup_ready=true`、`export_artifact_path_violations=0` | L4 production read-only/dry-run；证明中途 retained 仍完整、48h cutoff 尚未命中、0h graph coverage 保持；不证明 cleanup execute、canary deletion、default 168h multi-day TTL、provider/email/browser/export |
| Public content retained TTL final 168h observation | 2026-07-01 retained preflight 确认 retained account/source/task/dataset/version 均仍存在，Task `b8a4cb3f` 仍为 `manual_refresh_only`、`schedule_cron=null`、`task_runs=2`、`dataset_drift_events=1`、`dataset_export_jobs=1`、`reports=1`；default 168h dry-run 命中完整 retained graph：`users=1`、`workspaces=1`、`workspace_members=2`、`sources=1`、`collection_tasks=1`、`task_runs=2`、`raw_records=1`、`entities=1`、`entity_snapshots=1`、`datasets=1`、`dataset_versions=1`、`dataset_drift_events=1`、`dataset_export_jobs=1`、`reports=1`、`report_audit_events=1`、`notifications=1`、`export_artifact_files=1`、`cleanup_ready=true`、`export_artifact_path_violations=0`；0h dry-run 命中相同 graph | L4 production read-only/dry-run；证明 default 168h threshold 和 cleanup graph readiness；不证明 cleanup execute、canary deletion、provider/email/browser/export |
| Public content cleanup register | base smoke、Report asset gate 和 Dataset export gate 的 exact-ID cleanup 均执行；Dataset export gate 成功 run 的 pre-cleanup 命中 `users=1`、`sources=1`、`collection_tasks=1`、`task_runs=1`、`raw_records=1`、`entities=1`、`entity_snapshots=1`、`datasets=1`、`dataset_versions=1`、`dataset_export_jobs=1`、`export_artifact_files=1`；execute 后 exact-ID 与 generic E2E recount 全为 0；retained gate 仅跑 generic dry-run 且全 0 | L4 cleanup evidence；cleanup-after-evidence gate 不保留测试资产；retained gate 明确保留 canary |
| Local PRD2 docs | PRD2 源头文档为 `docs/product/product-prd-data-intelligence-hub-stable.md`；执行计划为 `docs/workflows/workflow-prd2-platform-collection-execution-plan-stable.md` | L1 repo evidence |
| Release commit | `b81a4be2a47f387d381293db7c4b2932128f6708` 已发布到 `/opt/data-achieve-scrapy/app`，active app marker 与 HEAD 匹配 | L3 deployment identity + health evidence；不代表后续 live gates 已执行 |
| Source branch state | 本地 `codex/release-3b-on-428` 与 `origin/codex/release-3b-on-428` 均为 `b81a4be2a47f387d381293db7c4b2932128f6708`；`main` 与 `origin/main` 仍为 `42851929d59d82708c9380d36347ca721979297d`；Loop 35 验证 `main..HEAD=1`、`HEAD..main=0`、无现有 GitHub PR | L1 source evidence；release 分支已同步且 fast-forward-capable，PR creation 或 main merge 仍需单独 gate |
| Production deploy access | 2026-06-23 生产部署、preflight、Docker build、Alembic upgrade、gateway retry 和 health/page smoke 已完成 | 当前发布入口已可用；未来每次 deploy 仍需单独记录 preflight/build/health evidence |
| Schema delta | `202606110021_browser_diagnostic_runs.py`、`202606110022_browser_diagnostic_jobs.py`、`202606110023_browser_diagnostic_job_runs.py`、`202606110024_email_channel_test_runs.py`、`202606110025_email_provider_live_gate_runs.py`、`202606110026_email_provider_live_send_runs.py` 已在生产 migration 中执行 | Browser diagnostic 和 email provider gate 资产表已上线；真实浏览器执行、provider call、邮件发送仍需单独授权 |
| Browser local smoke | `workflow-browser-evidence-artifact-retention-stable.md` 记录 `tmp/browser-harness-readonly-smoke-20260621.json` 为 `blocked_local_daemon`、`browser_started=false`、`collection_resources_written=false` | L2 local validation；不是生产可用性证明 |
| Cross-domain regression | `video.lute-tlz-dddd.top=200`、`mkt.lute-tlz-dddd.top=200`、`voc.lute-tlz-dddd.top=302`，跟随 redirect 后到登录页返回 200；`scrapy.lute-tlz-dddd.top/api/health=200` | L3 read-only gateway regression；`voc` 直接访问是 302，不应写成直接 200 |

## 1. Executive Snapshot

### Facts

1. 当前线上服务是可访问的：API health 正常，数据库已连接，核心页面均能返回 HTML。
2. 当前线上 API 未认证访问会返回 401，这和 API contract 中“登录、注册以外业务接口都要求当前用户和 workspace”的设计一致；既有 demo 账号 authenticated read-only smoke 已通过。
3. PRD2 的产品中心已经从通用情报平台收敛为“平台化采集工作台”，主链路是授权确认、能力探测、结构/浏览器诊断、字段候选、采集/清洗计划、Dataset、Export、Drift、Report、Alert、Evidence。
4. 生产远端 app working tree `HEAD=b81a4be2a47f387d381293db7c4b2932128f6708` 已包含 PRD2/M1/M2/M3/M5 的多项实现以及 Loop 24 release scope 中的 side-effect governance gates；active app `.deploy-sha` 同样为 `b81a4be2a47f387d381293db7c4b2932128f6708`。
5. 生产 Alembic head 已到 `202606110026`，PRD2 R0 release/schema gap 已闭合到最新 release commit；M3 GitHub API-first 小范围生产 package gate 已完成并清理；M5 public content 小范围生产 package smoke、Report asset gate、Dataset export gate 已完成并清理；M5 retained lifecycle gate 已保留一组 canary Dataset/Report/Export asset；public-content drift event 专用持久化、docs/page production gate、scheduler approval gate、scheduler tick gate、retained cleanup dry-run gate、retained canary scheduler/drift refresh gate、retained TTL observation baseline/midpoint/final 168h observation 均已完成。剩余 gap 转为更大 scope rate-limit、retained cleanup execute decision、provider/email 等独立 gate。
6. 未来 production identity probe 的命令源已固化到 `.codex/commands.md`；父级 `/opt/data-achieve-scrapy/.deploy-sha` 和 `/opt/data-achieve-scrapy/current` 仅作为旧 release-directory marker 记录，不能单独支撑当前 compose 部署身份结论。
7. 2026-07-01 retained TTL final 168h observation 证明 retained canary 已超过默认 168h threshold，default 168h dry-run 命中完整 retained graph，且 `cleanup_ready=true`、`export_artifact_path_violations=0`。

### Inferences

1. 线上产品已经完成 PRD2 R0 release/schema 对齐，并完成一次小范围 M3 GitHub API-first L4 package gate、一次 M5 public content L4 package smoke、一次 M5 Report asset gate、一次 M5 Dataset export gate、一次 M5 retained lifecycle gate、一次 M5 scheduler approval mutation gate、一次 scoped scheduler tick gate、一次 retained cleanup dry-run gate、一次 retained canary scheduler/drift refresh gate、一次 retained TTL observation baseline/midpoint/final 168h observation；这不等于大规模 recurring collection、production cleanup execute、canary deletion 或自动清理生命周期也已完成。
2. BrowserDiagnosticRun/Job/JobRun 与 email provider gate 资产化链路已随 schema `202606110026` 上线；真实浏览器执行器、文件保留、provider call、邮件发送和外部平台读取仍需单独授权。
3. GitHub API-first 与 Public Web/RSS/Docs 已经形成两个可复用样板：前者证明 API-first tool radar 的 Dataset/report/drift asset 链路，后者证明低风险公开 feed 的 Dataset/read-only drift/report preview 链路。
4. Public Web/RSS/Docs、Video transcript import、Public community trend 适合做 P1 新平台包；Marketplace、RPA/no-code、Social 平台应先做 API/import/SOP，不应默认做页面自动采集。

### Unknowns

1. GitHub API rate-limit、失败重试和数据完整性在大于 `max_repositories=3` 的 topic scope 下仍未验证。
2. retained lifecycle gate、retained refresh gate 与 retained TTL observation baseline/midpoint/final 只验证了即时保留、重登录后可见、DB/volume 中 canary asset 存在、一次 scheduler refresh、一次 retained `public_content_drift` 事件、cleanup dry-run graph 覆盖、24h dry-run 和 default 168h dry-run 命中；仍没有验证 cleanup execute、canary deletion、post-delete recount 或自动清理。
3. 生产 GitHub package gate 覆盖 Source/Task write、一次 GitHub API TaskRun、Dataset save、report asset、drift snapshot；M5 scheduler approval/tick/retained refresh gates 覆盖 public-content scheduler path，但不覆盖 provider enrichment、邮件发送、dataset export after refresh 或浏览器运行。
4. 线上运行环境是否安装 `agent-reach` 或 `browser-harness` 未验证；即便安装，也只能先进入 doctor/read-only probe 边界。

## 2. PRD2 Gap Matrix

| Area | PRD2 target | Current deployed evidence | Local/repo evidence | Gap | Priority |
|---|---|---|---|---|---|
| Product shell | `/automation` 作为平台化采集工作台主入口，`/datasets` 作为数据资产池 | `/automation=200`、`/datasets=200` | Web app 有 automation/datasets routes 和 E2E 覆盖 | 生产页面内交互未登录验证；根路径 `307` 只说明有跳转 | P0 release evidence |
| Auth/workspace boundary | 业务接口绑定登录态、workspace、current user | 未认证业务 API 返回 401；authenticated read-only smoke 通过；M3/M5 多个 scoped authorized production write gates 均带 cleanup evidence | API contract 明确 cookie auth；routes 使用 `get_auth_context` | 其它平台和 side-effect gates 仍需逐项授权与 cleanup/retention evidence | P0 evidence |
| Stable collectors | `github_repo`、`github_topic`、`generic_web`、`public_feed`、`manual_json`、`ecommerce_product_discovery`、`ecommerce_product_page` | M3 GitHub、M5 `public_feed` 和 M5 `generic_web` docs/page 已各完成一次小范围授权生产 gate/smoke | API docs、collector tests、Automation service 可见；`public_feed` 已生产验证 `https://hnrss.org/frontpage`；`generic_web` 已生产验证 `https://www.iana.org/help/example-domains` | 独立站、manual_json 等其它 collector 的生产写入 gate 仍需单独执行 | P0 release |
| PlatformPackage | 可解释、可验收平台包：independent site、GitHub API-first、public page preflight、public web/rss/docs | 未认证平台包接口返回 401；authenticated read-only 已确认 `github-api-first` M3 字段合同 | `list_platform_packages()` 返回 4 个 package；Batch 3 本地合同已补 version、owner、lifecycle status、evidence grade、authorization required、acceptance registry、cleanup policy、forbidden actions，并有 API/UI/test 覆盖 | 平台包仍是代码内 catalog；持久化/用户自定义层、生产部署验证和新增平台包仍未完成 | P0/P1 |
| CapabilityProbe | Agent Reach 风格 no-read/no-write doctor，区分 backend candidates 和 forbidden actions | 生产未登录未验证 | `list_capability_probes()`、`_probe_agent_reach_channel()`、TS types/UI 可见 | 线上未证明；缺 probe run history、probe evidence asset、operator remediation UI | P0 |
| Agent Reach fusion | 作为能力路由和 doctor，不直接读平台内容 | 线上未知 | 本地逻辑只允许 `agent-reach doctor --json`，缺失时返回 `missing_tool` | 未安装/线上运行态未知；尚未沉淀 channel-level evidence | P0/P1 |
| BrowserDiagnostic assets | BrowserDiagnosticRun/Job/JobRun 只读证据资产，selector/network/promotion/redaction 可审计 | 线上 schema head 已是 `202606110026` | migrations `021/022/023`、routes、service、UI、E2E 已保留在当前生产基线；email gate migrations `024/025/026` 也已上线 | 资产表已上线；生产 runner、artifact 写入、provider call、邮件发送和外部平台读取仍需单独授权 | M2-3 |
| Browser artifact retention | metadata-only 当前阶段，截图/trace/HAR 需单独批准 | 生产未验证 | retention workflow 已定义 `files_written=false` 等不变量 | 缺自动 TTL/cleanup job；未实现 approved artifact retention mode | P1 |
| GitHub Tool Radar | API-first 样板，能进入 Dataset/Export/Drift/Report | 2026-06-23 小范围 L4 gate 已跑通 Topic Radar -> GitHub API TaskRun -> Dataset save -> report asset -> drift snapshot -> cleanup | E2E 覆盖 Topic Radar -> dataset -> report -> drift；M3 已补 license、default branch、latest release、README metadata、pushed_at、schema/provenance、report risk sections 和 drift signal groups | 大 scope rate-limit、retained dataset、scheduler、export、provider/email 仍未闭合 | Done/M3 |
| Independent site | Shopify-style 商品发现、fan-out、dataset、drift、export | 2026-06-29 本地 fixture gate 覆盖 platform package、discovery、fan-out、batch、DatasetVersion、export/download、drift event 和 history；随后完成 WebScraper.io 公开测试站 local API E2E，Dataset `row_count=2`、完整度 `100%`、CSV export `966 bytes`、drift event `status=ok`；未执行生产写入 E2E | `origin/main=e97810a` 基线已随当前 `b81a4be2a47f387d381293db7c4b2932128f6708` 生产 release 保留；新增本地 API integration gate 和 schema.org microdata 商品页 fallback | Production/customer-site M4 gate 未完成；需要真实业务 URL、cleanup register、export/retention、scheduler/provider/email 边界 | P0/M4 |
| Public Web/RSS/Docs | 公开网页、RSS/Atom、docs 更新监控平台包 | M5 production smoke 已跑通 `public_feed` RSS TaskRun、`public_content_update` DatasetVersion、read-only drift/report preview；Report asset、Dataset export、retained lifecycle canary、scoped `public_content_drift` event gate、`generic_web` docs/page production gate、public-content scheduler approval gate、scheduler tick gate、retained cleanup dry-run gate、retained canary refresh gate 和 retained TTL final 168h observation 均已完成 | M5 local scaffold、Dataset/drift/report slice、Report asset/API/Web client/export contract、public-content drift event persistence、`generic_web` docs/page hash diff local slice、scheduler approval path、retained cleanup policy tooling、member workspace lineage fix、refresh-run lineage fix 和测试已完成 | production retained cleanup execute、post-delete recount、provider/email、browser runtime 仍未闭合 | Done/M5 |
| Video transcript import | YouTube/B 站公开视频 metadata/transcript import，不下载媒体 | 无 | PRD2 已定义边界 | 缺 import schema、source provenance、copyright/subtitle fields、UI flow | P1/M6 |
| Public community trend | 聚合主题趋势，不做人级画像 | 无 | PRD2 已定义边界 | 缺 V2EX 等公开社区 package、aggregate schema、redaction/privacy guard | P1/P2 |
| Marketplace | Amazon/marketplace 走官方 API、授权导出或人工导入优先 | 无 | PRD2 已定义边界 | 缺 import template、API credential boundary、sample dataset、cleanup/audit | P2 |
| RPA/no-code | Browse AI/Octoparse/影刀/Power Automate/UiPath 作为 workflow/import 连接器 | 无 | PRD2 已定义边界 | 缺 ExternalToolSnapshot 或 manual_json import review flow | P2 |
| Social SOP/import-only | Twitter/X、小红书、Instagram、LinkedIn 默认 SOP/import-only | 无 | PRD2 已定义边界 | 缺 SOP templates、field templates、UI 禁用自动采集按钮的 package states | P3 |
| Report/Alert/Notification | Report/Alert/Notification 绑定 Evidence 和授权发送边界 | GitHub `github_tool_radar` report asset 和 M5 `public_content` Report asset 已各完成一次小范围生产 gate；Report send、drift alert notification/email send、Report asset create、subscription run/retry、email-channel test、provider-live preflight 和 live-send default-deny 已有本地 `Idempotency-Key` replay 合同；生产站内通知/邮件发送/调度触发仍需单独 gate | routes/service/test 覆盖 report、drift alert、站内通知、邮件发送路径，并新增 report send / drift alert send / report asset / subscription run-retry / email-channel test / provider-live preflight / live-send replay 断言 | 需要继续把 L4 provider 生产发送和调度变更分成独立 authorization gate | P1 governance |

## 3. Deployed State vs Local Worktree Gap

当前最重要的 gap 已从“本地最新 PRD2/M2 能力和线上部署证据没有对齐”，转为“GitHub/M5 小范围 L4 gates 已完成，但更大 scope、长期保留、cleanup execute、provider/email 和下一平台包仍需分 gate 推进”。

| Gap | Why it matters | Required action |
|---|---|---|
| Production schema head aligned to `202606110026` | BrowserDiagnosticRun/Job/JobRun 与 email provider gate 表已上线，但仍需要生产 auth/read-only 和写入 E2E 证据分层 | 后续写入链路另走 L4 授权和 cleanup register |
| Worktree dirty and mixed scope | 当前已有多个修改和未跟踪文件，不能直接把“本地看起来有”说成“可发布” | 做 scoped diff audit，拆分 release PR 或明确本轮发布包 |
| Production API needs auth | 只读未认证 smoke 只能证明服务边界，不证明内部流程 | 需要授权的真实账号或专用测试账号执行 production read-only/authenticated smoke |
| Remaining L4 breadth | GitHub 小范围 L4 已完成；M5 public-content 多个生产 gate 和 retained TTL final 168h observation 已完成；其他平台、邮件、provider、cleanup execute 仍未执行 | 继续按 single-step authorization envelope 执行，每次保留 cleanup 或 retention evidence |
| Browser local daemon blocked | M2-3 real browser smoke 仍未形成 `browser_started=true` 证据 | 先修本机 daemon/connection，再只对 `https://example.com/` 或明确授权测试页重跑 |

## 3.1 First-principles Backlog Tracker

第一性原理：平台的完成标准不是“能抓一次”，而是能在授权边界内把目标输入稳定转成可追溯、可复现、可导出、可漂移检测、可报告、可清理的数据资产。

| ID | Area | Current evidence | Remaining task | Priority | Acceptance boundary |
|---|---|---|---|---|---|
| FP-00 | PRD/architecture/gap state sync | 2026-07-02 L3 production read-only identity and health refreshed after `b81a4be` deploy | Keep PRD2, architecture, gap plan aligned with `b81a4be` and known unfinished gates | P0 | Docs-only; no production mutation |
| FP-01 | PRD commitment tracker | Gap matrix exists; first-principles draft exists under `drafts/analysis/` | Keep this table as the canonical next-task tracker and update status after each gate | P0 | Evidence grade must be recorded per item |
| FP-10 | PlatformPackage registry | Batch 3 local API/UI contract exposes version, owner, lifecycle status, evidence grade, authorization requirement, acceptance registry, cleanup policy and forbidden actions | Persist/customize packages outside code catalog and verify production deployment when authorized | P0 | Local tests first; no side effect by registry creation alone; current slice is production unchanged |
| FP-20 | Run safety baseline | 2026-06-29/30 local validation added task row lock, collector `run_timeout_seconds`, scheduler `skipped_running`, frontend primary-submit guard, auto freshness retry budget, manual Task run, Dataset export create, Report send, drift alert notification/email send, Report asset create, subscription run/retry, email-channel test, provider-live preflight, live-send readiness and live-send default-deny `Idempotency-Key` replay contracts; L4 live-send runbook exists | Collect production read-only readiness and then one authorized provider send evidence before any wider live send gate | P0 | Local tests cover running-task skip, timeout, retry budget, manual run replay, dataset export replay, report send replay, drift alert send replay, report asset replay, subscription run/retry replay, email-channel test replay, provider-live preflight, readiness and live-send default-deny; production remains unchanged |
| FP-30 | CapabilityProbe evidence | no-read/no-write probe contract exists; computed `evidence_asset_reference.v1` now attaches to probe responses and list aggregation | Add durable probe run history table if long-term replay/audit is needed | P1 | Probe/doctor remains read-only; no read/search execution; current slice creates no collection resources |
| FP-31 | BrowserDiagnostic evidence | BrowserDiagnostic tables/API/UI exist; local isolated metadata-only smoke exists; run/job/job-run responses expose metadata-only evidence references, Source/Task promotion preview gate, no-write execution dry-run, explicit authorized Source+Task write gate with idempotency replay, and production metadata-only no-run gate | Execute L3 production read-only browser observation only after explicit authorization; keep TaskRun/Dataset promotion as a separate authorized gate | P1 | `files_written=false` unless retention mode is separately approved; production metadata gate returns `production_read_only_observed=false`、`run_started=false`、`browser_started=false`; evidence references, promotion preview and execution dry-run embed no screenshot/trace/HAR/header/body/cookie; write gate creates Source+Task only and keeps `task_run_started=false` |
| FP-40 | GitHub scale gate | Small L4 API-first package gate completed | Larger scope rate-limit, retention/export and scheduler gate | P1 | Explicit scope, rate budget, cleanup/retention register |
| FP-50 | Shopify/independent site E2E | Collectors and dataset/drift samples exist; local deterministic fixture gate now covers package -> discovery -> DatasetVersion -> export -> drift event | Authorized live test-site E2E from discovery to DatasetVersion and report/export/drift | P0 | Needs test URL, allowed pages, cleanup or retained decision |
| FP-60 | Public Web/RSS/Docs follow-up | M5 small gates, scheduler tick, retained refresh, retained dry-run, and default 168h TTL final observation exist | Cleanup execute decision, provider/email gate | P1 | cleanup execute/email/provider require separate authorization |
| FP-70 | ExternalToolSnapshot | PRD object defined, implementation absent | Implement external read/search/import evidence snapshot | P2 | External output is evidence/import input, not automatic Source truth |
| FP-80 | Video transcript import | PRD boundary defined | Metadata/transcript import schema and UI flow | P2 | No media download; provenance and copyright/subtitle source required |
| FP-81 | Public community aggregate | PRD boundary defined | V2EX/public community aggregate trend package | P2 | Aggregate topics only; no person-level profiling |
| FP-82 | Marketplace authorized import | PRD boundary defined | API/export/manual import template | P2 | No login-wall browser automation by default |
| FP-84 | Social SOP/import-only | PRD boundary defined | SOP templates and import-only package states | P3 | No automatic scraping button for SOP/import-only packages |
| FP-90 | Provider/email/scheduler gates | Provider/email/scheduler routes exist; email provider preflight, live-send readiness and live-send default-deny contracts are local-ready; L4 live-send runbook exists | Refresh production read-only inventory, then run email/provider/scheduler only under explicit L4 side-effect gate | P1/P3 | Config presence, readiness and local default-deny evidence are not production send evidence |

## 4. Execution Plan

### Track R0 - Release Boundary And Evidence Alignment

目标：在 release/schema 已对齐后，继续把生产证据分成 L3 authenticated read-only 和 L4 authorized write E2E，避免把只读发布验收夸大成全链路生产写入验收。

| ID | To do | Files/commands | Acceptance evidence | Boundary |
|---|---|---|---|---|
| R0-1 | 建立 release scope 清单 | `git status --short`、`git diff --stat`、PRD/API/workflow docs | 列出本次要发布的 code/doc/migration 文件，排除无关 dirty files | docs/code audit only |
| R0-2 | 本地门禁 | `pnpm lint:web`、`pnpm test:web`、`bash scripts/verify-mvp.sh` | 本地 lint/unit/build/E2E/MVP smoke 通过或列出阻断项 | local validation |
| R0-3 | DB migration rehearsal | `bash scripts/verify-mvp.sh --with-db` 或 `uv run alembic upgrade head` | 本地 DB 可从 `020` 升到 `023`，downgrade/recovery notes 清楚 | local DB only |
| R0-4 | 部署前 schema gate | 检查 `apps/api/alembic/versions` 和 health contract | 准备发布版本的 `schema_head=202606110023` 可解释 | no production write |
| R0-5 | 发布后只读 smoke | `/api/health`、`/automation`、`/datasets`、未认证 401 检查 | done：生产 health 显示 `schema_revision/schema_head=202606110023`，页面可达，API 边界不变 | L3 production read-only |
| R0-6 | 授权生产 E2E | 专用测试 workspace，最小 Source/Task/Dataset/Report run | done for M3 GitHub scope：真实 API E2E `2 passed`，cleanup recount 全 0 | L4 only after explicit approval；其他平台和 side effects 另行授权 |

R0-5 已完成；R0-6 已在 M3 GitHub 小范围 scope 下完成；M5 public content production smoke、Report asset gate、Dataset export gate、docs/page gate、scheduler approval gate、scheduler tick gate 和 retained canary refresh gate 已完成。M4、provider/email、production cleanup execute、多日 TTL 和生产浏览器运行仍不能宣称生产写入完成，除非各自获得单独授权并留下 cleanup 或 retention evidence。

### Track M3 - GitHub API-first Deepening

目标：把 GitHub 做成第一个 PRD2 “API-first 平台包样板”，形成可复用的采集、数据集、漂移和报告标准。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M3-1 | 扩展 GitHub collector 原始字段 | collector/service/tests | 支持 latest release、README metadata、license、default branch、open issue activity、commit freshness |
| M3-2 | Dataset schema version/provenance | dataset service、API schema、docs | `github_tool_radar` DatasetVersion 写入 `schema_version`、field source、collector version |
| M3-3 | Report 增强 | `automation_service.py`、report UI、tests | 报告包含维护风险、安装方式、适用采集场景、不适用边界 |
| M3-4 | Drift 规则增强 | drift service/tests | stars/forks/issues/release freshness/field missingness 能分层输出 drift status |
| M3-5 | E2E 和 cleanup | web E2E + API integration + authorized production runbook | 本地通过；生产写入只在授权后执行，并可清理 |

Acceptance commands:

```bash
pnpm lint:web
pnpm test:web
bash scripts/verify-mvp.sh
bash scripts/verify-mvp.sh --with-db
```

当前 M3 状态：

1. `M3-1` 已完成：GitHub collector/normalizer 已补 latest release、README metadata、license、default branch、issue/activity/freshness 相关字段，并通过 GitHub targeted tests。
2. `M3-2` 已完成：`github_tool_radar.v2` 暴露 schema version、field source、collector versions、endpoint origins 和 lineage provenance。
3. `M3-3` 已完成：report 已包含 maintenance risk、install/source entries、recommended use cases 和 unsuitable boundaries。
4. `M3-4` 已完成：drift 输出 `signal_groups`，覆盖字段缺失、repository coverage、popularity regressions、issue activity、release freshness 和 commit freshness。
5. `M3-5` 已完成本地门禁、production runbook 和小范围 L4 production package gate；后续只剩更大 scope、retention/export/scheduler/provider/email 等独立 gate。

### Track M4 - Independent Site / Shopify-style Deepening

目标：把独立站从 demo 闭环提升为可运营的商品数据采集模板。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M4-1 | Discovery 增强 | ecommerce collectors、automation service | done_main_67f611e：支持 collection/listing/sitemap/pagination/canonical 去重和 skip reasons |
| M4-2 | 商品字段增强 | collector/schema/tests/UI | done_main_67f611e：增加 variant、image、brand、category、price range、availability detail |
| M4-3 | Dataset/drift 样例 | dataset/drift tests、docs | done_main_and_deployed_in_current_baseline：新增/下架、价格变化可进入 DatasetDriftEvent；随 `origin/main=e97810a` 基线保留在当前 `42851929d59d82708c9380d36347ca721979297d` 生产代码点 |
| M4-4a | 本地 deterministic fixture E2E | API integration test | 已覆盖 URL -> Dataset/export/drift 全链路；L2 local validation，不代表真实测试站或生产写入 |
| M4-4b | 真实授权测试站 E2E | local API script、cleanup/retention register | done_local_external_20260629：WebScraper.io 公开测试站读取 + 本地临时 API DB 写入，跑通 URL -> Dataset/export/drift；证据等级 `L2 local validation + public test-site read`，不代表 production write |

Boundary: 只处理授权公开页面；不处理登录墙、验证码、购物车态、反检测或 marketplace 页面。

### Track M5 - Public Web/RSS/Docs Package

目标：新增第一个低风险公开内容监控平台包。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M5-1 | 定义 `public-web-rss-docs` package | API contract、platform package catalog、TS types/UI | done_local_20260623：package 显示 URL/RSS/Docs targets，含 risk boundary |
| M5-2 | RSS/Atom parser | collector + tests | done_local_20260623：`public_feed` 支持 title/link/published/updated/author/tags/content summary/hash |
| M5-3 | Public content dataset/drift | dataset service + drift service | done_production_smoke_20260623：`public_feed` entries 可保存为 `public_content_update.v1` DatasetVersion，并用 `link` + `content_hash` 做 read-only drift check |
| M5-4 | Report preview template | report service | done_production_smoke_20260623：`public-content-report` 可生成公开内容更新只读摘要、风险段和建议；preview 不创建 Report asset |
| M5-5 | Report asset persistence | report service + tests + production smoke | done_report_asset_gate_20260623：`public-content-report-assets` 可创建 `public_content` Report asset，内容保留 `public_content_update.v1` schema，并完成 exact-ID cleanup |
| M5-6 | Dataset export gate | existing export service + production smoke | done_export_gate_20260623：`product-dataset-exports` 可从 `public_content_update` DatasetVersion 创建 CSV DatasetExportJob、写入受控 export artifact、下载校验，并完成 exact-ID cleanup 与 artifact deletion |
| M5-7 | Retained lifecycle canary | existing source/task/dataset/report/export list APIs | done_retained_gate_20260623：retained user/source/task/run/dataset/version/report/export artifact 保留；重登录后 list/detail/download 校验通过；generic E2E cleanup dry-run 不命中 retained canary |
| M5-8 | Drift event production gate | public-content drift-event endpoints + production smoke | done_drift_event_gate_20260624：production SHA `68c27e0f9c62d542149eedc5b18439938103b4bb`；`public_content_drift` DatasetDriftEvent 创建/复用通过；exact-ID cleanup 和 generic cleanup dry-run 全 0 |
| M5-9 | Docs/page hash diff local slice | `generic_web` collector + public-content dataset/drift/report service + tests | done_local_20260624：`generic_web.v1` docs/page snapshot 可进入 `public_content_update` DatasetVersion、hash-only drift、`public_content_drift` event 和 public-content report/asset 本地链路；API full pytest `107 passed`、ruff、Web TypeScript/lint/unit/build、`git diff --check` 均通过 |
| M5-10 | Docs/page production gate | deploy + generic_web production smoke + exact cleanup | done_docs_page_gate_20260624：production SHA `af23cefc92aa9fec336f632a5b1561623811c2fd`；`generic_web` docs/page TaskRun success；`public_content_update` DatasetVersion `row_count=1`、`collector_schema_versions=["generic_web.v1"]`；`public_content_drift` DatasetDriftEvent 创建/复用；`public_content` Report asset 创建；exact-ID 和 generic cleanup dry-run 全 0 |
| M5-11 | Public content scheduler approval gate | scheduler approval service + production smoke + exact cleanup | done_scheduler_gate_20260624：production SHA `a81154426fd4e942fc9439de3dcbd9c816122562`；scoped `public_feed` DatasetVersion schedule approval persisted `manual_refresh_only`、`schedule_cron=null`、`freshness_target_hours=72`；audit `public_content_schedule_approved`；`run_started=false`、`scheduler_tick_started=false`；approval 前后 TaskRun 不变；exact-ID 和 generic cleanup dry-run 全 0 |
| M5-12 | Retained TTL/cleanup policy local slice | maintenance module + script + unit tests | done_local_20260624：retained public-content TTL dry-run/execute policy、export artifact root validation、protected fixture exclusion、script help；targeted retention tests `2 passed`、retention plus generic E2E cleanup tests `4 passed`、API full pytest `110 passed`、ruff 和 `git diff --check` 通过；无 production deploy、production cleanup dry-run/execute、retained canary deletion |
| M5-13 | Retained cleanup production dry-run gate | deploy + dry-run only + lineage fix | done_dry_run_20260624：initial SHA `c321a52` dry-run exposed member workspace lineage gap and no execute was run; fixed SHA `d11d5a4` deployed, local validation `3 passed` retention tests, `5 passed` retention plus E2E cleanup, API full `111 passed`, ruff; production `--older-than-hours 0` dry-run matched retained canary Source/Task/Run/Dataset/Version/Report/Export artifact with `export_artifact_path_violations=0`; default 168h dry-run returned all zero; no cleanup execute or canary deletion |
| M5-14 | Scheduler tick / recurring monitoring gate | schedule approval + production background tick + cleanup | done_scheduler_tick_20260624：production SHA `d11d5a4`；scoped `public_feed` Task 临时 approved `auto_freshness` + `* * * * *`；background tick `47356df1-8f5e-442c-883b-f46ec51c6bbc` returned `due=1`、`started=1`；scheduled TaskRun `258b2265-5f5a-4505-a9f7-400aee863259` success；read-only drift check surfaced risk; exact cleanup returned zero |
| M5-15 | Retained canary scheduler/drift refresh gate | retained canary + scheduler tick + drift event + cleanup dry-run fix | done_retained_refresh_20260624：retained Task `b8a4cb3f` 临时 approved `auto_freshness` + `* * * * *`；tick `b1fa40d1-215a-469c-b2b7-f841fb8edcab` returned `due=1`、`started=1`；retained TaskRun `fb2dc909-f125-402e-8759-7443e0214e55` success；task restored to `manual_refresh_only`/`schedule_cron=null`；saved retained `public_content_drift` event `73fbce88-ea11-4cc6-8c61-c6088d1ccaec`; cleanup lineage fix deployed as `3c92fcbf2230e1b0b4eef71afea2b8e7547d3331`; post-fix dry-run returned `task_runs=2`、`dataset_drift_events=1`、`cleanup_ready=true`、`export_artifact_path_violations=0` |

Boundary: 公开源、低频、保留 final URL/source timestamp/content hash；不覆盖原始事实。

### Track M6 - Video And Public Community Import

目标：先做 metadata/transcript 和聚合趋势导入，不下载媒体、不做人级画像。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M6-1 | Video transcript import schema | API docs、schemas、manual/import service | 保存 video url、platform、title、channel label、published_at、transcript source、license/copyright note |
| M6-2 | Video dataset/report | dataset/report service/UI | transcript rows 可进入 DatasetVersion 和 report summary |
| M6-3 | V2EX/public community aggregate | collector/import service/tests | 只保留 topic/title/link/time/reply_count/aggregate score，不保存个人画像 |
| M6-4 | Privacy gate | UI + tests | 高风险字段被拒绝或进入 manual review |

Boundary: 公开视频 metadata/transcript import；不下载媒体文件；社区只做聚合。

### Track M7 - Marketplace/RPA/Social Boundary Packages

目标：把高风险但业务价值高的平台做成授权导入/API/SOP，而不是默认自动采集。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M7-1 | Marketplace authorized import | import template、API docs、UI | Amazon/SP-API 或后台 CSV 导入 demo，字段模板可审计 |
| M7-2 | ExternalToolSnapshot | model/schema/service/UI | Browse AI/Octoparse/影刀/Power Automate/UiPath 输出先进入 snapshot review，再人工确认入 Dataset |
| M7-3 | SOP-only social packages | platform catalog、toolkit docs/UI | Twitter/X、小红书、Instagram、LinkedIn 显示 `sop_only`，不出现自动采集按钮 |
| M7-4 | Compliance checklist | docs + UI gates | cookie export、login bypass、anti-detect、bulk scroll scraping 均在 forbidden actions |

Boundary: API/import/SOP first；不复用主账号 cookie；不绕过登录态、验证码或平台限制。

### Track G1 - Governance And Evidence Quality

目标：把不同证据层的 closeout 固化，避免 mock/local/prod 被混写。

| ID | To do | Acceptance |
|---|---|---|
| G1-1 | Release closeout template | 每次收口列出 changed files、local gates、L3 smoke、L4 writes、cleanup assets |
| G1-2 | Production cleanup register | 每次授权生产写入都有 ids、resource type、cleanup dry-run、cleanup result |
| G1-3 | Notification/provider gate | Report save、站内通知、邮件发送、provider call、scheduler mutation 分开授权 |
| G1-4 | Evidence wording lint | 文档和 UI 不把 doctor/probe/read-only 说成采集成功 |

## 5. Platform Priority

| Priority | Platform/capability | Why next | Work mode |
|---|---|---|---|
| Done | Release boundary, migration to `026`, M3 GitHub package gate, M5 public content smoke, M5 Report asset gate, M5 Dataset export gate, M5 retained lifecycle gate, M5 public-content drift event production gate, M5 docs/page production gate, M5 public-content scheduler approval gate, M5 scheduler tick gate, M5 retained cleanup policy local slice, M5 retained cleanup production dry-run gate, M5 retained canary scheduler/drift refresh gate, M5 retained TTL observation baseline/midpoint/final 168h observation, deploy marker diagnosis, Loop 31 `b81a4be` deploy closeout | production app working tree HEAD and active app marker both `b81a4be2a47f387d381293db7c4b2932128f6708`，schema `202606110026`；父级 `.deploy-sha=dda2786` 与 `current` symlink 是旧 release-directory marker；小范围 L4 GitHub package gate、M5 public content smoke、M5 public content Report/Export/Drift/Docs/Scheduler/Retention/Refresh/TTL observation gates、cleanup/retention evidence、post-refresh cleanup dry-run lineage fix、Loop 31 deploy evidence 完成 | release/evidence |
| P0 | GitHub API-first scale/retention gates | 官方 API、低风险、已有 collector/Dataset/Report path；下一步只扩 scope、retention、export 或 scheduler，不重复证明小范围链路 | API collector |
| P0 | Independent site / Shopify-style | 已有业务闭环，能产生电商 dataset/drift；本地 fixture gate 和 WebScraper.io 公开测试站 local API E2E 已补齐，下一步才是生产/客户站授权 gate | public page collector |
| P1 | Public Web/RSS/Docs next gates | M5 base production smoke、Report asset gate、Dataset export gate、retained lifecycle gate、production drift-event gate、docs/page hash diff local slice、production docs/page gate、scheduler approval gate、scheduler tick gate、本地 retained cleanup policy、production retained cleanup dry-run、retained canary refresh、24h TTL observation baseline 和 default 168h final observation 已完成；下一步只剩 cleanup execute decision、provider/email 或更大 scope gate | URL/feed/docs collector |
| P1 | Video transcript import | 内容趋势价值高，但应 import metadata/transcript | import |
| P1/P2 | Public community trend | 可做聚合趋势，不做人级画像 | aggregate import/collector |
| P2 | Marketplace | 商业价值高，平台政策和账号边界复杂 | API/import first |
| P2 | RPA/no-code | 适合接业务后台导出结果，不应内置主账号自动化 | ExternalToolSnapshot |
| P3 | Twitter/X、小红书、Instagram、LinkedIn | 登录态、个人数据和平台限制风险高 | SOP/import-only |

## 6. Immediate Next To Do

按当前证据，R0 release/schema 对齐和 M3 GitHub 小范围 L4 package gate 已完成；M4-1 到 M4-3 已进入 `main@8cd3e8f` 并通过 main CI；M4-4b 公开测试站 local API E2E 已完成，但 M4 生产/客户站写入验收仍未执行。

1. 后续所有 production identity closeout 先执行 `.codex/commands.md` 的 active app marker probe；不要再把父级 marker/current symlink 当作当前 compose 部署身份来源。
2. M5 public content production package smoke、Report asset gate、Dataset export gate、retained lifecycle gate、production drift-event gate、docs/page hash diff local slice、production docs/page gate、scheduler approval gate、scheduler tick gate、retained TTL/cleanup policy local slice、production retained cleanup dry-run gate、retained canary scheduler/drift refresh gate、retained TTL observation baseline、2026-06-25 retained TTL midpoint observation 和 2026-07-01 retained TTL final 168h observation 已完成；下一步可选择一个独立授权 gate：retained cleanup execute decision、provider/email L4、M4 production/customer-site gate 或更大 scope rate-limit gate 之一。
3. M4-4b 已完成公开测试站 local API E2E；如继续独立站生产化，需要另起 production/customer-site gate，明确真实业务 URL、允许写入资源、cleanup register、是否允许 export file，以及 cleanup dry-run/execute。
4. M5 已完成小范围生产写入、Report asset 创建、Dataset export 创建/下载/删除、retained canary 保留、public-content drift event 创建/复用、docs/page `generic_web` gate、scheduler approval mutation、scheduler tick、retained canary refresh、本地 retained cleanup policy、production retained cleanup dry-run、24h TTL observation、default 168h final observation 和清理边界验证；BrowserDiagnostic 已补 L2 production metadata-only no-run gate；provider call、email、production retained cleanup execute、post-cleanup recount、L3 production browser observation 仍需另起授权 gate。

## 7. Definition Of Done

一个平台采集工作包只有同时满足以下条件，才可以被写成“已打通”：

1. PRD/API contract/schema/UI copy 同步。
2. Collector 或 import path 有本地测试。
3. DatasetVersion 记录 schema version、field provenance、source task/snapshot ids。
4. Export、Drift、Report 至少有一个可复现验收样例。
5. forbidden actions 和授权边界在 UI/API 中可见。
6. 本地门禁通过。
7. 生产只读 smoke 通过。
8. 若涉及生产写入，必须有显式授权、资源清单和 cleanup 记录。
