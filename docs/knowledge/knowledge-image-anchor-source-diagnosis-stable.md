---
title: 附件图片锚点寻源诊断与价值盘点
doc_type: knowledge
module: training
topic: image-anchor-source-diagnosis
status: stable
created: 2026-06-16
updated: 2026-06-16
owner: self
source: human+ai
---

# 附件图片锚点寻源诊断与价值盘点

## 结论

6 张附件图片不能直接作为事实源。它们的正确用途是发现候选工具、传播话术和培训切入点，然后回到官方 GitHub、官网或文档核验。

本轮将 6 张图归入 `/api/toolkit.image_anchor_diagnostics`，并同步到 `/toolkit` 和 `/toolkit/course-pack`。

## 锚点归类

| 图片 | 识别对象 | 一手来源 | 分类 | 风险 | 培训价值 |
|---|---|---|---|---|---|
| 附件 1 | invisible_playwright | `https://github.com/feder-cr/invisible_playwright` | 浏览器指纹诊断 | high | 理解 Playwright 自动化暴露面和反检测宣传风险 |
| 附件 2 | CloakBrowser | `https://github.com/CloakHQ/CloakBrowser` | stealth browser runtime | high | 理解 Chromium 运行时、指纹一致性和反爬检测面 |
| 附件 3 | Nanobrowser | `https://github.com/nanobrowser/nanobrowser` | AI browser agent | medium | 训练 Chrome 扩展形态的 Agent 浏览器权限、任务轨迹和人工接管 |
| 附件 4 | Agent Reach | `https://github.com/Panniantong/Agent-Reach` | Agent 跨平台搜索 | high | 训练多平台 source adapter、字段契约和平台政策复核 |
| 附件 5 | 20 个 GitHub 工具合集 | `https://x.com/DamiDefi/article/2061398246673547296` | 工具雷达 taxonomy | medium | 训练从二次传播图回到 GitHub API 的核验流程 |
| 附件 6 | Web-Check | `https://github.com/lissy93/web-check` | OSINT 站点预检 | high | 训练采集前公开暴露面、DNS、tech stack、robots 和边界诊断 |

## 处理边界

1. anti-detect、stealth browser、bypass 等能力只作为风险识别和授权测试背景，不提供绕过验证码、登录态、访问控制或平台风控的 SOP。
2. Web-Check 只用于自有、授权或明确允许分析的站点预检；不得作为未授权侦察流程。
3. 社媒和跨平台 Agent 搜索必须先确认官方 API、公开来源、平台 ToS 和个人数据边界。
4. 二次整理图只保留发现价值；stars、license、language、updated_at 必须从 GitHub API 或官方页面核验。

## 页面同步

1. `/toolkit`：新增“附件寻源诊断”模块，展示 6 张图片的提取主张、核验来源、风险等级、价值判断、归类用途和证据链。
2. `/toolkit/course-pack`：课程包打印页同步显示图片锚点诊断，作为培训开场的“如何从传播材料回到一手源”案例。
3. 后续新增截图或社媒材料时，先补充 `image_anchor_diagnostics`，再决定是否升格为正式 source 或 intelligence。
