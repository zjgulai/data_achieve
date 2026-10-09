---
title: 控制台能力实测与坑点沉淀
doc_type: workflow
module: operations
topic: console-capability-live-verification
status: stable
created: 2026-10-09
updated: 2026-10-09
owner: self
source: human+ai
---

# 控制台能力实测与坑点沉淀

把 `scrapy.luteos.com` 的"声明能力"变成"实测结论"，并把发现的坑点沉淀进 Skill/Playbook/MCP 与控制台。
能力清单见 [能力图谱](../architecture/【能力图谱】DIH-控制台能力地图.md)，通过标准见 [测试计划](../playbooks/【测试计划】DIH-平台采集生产实测.md)。

## 前置

- 工作分支基于生产分支：`git checkout -b <branch> deploy/scrapy-luteos-rebuild`。
- 本地跑单测需要 `apps/api/.venv`（`uv sync`）与一份 Postgres：
  ```
  docker run -d --name dih-test-pg -e POSTGRES_USER=data_intel -e POSTGRES_PASSWORD=dev_password \
    -e POSTGRES_DB=data_intel -p 5432:5432 postgres:16
  cd apps/api && .venv/bin/python -m alembic upgrade head
  ```
- 需要一个 demo 项目的 UUID 作为 quick-collect 的归属：`curl <base>/api/projects | jq '.[0].id'`。

## 步骤

### 1. 枚举页面与端点

- 页面：读 `apps/scraper-console/src/app/**/page.tsx` 与 `components/layout/sidebar.tsx`，对照线上导航（含 `target=_blank` 外链）。
- 端点：`curl <base>/api/collectors/catalog`，按 `collector_type` 分组、按 `endpoint_type` 去重。

### 2. 冒烟

```
curl -fsS <base>/api/health
curl -fsS <base>/api/collectors/catalog | jq '.collectors|length'
curl -fsS <base>/api/collectors/docs | jq '{total_endpoints,tested_endpoints,success_endpoints}'
curl -fsS <base>/api/platform-packages | jq '{platform_count,capability_count,unique_endpoint_count}'
curl -fsS "<base>/api/platform-packages/tiktok/download" -o /tmp/tiktok.zip && unzip -l /tmp/tiktok.zip
```
> `/api/collectors/docs` 的 `tested_endpoints=0` 说明平台还没有任何实测记录——这正是要改的。

### 3. 全量实测

```
python scripts/verify_platform_live.py --base-url <base> --project-id <uuid> \
  --delay 0.3 --concurrency 6 --timeout 180 [--resume]
```
- 先 `--dry-run` 校端点集合与是否缺演示参数。
- 结果在 `reports/live-sweep/latest.{json,md}`；按 `failure_class` 汇总。
- 中断可加 `--resume` 续跑（已 ok 跳过）。

### 4. 分流修复

按 [测试计划 §3](../playbooks/【测试计划】DIH-平台采集生产实测.md) 的分类决定改环境/镜像/代码/文档。
**改任何函数前先评估影响面**（本项目未挂 GitNexus 时用 `grep -rn <symbol> apps/api/src` 手工枚举调用点），改完跑相关单测。

### 5. 沉淀坑点（单一事实源）

1. 在 `apps/api/src/data_intelligence_hub/platform_packages/notes/<platform_id>.json` 增/改一条：
   ```json
   {"scope":"platform|endpoint","target":"<platform_id|endpoint_type>",
    "symptom":"...","cause":"...","workaround":"...",
    "failure_class":"config_gated","severity":"blocker","verified_at":"YYYY-MM-DD",
    "source_ref":"reports/live-sweep/latest.json","tags":["..."]}
   ```
   > `target` 必须是**真实 platform_id**（例如 Exa 端点的 platform 是 `web`，不是 `exa`）。
   > 禁止写入真实密钥；占位符 `XXX_API_KEY=...` 允许。
2. 重新生成并同步 lock：
   ```
   cd apps/api && .venv/bin/python ../../scripts/generate_platform_packages.py --update-lock
   .venv/bin/python ../../scripts/test_platform_packages.py
   ```
   坑点会渲染进 `SKILL.md` / `README.md` / `references/playbook.md` / `docs/playbooks/platforms/*.md`，
   并汇总到 `docs/playbooks/【坑点库】DIH-平台采集坑点汇总.md`。

### 6. 发布

- 仅重建 api 与 console（notes 在 api 镜像内，**必须重建 api**）：
  ```
  docker compose -f configs/deploy/scrapy/docker-compose.yml build api console
  docker compose -f configs/deploy/scrapy/docker-compose.yml up -d api console
  ```
  （先按 `docs/deployment-new-server.md` 确认 `scrapy.luteos.com` 挂的是 `scrapy` 还是 `scrapy-new` 的 compose。）
- 复跑第 2 步 + `curl <base>/api/platform-packages/<id>/playbook | grep 坑点与规避` + `/skills/<id>` UI。

## 收尾

- `reports/live-sweep/` 是本地产物，不入库（已在 `.gitignore`）。
- 提交前 `git status` 确认没有 `*.key` / `*.pem` / `.env`。
- 把 §2 的 `tested_endpoints` 与 §3 的 `summary` 回填进 [能力图谱](../architecture/【能力图谱】DIH-控制台能力地图.md)。
