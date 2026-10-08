---
name: platform-skill-mcp-implementation-plan
description: 平台 Skill 与 MCP 分阶段实施计划，涵盖生成器、MCP、网站、测试和生产发布。当执行平台工具包建设任务时使用。
---

# Platform Skill And MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task.

**Goal:** 从现有采集 catalog 自动生成 74 个平台 Skill、74 份 Playbook、共享 MCP Runtime 和网站卡片目录。

**Architecture:** 后端 catalog 是唯一事实源。生成器产出机器可读 manifest 与 Skill/Playbook 文件；MCP 和网站均消费相同 manifest，避免能力漂移。

**Tech Stack:** Python 3.12、Pydantic v2、MCP Python SDK v2、FastAPI、Next.js 16、React 19、TypeScript、pytest、Playwright。

## Global Constraints

- endpoint 去重后必须为 250 个，平台包必须为 74 个。
- 不在生成物中写入任何 Provider 密钥。
- Provider 真实测试失败或缺配置时标记 `config-gated`，不得伪造成功。
- 保留主工作区的 TikTok CDO 未提交改动，所有实现只发生在隔离 worktree。
- UI 禁止 emoji、渐变卡片和 glassmorphism，颜色使用现有 token。

---

### Task 1: Platform Manifest Builder

**Files:**
- Create: `apps/api/src/data_intelligence_hub/platform_packages/models.py`
- Create: `apps/api/src/data_intelligence_hub/platform_packages/builder.py`
- Create: `apps/api/tests/unit/test_platform_package_builder.py`

**Produces:** `build_platform_package_catalog(catalog) -> PlatformPackageCatalog`，完成 endpoint 去重、平台聚合和 digest 计算。

- [ ] 写失败测试：278 条输入得到 250 个唯一 endpoint、74 个平台。
- [ ] 实现冻结 Pydantic 模型和确定性 builder。
- [ ] 验证未知/重复 endpoint 的归属和排序。
- [ ] 运行定向 pytest、ruff、mypy。

### Task 2: Generated Skill And Playbook Artifacts

**Files:**
- Create: `scripts/generate_platform_packages.py`
- Create: `apps/api/tests/unit/test_platform_package_generation.py`
- Generate: `generated/platform-packages.json`
- Generate: `generated/platform-skills/<platform-id>/**`
- Generate: `docs/playbooks/platforms/*.md`

**Consumes:** `build_platform_package_catalog()`。

- [ ] 写失败测试：生成目录数量、必备文件、frontmatter、密钥扫描和幂等性。
- [ ] 实现 renderer 和原子目录替换。
- [ ] 生成 74 个包与 Playbook。
- [ ] 二次生成并断言 Git 无漂移。
- [ ] 验证下载 API 生成包含五类必备文件的独立 ZIP。

### Task 3: Platform Package API

**Files:**
- Create: `apps/api/src/data_intelligence_hub/api/routes/platform_packages.py`
- Create: `apps/api/tests/integration/test_platform_package_routes.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py`

**Produces:** `GET /api/platform-packages`、`GET /api/platform-packages/{platform_id}`、`GET /api/platform-packages/{platform_id}/playbook`。

- [ ] 写路由 404、筛选、详情和 playbook 测试。
- [ ] 实现只读路由并挂载到 FastAPI。
- [ ] 验证响应 digest 与生成 manifest 一致。

### Task 4: Shared MCP Runtime

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/uv.lock`
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/server.py`
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/service.py`
- Create: `apps/api/tests/unit/test_mcp_runtime.py`
- Modify: `apps/api/src/data_intelligence_hub/core/config.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py`

**Produces:** `/mcp` Streamable HTTP 和五个稳定工具。

- [ ] 使用官方 in-memory Client 写失败测试。
- [ ] 实现 list/describe/playbook 工具。
- [ ] 通过注入的 collection service 实现 collect，不回环 HTTP。
- [ ] 实现生产 Bearer Token 门禁。
- [ ] 验证 disabled/unknown endpoint 拒绝和无 Provider side effect 的只读工具。

### Task 5: Skills Website Directory

**Files:**
- Create: `apps/scraper-console/src/lib/api/platform-packages.ts`
- Create: `apps/scraper-console/src/app/skills/page.tsx`
- Create: `apps/scraper-console/src/app/skills/[platformId]/page.tsx`
- Create: `apps/scraper-console/src/components/skills/skills-directory.tsx`
- Create: `apps/scraper-console/src/components/skills/skill-detail.tsx`
- Modify: `apps/scraper-console/src/components/layout/sidebar.tsx`

**Produces:** 可搜索、筛选、查看 Skill/MCP/Playbook 的平台目录。

- [ ] 写组件数据映射与筛选测试或纯函数测试。
- [ ] 实现卡片目录和详情页。
- [ ] 验证移动端、空状态、错误状态和键盘导航。
- [ ] 运行 `pnpm exec tsc --noEmit` 与 `pnpm build`。

### Task 6: Contract And Live Test Matrix

**Files:**
- Create: `scripts/test_platform_packages.py`
- Create: `docs/playbooks/【测试用例】DIH-平台Skill与MCP.md`
- Create: `apps/api/tests/unit/test_platform_package_contract.py`

**Produces:** 每个平台的静态结果与可选生产 smoke 报告。

- [ ] 校验 74/250 覆盖、参数 schema、Skill 文件和 Playbook 链接。
- [ ] 增加 `--base-url`、`--live`、`--platform` 和 `--output`。
- [ ] 默认只运行无副作用的 catalog/MCP list/describe 测试。
- [ ] Provider live 测试显式 opt-in，并输出 `passed/config-gated/failed/disabled`。

### Task 7: Release And Production Verification

**Files:**
- Modify: `configs/deploy/scrapy-new/docker-compose.yml`
- Modify: `README.md`

- [ ] 为生产环境配置 `SCRAPY_MCP_TOKEN`，不得提交值。
- [ ] 按模块创建原子提交并 push 功能分支。
- [ ] 在 `192.168.204.230` 保留回滚镜像，定向重建 API/Console。
- [ ] 验证 `/skills`、平台详情、API、MCP initialize/list tools、CORS 和 HTTPS。
- [ ] 抽样验证旧域名与共享网关其他站点不受影响。
