# SP-Agent-TODO（2026-10-21）

基线：能力图谱 2026-10-15 版；对照：2026-10-21 生产与主分支。

部署口径：按 2026-10-21 指示，实际部署只做生产 A `43.163.92.244`。B 站相关 ticket 保留为待决策，状态标为阻塞或进行中。

飞书多维表格：SP-Agent-TODO · https://momcozy-in.feishu.cn/base/XXz5bHAwCa7qv5sTzrCci3jPnxd?table=tbli8kAkAqrndUvJ

共 65 条。任务类型：Agent机器人 / 工作台；任务属性：bug / 新需求 / 存量需求 / 方案迭代。

## 对比结论

| 模块 | 能力图谱基线（2026-10-15） | 2026-10-21 实际 | 差距 |
|---|---|---|---|
| 控制台 IA | /platforms、/skills、/collector-docs、/datasets、/raw-records | /tools、/docs、/assets、/assets/records | 文档与验收 skill 仍引用旧路由 |
| 目录计数 | 286 视图 / 258 唯一端点 | 309 视图 / 281 唯一端点 / 70 平台 | 图谱、总账、README 三处数字不一致 |
| MCP | 5 个工具 | 21 个工具（5 基础 + 16 TikTok） | 图谱与 MCP 描述未刷新 |
| TikTok R1 | 未进入能力图谱 | 16 工具、21 表、4 页签工作台 | 图谱缺模块；商品关系需 Cookie |
| 身份与租户 | demo workspace 回退 | main 有严格鉴权基础设施，P1 未合并 | 56 个路由仍用 demo workspace |
| 生产 | A/B 两套，schema 未统一 | A 健康且 schema=202610190045；B 停在 044 | B 迁移门禁未执行 |
| 广告与商品关系 | 仅迁移 | 广告已入库；关系工具已接，Cookie 未配置 | 关系表为空 |
| 文档与验收 | 2026-10-15 快照 | 代码与生产已前进 | 多份文档和 skill 过期 |

| Ticket | 任务类型 | 所属图谱模块 | 任务属性 | 任务方案 | 完成状态 | 登记时间 | 预计完成时间 | 实际完成时间 |
|---|---|---|---|---|---|---|---|---|
| SP-01 统一目录计数与摘要口径 | 工作台 | 工具目录与计数 | 方案迭代 | 以 endpoint_type 为计数单位。运行 scripts/reconcile_catalog.py，更新 configs/tool-catalog.lock.json。让 REST /api/tool-catalog、MCP list_capabilities 与脚本返回同一个 catalog_digest。能力图谱、能力总账与 README 统一写 309 视图/281 唯一端点（发布时实测值），并标注生成物日期。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-02 修复 catalog 与 providers/status 的状态语义 | 工作台 | 平台能力中心 | bug | 状态只由 label 恰好为 [test] <endpoint_type> 的最近 TaskRun 派生。catalog 不写静态 verified。前端 /tools、/docs、/settings/providers 统一读 /api/platform-packages/providers/status。为 label 漂移加守卫。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-03 写接口 fail-closed 与读接口 demo 回退收敛 | Agent机器人 | 账户与成员 | 方案迭代 | 按 ADR-007 D2/D3/D5 分批把写接口迁到 get_authenticated_context。读接口按路由分批迁移。跨 workspace 返回 403。MCP 与 agent 调用必须传 workspace。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-04 对齐两套生产的 schema、分支与部署点 | 工作台 | 生产运维 | 方案迭代 | 仅生产 A（43.163.92.244）执行；B 站按 2026-10-21 指示暂缓。B 机从 main 或 release/2026-10-20 部署。应用 045 前备份并取得授权。逐主机读 /api/health 的 schema_revision。A 不 downgrade、不 stamp。046/047 应用前演练回滚。重建 api/console 后必须 restart edge。 | 进行中 | 2026-10-21 | 2026-10-24 |  |
| SP-05 应用并验证 046/047 迁移与 tool_catalog 表 | 工作台 | 工具目录与计数 | 存量需求 | 在空 Postgres 上 upgrade head，确认只有一个 head。运行 seed 脚本写入 281 行，重复执行保持幂等。核对表行数与 configs/tool-catalog.lock.json 一致。验证 downgrade 删除表。生产应用需逐主机授权。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-06 数说上线收尾与密钥轮换 | Agent机器人 | Agent：数说 | bug | 仅生产 A（43.163.92.244）执行；B 站按 2026-10-21 指示暂缓。重置在对话中出现过的 App Secret。设置 SHUSUO_ALLOWED_OPEN_IDS。确认 SHUSUO_DEFAULT_PROJECT_ID 是数说专用项目。在飞书后台确认事件订阅 im.message.receive_v1 与回调 URL。按需部署生产 B。 | 进行中 | 2026-10-21 | 2026-10-24 |  |
| SP-07 补齐第二生产的 MCP allowed_hosts | Agent机器人 | Skill 包与共享 MCP | bug | 仅生产 A（43.163.92.244）执行；B 站按 2026-10-21 指示暂缓。把 scrapy.lute-tlz-dddd.top 加入 mcp_runtime/server.py 的 allowed_hosts 与 allowed_origins。验证 B 机 /mcp 初始化与 Bearer 鉴权。不要只改 nginx。 | 阻塞 | 2026-10-21 | 2026-10-31 |  |
| SP-08 同步能力图谱、总账、README 与交接文档 | 工作台 | 平台能力中心 | bug | 把 /platforms→/tools、/skills→/tools、/collector-docs→/docs、/datasets→/assets、/raw-records→/assets/records、/collect→/runs/[runId] 写入文档。删除 /settings/account 桩描述。MCP 工具数改为 21。项目详情假空态标记为已修。生成物 286/258 标注 2026-10-15。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-09 统一运行回执与运行查询 | Agent机器人 | 运行记录 | 方案迭代 | QuickCollectResponse 与 MCP collect 增加 records、output、usage、timing。新增 GET /api/runs/{id}。MCP 新增 get_run 与 list_records。复用 TaskRun 与 RawRecord，不新建重复状态。 | 已完成 | 2026-10-21 | 2026-10-31 | 2026-10-21 |
| SP-10 实现异步 start/poll/stop 与持久队列 | Agent机器人 | 运行记录 | 新需求 | 先持久受理，再返回 run id。用现有数据库做租约与心跳。保存 provider_run_id 与 dataset_id。超时与重启可恢复。取消请求要与上游已停止区分。 | 进行中 | 2026-10-21 | 2026-10-31 |  |
| SP-11 补齐 MCP 工具描述、typed schema 与运行工具 | Agent机器人 | Skill 包与共享 MCP | 存量需求 | 为 21 个工具补 description 与 annotations。describe_capability 返回 typed schema。新增 get_run、list_records、stop、balance 工具。统一 PublicTool 脱敏。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-12 数说意图层接入与确认卡 | Agent机器人 | Agent：数说 | 新需求 | 把 intents.build_proposal 接到 router 与 commands。自由文本只生成提案，不直接执行。增加一次性确认 token 与过期。前置参数校验。统一结果模板，单条回复不超过 6000 字符。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-13 数说额度、计数与 host 预检 | Agent机器人 | Agent：数说 | 存量需求 | 增加单次条数、批量端点数、每用户每日次数。平台/能力/总览按 endpoint_type 去重。执行前检查 public_feed 与 generic_web 的 host 批准。增加『运行 <run_id>』查询。补 P1-10 测试。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-14 TikTok CDO 全量迁移工具层与异步回执 | Agent机器人 | Agent：TikTok CDO | 方案迭代 | 把 top_ads、ads_search、live 等剩余动作逐步切 run_tiktok_tool。LARK_CDO_TOOL_ROUTING 支持 all。卡片按 message_id 原地更新，显示 run_id、状态、记录数与成本。客户端改异步，不再用 30 秒超时。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-15 TikTok 工作台补运行页签 | 工作台 | TikTok R1 工具与工作台 | 新需求 | 增加第 5 个页签『运行』。显示异步状态、provider_run_id、预留与实际成本、错误分类。支持取消与重跑。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-16 TikTok 商品关系 Cookie 门控生产验证 | 工作台 | TikTok R1 工具与工作台 | 存量需求 | 在生产工作区保存 creator_cookie。验证 tiktok_video_products 与 tiktok_creator_showcase 写入 video_product 与 creator_product。未配置时返回 credential_required，且不发起计费请求。 | 阻塞 | 2026-10-21 | 2026-10-31 |  |
| SP-17 项目级凭据与工具准入 | 工作台 | 凭证配置 | 方案迭代 | 给 platform_credentials 加 project_id。项目获得工具白名单、单次上限、每日额度与并发上限。管理员统一管密钥，项目只拿准入，不拿原始密钥。日志与 Skill 包不含秘密。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-18 账户、成员与角色最小闭环 | 工作台 | 账户与成员 | 新需求 | 实现 owner/admin/member 三角色。新增成员邀请、移除与项目授权 API。让 /settings/members 接真实后端。决定 /settings/account 删除后的账户入口。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-19 外访 grant 轮换与阻断监控 | 工作台 | 生产运维 | 存量需求 | 按 configs/deploy/scrapy/grants/batch-*.json 轮换 host。每月核对 public_feed 与 generic_web 的 5 host 上限。策略拒绝不自动重试。突破上限需策略变更评审。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-20 统一 ToolContract、价格簿与输出 schema | Agent机器人 | 工具目录与计数 | 方案迭代 | 为 223 个 executable 工具各建 rate card。为每个 endpoint 家族建 output schema。参数类型覆盖到 100%。契约版本与 catalog digest 一起版本化。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-21 任务幂等键贯通 API、MCP 与 UI | Agent机器人 | 采集任务 | 存量需求 | 对外暴露 idempotency_key。并发同 key 只建一个 TaskRun。MCP collect 与 agent 提交都带幂等键。保留旧 logs 解析一个发布周期。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-22 根 SKILL.md、llms.txt 与 /connect 接入闭环 | Agent机器人 | Skill 包与共享 MCP | 新需求 | 写根 SKILL.md 与 llms.txt。完善 /connect 的 REST、MCP、Skill 三页签与示例。补 robots、sitemap、OG。不承诺未实现的 CLI。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-23 21 张 canonical 表应用、回填与租户冲突处置 | 工作台 | TikTok R1 工具与工作台 | 存量需求 | 按下一批迭代 D3 在 B6 前完成生产应用与回滚演练。回填历史 RawRecord。记录 cross_tenant_conflicts。明确全局主键与租户属性的冲突策略。 | 进行中 | 2026-10-21 | 2026-11-14 |  |
| SP-24 数据集强血缘与类型扩展 | 工作台 | 数据集与资产 | 存量需求 | live DatasetVersion 写 source_raw_record_ids。扩展 3 类 dataset_type。增加版本对比与完整度趋势。导出字段结构。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-25 Dashboard 增加用量、成本与健康 | 工作台 | 工作台 Dashboard | 新需求 | 从 TaskRun 聚合每个端点的 p50、p95、成功率。显示成本、额度与告警。保留现有情报与任务健康块。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-26 采集文档刷新与公开文档面 | 工作台 | 采集文档 | 存量需求 | /docs 显示最近测试时间、失败原因，分开显示 policy 与 missing configuration。补 /openapi.json、robots、sitemap。保留 /collector-docs 重定向。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-27 任务创建、编辑与调度 UI | 工作台 | 采集任务 | 新需求 | 新增任务表单：项目、endpoint、参数、schedule_cron。支持编辑、启停、运行历史。保留 quick-collect 自动建任务路径。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-28 Apify Store 月检与成功率告警自动化 | 工作台 | 生产运维 | 存量需求 | 每月运行 scripts/check_apify_store_presence.py。非零退出码触发告警。对 30 天成功率跌 8pt 的 actor 建工单。把结果并入 dashboard。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-29 补齐 config-gated 能力 | Agent机器人 | 平台能力中心 | 存量需求 | 按业务价值排序部署 MediaCrawler、AnyCrawl、twscrape、Blackbird、BestBlogs 与 LLM key。先做策略评审，再做配置。MediaCrawler 需要登录态。不要承诺补 key 即可用。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-30 53 个 unsupported 类型的受控执行环境 | Agent机器人 | 平台能力中心 | 方案迭代 | 先定受控出口、出口验证与合规评审。不要用布尔参数放行。目录继续显示永久不可达。扩大 host 上限是安全边界变更，需单独评审。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-31 洞察工作台 B2-B6 | 工作台 | 洞察工作台与报告 | 新需求 | B1 验收后按 B2→B3→B4→B5→B6 推进。先授权与证据等级，再真实执行层，再 claims/report_contract，最后 /workbench 与模板。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-32 报告渲染替换与邮件实发门禁 | 工作台 | 洞察工作台与报告 | 方案迭代 | 用 report_contract 驱动两个纯渲染器。替换 report_service._render_daily_report 三段式。邮件保持默认关闭，满足 enabled + allowlist + approval_id 再发送。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-33 REST/quick-collect 全局限流与成本预算 | Agent机器人 | 平台能力中心 | 新需求 | 把 MCP 的内存限流扩到 REST 与 quick-collect。单次与每日额度原子扣减。TikTok 工具执行单次 2-3 美元上限。80% 告警，触顶阻止。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-34 apps/web 去留决策与处置 | 工作台 | 工作台 Dashboard | 方案迭代 | 先做端点级调用方审计。选择路由、下线或删除。不要直接删。迁 reports workspace 或明确保留。清理 CI 中的 24 个单测与 4 个 e2e 支出。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-35 运行详情补输入、HTTP 状态与成本 | 工作台 | 运行记录 | 存量需求 | 扩展 TaskRun 读模型与 /runs/[runId]。显示输入摘要、provider HTTP 状态、耗时、记录数、价格与成本、请求 ID。不复制 TaskRun 状态。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-36 部署前置检查接入发布流程 | 工作台 | 生产运维 | bug | 把 scripts/preflight-production.sh 接入发布脚本与人工发布清单。发布前检查本地分支、公网健康、edge 固定 IP、API 健康、密钥格式与 schema 版本；任一失败停止发布。 | 进行中 | 2026-10-21 | 2026-10-24 |  |
| SP-37 上游样本 fixture 固化 | Agent机器人 | 平台能力中心 | 方案迭代 | 每个新 TikHub 端点或 Apify Actor 接入前保存一次原始响应样本到 tests/fixtures/。归一化测试必须使用真实字段，覆盖对象金额、评分对象、K/M 缩写、空结果与错误信封。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-38 工具数量与端点映射断言动态化 | 工作台 | 工具目录与计数 | bug | 测试不再写死 8/12/16 个工具。从 TOOL_IDS、TOOL_HANDLERS、TIKHUB map 与 _ENDPOINT_TO_COLLECTOR 派生期望值，并保留注册完整性测试。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-39 生产重启手册与 edge 固定 IP 保护 | 工作台 | 生产运维 | 存量需求 | 写生产重启手册：只执行 up -d api console；禁止重建 edge；发布后检查 edge 在 172.20.0.16 且公网 200；网关不可 reload 时的回退路径。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-40 清理全量测试既有失败基线 | 工作台 | 工具目录与计数 | bug | 修复或标记环境依赖的既有失败：firecrawl API key 断言、spiderfoot target、v2 traceability、workflow postgres guard。让全量单测在干净环境可重复通过。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-41 增加目录跨层对账守卫并接入 CI | 工作台 | 能力目录契约 | 新需求 | 新增 scripts/check_catalog_locks.py，比较 live build、configs/tool-catalog.lock.json、configs/platform-packages.lock.json、generated/platform-packages.json 的 digest 与四组计数；断言 tool_count == unique_endpoint_count；在 .github/workflows/ci.yml 的所有分支和 PR 运行；移除 tests/unit/test_catalog_reconciliation.py 中「生成物可落后于工作树」的豁免。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-42 建立文档漂移检查与刷新触发器 | 工作台 | 文档与能力图谱治理 | 新需求 | 新增 scripts/check_docs_drift.py：从 page.tsx 生成路由集合，与图谱 §2 对比；从 live build 取计数，与图谱、总账、README 的数字对比；CI 失败即报差异。新增 docs/standards/capability-graph-maintenance.md，列明路由变更、catalog digest 变更、迁移、新 MCP 工具四类触发条件与负责人。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-43 增加生产健康监控与飞书告警 | 工作台 | 发布与运维 | 新需求 | 新增 scripts/prod_health_check.py 与 .github/workflows/prod-health.yml（每 5-10 分钟）：检查 A/B 的 /api/health、/tools、/api/tools、/mcp 401、数据库 revision；失败通过数说机器人 webhook 告警；记录响应时间与 schema。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-44 增加文件尾洞/NUL 检查器与提交钩子 | 工作台 | CI 与回归守卫 | bug | 新增 scripts/check_file_integrity.py：对 staged/changed 文件比较 os.stat().st_size 与 len(read())，并统计 NUL；退出 1。新增 .githooks/pre-commit 调用它；在 CI 增加一步；文档写明 `git config core.hooksPath .githooks`。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-45 增加控制台 Playwright 路由 E2E 冒烟 | 工作台 | 工作台首页 | 新需求 | 新增 apps/scraper-console/playwright.config.ts 与 e2e/routes.spec.ts：遍历 routes.ts 的 redirects/kept/new 路由，断言 HTTP 200、main 文本长度、无 4xx/5xx 的 /api 响应、无 console error；对 /tools/[toolId]、/runs/[runId] 用真实 ID；加 390x844 与 1280x800 两个视口；接入 CI。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-46 增加 API 路由挂载守卫 | 工作台 | 平台能力中心 | bug | 新增 apps/api/tests/unit/test_router_mounting.py：导入 create_app，遍历 data_intelligence_hub/api/routes 下所有模块的 router，断言每个 router 的 (method, path) 都出现在 app.routes；同时断言总路由数下限。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-47 建立本机外访归因与出口审计 | Agent机器人 | 采集外访策略 | 新需求 | 新增 scripts/egress_audit.sh：在 20:15-20:45 采集 `lsof -nP -iTCP`、`nettop -P -l 1`、`log show --last 2h` 的进程、PID、父进程、域名；给出 PF anchor 或独立 VM/网络命名空间的 allowlist 方案；把 2026-10-15 告警写入 docs/standards/collection-outbound-safety.md 的未决项。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-48 评估拆分 collector_type 以提高主机批准上限 | Agent机器人 | 采集外访策略 | 方案迭代 | 写 ADR：给出 public_feed/generic_web 按主机组拆分或引入多配置的设计，评估 15-20 个文件、主机上限 5→10+、单次预算 50→100+ 的安全影响；经策略变更评审后再实施。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-49 把仓储层静默字段过滤改为显式报错 | Agent机器人 | TikTok R1 内容与电商 | bug | 修改 TikTok 仓储的 _filter_values：未知键记录 warning 或在严格模式抛错；新增 creator.bio/signature 回归测试；审计所有 TikTok 映射的字段名与 ORM 列名。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-50 增加提交范围守卫与合并复查清单 | 工作台 | CI 与回归守卫 | 新需求 | 新增 scripts/check_commit_scope.py 与 .githooks/commit-msg：`docs:` 提交不得含 apps/ 或 scripts/ 代码；合并他人分支后必须重跑 pytest、pnpm test、detect-changes 并在提交信息记录数字；把清单写入 docs/standards/acceptance-checklist.md。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-51 收敛本地分支并让 CI 覆盖 feature 分支 | 工作台 | CI 与回归守卫 | 方案迭代 | 推送 feat/tool-catalog-catalog 并开 PR；把 .github/workflows/ci.yml 的 on.push.branches 扩到 feat/** 或在 PR 上强制；每周执行 fetch 与集成；清理已合并的临时分支/worktree；记录每个分支的基线与负责人。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-52 把数说飞书机器人纳入能力图谱与部署监控 | Agent机器人 | 数说飞书机器人 | 存量需求 | 在能力图谱新增「数说机器人」模块：webhook、意图、DeepSeek 只读问答、执行边界；部署清单标注仅生产 A；把 webhook 可用性加入 T-06 监控；补 B 站部署评估。 | 未开始 | 2026-10-21 | 2026-11-14 |  |
| SP-53 更新生产验收与镜像构建技能，去掉过期数字 | 工作台 | 发布与运维 | bug | 更新 .claude/skills/production/production-acceptance/SKILL.md：路由 /platforms→/tools，计数 70/270/242→70/309/281，schema 改逐主机期望；在 production-image-build/SKILL.md 增加 edge 固定 IP、`up -d --no-deps api console`、`restart edge`、网关 reload 失败的处理；加版本戳与季度复核。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-54 发布后数据级验收：不只 200，还要有数据 | 工作台 | 凭证与提供方 | 存量需求 | 扩展验收脚本：调用 /api/collectors/docs 断言 tested/success 计数，调用 /providers/status 断言状态分布，选 1 个已知可用端点跑 quick-collect 并断言 records>0；失败即阻断发布。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-55 TikTok 工作台增加广告页签与成本预估 | 工作台 | TikTok R1 工具与工作台 | 新需求 | 在工作台增加广告页签，接入 tiktok_ads_top 与 tiktok_ads_detail。列表展示广告主、标题、CTR、点赞、评论、分享；详情补齐落地页与行业。每个工具显示单次成本上限与预估。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-56 平台包 verified_count 改为实时证据 | 工作台 | Skill 与 MCP 目录（平台包） | bug | 平台包的 verified_count 不再写静态值。每个包从 /api/platform-packages/providers/status 的 live 状态聚合，或在页面明确标注“静态声明”。TikTok 包必须显示 15 verified/17 untested/5 empty/2 degraded，而不是 39/39。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-57 修正 /api/collectors/docs 的 success 语义 | 工作台 | 采集文档（/docs） | bug | success 只统计 last_records_count>0 的运行。last_run_status=success 且 0 条记录归入 empty。页面“失败或未测”计入 empty。当前 254 success 中 11 个是 0 条。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-58 完成 23 个未测端点与 16 个 TikTok 工具首测 | Agent机器人 | TikTok R1 工具与工作台 | 存量需求 | 按能力总账 §4.3 跑全量实测或按优先级抽样。23 个 untested 端点与 16 个 TikTok 工具至少各跑一次真实调用，记录 run_id、记录数、错误分类与耗时。 | 已完成 | 2026-10-21 | 2026-10-24 | 2026-10-21 |
| SP-59 修正 /api/tools 的 executable_now 与汇总计数 | 工作台 | 工具目录与计数 | bug | executable_now 必须与 availability!=disabled 且顶层 executable 一致。修正 pypi_search 的 disabled 但 executable_now=true。汇总 executable_count 与 executable_now 数量必须相等。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-60 给 config-gated 端点补原因与下一步 | 工作台 | 提供方状态（/settings/providers） | bug | 59 个 config-gated 端点必须显示可执行原因：缺哪个凭据、哪个批准、哪个服务。区分“补配置可解”与“策略永久阻断”。不要再给用户“补 key 即可用”的错误预期。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-61 给 TikTok CDO 增加健康端点 | Agent机器人 | Agent：TikTok CDO | 新需求 | 新增 GET /api/agents/tiktok-cdo/health，返回 ready、项目 ID 是否合法、工具路由开关、最近事件时间、错误计数。纳入生产监控与能力图谱。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-62 控制台无效 ID 返回 404 与错误态 | 工作台 | 运行记录（/runs 与 /runs/[runId]） | bug | /runs/{不存在 UUID}、/projects/{不存在 UUID}、/tools/{非平台 ID} 不再永久加载。API 返回 404 后页面显示“记录不存在”并提供返回链接。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-63 梳理 0/7 平台凭证与官方 Provider 取舍 | 工作台 | 凭证与提供方 | 存量需求 | 盘点 7 个平台的必填字段与当前 0 条凭证，决定哪些走官方 API、哪些走 TikHub/Apify、哪些暂缓。为每个平台给出“需要谁提供、何时可配”的结论。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-64 未测端点从 Agent/MCP 默认可执行面隐藏 | Agent机器人 | 工具目录与计数 | 新需求 | discover/list_capabilities 默认只返回 availability=verified 且最近实测有记录的工具。untested/config-gated/degraded 需显式 include_unverified=true 才出现，并标注原因。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-65 建立实测证据 TTL 与过期提醒 | 工作台 | 采集文档（/docs） | 方案迭代 | 为 last_test_at 设 TTL（建议 14 天）。超过 TTL 标为 stale，不计入 verified。Dashboard 与 /docs 显示过期数量，并生成复测清单。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
