# D8 · 2026-11-06(周五)第二发布 + 验收 + sweep 执行记录

## D8 #1 第二次 A 发布 ✓

- e92a008 上线(迁移 069 bot_request_log + 070 audit 分区 + abi-ingest
  常驻 + 5 新 MCP 工具 + telemetry 接口 + sweep 脚本认证)。
- 账本:e92a008 success(2026-11-05T18:16:27Z);edge/网关重载正常;
  目录 312/312;abi-export、abi-ingest 双 worker running。

## D8 #2 生产验收(全部通过)✓

| 验收 | 结果 |
|---|---|
| /api/health | status ok,**schema=202610310070** |
| abi-ingest | running,心跳发布后 30 秒内(18:16:58),ABI_FERNET_KEY 配置确认 |
| T-1 backfill | schedule_state 11-04→**11-05**(两账号),ingest_job succeeded 9→**11**,按 tick 逐日推进(剩余 5 天自动补齐中) |
| 删除冒烟 audit | DELETE 200→**meta.audit_log 第一行真实落库**(abi_dataset_delete,object 与冒烟 id 一致,occurred_month=2026-11,分区生效);audit_total=1 |
| MCP 工具 | 容器内 @_tool 计数 **44**;/api/tool-catalog 284(端点契约数,口径见 §1 冻结) |

## D8 #3 live sweep(PMO 六渠道,72 端点)✓ 如实记录

- 脚本修复:verify_platform_live.py 加 `--cookie`(生产 401 是 D8 前置
  blocker);sweep 账号注册走生产(隔离冒烟账号)。
- 第一轮全 72 params_invalid:上次 sweep 的 project_id 已不存在
  ("Unknown project_id")。处理:注册账号 → 建项目(domain=social)
  → 重跑。**project_id 是易失资源,报表要存 as_of。**
- 第二轮结果(报告 live-sweep-2026-11-05.json):
  - **22/72 ok**,全部 TikHub 路径:tiktok 10、instagram 4、reddit 4、
    youtube 4;**facebook 0/7、google_trends 0/1(全 Apify 型)**
  - 失败归因(72-22=50):**Apify upstream_4xx 26 条全为 yueguz token
    月度 $199 上限**("platform-feature-disabled")——平台级配额,
    非代码问题,修复=NB 切 complex_homage token;TikHub config_gated
    15(DAPI 参数变体待补);TikHub 空结果 7(demo 参数与上游不匹配);
    rate_limit 2。
- 结论:verified(新 as_of 2026-11-05)口径=22 fresh verified;
  与旧口径 200(含 15-27 天旧证据)的差异是 TTL 机制生效的预期结果,
  不是回退。Apify 型端点的恢复依赖 token 切换(12 月第一批)。

## D8 #4 PMO 证据回写(素材就绪,用户手工执行)

- MCP 工具 39→44(Reddit 3 + YouTube 2)
- 48 表:生产实测 42 实体/54 物理(as_of 2026-11-11,见
  abi-48tables-2026-11-11.json),manifest 48 口径裁决 PASS
- verified:sweep as_of 2026-11-05,六渠道 22 fresh(分布见上)
- T-1:abi-ingest 常驻,水位 11-04→11-05+,自动推进
- audit_log:写入者生效,第一行生产审计已落
- telemetry v0:bot_request_log 建表,接口 /api/telemetry/bot-summary
- 建议 PMO 说明字段口径:「monitor v1/telemetry v0/44 工具/48 表取证/
  audit 生效,全部 as_of 2026-11-05~06;自动转常驻、Apify token 切换
  与六渠道高频固化移 12 月」

## 冲刺收口

- D1~D8 全部交付;提交链:6805048…b6fa505(26+ commits)。
- 证据目录 docs/ops/sprint-c-evidence-2026-11-15/(9 个文件)。
- 延期批次 NB-2026-11-15(§4 清单)与 12 月排期以 Plan C 为准。
