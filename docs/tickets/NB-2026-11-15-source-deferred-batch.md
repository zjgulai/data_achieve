# NB-2026-11-15 · Source 延期批次(Plan C §4)

- 状态:已建档(2026-11-06,Plan C 冲刺收口时)
- 来源:docs/plans/source-plan-c-sprint-2026-11-05.md §4 显式延期清单
- 冲刺证据:docs/ops/sprint-c-evidence-2026-11-15/(01~09)
- 排期目标:2026-11-22 起分三波,12-15 全部收口(与 PMO 改期说明一致)

## P0(11-22 前,blocker 性质)

### NB-1 · Apify token 切换(yueguz → complex_homage)✅ 已完成(2026-11-06)

- 现象:live sweep(2026-11-05)26 个 Apify 端点全部 403
  "platform-feature-disabled: You've reached your monthly usage limit of
  $199.00"——facebook 0/7、google_trends 0/1 瘫在这里。
- 执行:env 值从 meta.apify_token 加密表解密(complex_homage,在 api
  容器内完成,明文不落盘不外泄)→ 原地替换 .env.production →
  **compose force-recreate api**(docker restart 不重做变量替换,这是
  本次唯一的坑)→ 按规约 restart edge → 公网 200。
- 验收:复测 26 个 Apify 端点 → **23 ok / 3 读超时**(120s 上限内
  actor 未完成,非权限;facebook 0/7→4/7,trends 1/1)。证据:
  live-sweep-apify-after-token-switch.json。
- 遗留:①3 个超时端点下次 sweep 观察(actor 时长问题,可能需要
  --timeout 上调);②yueguz 12-01 重置后可做双 token 分摊(可选);
  ③ABI 摄取路径(meta.apify_token,4 个 complex_homage active)未动,
  与 env 同账号,无冲突。

### NB-2 · T-1 补齐确认 ✅ 已完成(2026-11-06)

- 实测:schedule_state = **2026-11-05**(两账号)= 当日北京时间的
  T-1(compute_target_date 语义:北京日期-1 天);ingest_job 全部
  succeeded(11,无 failed);心跳正常;raw.apify_dataset
  max(modified_at)= 11-05 06:10。
- 结论:backfill 已追平进入稳态,「缺 11-05~11-10 六天」的判断
  **作废**——11-05 发布当天就把水位推到了当日 T-1,不需要再补 5 天
  (此前按「每天 +1 天」外推是错的:backfill 一次 enqueue 全部缺口,
  当晚就跑完了)。
- 保留动作:无。每日稳态由 abi-ingest 常驻保证。

## P1(11-22 ~ 12-05)

### NB-3 · 六渠道高频固化(依赖 telemetry 数据积累)

- PMO 行 27-33 的 P3 准出物(Emily/Clone 抓数字段、07:05 流水线、
  频道/字幕定时任务、达人/竞品帖、社媒查询、关键词池)全部依赖
  「≥10 次/周」统计。telemetry v0 已建表,数据从 11-05 起积累,
  11-19 才有满两周窗口。
- 动作:11-19 跑首个 bot-summary 周报(格式样张见证据 06 号);
  高频候选按 command 聚合人工确认;确认后逐个固化为常驻任务。
- 前置:飞书 im:message:readonly 权限(若批下来可回填历史,窗口更早)。
- 预算:每渠道 0.5-1 人日确认+固化,合计 3-5 人日。

### NB-4 · 数说文件消息(CSV MVP → 完整版)

- 阻塞已明确(能力图谱):file_key→下载 URL 桥接未实现,且需要消息
  资源下载权限(im:message.resource:read,与只读权限是两个申请)。
- 预算:MVP 2-3;完整版(CSV 映射/预览确认/XLSX)5-7。

### NB-5 · Secret 轮换自动化 + 双环境演练

- 现状:手工脚本+runbook 在,10-24 执行过一次(SP-06);无自动周期、
  只覆盖 A。
- 预算:2-3。注意:轮换操作只从隐藏输入读值,不落仓库/报告/日志
  (ops-workflow-scope-guard)。

### NB-6 · IG / Facebook / Trends 薄 MCP 工具

- 与 NB-3 合并做:哪个渠道先出现高频请求,哪个先固化(数据驱动,
  不按日期拍)。

## P2(12-05 ~ 12-15)

### NB-7 · order_id/sku_id 落库(ADR 已签)

- 按 docs/adr/2026-11-12-order-sku-primary-data.md 执行:
  - meta.product_order_map 迁移 + ETL(4-6 人日)
  - meta.category_drift_log + 每周对账(3-4 人日)
  - 468 清单:**先钉业务 owner**(Shopify/BrandOS 侧),否则继续滑期
  - 采集层 sku 规范化规则(ADR D2)可立即生效,不等迁移

### NB-8 · Echo 同源取数试点

- ADR D4:saved_query + access_grant,不建实时 API;跑通一个完整周期
  (含一次 drift 事件演练)后才扩其余 5 个 Agent。
- 预算:5 人日。

### NB-9 · 自动 CleaningPlan / PlatformPackage promotion

- telemetry→周聚合→阈值→人工批准→promotion 端点(13-17 人日的
  完整链路)。依赖 NB-3 的两周数据。quick-collect 的
  manual_refresh_only 语义在 promotion 端点落地时一并放开。

### NB-10 · B 生产对等

- bot 独立凭证(消除 tiktok_cdo 复用 A app_id 的串线)、端点复测预算、
  B 数说配置。2-3 人日。B 已声明冻结快照,不紧急但要收口。

### NB-11 · 工程债

- postgres_abi 入 CI:D6 已验证一次性 PG16 容器方案(54329 端口、
  库名 abi_contract_test、43/43 passed),照抄进 CI service container
  + env(0.5-1 人日)。
- E2E 补齐:控制台 10 条未覆盖路由(/abi、/workbench、/reports 等);
  /workbench 的 7-8 个 404 端点(3-5 人日)。
- L2-L4 门禁接入 MCP 主路径(2-3 人日)。
- scan.py offset→keyset(保留期删除会跳数,apify-raw-warehouse 文档
  明令禁止 offset;1 人日)。
- audit_log 分区例行化:迁移 070 只建到 2027-01,每月运维脚本续建
  (或 scheduler tick 内建,0.5 人日)。
- TikTok:creator_cookie 配置、21 表行数账本、广告页签(4-6 人日)。
- Apify 阶段 1(parquet/归因/去重)+ 每周增量同步例行化(4-6 人日)。

## 本批次不做(与 Plan C §5 一致)

- 不动 48 表冻结面内既有表结构(只增 meta 两张映射表)。
- 不自动改写 product_catalog 品类。
- 不为 6 Agent 建实时查询 API。
- 不重建 B 的 edge(静态 IP)。

## 产能与顺序建议

三波:P0 一天内清掉(NB-1+NB-2);P1 按 telemetry 数据就绪度排
(NB-3 是主线);P2 按 ADR 顺序(NB-7 → NB-8,其余并行)。
总量约 25-32 人日,3 人 ~2.5 周,12-15 收口可行但无缓冲;
NB-1 拖过 11 月底则 Apify 型端点继续瘫痪(月度重置在 12-01)。
