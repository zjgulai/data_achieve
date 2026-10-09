---
name: dih-platform-live-verification-plan
description: Data Intelligence Hub 平台采集分层测试计划，覆盖契约/单测/生产冒烟/全量 live 扫描/MCP/控制台/真值校验，含运行命令与通过标准。当验证采集平台可用性或回归时使用。
---

# DIH 平台采集生产实测计划

关联：[能力图谱](../architecture/【能力图谱】DIH-控制台能力地图.md) · [Skill 与 MCP 技术方案](../architecture/【技术方案】平台采集Skill与MCP目录.md) · [测试用例](./【测试用例】DIH-平台Skill与MCP.md)

## 0. 背景

平台 catalog 声明 278 条能力（266 `verified`），但生产 `GET /api/collectors/docs` 长期返回 `tested_endpoints=0`、`/api/platform-packages/providers/status` 全部 `last_test_status=null`。即 **"verified" 是静态声明，不是实测结论**。更严重的是 `platform_packages/status.py` 把"无证据、无缺失配置"的端点也判为 `verified`（本轮已修）。

本计划用分层测试把声明变成结论，并保证回归。

## 1. 分层

| 层 | 目的 | 命令 | 通过标准 |
|---|---|---|---|
| L1 契约 | 生成物与 catalog 一致、无密钥泄漏 | `cd apps/api && uv run python ../../scripts/generate_platform_packages.py --update-lock` 然后 `uv run python ../../scripts/test_platform_packages.py` | `status=passed`；74/278/250 与 lock 一致；`note_count` 与策展源相符；无真实密钥 |
| L2 单测/集成 | 回归 | `cd apps/api && uv run pytest -q` | 无**新增**失败（见 §4 基线） |
| L3 生产冒烟 | 面可用 | `curl /api/health`、`/api/collectors/catalog`、`/api/collectors/docs`、`/api/platform-packages`、`/{id}/release`、`/{id}/download`(ZIP 可解压) | 各 200；计数符合；ZIP 可解压 |
| L4 分组实测 | 逐组验证 | `python scripts/verify_platform_live.py --project-id <uuid> --group tikhub_social` | 每端点有 verdict；报告落盘 |
| L5 全量实测 | 全覆盖 | 同上去掉 `--group`，加 `--resume --concurrency 6` | 每个非 disabled 端点有 verdict |
| L6 MCP | Agent 通道 | 无 token → 401；带 token `initialize` + `tools/list` + `get_playbook` + 一次 `collect` | digest 与 REST 一致；`get_playbook` 含坑点段 |
| L7 控制台 | UI | `PLAYWRIGHT_BASE_URL=https://scrapy.luteos.com` 跑 Playwright；人工看 `/skills`、`/collector-docs`、390px 移动端 | 验证比例非零、坑点区块渲染、无横向溢出 |
| L8 真值校验 | 声明=结论 | `curl /api/collectors/docs`、`/api/platform-packages/providers/status` | `tested_endpoints>0`、逐端点 `last_test_status` 有值、无"无证据却 verified" |

## 2. 全量扫描器

`scripts/verify_platform_live.py`（与 `test_all_collectors.py` 共用 `scripts/collector_demo_params.py` 的演示参数）。

```
python scripts/verify_platform_live.py \
  --base-url https://scrapy.luteos.com \
  --project-id <demo-project-uuid> \
  [--group tikhub_social] [--only a,b] [--resume] \
  [--delay 0.3] [--concurrency 6] [--timeout 180] [--max-requests N] [--dry-run]
```

- 每端点发一次 `POST /api/quick-collect`，`label="[test] <endpoint_type>"`，使 `/api/collectors/docs` 与 `/providers/status` 反映真实结果。
- 断点续跑：`reports/live-sweep/checkpoint-*.json` 记录 `endpoint_type → failure_class`；`--resume` 跳过已 ok。
- 输出：`reports/live-sweep/<ts>.json` + `latest.json` + `latest.md`（按 failure_class 汇总）。`reports/` 已被 `.gitignore`。
- 失败分类：`ok / empty_records / config_gated / params_invalid / upstream_4xx / upstream_5xx / upstream_rate_limit / actor_failed / network_proxy / container_missing / timeout / quota_exceeded / request_error`。

### 2.1 基线与已知结果（2026-10-09）

249 唯一端点：`ok 101 / empty_records 55 / upstream_4xx 23 / config_gated 23 / params_invalid 12 / network_proxy 11 / request_error 7 / container_missing 5 / actor_failed 5 / timeout 1 / rate_limit 1`。

## 3. 失败分流与修复归属

| failure_class | 归属 | 动作 |
|---|---|---|
| config_gated | 环境 | 服务器 `.env.production` 补 key（Exa / Firecrawl / AnyCrawl / Twitter），重建 api 容器；不入库 |
| container_missing | 镜像 | 构建参数 `INSTALL_PLAYWRIGHT=true`；安装 markitdown PDF extra / browser-use；Robin 需 Tor |
| network_proxy | 基础设施 | 服务器出站代理；或改用 tikhub 替代中国站点直连 |
| upstream_4xx / actor_failed | 上游/代理 | Apify 住宅代理；核对 actor 入参 |
| params_invalid | 代码/文档 | 修 `collector_demo_params.py`；核对 catalog 参数名（曾出现文档与 catalog 漂移） |
| empty_records | 演示参数/上游 | 提升演示参数质量；仍空则按"需真实会话"标注 |
| request_error / timeout | 代码/超时 | 增大超时或限定范围 |

> 每类修复都要在对应平台的策展坑点（`platform_packages/notes/<platform>.json`）登记一条。

## 4. L2 基线（回归对照）

`deploy/scrapy-luteos-rebuild`（`9c06e27`）上 `pytest -q` = **137 failed / 1470 passed / 88 skipped**。
137 个失败为**分支既有**（主要是 workflow execution/lineage、capability governance 等与本平台无关子系统，以及需要 DB 种子/未挂载路由的用例），已存 `reports/live-sweep/baseline-pytest-failures.txt`。
回归判定：**不得出现基线之外的新失败**。

## 5. 数据污染与额度

- 每次 quick-collect 都会创建临时 `Source` + `CollectionTask` + `TaskRun`（`save_records` 字段被 `QuickCollectRequest` 忽略），失败也留孤儿行。
- 用固定 demo 项目与 `[test]` 前缀便于识别；跑完人工复核，用 `scripts/cleanup-demo-noise.sh` 清理，**不要在扫描进行中删除**。
- 额度：按 group 分批、`--delay`、`--concurrency` 适中、Apify `max_total_charge_usd`（默认 1.0）兜底。

## 6. 回归节奏

- 改 catalog / 生成器 / 坑点 → 跑 L1。
- 改 collector 实现 → 跑 L2 相关子集 + 对应 `--group` 的 L4。
- 发布前 → L3 + L6 + L7 + L8。
