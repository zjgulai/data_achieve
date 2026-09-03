---
name: adr-004-mediacrawler-cookie-strategy
description: MediaCrawler cookies 管理策略决策。记录为何采用"手动注入 + ego-lite 长效"的分阶段方案，而非从一开始就构建自动化 cookie 刷新系统。当维护 MediaCrawler 平台 cookies、实现自动化刷新时使用。
---

# ADR-004: MediaCrawler Cookies 管理策略（手动优先，ego-lite 长效）

**状态**: 已采纳（阶段一执行中）  
**日期**: 2026-09-03  
**决策者**: lute

---

## 背景

MediaCrawler 的 11 个端点（B站/微博/知乎/快手）全部因 cookies 缺失或失效而挂起。

根本原因：
- 平台 cookies 有效期 7~30 天，不可能一次性解决
- 手动维护需要每月重复操作
- 自动化登录在无头模式下面临滑块验证码

**备选方案评估**：

| 方案 | 描述 | 工程量 | 维护成本 |
|---|---|---|---|
| A：手动注入 | 用户提供 cookie 字符串，写入 `.env.production` | 1 小时 | 每月 1 次手动更新 |
| B：ego-lite 集成 | 借用用户本地浏览器登录态，agent 自动使用 | 3-4 天 | 低（自动刷新） |
| C：代理 + 多账号轮换 | 多账号池 + IP 轮换，避免封号 | 5+ 天 | 中（账号维护） |

---

## 决策

**分阶段实施：先方案 A，后方案 B**。

**阶段一（立即）**：手动 cookie 注入
- 用户提供各平台 cookie 字符串
- 写入服务器 `/data/scrapy/configs/.env.production`
- 环境变量：`BILIBILI_COOKIES`、`WEIBO_COOKIES`、`ZHIHU_COOKIES`、`KUAISHOU_COOKIES`
- 每次失效时手动更新

**阶段二（未来）**：ego-lite 自动刷新
- 用户本地安装 ego-lite，一次性登录各平台
- Agent 通过 MCP 协议使用用户的 Chrome 登录态
- 无需手动维护 cookie

**不选方案 C 的原因**：多账号轮换需要采购多个平台账号，成本高，且目前业务量不需要。

---

## 后果

**正面**：
- 阶段一可在 1 小时内激活 MediaCrawler 的 3~11 个端点
- 阶段二实现后，运维成本接近零

**负面**：
- 阶段一需要每月手动更新 cookie（平均每平台 10 分钟）
- 知乎 cookie 有效期约 30 天，B站约 60 天

**验收标准**：
- 知乎端点：`zhihu_hot_list`、`zhihu_keyword_search`、`zhihu_question_answers` 至少 1 个返回 records > 0
- Cookie 更新 SOP：写入 `.env.production` → `docker restart data_achieve_scrapy_api`

**平台 cookie 对应的 env 变量**：
```
BILIBILI_COOKIES  → bilibili.com 登录后 Cookie 请求头内容
WEIBO_COOKIES     → weibo.com 登录后 Cookie 请求头内容
ZHIHU_COOKIES     → zhihu.com 登录后 Cookie 请求头内容
KUAISHOU_COOKIES  → kuaishou.com 登录后 Cookie 请求头内容
```
