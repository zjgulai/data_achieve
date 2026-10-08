from __future__ import annotations

import json

from data_intelligence_hub.platform_packages.models import PlatformPackage


def render_skill(package: PlatformPackage) -> str:
    endpoint_names = ", ".join(endpoint.endpoint_type for endpoint in package.endpoints[:8])
    more = max(0, package.endpoint_count - 8)
    suffix = f"，以及另外 {more} 个能力" if more else ""
    description = (
        f"{package.display_name} 数据采集 Skill，覆盖搜索、内容、账号、评论等已注册能力。"
        f"当用户要采集、查询、监测或分析 {package.display_name} 数据时使用。"
    )
    return f"""---
name: {package.platform_id}-collector
description: {description}
---

# {package.display_name} 数据采集

通过 Data Intelligence Hub 选择并调用 {package.display_name} 采集端点。

## 运行入口

- API Base URL：`https://scrapy.luteos.com`
- MCP URL：`https://scrapy.luteos.com/mcp`
- REST：`POST /api/quick-collect`

## 工作流

1. 读取 `manifest.json`，按用户目标匹配 `content_type` 和 `method`。
2. 优先选择 `verified` 能力；`disabled` 能力不得调用。
3. 向用户补齐 `required_params`，不要索取 Provider API Key。
4. 通过 MCP `collect` 或 REST `/api/quick-collect` 发起采集。
5. 返回 records、errors 和可追溯的 endpoint_type。

## 代表能力

`{endpoint_names}`{suffix}。

## 边界

- 不直接调用第三方 Provider，所有请求经过平台 collector 抽象层。
- 不把 Cookie、Token、密码或生产环境变量写入对话和文件。
- Provider 缺配置时应报告 `config-gated`，不得声称采集成功。
- 本 Skill 不负责发布、点赞、评论或修改第三方平台数据。
"""


def render_readme(package: PlatformPackage) -> str:
    summary = (
        f"该包由 Data Intelligence Hub catalog 自动生成，包含 {package.endpoint_count} "
        f"个能力视图、{package.verified_count} 个 verified 能力。"
    )
    example_payload = (
        '{{"project_id":"<project-uuid>",'
        f'"endpoint_type":"{package.endpoints[0].endpoint_type}",'
        '"params":{}}}'
    )
    return f"""# {package.display_name} Collector Skill

{summary}

## 使用

```bash
curl -X POST https://scrapy.luteos.com/api/quick-collect \\
  -H 'Content-Type: application/json' \\
  -d '{example_payload}'
```

MCP 客户端连接：`https://scrapy.luteos.com/mcp`。

详细端点与参数见 `manifest.json`，操作流程见 `references/playbook.md`。
"""


def render_playbook(package: PlatformPackage) -> str:
    rows = "\n".join(
        "| `{}` | {} | {} | {} | {} |".format(
            endpoint.endpoint_type,
            endpoint.label.replace("|", "/"),
            endpoint.method,
            endpoint.content_type,
            endpoint.status,
        )
        for endpoint in package.endpoints
    )
    description = (
        f"{package.display_name} 数据采集 Playbook，涵盖能力选择、参数准备、调用、"
        f"验收和风险边界。当执行 {package.display_name} 采集任务时使用。"
    )
    return f"""---
name: {package.platform_id}-collection-playbook
description: {description}
---

# {package.display_name} 数据采集 Playbook

## 能力概览

- 能力视图：{package.endpoint_count}
- Verified：{package.verified_count}
- Provider 组：{", ".join(package.provider_groups)}
- 采集方式：{", ".join(package.methods)}

| endpoint_type | 名称 | method | content_type | 状态 |
|---|---|---|---|---|
{rows}

## 执行步骤

1. 根据目标数据类型选择 endpoint。
2. 从 manifest 获取 required_params 和 optional_params。
3. 先用 `describe_capability` 确认参数和状态。
4. 调用 MCP `collect` 或 REST `/api/quick-collect`。
5. 验收 HTTP 状态、errors、records 数量和 source URL。

## 验收

- endpoint 必须属于本平台包。
- disabled endpoint 不得执行。
- `errors` 非空时不得把任务标记为成功。
- Provider 缺少配置时记录为 `config-gated`。

## 风险边界

- 仅采集公开或已授权数据。
- 遵守目标平台条款、频率限制和隐私要求。
- 禁止把服务端 Provider 凭据下发给 Skill/MCP 客户端。
"""


def render_trigger_cases(package: PlatformPackage) -> str:
    cases = [
        {
            "input": f"帮我采集 {package.display_name} 的公开数据",
            "should_trigger": True,
        },
        {
            "input": f"查询 {package.display_name} 上最近的内容和账号数据",
            "should_trigger": True,
        },
        {"input": "帮我写一封销售邮件", "should_trigger": False},
        {"input": "修改数据库表结构", "should_trigger": False},
    ]
    return json.dumps(cases, ensure_ascii=False, indent=2) + "\n"
