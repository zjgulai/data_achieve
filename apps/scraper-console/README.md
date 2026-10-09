# scraper-console（采集控制台）

## 1. 这是什么

scraper-console 是采集平台的前端。

它使用 Next.js 16 App Router。它用 React 19。

后端 API 在 `apps/api`。

## 2. 本地运行

```bash
pnpm install
pnpm dev
```

打开 `http://localhost:3000`。

## 3. 环境变量

| 变量 | 作用 |
|---|---|
| `NEXT_PUBLIC_API_URL` | 后端 API 地址。不加时用 `http://localhost:8000`。 |

## 4. 页面

| 页面 | 路由 |
|---|---|
| 平台能力中心 | `/platforms` |
| 数据集 | `/datasets` |
| Skill 与 MCP 目录 | `/skills` |
| Skill 详情 | `/skills/[platformId]` |
| 我的项目 | `/projects` |
| 项目详情 | `/projects/[id]` |
| 运行记录 | `/runs` |
| 采集结果 | `/collect/[run_id]` |
| 采集任务 | `/tasks` |
| 采集文档 | `/collector-docs` |
| 凭证配置 | `/settings/credentials` |

## 5. 数据集页

数据集页展示全部采集数据资产。

页面提供 4 种切片方式：

1. 分类标签。分类与平台能力中心一致。
2. 平台筛选。可以多选。
3. 时间范围。有全部时段、今日、近 7 天、近 30 天。
4. 关键词搜索。

表格每行有 2 个动作：

1. 勾选。勾选多个数据集后，可以批量导出。
2. 预览。预览打开右侧抽屉。

导出有 2 个入口：

1. 批量导出。在工具栏。导出已勾选的数据集。
2. 单个导出。在预览抽屉里。导出当前版本。

预览抽屉有 3 个标签：

1. 数据预览。展示前 50 行。
2. 字段结构。展示字段名、类型、空值数。
3. 采集溯源。展示来源任务、清洗规则、版本历史。

导出支持 4 种格式：CSV、Excel、JSON、JSONL。

注意：后端同步渲染导出文件。所以导出请求返回时，`download_url` 已经可用。

## 6. 平台归因

后端从来源端点推导平台。

推导路径是：`DatasetVersion` → `TaskRun` → `CollectionTask.config.endpoint_type` → 能力目录的平台。

如果推导不到，前端按数据集名称和描述做关键词匹配。

## 7. 设计约束

1. 不使用 emoji。
2. 不使用原始十六进制颜色。颜色只用 `var(--token-name)`。
3. 不使用彩色渐变卡片和 glassmorphism。
4. 平台图标用 `PlatformLogo` 组件。

## 8. 检查

提交前运行这 3 条命令：

```bash
pnpm lint
pnpm test
pnpm build
```

`pnpm test` 运行 `src/lib` 下的单元测试。
