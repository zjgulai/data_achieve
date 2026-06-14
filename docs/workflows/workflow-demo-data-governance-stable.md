---
title: Demo 数据治理流程
doc_type: workflow
module: operations
topic: demo-data-governance
status: stable
created: 2026-06-14
updated: 2026-06-14
owner: self
source: human+ai
---

# Demo 数据治理流程

## 目标

Demo workspace 用来展示 Data Intelligence Hub 的最佳产品形态。它必须稳定呈现四类高质量情报：

1. `osint`：开源采集工具雷达。
2. `ecommerce`：电商采集方法库。
3. `social`：社媒热点采集方法库。
4. `competitor`：竞品网站采集哨兵。

Demo workspace 不是 E2E 沙箱，也不是生产用户工作区。任何测试运行、手动探索、调度重复执行产生的非 curated 数据，都应被识别为 demo 噪音。

## 数据分层

| 层级 | 定义 | 处理方式 |
|---|---|---|
| `curated_demo` | `demo_data.py` 用确定性 UUID 写入的演示主链路 | 保留并可重复 seed |
| `legacy_seed` | 旧版 `content`、`technology` 演示数据 | 清理 |
| `demo_runtime_noise` | demo workspace 内由调度、手动 run、旧 E2E 生成的非确定性记录 | 清理 |
| `e2e_fixture` | `e2e-` 一次性用户 workspace 下的测试数据 | 与 demo 隔离，后续可按 TTL 清理 |
| `user_generated` | 非 demo workspace 的用户数据 | 不由 demo cleanup 处理 |

## Curated Demo 白名单

白名单由 `apps/api/src/data_intelligence_hub/seed/demo_data.py` 中的确定性 ID 定义。

保留对象：

1. demo owner、workspace、workspace member。
2. 四个项目。
3. 四个 source。
4. 四个 collection task。
5. 五个 curated task run。
6. 八个 raw record。
7. 四个 entity。
8. 八个 entity snapshot。
9. 四个 signal。
10. 四个 intelligence item。
11. 四个 evidence。
12. 一个日报。
13. 三个 alert rule。
14. 三个 alert event。
15. 四个 notification。

## 噪音判定

在 demo workspace 内，以下对象属于噪音：

1. 不在 curated 白名单内的 `TaskRun`。
2. 不在 curated 白名单内的 `RawRecord`。
3. 不在 curated 白名单内的 `EntitySnapshot`。
4. 不在 curated 白名单内的 `Signal`。
5. 不在 curated 白名单内的 `IntelligenceItem`。
6. 不在 curated 白名单内的 `Report`。
7. 不在 curated 白名单内的 `AlertRule`、`AlertEvent`。
8. 不在 curated 白名单内的 `Notification`。
9. demo workspace 下所有 report subscription 和 subscription run。
10. 旧版 `content`、`technology` 项目及其依赖链。

## 防复发规则

1. Curated demo task 不设置 `schedule_cron`，避免生产 scheduler 重复运行 demo source。
2. Source config、task config、raw content、snapshot、signal metadata、evidence metadata 必须带 provenance。
3. 真实 API E2E 必须使用一次性用户，不使用 demo 账号。
4. Demo cleanup 默认 dry-run，只有显式 `--execute` 才写库。
5. Demo seed 每次执行前先清理 runtime noise，再写入 curated demo 数据。

## 操作命令

本地 dry-run：

```bash
bash scripts/cleanup-demo-noise.sh
```

本地执行：

```bash
bash scripts/cleanup-demo-noise.sh --execute
```

生产 dry-run：

```bash
SCRAPY_CLEANUP_USE_DOCKER=1 \
ENV_FILE=../.env.production \
COMPOSE_FILE=configs/deploy/scrapy/docker-compose.yml \
bash scripts/cleanup-demo-noise.sh
```

生产执行：

```bash
SCRAPY_CLEANUP_USE_DOCKER=1 \
ENV_FILE=../.env.production \
COMPOSE_FILE=configs/deploy/scrapy/docker-compose.yml \
bash scripts/cleanup-demo-noise.sh --execute
```

## 验收标准

清理后必须满足：

1. demo workspace 中 `projects=4`、`sources=4`、`collection_tasks=4`、`entities=4`。
2. demo 情报只有四条 curated 高质量情报。
3. demo 情报域为 `competitor,ecommerce,osint,social`。
4. 最新列表前四条分别覆盖开源、电商、社媒、竞品。
5. 生产真实 API E2E 仍通过。
6. 非 demo workspace 不受影响。
