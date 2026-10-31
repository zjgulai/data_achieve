#!/usr/bin/env python3
"""KG-04 四层记忆批量蒸馏入库脚本（SOP 第 4 步，方案 §4 定稿表）。

用法：
    python3 tools/dev/distill_memories_to_nmem.py --dry-run   # 只打印待写清单
    python3 tools/dev/distill_memories_to_nmem.py             # 实际入库（memories add --id upsert，幂等）

要点（来自 KG-02 冒烟裁决）：
- 每条显式 --space source-agent（hook 蒸馏会跟随 active space，不依赖环境默认）。
- 确定性 ID（ds-lX-NN）+ `memories add --id` upsert，重复运行不产生重复记忆。
- unit_type 只用 8 枚举；importance 按 0-1；--when 只取 past/present/future/timeless。
- 长正文走 --stdin，避免 shell 引号损坏。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SPACE = "source-agent"
CLI = "nmem"

# 每条：id, title, importance, unit_type, when, labels, content
MEMORIES: list[dict] = [
    # ============ 第一层 核心准则（L1，imp 1.0，decision，timeless）============
    dict(id="ds-l1-01", title="产品身份与 provider_call 红线", importance=1.0, unit_type="decision", when="timeless",
         labels=["identity", "redline"],
         content="Data Intelligence Hub（仓库 /Users/lute/Project/data_scrapy，线上 scrapy.luteos.com）的身份是纯数据采集平台：FastAPI 后端提供统一 catalog、quick-collect、任务调度、平台 Skill 与 MCP Runtime；Next.js scraper-console 是生产公网主界面。通用 Agent 工具平台是方向、尚未实施，不得当已实现能力陈述。硬红线 provider_call=false：业务路由、Agent、UI 不得直连第三方 Provider，必须经 collector 抽象层。来源：AGENTS.md 第 12、297 行；docs/architecture/【技术方案】DIH整站能力整合方案.md。"),
    dict(id="ds-l1-02", title="密钥与敏感文件红线", importance=1.0, unit_type="decision", when="timeless",
         labels=["redline", "security"],
         content="凭据禁入仓库、禁入记忆、禁入图谱：不得提交 .env.production、SSH key、TLS 私钥、API key、Cookie 或账号 JSON（仓库根 zhoujian_pachong.pem、DDDD.pem、luteos.com.key/.pem 不入库）。改密钥必须同时更新 configs/deploy/scrapy/docker-compose.yml 的 environment 显式列表，只改 .env.production 变量不会进容器。raw/secret 不入 Library：.pem/.key/.env/日志/原始 JSON 一律排除，Library 归档用显式白名单禁 glob。来源：AGENTS.md 第 28、300 行；docs/standards/collection-outbound-safety.md。"),
    dict(id="ds-l1-03", title="共享基础设施与生产隔离红线", importance=1.0, unit_type="decision", when="timeless",
         labels=["redline", "infra"],
         content="共享宿主机红线：不删外部网络 lighthouse_ai_video_net、不重建 edge（固定 IP 172.20.0.16 丢失会导致共享网关缓存旧 IP 而公网 502）、不重启无关 Compose 项目、不跑 docker volume/system/network prune、不绑 80/443、不重启 ai_video_nginx。生产只读优先，探索性操作不落生产。来源：AGENTS.md 第 301-303 行；docs/retrospectives/2026-10-11-生产B上线复盘.md。"),
    dict(id="ds-l1-04", title="发布红线", importance=1.0, unit_type="decision", when="timeless",
         labels=["redline", "deploy"],
         content="发布顺序四条：①先 git push 再上服务器发布（否则取旧 commit，表现为改动完全没生效）；②服务器同步用 git fetch + merge --ff-only FETCH_HEAD，禁 git pull（静默 Already up to date）与 reset --hard；③重建 api 后必须 restart edge（共享网关缓存容器 IP）；④热替换容器文件不是正式发布，下次部署必须重建镜像；平台坑点 notes 改动必须重建 api，只重建 console 不生效。不得在生产工作区 git commit。来源：AGENTS.md 第 326-329 行；docs/ops/workflow-release-rollback-stable.md。"),
    dict(id="ds-l1-05", title="双生产差异纪律", importance=1.0, unit_type="decision", when="timeless",
         labels=["redline", "deploy"],
         content="两套生产并存：A=scrapy.luteos.com（腾讯云 ubuntu@43.163.92.244，分支 main，主生产）；B=scrapy.lute-tlz-dddd.top（ubuntu@101.34.52.232，分支 deploy/tiktok-cdo-codex，TikTok CDO 专用）。两套差异只允许 codex 版 CDO Agent 一处。发布检查必须逐主机读取 /api/health 的 schema_revision，不得用单一基线覆盖两套生产。生产切换需点名目标主机与镜像授权。来源：AGENTS.md 第 306 行；ADR-007 D1。"),
    dict(id="ds-l1-06", title="能力边界红线", importance=1.0, unit_type="decision", when="timeless",
         labels=["redline", "scope"],
         content="采集能力边界：不加官方 Reddit/YouTube collector，不恢复 Shopee 直连；受控外访只走 COLLECTION_HTTP_GRANTS 白名单。整站能力整合类改动需授权（方案状态「范围已确认，尚未进入实施」，ADR-006「已提议，待实施评审」）。来源：docs/retro/2026-10-21-近一周复盘.md；docs/architecture/decisions/ADR-006。"),

    # ============ 第二层 业务口径（L2，imp 0.9，fact，timeless）============
    dict(id="ds-l2-01", title="契约冻结 v1.1 是唯一契约来源", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "contract"],
         content="《契约冻结 v1.1》（docs/design/【契约冻结】v1-表名-枚举-接口.md，2026-10-22）是表名、枚举、接口路径、字段名与页面路由的唯一契约来源；新增或修改必须先改契约与附录 A 机器登记块再改代码；设计文档与契约冲突时以契约为准。已知漂移：Project.domain 契约写 5 值、代码 schemas/project.py 是 8 值（osint/ecommerce/social/competitor/agent/platform/governance/mixed），两值并存待契约同步。来源：契约冻结 v1.1；apps/api/src/data_intelligence_hub/schemas/project.py 第 14-25 行。"),
    dict(id="ds-l2-02", title="冻结表名与运行语义", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "contract"],
         content="表名用契约冻结的物理名，不加 automation_ 前缀。runs、run_steps、task_runs、workflow_runs 四表语义不同不得互相替代：runs 是工作台编排运行（M10 拥有），task_runs 是采集任务执行（M04 采集执行唯一写 task_runs 与 raw_records）。一张表只能有一个拥有模块。来源：契约冻结 v1.1；docs/design/【模块设计】DIH工作模块与接口.md。"),
    dict(id="ds-l2-03", title="运行/步骤/结果/健康度/claim/门禁枚举互斥", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "enum"],
         content="枚举硬约束：runs.status 不接受 degraded/held（degraded 只属于 health_status，held 只属于 fixture 的 workflow_runs）；outcome 不接受 partial（四种合法结果见 ds-l2 相关契约条目）；枚举值一律用契约小写 snake_case 原文，不造同义词。违反契约冻结与数据库 CHECK 约束会直接报错。三套 Gate 不可混：G-Plan/G-Cost/G-Evidence/G-Claim/G-Publish 是运行门禁；authorizations.gate_status 是 pending/pass/fail/blocked/expired；VOC GateStatus 是 PASS/CONDITIONAL/BLOCKED/NOT_STARTED。来源：契约冻结 v1.1；docs/standards/。"),
    dict(id="ds-l2-04", title="能力口径三分法与并存数字", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "capability"],
         content="能力数量三个口径不可互换：平台（70）、能力视图（按 capability_id 计 catalog 条目）、唯一端点（按 endpoint_type 去重）。并存快照：生产 2026-10-21 实测 70/311/283；仓库 lock（configs/*.lock.json，catalog_digest 35ead4d9，两个 lock 共用同一 digest）70/312/284（含新增 exa_agent_research 无实测状态）。引用必须带口径日期与 digest，使用前重取生产 GET /api/tool-catalog；不同日期数字不比较不平均。来源：README.md 第 15-19 行；configs/tool-catalog.lock.json；configs/platform-packages.lock.json。"),
    dict(id="ds-l2-05", title="端点六态词表与 verified 语义", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "capability"],
         content="端点状态六态：verified/config-gated/degraded/empty/untested/disabled，不自造 success/fail/ok。verified 只是静态声明或最近一次 [test] 实测成功（返回 ≥1 条记录），不是永久可用承诺。真实状态看 GET /api/collectors/docs 与 GET /api/platform-packages/providers/status；实测证据 label 必须精确为 [test] <endpoint_type>，格式漂移会被静默忽略。生产目录行数与仓库生成物行数不同是代码代差，对账以 catalog_digest 为准。来源：AGENTS.md 第 218、237 行；reports/achievements-20261031/Source-项目成果总结-20261031.md §4.1。"),
    dict(id="ds-l2-06", title="两套证据等级不可混用", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "evidence"],
         content="证据等级两套且不得共用字段或互相映射：运行级 L0_unverified→L4_authorized_live 五级（run_evidence_grades）；VOC 级 Confirmed/Directional/Supported hypothesis/Evidence gap/Blocked/Not authorized 六级（VocClaim 专用）。VOC 的 Claim/Evidence/Gate 与主 API 的 claims/evidences 是两套实现，表名相似但语义、等级、字段都不同。来源：docs/standards/；voc_pipeline/spec/；docs/design/【模块设计】DIH工作模块与接口.md。"),
    dict(id="ds-l2-07", title="采集外访安全硬约束", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "security"],
         content="COLLECTION_NETWORK_MODE 只接受 offline/restricted 两态（无 unrestricted，未知值配置校验失败）；本地默认 offline，生产未显式配置时 restricted。受控 HTTP：每条批准配置 hosts 为 1-5 个精确主机（禁通配符/子域/端口/IP/userinfo），max_requests 1-50，max_domains 1-5 且不小于 hosts 数，timeout_seconds ≤60；同一 collector 只能有一条配置，追加第二条等于该类型全拒。外访配置只能服务端操作者维护，客户端/任务参数不能授权。来源：docs/standards/collection-outbound-safety.md 第 22-72 行。"),
    dict(id="ds-l2-08", title="控制台信息架构契约", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "console"],
         content="一级导航契约冻结为四项：工作台（/workbench，唯一任务入口）、报告（/reports）、连接器（/capabilities、/tools、/tools/tiktok、/connect、/docs）、设置（/usage、/settings/credentials、/settings/providers、/settings/members、旧版 /dashboard 重定向）；/projects、/runs、/assets 不得作为一级入口。改一级导航或重定向需产品确认（routes.ts P0 冻结）。Console UI 禁 emoji、彩色渐变卡片与 glassmorphism，颜色只用 var(--token-name)，平台图标用 PlatformLogo。来源：apps/scraper-console/src/lib/routes.ts 第 190-260 行；AGENTS.md 第 255-260 行。"),
    dict(id="ds-l2-09", title="MCP 工具数四口径", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "mcp"],
         content="MCP 工具数四个定义并存，按用途取：@_tool 装饰器计数 39 个（apps/api/src/data_intelligence_hub/mcp_runtime/server.py，2026-10-31 统计，现行）；TOOL_POLICIES 23 条策略（tool_registry.py）；README 的 25 已过期；tool_registry.py 文档串 36 已过期。锁文件维度：tool-catalog.lock.json 284 工具/226 可执行。说「工具数」必须注明口径来源。来源：mcp_runtime/server.py；mcp_runtime/tool_registry.py；configs/tool-catalog.lock.json；成果总结 §2.3/§4.6。"),
    dict(id="ds-l2-10", title="整站方案首期 13 项不做", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "scope"],
         content="通用工具平台整站改造首期不做：①不重写现有 Collector/TaskRun 与数据集链路；②不将生成结果包装成假 RawRecord；③不建设第三套前端；④不并列维护两套能力目录真相；⑤不开放任意 URL/HTTP 方法/上传插件；⑥不建设通用可视化工作流引擎；⑦不做支付/钱包/订阅/供应商入驻市场；⑧不承诺独立 SDK 或 CLI 等 13 项。产品方向陈述见 ds-l4-09。来源：docs/architecture/【技术方案】DIH整站能力整合方案.md 第 62-87 行。"),
    dict(id="ds-l2-11", title="迁移链纪律", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "migration"],
         content="Alembic 迁移文件命名 YYYYMMDDNNNN_<slug>.py，revision 与 down_revision 用同一数字串，alembic heads 必须只有一行。迁移默认 source-only：未经 exact-target 授权与备份/回滚计划不得上真实库；迁移 045 保留在 main，不得改写 main，不得对生产 A 执行 downgrade 或 stamp（ADR-007 D1）。生产 schema 版本有 053/056/057/067 多种文档说法且未实测统一，引用前以各主机 /api/health 实测为准。sql/ 目录是空的，schema 事实源在 apps/api/alembic/versions（67 迁移）+ models（42 文件 165 表）。来源：ADR-007；docs/standards/；docs/retro/。"),
    dict(id="ds-l2-12", title="ABI raw 湖契约", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "abi"],
         content="ABI raw 路径模板固定 raw/platform=.../data_type=.../dt=YYYY-MM-DD/actor=owner__name/dataset=<dataset_id>/rev=NN：dataset_id 保留原始大小写、不加 run= 段、dt 为 UTC 采集日。归因链经 platform→endpoint→actor→dataset。field_policy.mask_rule 白名单只有 redact/null/hash/last4/partial，越界值 fail-closed 回 ***，放宽遮罩须审批。export_policy 依赖两条部分唯一索引防重复，用重复行保存新策略会静默失效（读路径取最旧行）。ABI apify_item 入库前必须剔除 \\u0000（jsonb 拒绝 NUL，整批失败）。来源：docs/plans/abi-external-datacenter.md；docs/plans/apify-raw-warehouse.md；docs/retro/。"),
    dict(id="ds-l2-13", title="HTTP 错误信封与认证规则", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "api"],
         content="API 错误统一信封 error.code/error.message/error.request_id/error.details；request_id 取 X-Request-ID，缺失时生成 32 位小写十六进制并回显。MCP 入口 https://scrapy.luteos.com/mcp/ 要求 Bearer Token。身份事实源与审计链按 P1 身份统一工作流契约执行。来源：docs/api/api-contract-data-intelligence-hub-stable.md；契约冻结 v1.1 接口路径节。"),
    dict(id="ds-l2-14", title="新增采集能力七处注册面", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "procedure"],
         content="新增采集端点必须同步七处：①collector 实现；②registry；③catalog 定义；④quick-collect 映射；⑤配置校验；⑥Console 表单（按需）；⑦测试与平台包锁文件/Playbook。证据标签精确为 [test] <endpoint_type>。实测证据必须带 verified_at（YYYY-MM-DD）与 source_ref；无实测的声明标 config-gated 或静态声明，不得写 verified。来源：docs/standards/；AGENTS.md 第 237 行。"),
    dict(id="ds-l2-15", title="双前端分工与生产编排位置", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "deploy"],
         content="scraper-console（26 页）是生产公网主界面；apps/web（29 页）由 edge 以 /insight 子路径转发、生产容器 data_achieve_scrapy_web 仅内部网络运行，不是公网主界面。生产编排只在 configs/deploy/scrapy/docker-compose.yml（常驻 db/export-init/abi-export/api/web/console/tor/maigret/spiderfoot-real/spiderfoot/edge；abi-migrate/abi-ingest 走 profile abi，proxy_rotator 走 profile proxy，obscura 走 profile obscura，browser-use 走 profile browser_use）；仓库根 docker-compose.yml 只有本地 db。edge 路由：/api/ 与 /mcp → api:8000，/insight → web:3000，/ → console:3001；/api/quick-collect 超时 1800 秒。来源：configs/deploy/scrapy/docker-compose.yml；configs/deploy/scrapy/edge-nginx.conf；成果总结 §4.3。"),
    dict(id="ds-l2-16", title="写作标准与术语表指向", importance=0.9, unit_type="fact", when="timeless",
         labels=["caliber", "writing"],
         content="中文技术写作按 ASD-STE100 等效规则：一名一义、一句一个意思、短句、主动语态、先结论后原因；标准文件 docs/standards/writing-standard-ste.md，术语以整站能力整合方案 §1.1 左列固定表为准（工具、能力视图、端点、平台包、调用、采集任务、运行、产物、数据集、抽屉、对话框）。新增/重写 Markdown 必须带 name 与 description Frontmatter；业务文档间用 Markdown 链接；历史材料只加「历史快照」提示不改写当时数据。所有数字必须标注口径日期。来源：docs/standards/writing-standard-ste.md；AGENTS.md 第 351-356 行。"),

    # ============ 第三层 避坑实证（L3，imp 0.85，learning）============
    dict(id="ds-l3-01", title="假绿灯验收：四个不算通过的信号", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "verify"],
         content="build 成功、curl 200、页面有文本、run SUCCEEDED 都不是功能通过证据。验收必须断言真实网络响应与 records_count：apify_amazon_reviews_extractor 的 Store 成功率 99.8% 但实际恒 0 条。status=success 但 0 条时先取原始响应比对形状，不要反复调参数（上游响应形状漂移会静默空结果）。来源：docs/retro/；docs/playbooks/【坑点库】DIH-平台采集坑点汇总.md。"),
    dict(id="ds-l3-02", title="config-gated ≠ degraded ≠ Connection refused", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "diagnose"],
         content="三种状态处置完全不同：config-gated 是没配密钥所以没跑（不应按补密钥重试处理，也不是代码缺陷）；degraded 是跑了但失败；Connection refused 是服务没部署（不是被墙）。policy_block/config-gated 不是瞬时错误，scheduler 不会重试，策略拒绝会清空 next_run_at。来源：docs/retro/；docs/playbooks/坑点库。"),
    dict(id="ds-l3-03", title="Apify 403 判据与 inputSchema 纪律", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "apify"],
         content="Actor 2 秒内失败返回 403 是下架或拒绝本账号，不是反爬，不要加重试。Apify 入参必须以 inputSchema 为准（additionalProperties/prefill/minimum/计费上限）。禁用占位 ID（123456、MS4wLjABAAAA、自造 finder id）判断端点可用，演示值必须从上游真实结果回收。探索前先跑免额度的 Actor 存在性与 inputSchema 审计。来源：docs/apify-actors/；docs/retro/。"),
    dict(id="ds-l3-04", title="quick-collect 落库计费", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "cost"],
         content="quick-collect 没有 save_records 开关，一跑必落库并产生费用，禁止在其上做探索性批量扫描。source_type/user_tag 等元键误删会造成数据不可归因（MCP 三事故之一）。来源：docs/retro/2026-10-21-近一周复盘.md。"),
    dict(id="ds-l3-05", title="edge 502 根因与处置", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "deploy"],
         content="重启 api 后公网 502 的根因是共享网关 ai_video_nginx 缓存了 edge 旧容器 IP（固定 IP 172.20.0.16）。处置：重建 api/console 后必须 restart edge 恢复 IP 绑定；绝不重建 edge 本身或删 lighthouse_ai_video_net。来源：docs/retrospectives/2026-10-11-生产B上线复盘.md。"),
    dict(id="ds-l3-06", title=".env.production 不生效的根因", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "deploy"],
         content="生产 Compose 用显式 environment 变量列表：只改 .env.production 变量不会进容器，必须同步 configs/deploy/scrapy/docker-compose.yml 的 environment 列表，默认值漏写 :-[] 会启动失败。改完环境变量用 docker compose restart api 无效（restart 不重读 --env-file），必须 up -d --no-deps api 重建。来源：docs/retro/；provider-key-install 实战。"),
    dict(id="ds-l3-07", title="服务器 git 纪律与命令自欺", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "deploy"],
         content="服务器不用 git pull（静默 Already up to date）不用 reset --hard，用 fetch + merge --ff-only FETCH_HEAD。命令自欺三件：管道吞退出码（set -o pipefail）、部署函数内关 errexit、pgrep/pkill 自匹配（grep 自己的命令行）。来源：docs/retro/；docs/ops/。"),
    dict(id="ds-l3-08", title="中文文件写坏：尾洞与 NUL", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "engineering"],
         content="heredoc/cat >> 写中文文件会产生 NUL 字节；Write/Edit 写中文文件可能留 +4096 字节尾洞（st_size 大于可读字节，ruff 报 E902）。修法：Python 读 bytes 重写 inode 并 fsync。检测：scripts/check_file_integrity.py（--staged 用于提交前），每台机器需 git config core.hooksPath .githooks 启用钩子。ABI jsonb 拒绝 \\u0000，入库前剔除。来源：docs/retro/；scripts/check_file_integrity.py。"),
    dict(id="ds-l3-09", title="构建期烧录与国内镜像", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "build"],
         content="SCRAPY_PUBLIC_URL/NEXT_PUBLIC_API_URL 在前端构建期烧录，构建后改环境变量无效，必须重建镜像；源码硬编码域名会绕过构建参数造成跨环境串台。国内主机构建：uv.lock 绝对地址让换源失效，另有 DNS 与 corepack 子坑。来源：docs/retro/；docs/standards/。"),
    dict(id="ds-l3-10", title="worktree venv 指向与 GitNexus UNKNOWN", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "engineering"],
         content="worktree 里跑脚本可能加载另一个检出的代码：显式 PYTHONPATH=<worktree>/apps/api/src 并确认 .venv editable 指向当前检出。GitNexus impact 返回 UNKNOWN 不等于安全（调用方可能不可解析），必须再用文本搜索确认；编辑前 impact、提交前 detect-changes，partial/truncated 不算干净。来源：docs/retro/；CLAUDE.md（GitNexus 规则）。"),
    dict(id="ds-l3-11", title="坑点库是生成物", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "docs"],
         content="docs/playbooks/【坑点库】DIH-平台采集坑点汇总.md 是自动生成物，禁止手工编辑；单一真源是 apps/api/src/data_intelligence_hub/platform_packages/notes/<platform_id>.json，只改 notes JSON 后跑生成器与契约测试，改完重建 api。坑点条目固定字段 scope/target/symptom/cause/workaround/failure_class/severity/verified_at/source_ref/tags；target 必须真实存在的 endpoint_type 或 platform_id。来源：docs/playbooks/坑点库头部说明；docs/retro/。"),
    dict(id="ds-l3-12", title="ABI 生产暗坑四条", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "abi"],
         content="ABI 导出链路：①审批缺省放行（无审批记录时导出仍可执行）；②abi-export worker 未启动时任务静默排队；③上传漏记 actual_rows 导致对账缺口；④export_policy 重复行使新策略静默失效。分区/遮罩规则见 ds-l2-12。来源：docs/retro/；git commit 记录（无独立复盘文档，2026-10-29 交付）。"),
    dict(id="ds-l3-13", title="MCP 生产三事故", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "mcp"],
         content="三次生产事故：①空 Bearer token 调 /mcp/；②未知 project_id 写入；③Apify 元键误删致数据不可归因。教训：MCP 调用前校验 token 与 project 归属；元键（source_type/user_tag）是归因链一部分，禁删。来源：docs/retro/2026-10-21-近一周复盘.md。"),
    dict(id="ds-l3-14", title="回填上限与上游字段漂移", importance=0.85, unit_type="learning", when="timeless",
         labels=["pitfall", "collection"],
         content="回填的 batch_size 是单批不是总量，需配合停止条件（崩溃重试 5 次，正常退出且 0 目标才算补尽）；补采期间 DuckDB 单写，写锁期间只读日志不并行查库。金额、评分、计数字段要专门归一化（上游漂移高频区）。来源：docs/retro/；source-agent 存量记忆（评论补采系列）。"),

    # ============ 第四层 沉淀纪要（L4，imp 0.7-0.85，context，past）============
    dict(id="ds-l4-01", title="Source 项目能力画像 2026-10-31", importance=0.85, unit_type="context", when="past",
         labels=["history", "profile"],
         content="Source（Data Intelligence Hub）2026-10-31 快照：142 天、约 926 提交（推导值，来自成果报告基线 main@bfa0b4a，未经 rev-list 复核）、70 平台、双生产、55 页面（console 26 + web 29）。五层能力：采集目录（70/311/283 生产实测 2026-10-21）、双生产 A/B、双前端、VOC 洞察报告管线、治理与测试。缺口：VOC G7 后指标产出、生产 B 自动发布与全栈健康、ABI 生产验收、成本/数据规模/用户任务维度无统一看板。来源：reports/achievements-20261031/Source-项目成果总结-20261031.md（引用前核对该目录 frontmatter 基线，reports/achievements-2026-10/ 是旧版）。"),
    dict(id="ds-l4-02", title="10 月里程碑时间线", importance=0.8, unit_type="context", when="past",
         labels=["history", "milestone"],
         content="交付节奏三段停更加 10 月爆发。关键节点：10-11 生产 B 上线；10-18 双生产格局；10-19 TikTok R1（16 工具、回填 355 条、广告入库）；10-21 能力口径 70/311/283；10-28/29 deploy-p0 发布 13 次；10-29 ABI 交付（迁移链 045→050 后续至 067）；10-31 VOC 自动洞察报告管线（六档证据+禁写 FC-01..FC-12 闸门+视频层）。07/08/09 月无阶段性成果总结。时间线以 reflog 合入时刻为准。来源：成果总结 §3；docs/ops/releases.jsonl；docs/retrospectives/。"),
    dict(id="ds-l4-03", title="32 star 仓库五态结论", importance=0.85, unit_type="context", when="past",
         labels=["history", "research"],
         content="2026-10-12 调研 32 个 star 仓库分五态，硬结论：11 个「已集成」实际拿不到干净数据（契约破裂或数据降级）。旧调研文档已证伪，判定以生产 catalog 为准。调研产物在 32 仓库调研报告；3 个 Apify actor 无声下架（docs/apify-actors/）。时点提示：此后新增/下架端点未复核。来源：docs/ 32 仓库调研产物；starred-repos-analysis.md。"),
    dict(id="ds-l4-04", title="Apify 十平台选型结论", importance=0.85, unit_type="context", when="past",
         labels=["history", "research"],
         content="Apify 十平台深挖（2026-10-14）按 30 天成功率选型：主力换 harshmaur/data_xplorer 等；官方出品不等于稳定（实测淘汰案例在案）。3 actor 无声下架。账号事实：5 token 对应 2 账号，实测 8383 dataset/247k item；complex_homage 数据第 33 天仍可读；t1-t4 同账号不叠加吞吐。月检脚本用法见 docs/apify-actors/。时点提示：2026-10-14 后未复核。来源：docs/apify-actors/；apify-deep-research 记忆。"),
    dict(id="ds-l4-05", title="VOC 管线能力边界", importance=0.85, unit_type="context", when="past",
         labels=["history", "voc"],
         content="VOC 自动洞察报告管线（2026-10-31 合入）：六档证据分级、禁写闸门 FC-01..FC-12（以 voc_pipeline/spec/forbidden_conclusions.json count=12 为准，14 是提交信息旧值）、视频层。已知边界：G7 后指标产出缺口；评论分析四张表未在生产建成（历史检查点，现状需实测）；LLM 编码未达精度门槛时只输出 high 置信度。样本口径：141 条视频仅 10 条锚点确证目标商品。来源：成果总结 §4.5；voc_pipeline/spec/；git log feat/voc-report-pipeline。"),
    dict(id="ds-l4-06", title="双生产演进与发布事实", importance=0.85, unit_type="context", when="past",
         labels=["history", "deploy"],
         content="发布账本 docs/ops/releases.jsonl 15 条只记成功（失败不追加，不能当零失败证明）；2026-10-28/29 deploy-p0.sh 发布 13 次全成功、10-29 单日 12 次。生产 B（10-11 上线）自动发布仍阻塞，10-27 probe 只查了 API 容器。生产 A 当前 schema 未确认（053/056/057/067 四说）。生产切换需点名目标与镜像授权。来源：docs/ops/releases.jsonl；成果总结 §4.2；docs/【运维手册】生产环境基线.md。"),
    dict(id="ds-l4-07", title="报告资产与命名约定", importance=0.8, unit_type="context", when="past",
         labels=["history", "report"],
         content="成果报告命名 Source-项目成果总结-YYYYMMDD.md+html，目录 reports/achievements-YYYYMMDD/；launchd 每天 21:07 触发 scripts/daily-report.sh（durable job 95bf52d2，7 天过期需续期）。当前有效版本在 reports/achievements-20261031/（基线 main@bfa0b4a）；reports/achievements-2026-10/ 是旧版（基线 0e76364）勿引用。reports/ 被 .gitignore 的 /reports/ 规则忽略，入库要 git add -f。headless 运行无提交权限，提交需主会话执行。来源：成果总结 frontmatter；scripts/daily-report.sh；launchd 配置。"),
    dict(id="ds-l4-08", title="历史快照时效裁决", importance=0.8, unit_type="context", when="past",
         labels=["history", "caliber"],
         content="以下为历史快照不得当现行口径：docs/knowledge/ 四份 2026-08 调研；docs/product/README 声明该目录是历史文档（但目录内 PRD 与 Playbook 是否现行存在冲突，待产品确认，裁决前 PRD 的四态/六计数器/七槽位最多写「待确认口径」）；TODO.md 是 2026-07-23 历史状态机（current_task=uix_09_phase_f4b）；AGENTS.md 生产速查的分支与 schema 已过期；apps/scraper-console/README 页面路由已过期；2026-10-09 live sweep 100/244 是当时口径（与 providers/status 的 verified 口径不同不混用）。现行口径以能力图谱/能力总账/生产 catalog/运维手册为准。来源：docs/product/README；TODO.md；成果总结 §6。"),
    # ds-l4-09 已在 KG-01 写入（产品演进方向合并条目），此处不重复。
]

# KG-01 已迁入的存量记忆与本批主题重叠者，脚本跳过（写入前按 id 检查，不重复不覆盖）
SKIP_EXISTING_IDS = {"ds-l4-09"}


def mem_exists(mem_id: str) -> bool:
    r = subprocess.run([CLI, "--json", "memories", "show", mem_id, "--space", SPACE],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return False
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        return False
    m = d.get("memory", d)
    return bool(m.get("id"))


def add_memory(m: dict, dry: bool) -> tuple[str, str]:
    cmd = [CLI, "--json", "memories", "add", "--stdin",
           "--id", m["id"], "--title", m["title"],
           "--importance", str(m["importance"]),
           "--unit-type", m["unit_type"], "--when", m["when"],
           "--labels", ",".join(m["labels"]), "--space", SPACE]
    if dry:
        return "dry", f"{m['id']} {m['title']}"
    r = subprocess.run(cmd, input=m["content"], capture_output=True, text=True)
    if r.returncode != 0:
        return "fail", f"{m['id']}: {r.stderr.strip()[:120]}"
    try:
        d = json.loads(r.stdout)
        return ("ok", f"{m['id']} action={d.get('action')}")
    except json.JSONDecodeError:
        return "ok", f"{m['id']} (unparsed)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印待写清单，不写库")
    args = ap.parse_args()

    print(f"SPACE={SPACE}  total={len(MEMORIES)}  dry_run={args.dry_run}")
    counts = {"ok": 0, "skip": 0, "fail": 0, "dry": 0}
    for m in MEMORIES:
        if m["id"] in SKIP_EXISTING_IDS:
            print(f"  [skip-existing] {m['id']}")
            counts["skip"] += 1
            continue
        if mem_exists(m["id"]):
            print(f"  [exists-idempotent] {m['id']} (已存在，add --id 为 upsert，可安全重放；默认跳过以保幂等)")
            counts["skip"] += 1
            continue
        status, msg = add_memory(m, args.dry_run)
        print(f"  [{status}] {msg}")
        counts[status] = counts.get(status, 0) + 1
    print(f"DONE: {counts}")
    return 1 if counts.get("fail") else 0


if __name__ == "__main__":
    sys.exit(main())
