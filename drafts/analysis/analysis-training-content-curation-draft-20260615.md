---
title: 培训内容情报萃取草稿
doc_type: analysis
module: operations
topic: training-content-curation
status: draft
created: 2026-06-15
updated: 2026-06-15
owner: self
source: human+ai
---

# 培训内容情报萃取草稿

## 摘要

- source snapshot: `tmp/outputs/training-content-snapshot-20260615.json`
- raw records: 44
- entities: 44
- signals: 13
- intelligence items: 14

## 情报清单

| ID | 标题 | 分类 | 证据数 | Final Score |
|---|---|---|---:|---:|
| `intel-ai-ready-crawling-stack` | AI 原生采集工具已形成独立培训模块 | `ai_agent_collection` | 3 | 0.867 |
| `intel-browser-automation-remains-core` | 浏览器自动化仍是动态页面采集的基础能力 | `browser_automation` | 4 | 0.814 |
| `intel-scrapy-remains-python-baseline` | Scrapy 仍适合作为 Python 爬虫工程基线 | `crawler_framework` | 2 | 0.723 |
| `intel-crawlee-bridges-crawler-production-patterns` | Crawlee 适合讲生产化 crawler 队列和运行抽象 | `crawler_framework` | 3 | 0.727 |
| `intel-agent-frameworks-need-tool-boundaries` | Agent 框架要先定义 tool 边界，再谈自动采集 | `ai_agent_collection` | 4 | 0.8 |
| `intel-mcp-source-connectors` | MCP 适合讲数据源工具化，而不是直接替代采集系统 | `ai_agent_collection` | 3 | 0.79 |
| `intel-github-api-first-low-risk` | GitHub 适合作为低风险 API-first 采集训练样板 | `platform_method` | 4 | 0.826 |
| `intel-official-docs-need-parser-strategy` | 官方文档采集要区分标题、正文摘要和版本线索 | `platform_method` | 3 | 0.705 |
| `intel-ecommerce-method-boundary` | 电商平台训练先讲合规方法卡，不直接讲绕过式抓取 | `platform_method` | 2 | 0.757 |
| `intel-social-collection-aggregate-only` | 社媒采集训练应聚焦聚合趋势，不暴露个人级数据 | `platform_method` | 3 | 0.785 |
| `intel-competitor-public-site-monitoring` | 竞品监控应从公开页面变化检测开始 | `platform_method` | 2 | 0.705 |
| `intel-compliance-as-first-class-intelligence` | 合规边界必须成为工作台的一等情报对象 | `compliance_boundary` | 1 | 0.865 |
| `intel-topic-map-guides-training-priority` | GitHub topic 覆盖量可用于安排培训优先级 | `github_intelligence` | 3 | 0.69 |
| `intel-raw-evidence-trail-is-training-asset` | 原始记录和 evidence trail 本身就是培训资产 | `platform_method` | 3 | 0.758 |

## 验收备注

1. 本草稿只用于审阅萃取结果，不代表生产已写库。
2. 所有“当前”判断来自快照文件中的 `last_checked_at`。
3. 高风险平台只保留方法边界，不包含绕过访问控制的操作细节。
