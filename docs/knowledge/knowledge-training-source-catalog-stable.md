---
title: 培训内容源目录与字段契约
doc_type: knowledge
module: operations
topic: training-source-catalog
status: stable
created: 2026-06-15
updated: 2026-06-17
owner: self
source: human+ai
---

# 培训内容源目录与字段契约

## 目标

`configs/training-content-sources.json` 是培训内容刷新的正式输入。后续采集、萃取、seed、验收都必须以该配置为准，避免把培训内容写成一次性文案。

## 数据集

培训内容统一标记为 `curated_training`。

该标记用于区分：

1. `curated_demo`：现有演示主链路。
2. `curated_training`：本轮培训内容主链路。
3. `e2e_fixture`：测试隔离数据。
4. `user_generated`：用户真实数据。

## 来源构成

| 类型 | 数量 | 用途 |
|---|---:|---|
| GitHub topic | 10 | 发现生态趋势和候选项目 |
| GitHub repo | 27 | 跟踪重点工具仓库的 stars、forks、issues、更新时间 |
| 官方文档 | 17 | 支撑方法、版本、产品能力和安装路径解释 |
| 平台方法卡 | 18 | 补足平台、RPA、no-code、预检和风险边界 SOP |

总配置 sources 为 72；2026-06-17 快照成功采集 69 条记录，3 条 GitHub topic 因上游 403 未进入本轮 seed。

## 字段契约

每个 source 必须包含：

1. `id`：稳定 ID，用于确定性 UUID 和增量更新。
2. `project_key`：所属训练项目。
3. `category`：培训内容分类。
4. `collector_type`：现有 collector 类型。
5. `config`：collector 配置。
6. `source_url`：用户可追溯来源。
7. `title`：用户可见名称。
8. `risk_level`：`low`、`medium` 或 `high`。
9. `training_use`：培训用途。
10. `content_targets`：该来源应支撑的页面或对象。

每条快照必须包含：

1. `source_id`
2. `collector_type`
3. `source_url`
4. `collected_at`
5. `status`
6. `content`

每条情报必须包含：

1. `title`
2. `category`
3. `claim`
4. `impact`
5. `recommended_action`
6. `evidence_urls`
7. `last_checked_at`

## 风险分级

| 风险 | 定义 | 本轮处理 |
|---|---|---|
| `low` | 官方 API、GitHub metadata、公开文档 | 可直接采集 |
| `medium` | 平台公开页面、社媒/电商趋势、竞品公开页、RPA/no-code 产品 | 只写方法卡和边界，不做绕过式抓取 |
| `high` | 合规边界、个人信息、登录态、访问控制、浏览器指纹和安全预检工具 | 只写治理情报、授权前提和禁止项 |

## 页面覆盖要求

配置中的 `content_contract.page_contract` 是逐页验收契约；`content_targets` 是每个 source 参与生成的对象类型。

页面必须覆盖：

1. `/dashboard`
2. `/projects`
3. `/sources`
4. `/tasks`
5. `/raw-records`
6. `/entities`
7. `/signals`
8. `/intelligence`
9. `/reports`
10. `/alerts`
11. `/notifications`

如果后续新增页面，必须先更新 `page_contract`，再补 seed 与 E2E 验收。

## 质量门槛

上线前必须满足：

1. source 不少于 60。
2. raw record 不少于 60。
3. entity 不少于 60。
4. signal 不少于 12。
5. intelligence item 不少于 16。
6. report 不少于 1。
7. 用户可见内容不得出现 `sample`、`placeholder`、`demo-`、`demo_`、`example only`、`示例`、`样本`。

## 执行约束

1. 所有“最新”判断必须来自 Phase 2 执行时快照。
2. `curated_training` 不得被 E2E 测试写入。
3. 生产无 GitHub token 时，topic search 必须小批量执行。
4. 中间快照进入 `tmp/outputs/`；单元测试依赖的稳定快照进入 `apps/api/tests/fixtures/training_content/`。
5. 高风险平台只沉淀方法、边界和风险，不提供绕过限制的操作细节。
