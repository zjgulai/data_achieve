from __future__ import annotations

import json

from data_intelligence_hub.platform_packages.models import CapabilityNote, PlatformPackage


def _escape(value: str) -> str:
    return value.replace("|", "/").replace("\n", " ").strip()


def _notes_table(notes: list[CapabilityNote], header: str) -> str:
    rows = "\n".join(
        "| {} | {} | {} | {} | {} | {} |".format(
            note.target,
            _escape(note.symptom),
            _escape(note.cause),
            _escape(note.workaround),
            note.severity,
            note.verified_at.isoformat() if note.verified_at else "—",
        )
        for note in notes
    )
    return (
        f"{header}\n\n"
        "| 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 |\n"
        "|---|---|---|---|---|---|\n"
        f"{rows}\n"
    )


def _collect_notes(package: PlatformPackage) -> list[CapabilityNote]:
    notes: list[CapabilityNote] = list(package.platform_notes)
    for endpoint in package.endpoints:
        notes.extend(endpoint.notes)
    return notes



def render_skill(package: PlatformPackage) -> str:
    endpoint_names = ", ".join(endpoint.endpoint_type for endpoint in package.endpoints[:8])
    more = max(0, package.endpoint_count - 8)
    suffix = f"，以及另外 {more} 个能力" if more else ""
    description = (
        f"{package.display_name} 数据采集 Skill，覆盖搜索、内容、账号、评论等已注册能力。"
        f"当用户要采集、查询、监测或分析 {package.display_name} 数据时使用。"
    )
    notes = _collect_notes(package)
    ordered_notes = sorted(notes, key=lambda n: {"blocker": 0, "warning": 1, "info": 2}[n.severity])
    skill_notes_block = ""
    if ordered_notes:
        bullets = "\n".join(
            f"- [{note.severity}] `{note.target}`：{_escape(note.symptom)} → {_escape(note.workaround)}"
            for note in ordered_notes[:8]
        )
        skill_notes_block = (
            "\n## 已知限制与坑点\n\n"
            f"{bullets}\n\n"
            "完整清单见 `references/playbook.md` 的「坑点与规避」。\n"
        )
    return f"""---
name: {package.platform_id}-collector
description: {description}
---

# {package.display_name} 数据采集

通过 Data Intelligence Hub 选择并调用 {package.display_name} 采集端点。

## 运行入口

- API Base URL：`https://scrapy.luteos.com`
- MCP URL：`https://scrapy.luteos.com/mcp/`
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
{skill_notes_block}"""


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
    note_count = len(_collect_notes(package))
    readme_notes_hint = (
        f"\n> 本平台已知 {note_count} 条坑点/限制，采集前请先阅读。\n" if note_count else ""
    )
    return f"""# {package.display_name} Collector Skill

{summary}

## 使用

```bash
curl -X POST https://scrapy.luteos.com/api/quick-collect \\
  -H 'Content-Type: application/json' \\
  -d '{example_payload}'
```

MCP 客户端连接：`https://scrapy.luteos.com/mcp/`。

发布元数据：`GET /api/platform-packages/{package.platform_id}/release`，包含版本、
catalog digest 与 ZIP SHA-256。

详细端点与参数见 `manifest.json`，操作流程见 `references/playbook.md`，
已知坑点与规避见 `references/playbook.md` 的「坑点与规避」一节。
{readme_notes_hint}"""


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
    notes = _collect_notes(package)
    notes_block = (
        "\n" + _notes_table(notes, "## 坑点与规避") + "\n"
        if notes
        else ""
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

`manifest.json` 中 `canonical_capability_id` 标识唯一可调用能力；
`is_alias_view=true` 表示该行是同一 endpoint 在其他平台或预设场景下的能力视图。
{notes_block}
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
