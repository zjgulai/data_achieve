---
name: collection-outbound-safety
description: 本地与服务端采集的外访策略、批准范围、请求预算及离线验收边界
---

# 采集外访安全边界

## 目的与范围

阻止项目在未批准范围内自动访问网站。策略在请求发出前检查，不以入库后的内容过滤代替。

用户报告的北京时间 20:30 外访尚未完成进程归因。本次改造针对已确认的执行控制缺口，不代表已证明告警由某个采集器产生。

本策略覆盖项目内采集入口与已接入的采集器。它不是主机防火墙，不控制独立启动的 CLI、其他应用或项目外的容器。设备侧告警应保留，不得通过关闭检测解决。

## 默认执行规则

| 执行方式 | 默认行为 |
|---|---|
| 本地开发、测试环境 | `offline`。真实采集联网被拒绝，`manual_json` 可用 |
| 生产环境 | 未显式配置时采用 `restricted`。固定 Provider API 可执行，仍受平台鉴权和额度约束 |
| 可控 HTTP | 必须有有效的服务端域名批准，逐请求执行范围与预算检查 |
| 未分类采集器 | 拒绝执行 |
| 未具备受控出口的扫描器、浏览器、sidecar | 禁止执行，不提供请求参数解锁 |

`COLLECTION_NETWORK_MODE` 只接受 `offline`、`restricted`。没有 `unrestricted` 模式。未知值导致配置校验失败。

Aliens Eye、Maigret、Sherlock、Blackbird、SpiderFoot、Robin、browser-use、Playwright，以及未接入受控 HTTP 的任意站点提取器，在本版本中保持禁止。范围以 `collectors/outbound_policy.py` 的显式分类为准。

`sites`、`--no-nsfw`、超时和返回条数不构成外访许可。恢复这些工具需要受控执行环境和出口验证，不能只增加一个布尔参数。

固定 Provider 的请求目标与云端下游目标不同。例如 Apify Actor 在云端执行采集，本机向 Apify API 提交任务。允许 API 请求不代表平台已验证云端所有下游域名或内容；仍须遵守第三方权限、额度和内容边界。

## 服务端配置

真实配置只能由运行环境的操作者维护。客户端、任务参数和来源参数不能授予外访权限。

```dotenv
COLLECTION_NETWORK_MODE=offline
COLLECTION_HTTP_GRANTS=[]
```

批准一项 HTTP 采集时，每条配置包含：

| 字段 | 含义与限制 |
|---|---|
| `collector_type` | `generic_web`、`public_feed`、`ecommerce_product_page` 或 `ecommerce_product_discovery` |
| `hosts` | 1–5 个精确主机名；不支持通配符，不隐式允许子域 |
| `expires_at` | 带时区的 ISO 8601 有效期，过期拒绝 |
| `max_requests` | 本次运行的请求尝试上限，1–50，默认 50 |
| `max_domains` | 本次运行的不同域名上限，1–5，默认 5 |
| `timeout_seconds` | 本次运行共享的时间预算，大于 0 且不超过 60 秒 |

同一 collector 必须且只能有一条有效批准配置。没有配置时拒绝，配置冲突、字段无效或已过期时也拒绝。

由于每个 collector 只能有一条配置，且 `hosts` 最多 5 个，每个 collector 类型全局最多批准 5 个主机。这条上限不会因为追加第二条配置而扩充：追加后该类型会同时匹配两条，所有请求都被拒。

因此需要超过 5 个主机的场景只能分批。做法是改同一条配置里的 `hosts`，重启 api，跑完该批任务，再换下一批。不在当前批次的主机会收到 `collection_policy_denied`。策略拒绝不是瞬时故障，scheduler 不会自动重试；换批后需由操作者显式复核。

2026-10-18 实测的待批主机数：`public_feed` 21 个，`generic_web` 7 个（其中 2 个端点在目录里标为 `disabled`，前端不放行）。两者都超过上限，无法一次全部批准。

配置通过 `COLLECTION_HTTP_GRANTS` 的 JSON 数组注入。维护者必须先核对主机和业务目的，再设置有效期。本文不提供默认站点批准，也不修改本机或生产的真实环境变量。

禁止 IP 地址、URL userinfo、非 HTTP(S)、非默认端口、`.onion`、本地主机名。大小写、尾点和 IDNA 按统一规则规范化。公网地址检查是额外的 SSRF 防护，不是色情、暴力分类器，也不代表覆盖所有 DNS 重绑定情形。

生产 Compose 使用显式环境变量列表。若后续批准部署并需启用上述配置，必须同时在 Compose 中声明对应变量；只改 `.env.production` 不会自动注入。发布和配置变更需另行批准。

## 实际请求预算

- 每次 HTTP 尝试发出前计数。失败重试同样计数。
- 自动重定向必须关闭。每一跳重新检查批准主机和公网地址。
- 在批准范围外的主机，连 DNS 查询也不应由受控请求层发起。
- 每条跳转链最多 3 跳。
- 同一运行的嵌套 Generic Web、电商详情和发现请求共享预算。
- 不通过创建新的 HTTP 客户端或内部 collector 重置预算。
- 并发请求不能共用最后一个名额；第 N+1 次尝试发出前拒绝。
- 新建受控客户端不继承环境代理。注入客户端属于服务端依赖，不能由 API 参数创建或替换。

请求上限不是结果条数。扫描超时也不是请求上限。预算用尽时不得自动降级到未受控实现。

## 手动、测试与定时任务

快速采集由服务端写入：

```json
{
  "execution_origin": "quick_collect",
  "schedule_policy": "manual_refresh_only"
}
```

该标记与 Actor 输入分开。客户端不能借 `params` 注入 cron、自动鲜度或执行来源。`[test]` 名称仅用于查询证据，不授予权限。

scheduler 排除一次性快速采集。合法的普通 cron、auto-freshness 任务保留原有调度语义，但实际执行仍检查外访策略。停用 Source 后不能继续自动执行其任务。

策略拒绝不是上游瞬时错误。scheduler 不进行普通的 15 分钟失败重试。修改批准配置后，如需恢复执行，应由操作者明确发起一次复核；不自动重跑历史任务。

历史数据不自动删除。检查历史测试任务时，先列出任务 ID、来源、cron、schedule_policy 和最近运行，再逐项决定停用。不能只按名称批量删除。

## 状态与审计

错误原因包括：

- `collection_policy_denied`：执行环境离线、执行器未受控、缺少或失效的服务端批准。
- `outbound_domain_denied`：目标地址超出批准范围。
- `outbound_budget_exceeded`：请求、域名或时间预算用尽。

`TaskRun.logs` 记录策略版本、触发来源、collector、任务/运行 ID、HTTP 请求计数和使用的批准主机。策略检查前拒绝时计数为 0；云端 Provider 的内部请求数未知，不伪造计数。

Provider 状态用 `config-gated` 表示当前策略限制，并返回 `policy_block_reason`。历史成功记录仍保留，但不能覆盖当前阻断。目录、Skill 与快速采集界面显示限制原因。

## 离线验收

只使用 SQLite、ASGITransport、MockTransport、模拟 DNS 和子进程替身。

验证重点：
1. 受限采集器直接调用和平台入口都不产生外访。
2. 伪造批准参数、改名、别名和 fallback 不能绕过。
3. 未批准跳转在下一次 DNS/HTTP 之前被拒绝。
4. 并发、重试、嵌套请求共享实际预算。
5. 快速采集次日不会重新进入 scheduler。
6. 合法离线任务、固定 Provider 模拟调用和既有解析输出保持可用。

不得为验收启动真实扫描，不得打开设备告警中的网站。

## 继续定位 20:30 告警

需要一条脱敏设备记录：日期、北京时间、进程或可执行文件路径、父进程、事件类型，以及目标域名。

先区分 DNS 查询、连接尝试和实际网页访问。若显示 Colima/Docker，需进一步定位容器；若显示浏览器或 Python，需核对父进程和当时任务。只根据站点类别不能认定为病毒，也不能认定是本项目。

相关文档：[平台能力总账](../architecture/【能力总账】DIH-平台能力现状与维护手册.md)、[生产环境基线](../【运维手册】生产环境基线.md)。
