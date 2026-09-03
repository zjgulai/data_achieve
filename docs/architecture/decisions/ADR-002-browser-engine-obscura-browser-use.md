---
name: adr-002-obscura-browser-engine
description: 浏览器引擎选型决策。记录为何选择 Obscura（Rust CDP）替换 Playwright 底层，而非直接集成 browser-use 作为主力浏览器采集方案。当调整浏览器采集基础设施、部署 Obscura 容器时使用。
---

# ADR-002: 浏览器引擎选型（Obscura 优先，browser-use 补充）

**状态**: 已采纳  
**日期**: 2026-09-03  
**决策者**: lute

---

## 背景

现有 `PlaywrightBrowserCollector` 直接启动 Chromium，存在两个问题：
1. **反检测弱**：被小红书、抖音等平台检测，成功率低
2. **资源重**：每次请求启动/关闭 Chromium，内存 200+ MB，启动 ~2s

**备选方案评估**：

| 方案 | 内存 | 反检测 | Playwright 兼容 | 工程量 |
|---|---|---|---|---|
| A：Obscura（Rust CDP） | 30 MB | ✅ 内置 | ✅ connect_over_cdp | 2 天 |
| B：browser-use（AI 驱动） | 200+ MB + LLM | ✅（AI 自适应） | 间接 | 3-4 天 |
| C：都做（A 为引擎，B 为智能层） | 按需 | ✅✅ | ✅ | 5-7 天 |
| D：暂不动 | 200+ MB | ❌ | ✅ | 0 天 |

---

## 决策

**选方案 C，分阶段实施**：

**阶段一（本批）**：集成 Obscura 作为 CDP 后端
- `PlaywrightBrowserCollector` 读取 `OBSCURA_CDP_URL` 环境变量
- 有 Obscura → `connect_over_cdp()`；无 → 降级本地 Chromium
- 新服务器 docker-compose 加 `data_achieve_scrapy_obscura` 容器

**阶段二（本批）**：新增 `BrowserUseCollector`
- 独立 `browser_use_task` 端点，接受自然语言任务描述
- 需要 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`
- 与现有 Playwright 端点并存，不替换

**不选方案 B 作为主力的原因**：browser-use 每次请求消耗 LLM token，成本不可控，不适合作为底层基础设施。

---

## 后果

**正面**：
- 现有 3 个 Playwright 端点质量提升（Obscura 内置反检测）
- 新增 1 个 AI 驱动采集端点（browser-use），支持复杂动态页面
- Playwright 代码零改动（CDP 协议兼容）

**负面**：
- Obscura 容器需要在新服务器重建镜像时自动拉取
- browser-use 依赖外部 LLM API，有 token 成本和延迟

**部署依赖**：
- `OBSCURA_CDP_URL=http://obscura:9222`（已写入 docker-compose）
- `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`（待用户配置）
