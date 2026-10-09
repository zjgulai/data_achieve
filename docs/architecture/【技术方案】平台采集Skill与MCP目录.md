---
name: platform-collection-skill-mcp-catalog
description: 平台采集 Skill 与 MCP 技术方案，涵盖生成架构、运行边界、测试分层和网站目录。当批量生成或维护平台采集工具包时使用。
---

# 平台采集 Skill 与 MCP 目录

## 1. 目标

把采集平台现有 catalog 自动转换为以下交付物：

- 每个用户平台一个可安装 Skill 包。
- 一个共享 MCP Runtime，通过受控工具调用现有 `/api/quick-collect`。
- 每个平台一份 Playbook。
- 网站 `/skills` 中可搜索、筛选和查看详情的卡片目录。

平台边界使用 endpoint 的 `platform` 字段。当前生产 catalog 对应 70 个平台、242 个唯一端点。`collector_type` 只作为 Provider/实现来源，不额外生成重复包。

## 2. 关键约束

- 不复制 collector 业务逻辑，Skill 和 MCP 都调用现有 API。
- 不在 Skill、Playbook、前端静态资源中写入 Provider API Key。
- 同一个 `endpoint_type` 只保留一次；重复 catalog 定义按首次出现去重。
- 生成物包含 catalog SHA-256。源 catalog 变化后，漂移测试必须失败并要求重新生成。
- 静态契约通过不等于 Provider 真实调用通过。真实调用状态分为 `verified`、`config-gated`、`disabled`。
- MCP 的写操作仅允许 catalog 中非 disabled 的端点，并复用服务端参数校验。

## 3. 架构

```mermaid
flowchart LR
    Catalog[Collector Catalog API]:::entry --> Builder[Platform Package Builder]:::entry
    Builder --> Manifest[platform-packages.json]:::store
    Builder --> Skills[70 Platform Skills]:::success
    Builder --> Playbooks[70 Playbooks]:::success
    Manifest --> MCP[Shared MCP Runtime]:::external
    Manifest --> Web[Skills Website Directory]:::external
    MCP --> Quick[/api/quick-collect]:::entry
    Quick --> Collectors[Collector Registry]:::success

    classDef entry fill:#e3f2fd,stroke:#1976d2,color:#0d47a1;
    classDef success fill:#c8e6c9,stroke:#388e3c,color:#1b5e20;
    classDef external fill:#e1bee7,stroke:#7b1fa2,color:#4a148c;
    classDef store fill:#e0f2f1,stroke:#00796b,color:#004d40;
```

### 3.1 唯一事实源

`get_collector_catalog()` 仍是能力事实源。生成器读取其序列化结果并构建 `PlatformPackageManifest`：

- `platform_id`、显示名、描述和分类。
- 去重后的 endpoint 列表。
- endpoint 所属 collector group、Provider、method、content type、参数与状态。
- Skill、Playbook、MCP 和网站详情路径。
- catalog digest 和生成版本。

### 3.2 Skill 包

本地生成目录：`generated/platform-skills/<platform-id>/`。该目录属于可再生构建产物，
不进入 Git；生产通过下载 API 按 catalog 实时生成同结构 ZIP。

每个包包含：

- `SKILL.md`：触发描述、选择端点规则、最小调用流程和排除项。
- `README.md`：安装、能力表、API/MCP 示例和故障排查。
- `references/playbook.md`：完整平台 Playbook。
- `manifest.json`：机器可读端点契约。
- `evals/trigger_cases.json`：正向与负向触发样例。

下载入口：`GET /api/platform-packages/{platform_id}/download`。

Skill 只要求 `SCRAPY_BASE_URL`，默认 `https://scrapy.luteos.com`。若服务端启用 MCP Token，则客户端另外配置 `SCRAPY_MCP_TOKEN`。

### 3.3 MCP Runtime

MCP 采用官方 Python SDK v2，挂载于现有 FastAPI 的 `/mcp`。工具保持少而稳定：

- `list_platforms(query?, status?)`
- `list_capabilities(platform_id, query?, status?)`
- `describe_capability(endpoint_type)`
- `collect(endpoint_type, params)`
- `get_playbook(platform_id)`

`collect` 直接调用现有 quick-collect 服务层，不通过公网回环请求。MCP HTTP 请求使用可选 Bearer Token；生产必须设置 `SCRAPY_MCP_TOKEN`，开发环境可关闭。

### 3.4 网站目录

新增 `/skills` 页面及 `/skills/[platformId]` 详情页。页面读取后端 `/api/platform-packages`，展示：

- 平台名称、能力数量、Provider 数量和验证比例。
- Skill 与 MCP 可用状态。
- 数据类型、采集方式和配置门禁。
- Skill 安装路径、MCP URL、JSON/curl 调用示例。
- Playbook 摘要和详情。

页面沿用现有设计 token、字母徽标和工业质感，禁止 emoji、渐变卡片和 glassmorphism。

## 4. 测试策略

### 4.1 生成器测试

- 270 条 catalog 定义去重为 242 个 endpoint。
- 70 个 platform id 生成 70 个包。
- 每个非 disabled endpoint 恰好归属一个平台包。
- 所有 required/optional params 写入 manifest。
- 生成器二次运行无 diff。

### 4.2 Skill 质量门

- Frontmatter、名称、描述、排除项完整。
- `SKILL.md` 不含密钥或 `.env.production` 内容。
- trigger cases 至少包含 2 个正向、2 个负向样例。
- Playbook 包含适用场景、端点选择、参数、调用、验收、限制和错误处理。

### 4.3 MCP 测试

- 使用官方 in-memory Client 测试工具发现与参数结构。
- list/describe/playbook 不触发 Provider 调用。
- collect 使用 fake service 验证 endpoint 与 params 传递。
- disabled/unknown endpoint 被拒绝。
- HTTP transport 无效 Token 返回未授权。

### 4.4 网站测试

- TypeScript 与 Next.js production build 通过。
- Playwright 验证列表搜索、状态筛选、详情导航、复制示例和移动端布局。
- 生产 smoke 验证 `/skills`、一个平台详情页、`/api/platform-packages` 和 `/mcp` 初始化。

## 5. 发布与回滚

1. 生成物与生成器同一提交，禁止手工修改生成目录。
2. API 和 Console 分别构建镜像并保留发布前镜像标签。
3. 仅重建 API/Console；不重建数据库和辅助采集容器。
4. MCP 通过现有 HTTPS 域名 `/mcp` 发布，不新增公网端口。
5. 回滚恢复 API/Console 镜像；生成物与代码随 Git 提交一起回滚。

## 6. 非目标

- 不为每个平台启动独立 MCP 进程。
- 不发布 70 个独立 GitHub 仓库。
- 不把 Provider 凭据下发给客户端。
- 不把 config-gated 能力声明为真实采集通过。
