# D7 · 2026-11-12(周四)MCP 工具 + ADR 执行记录

交付:7364882,CI 全绿。

## D7 #1/#2 Reddit 3 + YouTube 2 MCP 工具 ✓(39→44)

- 新模块 `services/social_tools.py`,与 tiktok_tools 同构:
  `_collect`/`_result`/`_limit` 直接复用(不复制);TOOL_ENDPOINTS
  合并视图(MCP 端点白名单按它判定);`run_social_tool` 与
  `run_tiktok_tool` 同签名。
- 5 工具与端点映射:
  | 工具 | 主端点 | 备注 |
  |---|---|---|
  | reddit_search | tikhub_reddit_search | keyword 必填,接受 query 别名 |
  | reddit_subreddit_posts | tikhub_reddit_subreddit_posts | 自动剥 r/ 前缀 |
  | reddit_post_comments | tikhub_reddit_post_comments | post_id 必填 |
  | youtube_search | tikhub_youtube_search → apify_youtube_scraper | 空结果回落,run 标 superseded_by |
  | youtube_channel_videos | tikhub_youtube_channel_videos | channel_id 必填 |
- 缺参语义:metadata["*_required"] + status=empty(_result 的既有语义:
  无 records 无 errors = empty,不是 failed)。
- 注册面三处快照守卫全部联动:b5 EXPECTED_TOOLS(39→44)、
  tool_registry(count+EXPECTED set)、policies route 汇总(39→44)。
- tool_registry:SOCIAL_EXECUTE_TOOLS,per_call 扣额度,preset group
  "social"(与 "tiktok" 平行);preset 计算式自动纳入。

## D7 #3 order/sku ADR ✓

- `docs/adr/2026-11-12-order-sku-primary-data.md`,四项决策:
  - D1 主数据映射层(meta.product_order_map),不动事实表主键
  - D2 sku 规范化规则立即生效(变体后缀单列 variant 字段)
  - D3 468 品类漂移 = 对账驱动 + 显式批次改写,不自动改写
    product_catalog(漂移>5% 触发 DatasetDriftEvent)
  - D4 6 Agent 同源取数从 Echo 试点(saved_query+access_grant,
    不建实时 API)
- 落库执行在 12 月批次(NB);风险:468 清单业务 owner 未钉,NB 先钉。
- ADR 签字:待用户确认后正式生效(已按 plan 决策记录标注)。

## 质量门

- 全量 unit 3908 passed;mypy 934=934;ruff 干净;CI 7 job 绿。
- APFS 脏 inode 常态化防御执行(test_social_tools 中招一次,重建即好)。
- 一次教训:test_tool_registry 的 EXPECTED_TOOLS 是 **set**(以 `}` 收尾),
  字符串替换按 tuple 的 `)` 找没命中——快照守卫有三处,别只改一处。

## 明日 D8(冲刺最后一天)

1. 第二次 A 发布(迁移 069/070 上生产、abi-ingest 拉起、新工具生效)
2. 生产验收四连:/api/health schema=070、abi-ingest running、
   schedule_state→11-10、删除冒烟产生 audit 行
3. live sweep 补测(脚本加 --cookie/--token;yueguz token 超限用
   complex_homage;24 个无 DEMO_PARAMS 端点显式跳过)
4. PMO 证据回写(MCP 44、48 表取证、freshness、sweep 结果)
5. 成果总结上架(POST /api/ingest/report)
