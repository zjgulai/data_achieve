# PG0 Ruff 基线冻结（2026-10-22）

R0 任务 0 的 RED 基线证据。本文只记录事实，不做修复。

## 起点

- 分支：`feat/pg0-ruff-cleanup`（自 `feat/pg0-baseline-c0` 切出）
- 起始 SHA：`8a68069790d9d7c905505892be2968d90f394629`
- Worktree：`/Users/lute/Project/data_scrapy-r0`
- 依赖：`uv sync --locked --dev`（apps/api，未改锁文件）
- 命令：`uv run ruff check . --output-format json`（apps/api 内）
- 原始输出：`/tmp/r0-ruff-baseline.json`（退出码 1，即存在违规）

## 基线总量与分布

总量：**140**。规则计数：E501=124、I001=5、F401=4、SIM117=3、B905=2、E402=1、B006=1。

| 规则 | 数量 | 文件（apps/api 相对路径） |
| --- | --- | --- |
| E501 | 39 | src/data_intelligence_hub/services/collector_catalog.py |
| E501 | 25 | src/data_intelligence_hub/api/routes/collectors.py |
| E501 | 16 | src/data_intelligence_hub/collectors/pkg_community_collector.py |
| E501 | 9 | src/data_intelligence_hub/collectors/pkg_registry2_collector.py |
| E501 | 9 | tests/unit/test_tikhub_social_collector.py |
| E501 | 8 | src/data_intelligence_hub/collectors/tikhub_social.py |
| E501 | 6 | src/data_intelligence_hub/collectors/package_registry_collector.py |
| E501 | 5 | src/data_intelligence_hub/collectors/aliens_eye_collector.py |
| E501 | 4 | src/data_intelligence_hub/collectors/hackernews_collector.py |
| B905 | 2 | src/data_intelligence_hub/collectors/hackernews_collector.py |
| SIM117 | 2 | tests/unit/test_anydoc_collector.py |
| B006 | 1 | tests/unit/test_wappalyzer_collector.py |
| E402 | 1 | src/data_intelligence_hub/collectors/pkg_registry2_collector.py |
| E501 | 1 | src/data_intelligence_hub/collectors/base.py |
| E501 | 1 | src/data_intelligence_hub/collectors/robin_collector.py |
| E501 | 1 | src/data_intelligence_hub/platform_packages/renderers.py |
| F401 | 1 | tests/unit/test_anycrawl_collector.py |
| F401 | 1 | tests/unit/test_anydoc_collector.py |
| F401 | 1 | tests/unit/test_twscrape_collector.py |
| F401 | 1 | tests/unit/test_wappalyzer_collector.py |
| I001 | 1 | src/data_intelligence_hub/collectors/pkg_community_collector.py |
| I001 | 1 | tests/unit/test_anycrawl_collector.py |
| I001 | 1 | tests/unit/test_anydoc_collector.py |
| I001 | 1 | tests/unit/test_platform_package_generation.py |
| I001 | 1 | tests/unit/test_twscrape_collector.py |
| SIM117 | 1 | tests/unit/test_twscrape_collector.py |

合计 26 行（规则 × 文件），140 条违规。

## 约束

- `migration=none`：本任务不含任何数据库迁移。
- `behavior_change=forbidden`：只做 lint 修复，禁止行为变更。
