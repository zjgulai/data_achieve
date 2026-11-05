# D6 · 2026-11-11(周三)48 表取证 + ABI 常驻 执行记录

交付:342211a,CI 全绿。

## D6 #1 48 表生产取证 ✓

- 方法:SSH → docker exec psql → information_schema(生产 A db 容器)。
- 证据:`abi-48tables-2026-11-11.json`(as_of 2026-11-11)。
- 结果:ABI 三 schema 物理表 54 张 = **42 实体+母表 + 6 分区子表
  (audit_log_202610、apify_item_202609/202610/202611/202612/202701)
  + 6 upload 物理表(动态,随数据集)**。
- **口径裁决(PASS)**:manifest 的 48 = 42 实体 + 快照时点的 6 个预建
  分区;分区子表与母表同构,766 字段为实体合计。生产 42 实体与 manifest
  实体清单一致;分区按月正常滚动(202701 已建,202702 待建)。
  物理表总数是时点数,不恒等于 48——回写 PMO 时用「48(定义)」+
  「生产实测 42 实体/54 物理,as_of 2026-11-11」。

## D6 #2 abi-ingest 常驻化 ✓(代码面,D8 发布生效)

- deploy-p0.sh 第 5/7 步:`--profile abi up -d abi-export abi-ingest`;
  6/7 步增加 ingest 进程检查(非 running 即 fail)。
- compose 无需改:profiles:["abi"] 保留(防 `up -d` 误拉),deploy
  点名拉起即绕过;ABI_FERNET_KEY 已声明(队列消费读 meta.apify_token
  的加密 token,不是 env 的 APIFY_API_TOKEN)。

## D6 #3 T-1 补扫 ✓(路径变更:不手工补,常驻自动补)

- 生产水位实测:schedule_state last_target_date=11-04(两账号)、
  raw.apify_dataset modified_at=11-04 06:29、心跳 11-05 13:15。
  **缺 11-05~11-10 六天。**
- 决策:不手工 --scan-once——它不写 schedule_state(记忆已确认),
  手工补会让常驻 tick 再次入队同日期。backfill_scan_jobs(max_days=7)
  在 abi-ingest 首个 tick 自动 enqueue 全部缺失日期(6<7,一次补齐)。
- 验收挪到 D8 发布后:心跳出现 → schedule_state 前进到 11-10 →
  raw.apify_dataset 行数对账(按账号)。

## D6 #4 audit_log 写入者 + 11 月分区 ✓

- `delete_abi_dataset` 落 meta.audit_log(action=abi_dataset_delete,
  occurred_month 与 occurred_at 同月=分区键);审计失败只 warning,
  不阻断删除。D2 冒烟发现的「审计 0 行」两项根因(无写入者 + 缺 11 月
  分区)本日全部修复。
- 迁移 `202610310070_audit_log_partitions.py`:DO 块动态建当前月+2 月
  的分区,幂等;downgrade 只删这三个月的分区。
- head pin 16 处联动(069→070)。
- **postgres_abi 首次本地真跑**(一次性 PG16 容器,端口 54329,
  库名按守卫要求 abi_contract_test):43/43 passed,含新 audit 断言。
  这套测试此前在本地只能 skip(CI 也没有)——测试基础设施前进了
  一大步,值得记入 12 月批次:把这个容器化方案写进 CI。
- 队列字段名备忘:meta.ingest_job 用 state(非 status),
  meta.ingest_run 用 finished_at(非 created_at)。

## 质量门

- unit 3901 passed;mypy 934=934;ruff 干净;CI 7 job 绿(342211a)。
- deploy-p0.sh 语法检查过(--dry-run 被脏树拦截属预期,提交后可用)。

## 遗留到 D8

- 第二次发布(迁移 069+070 上生产、abi-ingest 拉起、T-1 自动补齐、
  audit_log 写入者生效)。
- 发布后生产验收四连:/api/health schema=070、abi-ingest 容器 running、
  schedule_state → 11-10、删除冒烟产生 audit 行。
