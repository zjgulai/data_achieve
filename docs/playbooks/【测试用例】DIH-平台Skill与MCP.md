---
name: dih-platform-skill-mcp-test-cases
description: Data Intelligence Hub 平台 Skill 与 MCP 测试用例，覆盖生成契约、API、MCP、网站和生产发布。当验证平台工具包版本时使用。
---

# DIH 平台 Skill 与 MCP 测试用例

关联方案：[【技术方案】平台采集Skill与MCP目录](../architecture/【技术方案】平台采集Skill与MCP目录.md)

## 测试范围

| 用例编号 | 类型 | 标题 | 优先级 |
|---|---|---|---|
| DIH-SM-001 | 功能 | 生成-平台工具包-覆盖全部平台 | P0 |
| DIH-SM-002 | 异常 | 生成-密钥边界-阻止敏感信息 | P0 |
| DIH-SM-003 | 业务 | MCP-发现能力-返回一致目录 | P0 |
| DIH-SM-004 | 异常 | MCP-未知或停用端点-拒绝调用 | P0 |
| DIH-SM-005 | UI | 网站-Skill目录-筛选与导航成功 | P1 |
| DIH-SM-006 | UI | 网站-移动端详情-无横向溢出 | P1 |
| DIH-SM-007 | 功能 | API-Playbook详情-返回对应平台 | P1 |
| DIH-SM-008 | 异常 | 生产-MCP无Token-返回未授权 | P0 |

## DIH-SM-001 生成-平台工具包-覆盖全部平台

前置条件：后端 catalog 可导入，生成目录可写。

测试步骤：

1. 运行 `cd apps/api && uv run python ../../scripts/generate_platform_packages.py`。
2. 运行 `uv run python ../../scripts/test_platform_packages.py`。

预期结果：生成 74 个平台目录、278 个能力视图、250 个唯一 endpoint；每个目录包含 Skill、README、manifest、trigger cases 和 Playbook。

## DIH-SM-002 生成-密钥边界-阻止敏感信息

前置条件：平台包已生成。

测试步骤：运行契约测试脚本并扫描生成目录。

预期结果：不存在 `API_KEY=`、`PASSWORD=` 或私钥头；生成文件只引用 `SCRAPY_BASE_URL`、MCP URL 和占位 Token。

## DIH-SM-003 MCP-发现能力-返回一致目录

前置条件：API 已启动，MCP session manager 正常运行。

测试步骤：使用官方 MCP in-memory Client 调用 `list_platforms` 与 `describe_capability`。

预期结果：平台数量、endpoint 参数和 catalog digest 与 `/api/platform-packages` 一致，不产生采集任务。

## DIH-SM-004 MCP-未知或停用端点-拒绝调用

前置条件：MCP 可用。

测试步骤：调用不存在的 endpoint，并调用 disabled endpoint。

预期结果：分别返回 `capability_not_found` 与 `capability_disabled`，数据库不新增任务。

## DIH-SM-005 网站-Skill目录-筛选与导航成功

前置条件：Console 和 API 已启动。

测试步骤：

1. 打开 `/skills`。
2. 搜索 TikTok。
3. 选择一种 method 和 verified 状态。
4. 打开 TikTok 详情。

预期结果：卡片数量正确，详情包含 Skill、MCP、Playbook、能力清单和参数。

## DIH-SM-006 网站-移动端详情-无横向溢出

前置条件：浏览器宽度 390px。

测试步骤：打开 `/skills/tiktok` 并滚动页面。

预期结果：正文、代码块和能力参数可滚动或换行，页面主体无横向溢出。

## DIH-SM-007 API-Playbook详情-返回对应平台

前置条件：API 已启动。

测试步骤：请求 `/api/platform-packages/tiktok/playbook`。

预期结果：HTTP 200，`platform_id=tiktok`，Markdown 包含能力表、执行步骤、验收和风险边界。

## DIH-SM-008 生产-MCP无Token-返回未授权

前置条件：生产设置 `SCRAPY_MCP_TOKEN`。

测试步骤：不带 Authorization 请求 `/mcp`，再携带正确 Bearer Token 初始化 MCP。

预期结果：无 Token 返回 401；正确 Token 可以 initialize 和 list tools。
