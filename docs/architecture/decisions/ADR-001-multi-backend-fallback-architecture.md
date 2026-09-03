---
name: adr-001-multi-backend-fallback-architecture
description: 采集器多后端路由架构决策。记录为何选择在单个 Collector 内内置 primary+fallback 逻辑，而非引入独立路由网关层。当修改采集器路由策略、新增备选后端时使用。
---

# ADR-001: 采集器多后端路由架构（Collector-Level Fallback）

**状态**: 已采纳  
**日期**: 2026-09-03  
**决策者**: lute

---

## 背景

平台封禁和 API 限流导致单后端采集器一挂全挂。典型案例：
- B站 `yt-dlp` 被封后，MediaCrawler 11 个端点全部失效
- Playwright 被反爬检测，3 个浏览器端点成功率下降
- TikHub 订阅等级不足，10+ 端点返回 400/422

参考 Agent-Reach 项目的路由思路，需要引入 primary + fallback 机制。

**备选方案评估**：

| 方案 | 描述 | 优点 | 缺点 |
|---|---|---|---|
| A：Collector 内 fallback | 每个 Collector 类内部维护备选逻辑 | 改动最小，无新抽象 | 各 Collector 各自实现，不统一 |
| B：CollectorCatalog 路由层 | `endpoint_type → [collector_list]`，按可用性选 | 统一管理，可监控 | 需改 catalog + quick_collect 架构 |
| C：独立路由网关服务 | 单独微服务，健康检查 + 自动切换 | 最完整 | 工程量 5-7 天，当前规模不需要 |

---

## 决策

**选方案 A**：在 Collector 类内部实现 primary + fallback 逻辑。

具体实现：`PlaywrightBrowserCollector._get_browser()` 优先连接 Obscura CDP，失败时降级到本地 Chromium。

```python
async def _get_browser(self, pw: Any) -> Any:
    cdp_url = _obscura_cdp_url()
    if cdp_url:
        try:
            return await pw.chromium.connect_over_cdp(cdp_url)
        except Exception:
            pass
    return await pw.chromium.launch(**_chromium_launch_kwargs())
```

后续扩展路径：当 3 个以上 Collector 需要多后端时，升级为方案 B（CollectorCatalog 路由层）。

---

## 后果

**正面**：
- 零架构变更，现有 218 个端点不受影响
- Playwright 端点获得 Obscura 反检测能力，降级时仍可用
- 新增 Collector 可自由选择是否实现 fallback

**负面**：
- 各 Collector 各自实现，没有统一监控
- 主备切换对上层透明，故障时难以归因

**触发升级的条件**：当出现 5+ 个需要路由的 endpoint 组时，启动方案 B 改造。
