# Source · Plan C 可信收口冲刺(2026-11-05 ~ 11-15)· r2

- 状态:已批准(2026-11-05,与负责人对齐);r2 = 同日三视角对抗验证(风险/验收/PMO,45 blocker)后修订
- 方案:Plan C「可信收口」,无增援
- 产能:11-05~11-15 共 7 个工作日(05/06/09/10/11/12/13)× 3 人 = 21 人日;周末自愿
- 冲刺目标:11-15 只声明「可当场复验」的完成项;其余进 NB-2026-11-15 延期批次
- 决策记录:
  1. Plan C,无增援(2026-11-05 拍板)
  2. Apify:经实测数据大部分已落盘(/Users/lute/data/apify-lake,8,465 集),冲刺内**无不可逆截止**;D3 改为增量同步,周末自愿
  3. 生产 B:「冻结快照」口径,B=60c9629(11-02),监控不验收;调度停用需访问权限,无则仅公告
  4. 48 表口径:以 docs/plans/abi-schema-manifest.md 为权威(48 表/766 字段,来自真实 PG16 information_schema);见附录 A
  5. mypy 修法 = 修掉新增错误,不调基线(TD-2026-11-02 完成定义)
  6. postgres_abi 入 CI 延期到 12 月(D1 无产能;§1 测试口径相应调整)
  7. 飞书历史消息权限:申请照发;批不下来不影响冲刺
  8. 数说文件消息(CSV)整体移出冲刺:架构文档已明确「file_key 下载链路完成前拒绝文件消息」,真实工作量 2-3 人日

## 0 背景与依据

2026-11-05 七代理差距分析 + 三视角对抗验证确认:

- PMO 对 Source 的 8 项能力 + 2 项待补齐,合计剩余约 82~115 人日,为产能 3 倍以上。
- 口径失真:200 verified 全为 10-09~10-21 历史证据(179/200 已超 14 天);B 0 verified / 224 untested / 数说 ready=false;最新 CI(17a9284)因 mypy 935>934 失败;Cap#75 标 100% 但 11-07 准出物(临时采集转常驻)0 代码路径。
- 飞书 sweep 脚本无认证参数(生产 quick-collect 401);24 个六渠道端点无 DEMO_PARAMS;上次全量 sweep 244 端点仅 101 ok。
- Apify lake 缺口仅 1,049 集(全部建于 10-28~11-05,保留期删除 11-28 起才触达);rescue.py 在 _SUCCESS 存在时跳过,需补 rev 规则;DuckDB catalog/ledger 尚不存在。
- order_id 在 ABI 0 实现;468 品类漂移 0 定义;abi-ingest 容器被 profiles:["abi"] 门控,deploy-p0.sh 只拉起 abi-export。
- meta.audit_log 只有表和模型,无写入者,且只建了 202610 分区(11 月写入会报错)。
- PMO 三棒模型:cap = floor5(0.3×P1 + 0.4×P2 + 0.3×P3);P1/P2 已 100 的 cap 下限 70%。

## 1 口径冻结(D1 宣布,写入周报与 PMO)

| 口径 | 冻结值 | as_of |
|---|---|---|
| 端点目录 | 70 平台 / 312 能力视图 / 284 端点,digest 35ead4d9… | 2026-11-05 |
| verified 规则 | verified = 最新实测成功且 last_test_at ≤ 14 天(TTL 在 D4 落地);每次回写注明 sweep as_of | D4 生效 |
| 生产 | A = scrapy.luteos.com 唯一生产;B = scrapy.lute-tlz-dddd.top **冻结快照(60c9629,2026-11-02)**,监控不验收 | D2 公告 |
| 48 张 schema | 以 docs/plans/abi-schema-manifest.md 为权威:48 表/766 字段(meta 12/raw 24/abi 12);分区子表(apify_item_2026xx、audit_log_202610)单列不并入计数 | 2026-11-05 |
| MCP 工具 | 39 = 16 TikTok + 23 基础(@_tool 注册于 mcp_runtime/server.py);注意 /api/tool-catalog 的 284 是端点契约数,不是 MCP 工具数 | 2026-11-05 |
| 测试 | 以最新 CI 绿 commit 为准;postgres_abi 41 函数/43 用例本地通过,CI 纳入移 12 月 | D1 |
| Cap#75 | 开发状态 已完成→进行中,进度 100→85(P3=50);验证状态保留「已验证」;回退 11-04 01:55 的 85→100 审计并注明原因 | D2 |
| Stage 3 | 六渠道 P3 收口 12-05;telemetry v0 定位为「统计基座」,不计 Stage 3 完成度;/sop 漏斗 Source 行同步改 | D2 |
| 项目标签 | 「Stage 3 自进化 78%」→「Stage 2→3(统计基座建设中)」 | D2 |

## 2 逐日分解

三个人:**后端**=采集中台研发 / **运营**=控制台运营 / **架构**=建模架构。
验收统一要求:命令 + 期望值 + 证据落点(目录 `docs/ops/sprint-c-evidence-2026-11-15/`,下称 EVID)。

### D1 · 11-05(周四,今天,剩余产能 ~1.0)

| # | 任务 | 负责 · 预算 | 验收 |
|---|---|---|---|
| 1 | 冻结会 30 分钟 | 全员 · 0.25 | §1 十条口径宣布;纪要落 EVID/01-freeze-minutes.md |
| 2 | 提交工作树 4 路径 | 后端 · 0.25 | 2 个 console 文件 + releases.jsonl + **本计划文档**;`git status --porcelain` 空 |
| 3 | 修 mypy 新增错误 | 后端 · 0.5 | current 935→934,不调基线;`check_mypy_baseline.py` OK |
| 4 | push + CI 确认 | 后端 · 0.25 | main == origin;CI 7 job 绿(commit 哈希记 EVID) |

### D2 · 11-06(周五)发布与口径落地 —— 3.0

| # | 任务 | 负责 · 预算 | 验收 |
|---|---|---|---|
| 1 | A 发布 | 后端 · 0.5 | 干净树 deploy-p0.sh;`curl -sS -o /dev/null -w '%{http_code}' https://scrapy.luteos.com/api/health` = 200 且 schema=current;账本 +1 |
| 2 | 删除端到端冒烟 | 运营 · 0.5 | 生产建 PII 测试集→声明→删除→404;**审计流水当前无写入者,验收=404+账本备注**;写入者补齐见 D6#4 |
| 3 | B 冻结公告 | 架构 · 0.5 | PMO Source 卡改「A 生产 + B 冻结快照(60c9629)」;B scheduler 停用(有权限则执行,无则公告+NB) |
| 4 | PMO 改期回写 | 架构 · 1.0 | 按 §6 diff 表改五处渲染页(/、/projects、/roadmap、/sop、/present)+ Cap#75 字段(开发/验证/进度/P3 起止)+ 11-04 审计回退说明;证据=/api/export.csv diff + /api/audit-logs 截图 |
| 5 | telemetry schema 冻结 | 后端 · 0.25 | D1 已由本计划冻结最小 schema(channel/chat_id/trigger/command/created_at,保留 90 天,迁移号 069);D2 仅确认,评审不过走本条 |
| 6 | 飞书权限申请 | 运营 · 0.25 | im:message:readonly 申请单号记 EVID |

### D3 · 11-07(周六,自愿;不投入则顺延,无不可逆截止)—— 1.5

| # | 任务 | 负责 · 预算 | 验收 |
|---|---|---|---|
| 1 | Apify 增量同步 | 后端 · 1.0 | 按 abi-external-datacenter.md(现权威方案)执行:枚举差集(keyset 游标,实测差 1,049 集/112,415 item)→ rescue.py 补「远端 itemCount 变大则 rev+1」→ 原子写;**不改 apify-raw-warehouse.md 状态(已被取代)** |
| 2 | DuckDB catalog/ledger | 后端 · 0.4 | 用 python duckdb 1.4.5(CLI 未装)建 catalog;对账:远端 total == 本地行数和 == 0 差 |
| 3 | 第二副本 | 运营 · 0.1 | lake 196MB 复制到独立磁盘/B 机,清单哈希比对 |

### D4 · 11-09(周一)monitor v1 —— 2.75

| # | 任务 | 负责 · 预算 | 验收 |
|---|---|---|---|
| 1 | verified TTL 判定 | 后端 · 0.5 | build_provider_status 加「last_test_at ≤ N 天(N=14 可配)」;单测;**上线后 verified 200→约 21,属预期,回写时如实披露** |
| 2 | freshness 告警 | 后端 · 0.75 | maintenance/freshness_check.py(仿 prod_health_check 模式;复用 task.py freshness_status/stale_hours;stale 阈值 72h;Notification 通道);scheduler tick 接入;构造 stale 任务→通知产生,截图记 EVID |
| 3 | prod_health 配置化 | 后端 · 0.75 | per-check base_url 外置;B 纳入巡检(文案去硬编码「生产 A」;B 独立 state 文件);「监控不验收」口径与 §1 一致 |
| 4 | 控制台 /tasks 增强 | 运营 · 0.5 | next_run_at 展示 + pause/resume;手工验收截图 |
| 5 | providers 页 freshness 列 | 运营 · 0.25 | 展示 TTL 后 verified 与 last_test_at |

### D5 · 11-10(周二)telemetry v0 —— 2.5

| # | 任务 | 负责 · 预算 | 验收 |
|---|---|---|---|
| 1 | BotRequestLog 落库 | 后端 · 1.0 | 迁移 069;webhook 单函数写点(失败不阻断回执);带登录态发测试消息→`SELECT count(*) FROM bot_request_log` ≥1 |
| 2 | bot-summary 接口 | 后端 · 0.5 | GET /api/telemetry/bot-summary?days=30(鉴权;字段 command/channel/count);curl 带 token 返回 200+字段齐全(实现前 404 属预期) |
| 3 | 样张 | 运营 · 0.5 | 汇总输出样张(**格式样张,注明无历史数据,不验证 ≥10 次/周阈值**) |
| 4 | 周报口径冻结 | 架构 · 0.25 | 「≥10 次/周」判定规则落 EVID;首份周报 12 月首周 |
| 5 | CI/杂项缓冲 | 后端 · 0.25 | D4 遗留单测/类型修补 |

### D6 · 11-11(周三)48 表证据 + ABI 常驻 —— 2.5

| # | 任务 | 负责 · 预算 | 验收 |
|---|---|---|---|
| 1 | 48 表生产取证 | 架构 · 0.5 | SSH+docker exec psql(路径见 docs/ops/production-restart.md:112,141);information_schema 直查;输出 EVID/abi-48tables-2026-11-11.json(schema/table/column/type/nullable/row_count/as_of);与 abi-schema-manifest.md 对账;差异判定:分区子表单列,实体表缺失=降级口径 |
| 2 | abi-ingest 常驻 | 后端 · 0.75 | run_tick 已存在(ingest.py:189-230),真实缺口=compose profiles:["abi"] 门控 + deploy-p0.sh:449 只拉 abi-export;改 deploy 服务列表;验收=发布后 /api/health scheduler 心跳 + scan 日志;token 用 APIFY_API_TOKEN env(--scan-once 的 stdin 仅用于 --seed-tokens);注意 --scan-once 不写 schedule_state,补扫走队列 |
| 3 | T-1 补扫 | 运营 · 0.5 | 走队列扫 2026-11-10;对账按账号维度:raw.apify_dataset 行数 == 该账号远端 dataset 数;分区和校验 |
| 4 | audit_log 写入者 | 后端 · 0.75 | 建 audit_log_202611 分区 + 删除路径 INSERT meta.audit_log(action/object_id/workspace_id/detail);D2#2 验收升级为「404+审计行」 |

### D7 · 11-12(周四)MCP 工具 + ADR —— 3.0

| # | 任务 | 负责 · 预算 | 验收 |
|---|---|---|---|
| 1 | Reddit 3 MCP 工具 | 后端 · 1.0 | reddit_search / fetch_thread / subreddit_hot(@_tool,走 TikHub+现有归一化);`grep -c '^@_tool' server.py` 39→42;数说触发截图 |
| 2 | YouTube 2 MCP 工具 | 架构 · 0.75 | youtube_channel_videos / youtube_captions;@_tool 计数→44;各 1 单测 |
| 3 | order/sku ADR | 架构(并行) · 0.75 | 主键选型、映射边界、468 漂移处理原则;**不落库**;ADR 合并 |
| 4 | NB 建档(若 D3 未做) | 运营 · 0.5 | NB-2026-11-15-source-deferred-batch.md 按 §4 |

### D8 · 11-13(周五)第二次发布 + 补测 + 回写 —— 3.0

| # | 任务 | 负责 · 预算 | 验收 |
|---|---|---|---|
| 1 | A 第二次发布 | 后端 · 0.5 | monitor v1+telemetry+audit_log+迁移 069+新工具;**CI 全绿为前置门禁**;/api/health 200+schema=current;账本 +1 |
| 2 | live sweep 补测 | 后端+运营 · 1.0 | 脚本先加 --cookie/--token 参数(当前 401);单端点预检 201 再批量;--project-id 取 reports/live-sweep/latest.json;24 个无 DEMO_PARAMS 端点显式跳过并记录;Apify 用例用 complex_homage token(yueguz 本月 $201.17/$199 已超限);结果落 EVID/live-sweep-2026-11-13.json(/reports 被 gitignore,需复制或 add -f) |
| 3 | PMO 证据回写 | 架构 · 0.75 | verified(新 as_of)、MCP 44、48 表 JSON、freshness;派生数按 §6 表 |
| 4 | 成果总结上架 | 运营 · 0.5 | 日报 + POST /api/ingest/report(带 html_content);验收=reports-view URL 返回 200(当前 11-03/11-04 报告 303 缺文件) |
| 5 | NB 补充 | 运营 · 0.25 | sweep 失败端点、B 停用结果、权限进度入 NB |

### 11-14/15(周末)证据包整理(自愿,≤1.0)

- EVID/index.md:12 类证据按附录 B 索引补齐。
- **不做新验收签发**(11-15 周日)。

## 3 预算汇总

| 天 | 预算 | 主项 |
|---|---|---|
| D1 11-05 周四 | 1.25(今日剩余) | 冻结会、提交、mypy、CI |
| D2 11-06 周五 | 3.0 | 发布、B 冻结、PMO 回写 |
| D3 11-07 周六(自愿) | 1.5 | Apify 增量 + catalog |
| D4 11-09 周一 | 2.75 | monitor v1 |
| D5 11-10 周二 | 2.5 | telemetry v0 |
| D6 11-11 周三 | 2.5 | 48 表 + abi-ingest + audit |
| D7 11-12 周四 | 3.0 | MCP 工具 + ADR |
| D8 11-13 周五 | 3.0 | 第二发布 + sweep + 回写 |
| 周末 11-14/15 | ≤1.0 | 证据包 |
| **合计** | **工作日 18.0 / 21,缓冲 3.0;含周末 ~20.5** | |

## 4 显式延期清单(NB-2026-11-15-source-deferred-batch.md)

每条含 PMO 行号与 old→new 日期(三棒字段按 PMO CSV 行 26-33):

| 延期项 | PMO 行 | old→new | 估量 |
|---|---|---|---|
| #75 P3 高频临时采集自动转常驻(11-07) | 行 26 | 11-07→12-15 | 13-17 人日(telemetry→聚合→promotion→自动 CleaningPlan) |
| #76 TikTok P3 Emily/Clone 高频抓数字段固化(11-08) | 行 27 | 11-08→12-05(依赖 telemetry 数据积累) | 2-3 |
| #77 Reddit P3:DOM 通道+confidence+07:05 流水线(11-08) | 行 28 | 11-08→12-05 | 6-8 |
| #78 YouTube P3:高频频道/字幕→定时任务固化(11-09) | 行 29 | 11-09→12-05(依赖 telemetry) | 2-3 |
| #79 IG P3 达人/竞品帖高频固化(11-11) | 行 30 | 11-11→12-05 | 3-4 |
| #80 FB P3 社媒高频查询固化(11-13) | 行 31 | 11-13→12-05 | 3-4 |
| #81 Trends P3 关键词池并入监控池(11-14) | 行 32 | 11-14→12-05 | 2-3 |
| #82 P3:order/sku 主键落库+468 漂移映射执行+6 Agent 同源取数(11-15) | 行 33 | 11-15→12-15(ADR 本冲刺交付) | 8-12+15-20 |
| IG/FB/Trends 薄 MCP 工具 | 行 30-32 | — | 6-9 |
| 数说文件消息完整版(CSV 映射/预览/权限+Excel;含 file_key 下载链路与资源下载权限申请) | 首页待补齐 | 11-15→12-05 | 2-3(MVP)/5-7(完整) |
| Secret 轮换自动化+双环境演练 | 首页待补齐 | 11-15→12-05 | 2-3 |
| TikTok 广告页签/商品关系回填/creator_cookie 配置 | 行 27 | — | 4-6 |
| L2-L4 门禁接入 MCP 主路径;E2E 补齐(10 路由);postgres_abi 入 CI | §4 旧版 | 12 月 | 5-8 |
| Apify 每周增量同步例行化 + 阶段 1(parquet/归因/去重) | — | 12 月 | 4-6 |
| B 生产对等(bot 独立凭证+端点复测;凭证串线 ticket) | — | 12 月 | 2-3 |
| 工作台 /workbench 404 端点(7-8 个)与报告合同 404 | — | 12 月 | 3-5 |

## 5 风险与回滚

| 风险 | 缓解 |
|---|---|
| TTL 生效后 verified 200→~21 的视觉冲击 | D2 改期说明里**预先披露**数字变化逻辑;D8 sweep 后回写真实值;不粉饰 |
| sweep 暴露失败端点 | 按实际结果降级;失败项入 NB;上轮 244→101 ok 的先例已在案 |
| yueguz token 超限 | Apify 用例切 complex_homage token;额度在 D8 前确认 |
| scan.py 用 offset 枚举,保留期删除会跳数 | D6#2 验收只按账号维度对账;offset→keyset 改列入 NB |
| audit_log 分区缺失导致 11 月写入报错 | D6#4 建 202611 分区,先于删除路径写入合并 |
| abi-ingest 常驻后 Postgres 写入量 | 先保持每 tick 补齐 T-1 的现状节奏;不加频 |
| D2 PMO 回写被打回 | diff 表已按三棒模型算术预演(§6);被打回项当天修正重提 |
| 周末投入不可用 | D3 无不可逆截止(增量数据 11-28 才过保留期),顺延即可 |
| 发布事故 | deploy-p0.sh 脏树拦截;回滚走旧镜像 retag;B 冻结不参与发布 |

## 6 PMO 口径变化(字段级 diff,D2/D8 回写依据)

三棒模型:cap = 0.3×P1 + 0.4×P2 + 0.3×P3(floor5)。P1/P2 已 100 的 cap 下限 70。

| Cap | P1/P2/P3 现 | P3 目标 | cap 现值→目标 | 依据 |
|---|---|---|---|---|
| #75 平台与 monitor | 100/100/100 | 50 | 100→85 | monitor v1+telemetry v0 交付;自动转常驻延期 |
| #76 TikTok | 100/100/50 | 0 | 85→70 | Emily/Clone 固化依赖 telemetry,延期 |
| #77 Reddit | 100/100/50 | 0 | 85→70 | DOM/confidence/07:05 延期 |
| #78 YouTube | 100/100/17 | 0 | 75→70 | 高频→定时任务延期 |
| #79 IG | 100/100/50 | 0 | 75→70 | 同上 |
| #80 FB | 100/100/10 | 10(不变) | 70→70 | 无变化 |
| #81 Trends | 100/100/10 | 10(不变) | 70→70 | 无变化 |
| #82 上游底座 | 100/100/17 | 0 | 75→70 | 主键/468/6Agent 延期;48 表取证+abi-ingest 属 P2 维护 |

**派生数(回写时随 export.csv 实测校准):**
- 项目 pct = round((85+70×7)/8) = **79→76**;能力装配 已完成 1/进行中 7 → **0/8**
- G2 = (Echo 290 + Market 100 + Source 575 + Signal 75)/17 = **65→61**
- S4 = (Signal 75 + Source 575)/11 = **65→59**
- 全站 = 49 能力加权,Δ≈ −0.6 → **58→57**(回写时实测)
- 首页审计:必须引用并回退 11-04 01:55「Cap#75 进度 85%→100%、状态 进行中→已完成」一条,注明改期原因
- /sop 漏斗 Source 行:「22 次/周、Stage 3、截止 11-07」→「统计基座 11-10 上线,首份周报 12 月首周」;「Stage 3 自进化 78%」→「Stage 2→3(统计基座建设中)」

## 附录 A · 48 张 schema 口径(r2 修正)

r1 曾按 `grep op.create_table` 判定「48 无法复现」——**该结论错误**,漏计了三处:

1. `202610280061_abi_raw.py:183` 用原生 SQL `CREATE TABLE raw.apify_item`(月 RANGE 分区母表,不在 op.create_table 统计内);
2. `202610280060_abi_meta.py:377/402` 的 meta.audit_log + audit_log_202610 分区;
3. `202610280061_abi_raw.py:218/242` 运行时动态建的月分区(apify_item_2026xx)。

正确算式:40(op.create_table:meta 10 + raw 2 + raw_local 16 + abi 12)+ apify_item + audit_log + 6 张运行时分区 = **48**。权威清单已存在:**docs/plans/abi-schema-manifest.md(48 表/766 字段,来自真实 PG16 information_schema,meta 12/raw 24/abi 12,分区子表单列)**。D6#1 取证即以该 manifest 为期望值,与生产 information_schema 对账,不再重造口径。

## 附录 B · 冲刺证据索引(落点 EVID = docs/ops/sprint-c-evidence-2026-11-15/)

1. 01-freeze-minutes.md(冻结会纪要)
2. ci-green-commit.txt(D1/D8 两次 CI 绿 commit 哈希)
3. release-a-d1.md / release-a-d8.md(/api/health 输出 + 账本行)
4. delete-smoke.md(D2 404 冒烟;D6 后补审计行截图)
5. apify-delta-sync.md(D3 对账输出)
6. monitor-freshness-alert.png(D4 告警截图)
7. telemetry-bot-summary.json(D5 样张,注明格式样张)
8. abi-48tables-2026-11-11.json(D6,与 manifest 对账)
9. t1-scan-reconcile.md(D6 账号维度对账)
10. mcp-tools-44.txt(D7 grep 输出 + 数说触发截图)
11. live-sweep-2026-11-13.json(D8)
12. pmo-diff-before-after/(/api/export.csv 前后 diff + audit-logs 截图 + reports-view 200 验证)
