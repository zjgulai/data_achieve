# D4 · 2026-11-09(周一)monitor v1 执行记录

交付:44cdde5(功能)+ 63c570c(修复),CI 全绿。

## 前置:PMO 回写核对

用户已完成手工回写,核对结果见 04-pmo-diff.md:
- 已落地:行 26 状态/进度(85%/进行中)、行 27-33 全部「进行中」、
  Source 能力装配 0/8、G2 64%
- 未落地:截止日期仍为 11-07~11-15(开发状态已是进行中,翻红即改期
  可视化,不阻塞);说明字段与四阶标签 D8 有 fresh 证据后一并补

## D4 #1 verified TTL(SP-65)

- `build_provider_status` 新增 `evidence_freshness` 派生字段(fresh/stale),
  VERIFIED_TTL_DAYS=14;**不改 availability 语义**——GitNexus impact
  HIGH(20 个上游符号:数说 commands.execute、/api/platform-packages、
  MCP collect、list_product_datasets_route),行为兼容优先。
- 无时间戳的 verified 证据按 stale(不可辩护即无效)。
- 单测 +4(7 passed):stale/fresh/non-verified/无时间戳。

## D4 #2 freshness 告警

- 新增 `maintenance/freshness_check.py`:72h 阈值(24h 目标+48h 宽限,
  目标可按任务 config.freshness_target_hours 覆盖);stale 任务按工作区
  聚合,给 owner/admin 发 Notification(notification_type=task_freshness)。
- 纯函数(evaluate_stale_tasks/build_report_text)单测 6 条。
- `python -m data_intelligence_hub.maintenance.freshness_check` 退出码:
  0 健康 / 1 有超期。

## D4 #3 多目标巡检(SP-43)

- `SCRAPY_HEALTH_EXTRA_TARGETS`(格式 `nameA=urlA,nameB=urlB`)注入
  额外巡检目标;每个目标独立 state 文件(stem-name 推导)与独立告警决策。
- **B 口径=监控不验收**:B 掉线要告警,但不改变 A 的退出码。
- 告警文案「生产 A 健康告警」→「采集平台健康告警」。
- 单测 +3(独立文件 test_prod_health_extra_targets.py)。

## D4 #4 控制台 /tasks 增强

- 后端已就绪(next_run_at/freshness_status/stale_hours 在 schema;
  pause/resume 端点在 tasks.py:144/156)——只缺前端。
- CollectionTask 类型补 schedule_policy/freshness_*/next_run_at 字段;
  api lib 加 pauseTask/resumeTask。
- 页面:freshness 徽章(hover 显示目标/超期小时数)、定时列下方显示
  下次运行时间、enabled/paused 行显示暂停/恢复按钮。
- tsc 干净,258 测试过。

## CI

- 44cdde5:CI failure(Ruff E902×7 + F841)——见下「工程发现」。
- 63c570c:CI 全绿(7 job),pages 绿。

## 工程发现:APFS 脏 inode 与 ruff E902(重要)

44cdde5 的 Ruff job 报 7 个文件 E902「stream did not contain valid UTF-8」,
但这些文件 Python/cat/git 读取全部正常,内容确实合法 UTF-8。定位:

- 同内容文件:stdin 模式 ruff OK、复制到 /tmp OK、树内新建副本 OK,
  仅原路径 E902。
- `stat` 显示异常:blocks 数约为 size/512 的 2-4 倍(如 5823 字节占
  24 blocks)——inode 尾部有脏页。
- 因果:凡被 Edit/Write 工具(原子写=写临时文件+rename)覆盖过的文件,
  都可能留下这种 inode;ruff(Rust)按块 mmap 读取,会碰到尾页垃圾;
  Python/cat 按声明的 size 读,所以正常。
- **修法:`rm` + 重写同内容(重建 inode)**,内容零变化。
- 已知关联:本机记忆 heredoc-file-corruption(三种假损坏/真损坏)——
  这是第四种变体:「真脏 inode,内容完好」。ruff/mypy 等按块读的
  Rust/原生工具都会中招;CI 侧不受影响(CI 文件来自 git checkout)。
- 后续:遇到本地 ruff E902 但内容合法,先 rm+重写再怀疑别的。
