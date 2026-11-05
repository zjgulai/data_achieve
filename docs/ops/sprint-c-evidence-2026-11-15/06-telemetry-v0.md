# D5 · 2026-11-10(周二)telemetry v0 执行记录

交付:61df93d,CI 全绿。

## D5 #1 BotRequestLog 落库

- 迁移 `202610310069_bot_request_log.py`(revises 068):bot/channel/
  chat_id/open_id/trigger/command/argument/message_type/created_at;
  索引 created_at + command。最小 schema,**不存消息原文**(argument
  截断 200)。
- 模型 `models/bot_request_log.py`,导出进 models/__init__。
- **head pin 联动**(本仓库防呆门):新迁移必须同步 16 处 pin——
  test_migration_head_pins.py、6 个 verify-*.sh、4 个 dedicated suite、
  5 个 guard test。全部更新,pin 测试 10 条过。
- 注意区分:prod_health 测试夹具里的 `202610310068` 是模拟旧 schema
  响应的数据,不是 pin,不改。

## D5 #2 webhook 打点

- `_log_bot_request` 辅助:消息分支(命令解析后,记录 command/argument)
  与 card_action 分支(trigger=card_action、command=card:{action})。
- 失败只 warning(`shusuo_request_log_failed`),绝不阻断回复链路。
- 空 chat_id 跳过(非消息事件不记)。

## D5 #3 bot-summary 接口

- `GET /api/telemetry/bot-summary?days=30`(days 1-365):按 command/
  channel/trigger 聚合计数 + total;AuthenticatedContextDep 鉴权
  (与 /api/automation 同级)。挂载 prefix=/api/telemetry。
- 实现前 404 属预期(对抗评审已注明);D8 第二次发布后可 curl 验收。

## D5 #4 测试

- test_telemetry.py 5 条:写行/失败不抛/空 chat_id 跳过/全链路 help
  消息打点(command=help, channel=p2p)/聚合函数级验证。
- 全量 unit 3901 passed;mypy 934=934;ruff 干净;CI 7 job 绿。

## 工程注意

- **APFS 脏 inode 已常态化防御**:每次 Edit/Write 后对新文件
  rm+重写再跑 ruff(D5 全程零 E902)。
- head pin 是「有意编辑」机制:新迁移必须动 test_migration_head_pins.py
  的 CURRENT_HEAD,漏掉会被 4 层测试拦下(单测/verify 脚本/dedicated
  suite/guard)。
- 测试 fake session factory:必须是同步 callable 返回 async context
  manager(不是 async def factory——那会返回 coroutine,`async with`
  报错被打点的吞异常逻辑吃掉,表现为 0 行写入)。

## 周报口径(冻结,见计划 §6)

- 「≥10 次/周」判定:bot-summary 按 command 聚合,window=7 天,
  count≥10 视为高频候选;候选经人工确认后进常驻固化流程(12 月)。
- 首份周报:12 月首周。数据从 D8 发布(本迁移上线)后开始积累;
  飞书历史消息(im:message:readonly)获批后可回填,未批则自然积累。
