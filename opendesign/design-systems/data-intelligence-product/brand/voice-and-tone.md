---
title: Data Intelligence Product Voice and Tone
status: stable
updated: 2026-07-22
---

# Voice and tone

## Default product voice

- Direct, calm and specific.
- Describe the business fact before the system detail.
- State impact and the next safe action.
- Separate fact, inference and uncertainty.

Preferred pattern:

> 采集已暂停。YouTube 凭证尚未验证，因此本次运行没有发起外部请求。你可以先完成凭证可达性检查。

Avoid:

> held / provider_call=false / credential_reachable=false

## Terminology

| Default UI | Advanced / canonical |
|---|---|
| 原始记录 | RawRecord |
| 数据版本 | DatasetVersion |
| 本地样例 | fixture |
| 配置校验值 | fingerprint |
| 已暂停，等待处理 | held |
| 已完成，但结果有缺失 | degraded |
| 有效空结果 | empty_valid |
| 外部能力 | Provider / Adapter |

## Formatting

- Chinese sentence case; no title case convention for Chinese.
- Use Arabic numerals and explicit units.
- Keep API paths, provider names, state codes and IDs unchanged in Advanced mode.
- No emoji. Avoid exclamation marks in operational feedback.
