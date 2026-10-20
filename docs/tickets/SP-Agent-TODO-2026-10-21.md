# SP-Agent-TODO（2026-10-21）

基线：能力图谱 2026-10-15 版；对照：2026-10-21 生产与主分支。

部署口径：按 2026-10-21 指示，实际部署只做生产 A `43.163.92.244`。B 站相关 ticket 保留为待决策，状态标为阻塞或进行中。

共 40 条。任务类型：Agent机器人 / 工作台；任务属性：bug / 新需求 / 存量需求 / 方案迭代。

| Ticket | 任务类型 | 所属图谱模块 | 任务属性 | 任务方案 | 完成状态 | 登记时间 | 预计完成时间 | 实际完成时间 |
|---|---|---|---|---|---|---|---|---|
| SP-01 统一目录计数与摘要口径 | 工作台 | 工具目录与计数 | 方案迭代 | 以 endpoint_type 为计数单位。运行 scripts/reconcile_catalog.py，更新 configs/tool-catalog.lock.json。让 REST /api/tool-catalog、MCP list_capabilities 与脚本返回同一个 catalog_digest。能力图谱、能力总账与 README 统一写 309 视图/281 唯一端点（发布时实测值），并标注生成物日期。 | 未开始 | 2026-10-21 | 2026-10-24 |  |
| SP-02 修复 catalog 与 providers/status 的状态语义 | 工作台 | 平台能力中心 | bug | 状态只由 label 恰好为 [test] <endpoint_type> 的最近 TaskRun 派生。catalog 不写静态 verified。前端 /tools、/docs、/settings/providers 统一读 /api/platform-packages/providers/status。为 label 漂移加守卫。 | 未开始 | 2026-10-21 | 2026-10-24 |  |
| SP-03 写接口 fail-closed 与读接口 demo 回退收敛 | Agent机器人 | 账户与成员 | 方案迭代 | 按 ADR-007 D2/D3/D5 分批把写接口迁到 get_authenticated_context。读接口按路由分批迁移。跨 workspace 返回 403。MCP 与 agent 调用必须传 workspace。 | 进行中 | 2026-10-21 | 2026-10-24 |  |
| SP-04 对齐两套生产的 schema、分支与部署点 | 工作台 | 生产运维 | 方案迭代 | 仅生产 A（43.163.92.244）执行；B 站按 2026-10-21 指示暂缓。B 机从 main 或 release/2026-10-20 部署。应用 045 前备份并取得授权。逐主机读 /api/health 的 schema_revision。A 不 downgrade、不 stamp。046/047 应用前演练回滚。重建 api/console 后必须 restart edge。 | 进行中 | 2026-10-21 | 2026-10-24 |  |
| SP-05 应用并验证 046/047 迁移与 tool_catalog 表 | 工作台 | 工具目录与计数 | 存量需求 | 在空 Postgres 上 upgrade head，确认只有一个 head。运行 seed 脚本写入 281 行，重复执行保持幂等。核对表行数与 configs/tool-catalog.lock.json 一致。验证 downgrade 删除表。生产应用需逐主机授权。 | 未开始 | 2026-10-21 | 2026-10-24 |  |
| SP-06 数说上线收尾与密钥轮换 | Agent机器人 | Agent：数说 | bug | 仅生产 A（43.163.92.244）执行；B 站按 2026-10-21 指示暂缓。重置在对话中出现过的 App Secret。设置 SHUSUO_ALLOWED_OPEN_IDS。确认 SHUSUO_DEFAULT_PROJECT_ID 是数说专用项目。在飞书后台确认事件订阅 im.message.receive_v1 与回调 URL。按需部署生产 B。 | 进行中 | 2026-10-21 | 2026-10-24 |  |
| SP-07 补齐第二生产的 MCP allowed_hosts | Agent机器人 | Skill 包与共享 MCP | bug | 仅生产 A（43.163.92.244）执行；B 站按 2026-10-21 指示暂缓。把 scrapy.lute-tlz-dddd.top 加入 mcp_runtime/server.py 的 allowed_hosts 与 allowed_origins。验证 B 机 /mcp 初始化与 Bearer 鉴权。不要只改 nginx。 | 阻塞 | 2026-10-21 | 2026-10-31 |  |
| SP-08 同步能力图谱、总账、README 与交接文档 | 工作台 | 平台能力中心 | bug | 把 /platforms→/tools、/skills→/tools、/collector-docs→/docs、/datasets→/assets、/raw-records→/assets/records、/collect→/runs/[runId] 写入文档。删除 /settings/account 桩描述。MCP 工具数改为 21。项目详情假空态标记为已修。生成物 286/258 标注 2026-10-15。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-09 统一运行回执与运行查询 | Agent机器人 | 运行记录 | 方案迭代 | QuickCollectResponse 与 MCP collect 增加 records、output、usage、timing。新增 GET /api/runs/{id}。MCP 新增 get_run 与 list_records。复用 TaskRun 与 RawRecord，不新建重复状态。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-10 实现异步 start/poll/stop 与持久队列 | Agent机器人 | 运行记录 | 新需求 | 先持久受理，再返回 run id。用现有数据库做租约与心跳。保存 provider_run_id 与 dataset_id。超时与重启可恢复。取消请求要与上游已停止区分。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
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
| SP-36 部署前置检查接入发布流程 | 工作台 | 生产运维 | bug | 把 scripts/preflight-production.sh 接入发布脚本与人工发布清单。发布前检查本地分支、公网健康、edge 固定 IP、API 健康、密钥格式与 schema 版本；任一失败停止发布。 | 未开始 | 2026-10-21 | 2026-10-24 |  |
| SP-37 上游样本 fixture 固化 | Agent机器人 | 平台能力中心 | 方案迭代 | 每个新 TikHub 端点或 Apify Actor 接入前保存一次原始响应样本到 tests/fixtures/。归一化测试必须使用真实字段，覆盖对象金额、评分对象、K/M 缩写、空结果与错误信封。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-38 工具数量与端点映射断言动态化 | 工作台 | 工具目录与计数 | bug | 测试不再写死 8/12/16 个工具。从 TOOL_IDS、TOOL_HANDLERS、TIKHUB map 与 _ENDPOINT_TO_COLLECTOR 派生期望值，并保留注册完整性测试。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
| SP-39 生产重启手册与 edge 固定 IP 保护 | 工作台 | 生产运维 | 存量需求 | 写生产重启手册：只执行 up -d api console；禁止重建 edge；发布后检查 edge 在 172.20.0.16 且公网 200；网关不可 reload 时的回退路径。 | 未开始 | 2026-10-21 | 2026-10-24 |  |
| SP-40 清理全量测试既有失败基线 | 工作台 | 工具目录与计数 | bug | 修复或标记环境依赖的既有失败：firecrawl API key 断言、spiderfoot target、v2 traceability、workflow postgres guard。让全量单测在干净环境可重复通过。 | 未开始 | 2026-10-21 | 2026-10-31 |  |
