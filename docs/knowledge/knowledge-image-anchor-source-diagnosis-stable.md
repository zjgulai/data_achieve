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

本轮将 6 张图归入 `/api/toolkit.image_anchor_diagnostics`，并继续补充：

- `/api/toolkit.browser_labs`：浏览器解析实验室。
- `/api/toolkit.authorization_checklists`：授权采集检查清单。
- `/api/toolkit.tools[].source_credibility_*`：工具来源可信度评分。
- `/api/toolkit/preflight`：授权 URL 预检向导。

以上内容已同步到 `/toolkit` 和 `/toolkit/course-pack`。

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

## 浏览器解析实验室

| 实验 | 目标 | 风险 | 产出 |
|---|---|---|---|
| 公开暴露面预检 | 读取 robots、sitemap、headers、DNS 和技术栈线索 | medium | preflight JSON、截图、headers 快照 |
| DOM 与选择器契约 | 把页面结构转成稳定字段契约 | low | selector contract、字段样例、失败轨迹 |
| Network 与公开接口观察 | 判断是否存在官方 API 或公开接口优先路径 | medium | network log、response schema、API-first 判断 |
| 会话、Cookie 与隐私审计 | 识别登录态、storage state 和截图敏感信息 | high | 脱敏截图、storage scope、人工复核记录 |
| 浏览器指纹与反检测风险诊断 | 理解自动化检测面和高风险工具边界 | high | fingerprint diff、风险复核、禁止项说明 |

## 来源可信度评分

评分只判断来源事实是否可复核，不判断工具是否合规可用。

评分因子：

1. 来源是否指向官方 GitHub 仓库。
2. GitHub API 元数据是否完整。
3. stars 是否达到可验证社区采用度。
4. license 是否声明。
5. updated_at 与采集时间的距离。
6. issue 比例是否需要维护风险提示。

评分等级：

- `high`：可作为培训重点源，但仍需讲风险边界。
- `medium`：可进入工具雷达，课程中保留复核提示。
- `review`：只能作为候选，不直接进入 SOP。

## 授权采集检查清单

| 清单 | 用途 | 阻断条件 |
|---|---|---|
| 公开来源采集前检查 | 匿名公开页面、官方文档、公开 API | 登录、验证码、个人级字段、目的不清 |
| 账号态或登录态采集检查 | 业务授权下的自有账号、导出、后台数据 | 个人账号、未授权登录态、token 外泄、绕过限制 |
| 平台政策与 ToS 检查 | 社媒、电商、视频、内容平台 | 以绕过限制为目标、政策禁止、再使用权不明 |

## 授权 URL 预检向导

预检向导用于把“浏览器解析实验室”从课程卡升级为可执行检查。

输入条件：

1. 用户必须确认 URL 属于自有、客户授权、公开许可或明确允许分析的范围。
2. 只允许 HTTP/HTTPS 绝对 URL。
3. 禁止 localhost、私网、link-local、metadata、保留地址和带用户名密码的 URL。
4. 预检报告不持久化保存，只作为当前页面的采集前判断。

输出字段：

| 模块 | 字段 |
|---|---|
| 主文档 | requested_url、final_url、status、redirects、content-type |
| 公开声明 | robots.txt、sitemap.xml、security.txt 可读性和摘要 |
| Headers | CSP、HSTS、X-Robots-Tag、Server、Cache-Control 等白名单字段 |
| DOM | title、description、canonical、meta robots、headings、links、scripts、forms、text sample |
| Network 摘要 | redirect_count、same_origin_links、external_links、script_count、stylesheet_count、image_count、form_count |
| 授权门禁 | risk_level、allowed_to_continue、blocked_reasons、required_next_actions |

边界：

- 当前实现使用服务端 HTTP 预检和 HTMLParser，不执行页面 JS。
- 动态页面、登录态页面和含表单页面必须进入人工复核或浏览器采集实验。
- 预检不能替代平台 ToS、业务授权或法律判断。

## 页面同步

1. `/toolkit`：显示附件寻源诊断、浏览器解析实验室、授权采集检查清单、工具来源可信度评分和授权 URL 预检向导。
2. `/toolkit/course-pack`：课程包打印页同步显示图片锚点诊断、实验室和授权清单，作为培训开场的“如何从传播材料回到一手源”案例。
3. 后续新增截图或社媒材料时，先补充 `image_anchor_diagnostics`，再决定是否升格为正式 source 或 intelligence。
