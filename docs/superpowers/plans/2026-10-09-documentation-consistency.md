---
name: documentation-consistency-plan
description: Data Intelligence Hub 文档一致性治理实施计划，涵盖生产基线、核心入口、部署运维和活跃技术文档。当产品状态或生产架构发生变化后同步文档时使用。
---

# Documentation Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让当前产品、生产环境、部署方式和能力口径在所有活跃文档中保持一致，同时保留历史文档的时间语义。

**Architecture:** 新增一份生产环境基线作为易变事实的唯一来源。README、AGENTS、API、架构和运维文档按受众引用该基线，不在历史 ADR 与执行日志中回填当前数据。

**Tech Stack:** Markdown、Bash、Docker Compose、FastAPI、Next.js。

## Global Constraints

- 当前生产域名为 `https://scrapy.luteos.com`。
- 当前生产主机为 `43.163.92.244`，登录用户为 `ubuntu`。
- 当前项目路径为 `/opt/data-achieve-scrapy/app`。
- 当前生产 Compose 为 `configs/deploy/scrapy/docker-compose.yml`。
- 能力口径不在本计划内固定，以 [生产环境基线](../../【运维手册】生产环境基线.md) 为唯一来源。
- 当前数据库 schema 为 `202607280044`。
- 历史 ADR、执行日志和阶段报告保留原始数字、域名和 revision。
- 密钥、Token、证书和 `.env.production` 内容不得写入文档。

---

### Task 1: 建立生产环境基线

- [ ] 新建带 Frontmatter 的生产环境基线文档。
- [ ] 记录主机、域名、路径、容器、网络、数据卷、能力口径和验收命令。
- [ ] 明确哪些内容属于当前事实，哪些内容应留在历史文档。

### Task 2: 更新核心入口文档

- [ ] 更新 `README.md` 的产品定位、服务拓扑、部署入口和文档导航。
- [ ] 精简 `AGENTS.md`，删除旧生产、内网迁移和重复任务状态。
- [ ] 重写 `docs/deployment-new-server.md` 为当前腾讯云生产部署说明。

### Task 3: 更新活跃技术与运维文档

- [ ] 更新 API 合同的生产 Base URL。
- [ ] 更新架构文档的 Console/API/共享网关拓扑。
- [ ] 更新发布回滚文档的路径、Compose、网关、seed 和验收口径。
- [ ] 更新平台采集手册的当前目录口径和生产调用入口。
- [ ] 更新活跃 smoke/preflight 脚本的默认域名。

### Task 4: 验证一致性

- [ ] 检查所有新增或重写 Markdown 的 Frontmatter。
- [ ] 检查核心文档链接存在。
- [ ] 扫描活跃文档中的旧域名、旧服务器和旧能力口径。
- [ ] 运行 Shell 语法检查和 Git diff 检查。
