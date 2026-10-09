---
name: scrapy-luteos-rebuild-plan
description: Data Intelligence Hub 全量重建实施计划，涵盖源码整合、备份、销毁、部署与验收。当 scrapy.luteos.com 需要覆盖重建时使用。
---

# Scrapy Luteos Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task.

**Goal:** 在 `43.163.92.244` 上清除旧 `data_achieve_scrapy` 实例并以空库重新部署 `scrapy.luteos.com`。

**Architecture:** 共享 `ai_video_nginx` 继续占用 80/443，通过外部网络 `lighthouse_ai_video_net` 和别名 `data_achieve_scrapy_proxy` 转发至应用 edge。应用自身容器、内部网络和 volumes 全量重建。

**Tech Stack:** FastAPI、Next.js、PostgreSQL 16、Docker Compose、Nginx。

## Global Constraints

- 不修改或重启与本项目无关的容器。
- 不删除 `lighthouse_ai_video_net` 或共享 `ai_video_nginx`。
- 旧数据库仅离线备份，不导入新环境。
- 证书、私钥、Token 和生产环境变量不得提交 Git。

- [ ] 整合远端最新源码与 CDO collector 调用链并通过测试。
- [ ] 参数化 `SCRAPY_PUBLIC_URL=https://scrapy.luteos.com` 并校验 Compose。
- [ ] 分批提交并推送生产分支。
- [ ] 备份数据库、exports、环境变量、镜像与 Compose 元数据。
- [ ] 删除旧路径、同名容器、内部网络和三个 volumes。
- [ ] 重新克隆、创建生产环境变量并以空库启动。
- [ ] 验收健康检查、能力目录、Skill/MCP、CDO、TLS 和容器隔离。
- [ ] 记录备份位置、部署 commit、验收结果和回滚命令。
