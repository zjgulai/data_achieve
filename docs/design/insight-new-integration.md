# /insight/new 接入设计：TikTok 爆款选题分析

- 状态：设计定稿，待实现
- 日期：2026-10-31
- 范围：`apps/web` 的 `/insight/new`、`apps/api` 的 `/api/insight/*`、一份已生成的 TikTok 报告
- 不在范围：实时分析、LLM 生成、PDF 归档、跨工作区共享

## 0. 结论摘要

| 问题 | 决定 |
| --- | --- |
| 功能形态 | 方案 A：报告查看器。只展示已生成并导入的报告，不在页面内跑分析。 |
| 数据模型 | 新建 `insight_reports` 与 `insight_report_contents` 两张表，不复用 `reports` 或 `report_artifacts`。 |
| 正文格式 | HTML 是唯一成品，存数据库。Markdown 留在仓库，不进数据库。 |
| API | 4 个只读端点：分析类型、报告列表、报告详情、报告正文。v1 没有生成端点。 |
| 降级 | 查看正文不依赖数据源。数据源未连接只影响未来的生成，页面显示来源说明，不显示错误页，也不显示假的“分析中”。 |
| 导航 | 挂在 `apps/web` 的“洞察与交付”下，新增二级项“新建洞察”。不动根站 `apps/scraper-console` 的 4 个一级导航，也不动 `apps/web` 的 7 个一级项。 |
| 渲染 | 认证拉取 HTML，放进 `sandbox="allow-scripts"` 的 `iframe srcdoc`，客户端注入 CSP。不用 `dangerouslySetInnerHTML`。 |
| 新依赖 | 无。前端用原生 `fetch`/`iframe`，后端正文校验用 Python 标准库。 |

---

## 1. 决策：报告查看器，不是报告生成器

### 1.1 选择方案 A

`/insight/new` 的第一个功能是“TikTok 爆款选题分析”的**归档报告查看器**。

用户看到的是：

1. 一个分析类型：TikTok 爆款选题分析。
2. 一份已归档报告：2026-10-31 生成，数据截止 2026-10-28，288 条样本。
3. 一份明确的来源说明：报告来自本地 `abi_migtest` 快照，生产环境未接入该数据源，不能重新生成。

用户看不到：

1. “开始分析”按钮。
2. “分析中”进度。
3. 示例报告或假数据。
4. 一个点了只会报错的功能入口。

### 1.2 为什么不是方案 B

#### 生产没有这份数据

报告依赖本地 docker 容器 `abi_migtest` 的五张 raw 表。生产 ABI 库在内网，`abi` schema 是空的。方案 B 上线后，用户第一次点击就会失败。把失败包装成“数据源不可用”不是功能，只是把空页面换了一种说法。

#### 管线的数字层能重跑，成品层不能

现有脚本是 Python 标准库、单机、秒级。慢的不是计算，而是没有被脚本化的三步：

1. **取数 SQL 没有保留。** 五个 raw 表的查询、去重、392 tag × 43 天 × top20 的采样口径，只存在于文字说明里。仓库里没有任何脚本连过这个库。
2. **语义层是人工覆盖。** `theme-clusters.json` 来自 `viral-work/build.py` 的 13 个母题、993 个 theme 映射、315 条人工 `OVERRIDES`。`build_replicability.py` 把 288 个类别码按播放量降序写死，并断言 `len(CATS) == 288`。换语料必须重新标注，不能自动迁移。
3. **正文和图表是手写的。** `report.md` 781 行、`sections/*.html` 11 个、`parts/*.html` 8 个都是人工撰写；`gen_charts.py` 只做拼装，六张 SVG 的数字全是代码字面量，改 JSON 不会改图表。

即使把数据接进生产，B 也不是“加一个按钮”。它需要产品化的取数、参数化、任务队列、报告撰写和审校。这不是一周的工程量。

#### 第一次点进来，A 有东西可看

A 打开后有东西可看：一份 288 条样本、8 个章节、6 张内联 SVG、22 张表的完整报告。B 的第一屏要么是空列表，要么是转圈，最后是“数据源不可用”。

#### A 是 B 的只读子集

A 的表结构、API、页面都按“一份报告有元数据、数据范围、正文、版本”设计。B 上线时，生成器写同一张表，再加一个 `POST` 和一个运行状态接口即可。A 不是绕路，是 B 的读半边。

### 1.3 方案 B 的真实成本

| 工作 | 现状 | B 需要做什么 |
| --- | --- | --- |
| 数据接入 | 本地 docker，生产没有 | 内网 DSN、只读账号、网络策略、授权 |
| 取数 | SQL 未保留 | 重写五张表的查询、去重、采样，补时间字段 |
| 聚类 | 315 条人工覆盖、288 个写死类别 | 参数化词表、重标注、可复现的聚类流程 |
| 机制分类 | 约 600 条正则、两份重复的 `FAMILIES` | 合并词表、按品类配置、回归测试 |
| 异步 | 只有 runs/run_steps 队列 | 新增分析任务类型或专用 worker，处理重试、超时、取消 |
| 报告撰写 | 人工写正文、手写图表数字 | 结构化报告数据 + 渲染器 + 人工审校，禁止编造数字 |
| 结论 | 一周内不可交付 | 数周起步，且没有数据时仍然不可用 |

### 1.4 A 的边界

A 必须守住四条：

1. 页面不跑分析，不显示“分析中”。
2. 页面不用 `NEXT_PUBLIC_MOCK_API` 造一份报告。mock 模式只返回空状态。
3. 不显示禁用的“开始分析”按钮。按钮不存在，比灰掉的按钮诚实。
4. 正文缺失或校验失败时停止展示，不渲染半份报告。

### 1.5 一周交付计划

| 天 | 工作 | 可验收产物 |
| --- | --- | --- |
| 1 | 迁移、模型、仓储、导入校验器 | `alembic upgrade head` 通过，单测通过 |
| 2 | 服务、4 个只读路由、正文端点 | API 单测通过 |
| 3 | 报告打包、导入目标工作区 | 数据库里有 1 份可读报告 |
| 4 | `/new` 列表页、类型栏、报告卡 | 页面能打开并显示报告卡 |
| 5 | `/new/[reportId]` 详情、iframe、降级态 | 正文可读，五种降级态可复现 |
| 6 | 全量测试、lint、部署 A、导入、冒烟 | 生产 A 可只读访问 |
| 7 | 缓冲 | — |

---

## 2. 数据模型

### 2.1 为什么不复用现有表

#### `reports` 不适合

1. `report_type` 在 schema 里被锁成 `Literal["daily"]`（`apps/api/src/data_intelligence_hub/schemas/report.py:19`）。改这个类型会影响现有日报生成链路。
2. `GET /api/reports` 的响应模型 `ReportResponse` 包含完整 `content`（`schemas/report.py:54`），路由对每条报告都返回正文（`api/routes/reports.py:60`）。把 55 KB Markdown 或 182 KB HTML 塞进 `content`，报告中心列表会整体膨胀。
3. 缺字段：没有 `analysis_type`、`data_scope`、`version`、`source_status`、`content_sha256`。
4. `content` 的语义是 Markdown 日报。把 HTML 长报告塞进去，会让“报告中心”和“选题分析”两个概念混在一张表里。

#### `report_artifacts` 不适合

1. 它是 MCP 合同制报告产物表。`project_id` 非空，必须有 `template_id`、`contract_json` 和五个哈希。本报告没有合同、模板、SOP。
2. 没有 `title`、`status`、`analysis_type`、`data_scope`。
3. `report_id` 没有外键，MCP 调用也不写它（`models/report_artifact.py:49` 附近）。
4. 没有 REST 读取端点。补一个读接口意味着把 MCP 的合同表扩成通用报告表。
5. 它的迁移被标注为 source-only，未经授权不得对真实库执行（`alembic/versions/202610220059_report_artifacts.py:7`）。

#### 新建两张表

新表是纯增量，不改任何既有表。它们只服务“洞察分析报告”这一件事。未来生成器写同一张表，读 API 不变。

### 2.2 `insight_reports`

```sql
CREATE TABLE insight_reports (
    id uuid PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES workspaces(id),
    project_id uuid NULL REFERENCES projects(id),
    analysis_type varchar(40) NOT NULL,
    title varchar(300) NOT NULL,
    summary text NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'ready',
    version varchar(40) NOT NULL,
    data_scope jsonb NOT NULL,
    source_status varchar(20) NOT NULL DEFAULT 'snapshot_only',
    source_note text NULL,
    generated_at timestamptz NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid NULL REFERENCES users(id),
    CONSTRAINT uq_insight_reports_workspace_type_version
        UNIQUE (workspace_id, analysis_type, version),
    CONSTRAINT ck_insight_reports_status
        CHECK (status IN ('ready', 'withdrawn')),
    CONSTRAINT ck_insight_reports_source_status
        CHECK (source_status IN ('snapshot_only', 'connected', 'unavailable'))
);

CREATE INDEX ix_insight_reports_workspace_type_generated
    ON insight_reports (workspace_id, analysis_type, generated_at DESC);

CREATE INDEX ix_insight_reports_project
    ON insight_reports (project_id);
```

| 字段 | 说明 |
| --- | --- |
| `workspace_id` | 必填。租户隔离边界。跨工作区一律 404。 |
| `project_id` | 可空。本报告是工作区级分析，不属于某个项目。不要为了填字段造一个假项目。 |
| `analysis_type` | `tiktok_viral_topic`。v1 只接受注册表里的类型。 |
| `title` | `下周拍什么：288 条母婴爆款的选题报告`。 |
| `summary` | 一句话结论。列表卡和详情头部使用。 |
| `status` | 编辑状态：`ready` 可展示，`withdrawn` 下架。API 会再计算 `content_missing`。 |
| `version` | `2026-10-31`。与工作区、分析类型组成唯一键。内容变更必须换版本。 |
| `data_scope` | JSONB。时间窗、样本量、来源表。见 §2.4。 |
| `source_status` | `snapshot_only`（v1）、`connected`、`unavailable`。 |
| `source_note` | 人类可读的来源说明。v1 写“报告基于本地 abi_migtest 快照生成；生产环境未接入该数据源。” |
| `generated_at` | 报告生成时间，来自 manifest。 |
| `imported_at` | 入库时间。 |
| `created_by` | 导入操作人，可空。不是可见性边界。 |

**归属选择：**

- 工作区必填，因为报告是团队资产，必须按租户隔离。
- 项目可空，因为分析对象是一批数据，不是一个项目。
- 用户只记录为 `created_by`，不做个人私有。个人私有报告需要额外的可见性字段，v1 不做。
- 不建 `dataset_id` 外键。报告的数据源是本地 ABI 快照，不是工作区里已注册的数据集。强行关联会要求造一条假数据集记录。数据来源放在 `data_scope` 里。

### 2.3 `insight_report_contents`

```sql
CREATE TABLE insight_report_contents (
    report_id uuid PRIMARY KEY
        REFERENCES insight_reports(id) ON DELETE CASCADE,
    content_format varchar(10) NOT NULL DEFAULT 'html',
    content_html text NOT NULL,
    content_sha256 varchar(64) NOT NULL,
    content_bytes integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_insight_report_contents_format
        CHECK (content_format IN ('html'))
);
```

**为什么正文单独一张表：**

1. 列表和详情只查元数据，不读 `content_html`。Postgres 的 TOAST 本来就把大字段放在行外，但独立表把“列表不碰正文”变成结构约束，而不是靠每个人记得不选这一列。
2. 元数据可以存在而正文缺失。正文表没有行，就是 `content_missing`。不需要在报告表里放一个可空的 182 KB 字段。
3. 未来换存储（对象存储、PDF）时，只改正文表，报告表和 API 契约不变。

**182 KB 存 DB 合适吗：**

- 合适。Postgres 的 `text` 上限约 1 GB，超过约 2 KB 的值会 TOAST 到行外并压缩。182,450 字节对 Postgres 是小值。
- 不合适的是把 182 KB 放进列表响应。这个问题由独立表 + 不选正文列解决。
- 现有部署没有跨容器共享文件卷。`api` 和 `web` 是不同容器；`web` 的 `public/` 会打进镜像，每换一份报告要重建镜像；`api` 的本地文件没有持久卷和备份。数据库卷已经在备份范围内。
- 引入对象存储是为 182 KB 增加一套新依赖和运维面。v1 不做。
- 迁移阈值：单份正文超过 5 MB，或正文表超过约 1 GB 时，再加 `storage_kind` + `storage_ref`，把正文移到对象存储。API 的正文端点不变。

**为什么是 HTML，不是 Markdown：**

- HTML 是唯一成品。六张 SVG 图、22 张表、最终改过的正文都只在 HTML 里。
- `report.md` 是 55,510 字节的源文件，但它和 HTML 不完全一致：`sections/` 与 `parts/` 被重写过，图表也不在 Markdown 里。
- 同时存两份会产生两个事实源。v1 只存 HTML。`report.md` 留在仓库的报告包里，供维护使用，不进数据库。
- 如果以后需要全文检索，导入时从 HTML 派生一个 `plain_text` 列，不要拿 Markdown 当第二份正文。

### 2.4 `data_scope` 结构

```json
{
  "window_label": "2026-10",
  "window_end": "2026-10-28",
  "sample_size": 288,
  "sampling": "392 个 hashtag × 43 天，每个 tag 取榜单 top20",
  "source": {
    "environment": "local docker / abi_migtest",
    "database": "abitest",
    "last_write_at": "2026-10-28",
    "tables": [
      {"schema": "raw", "name": "si_tiktok_video", "rows": 31366},
      {"schema": "raw", "name": "si_tiktok_comment", "rows": 47073},
      {"schema": "raw", "name": "si_tiktok_hashtag_snapshot", "rows": 102153},
      {"schema": "raw", "name": "si_metric_snapshot", "rows": 4856},
      {"schema": "raw", "name": "si_author_video_snapshot", "rows": 904}
    ]
  }
}
```

选择 JSONB 的理由：

1. 不同分析类型的数据范围字段不同。TikTok 报告有 comment、hashtag、competitor；以后别的类型可能没有。
2. v1 只展示，不做范围筛选。JSONB 足够。
3. 导入时用 Pydantic 校验内层结构；数据库不约束内层形状。这样加字段不用迁移。

`window_label` 写“2026-10”，不编造一个精确开始日期。报告原文只写“2026-10 采集窗口、43 天、数据最后写入 2026-10-28”。`window_end` 是确定值；开始日期没有可信来源，不填。

### 2.5 状态与来源

| 字段 | 值 | 含义 |
| --- | --- | --- |
| DB `status` | `ready` | 报告元数据可用，正文已导入并通过校验 |
| DB `status` | `withdrawn` | 运营下架，列表不返回，详情 404 |
| API `status` | `ready` | 可查看 |
| API `status` | `content_missing` | 元数据在，正文表没有行 |
| API `status` | `withdrawn` | 不返回（列表隐藏，详情 404） |
| `source_status` | `snapshot_only` | 报告来自一次性快照，v1 的生产值 |
| `source_status` | `connected` | 未来：数据源已接入 |
| `source_status` | `unavailable` | 未来：来源当前不可用 |

`content_missing` 是 API 计算值，不写数据库。判断依据是 `LEFT JOIN insight_report_contents` 是否命中。

完整性失败不在元数据里预计算。列表不解压正文，不做哈希；正文端点每次读取时校验 SHA-256，不一致返回 409。这样列表保持轻，失败仍然 fail-closed。

### 2.6 导入清单与流程

报告包放在仓库里，避免 `/tmp` 丢失：

```text
tools/insight-reports/tiktok-viral-topic/2026-10-31/
  manifest.json
  report.html
  report.md          # 可编辑源，不导入
```

实现第一步是复制资产：`/tmp/viral/report.html` 与 `/tmp/viral/report.md` 进报告包；`/tmp/deepread288.tsv` 和分析脚本只用于追溯，不是运行时依赖，不进报告包。`chrome-profile/`、`pdfpages/`、PDF 副本、`report-before*.html` 都不进仓库。

`report.html` 是 182,450 字节的成品。`report.md` 是 55,510 字节的源文件。报告包只保留这两个文件和 manifest。

`manifest.json`：

```json
{
  "schema_version": "insight_report_bundle_v1",
  "analysis_type": "tiktok_viral_topic",
  "version": "2026-10-31",
  "title": "下周拍什么：288 条母婴爆款的选题报告",
  "summary": "下周优先拍产品清单、教程、身份共鸣三类常青内容；万圣节内容应从全年选题中剔除。",
  "generated_at": "2026-10-31T00:00:00Z",
  "source_status": "snapshot_only",
  "source_note": "报告基于本地 abi_migtest 快照生成；生产环境未接入该数据源。",
  "data_scope": {
    "window_label": "2026-10",
    "window_end": "2026-10-28",
    "sample_size": 288,
    "sampling": "392 个 hashtag × 43 天，每个 tag 取榜单 top20",
    "source": {
      "environment": "local docker / abi_migtest",
      "database": "abitest",
      "last_write_at": "2026-10-28",
      "tables": [
        {"schema": "raw", "name": "si_tiktok_video", "rows": 31366},
        {"schema": "raw", "name": "si_tiktok_comment", "rows": 47073},
        {"schema": "raw", "name": "si_tiktok_hashtag_snapshot", "rows": 102153},
        {"schema": "raw", "name": "si_metric_snapshot", "rows": 4856},
        {"schema": "raw", "name": "si_author_video_snapshot", "rows": 904}
      ]
    }
  },
  "content": {
    "path": "report.html",
    "format": "html",
    "source_bytes": 182450,
    "source_sha256": "415445711c9fc293d330c34cbb6a273af768348adbefe18739a4318ad31ed8d1",
    "content_bytes": 181984,
    "content_sha256": "f7f7c4f0b5483e789740345cff7c115100283b5ec1847cd181ef55e7f00b50dc",
    "normalize": [
      {"find": "/tmp/viral/", "replace": ""},
      {"find": "/tmp/deepread288.tsv", "replace": "deepread288.tsv"}
    ]
  }
}
```

这份 manifest 里的数字来自实际文件：

- 源文件 182,450 字节，SHA-256 `415445711c9fc293d330c34cbb6a273af768348adbefe18739a4318ad31ed8d1`。
- 去掉 44 处 `/tmp/...` 绝对路径后，正文 181,984 字节，SHA-256 `f7f7c4f0b5483e789740345cff7c115100283b5ec1847cd181ef55e7f00b50dc`。
- 报告有 2 段内联脚本，分别 1,762 和 1,764 字节。脚本白名单写在导入器代码里，不写在 manifest 里。manifest 不能自己授权脚本。

`schema_version` 加上文件 `bytes/sha256` 的形状，沿用现有 `tools/insight-report/ir_impl/delivery-manifest.json` 的约定（见 `tools/insight-report/ir_impl/build.py:108`）。不另造一套哈希命名。

**导入器校验顺序：**

1. 文件路径必须在报告包目录内，拒绝 `..`。
2. `source_bytes` 和 `source_sha256` 必须匹配。
3. UTF-8 必须可解码。
4. 必须包含 `<!DOCTYPE html>`、`<html`、`<head`、`<body>`。
5. 按 manifest 的 `normalize` 规则做**字面量替换**，拒绝正则。替换后不得残留 `/tmp/`。
6. 计算替换后的 `content_bytes` 和 `content_sha256`，必须匹配 manifest。
7. HTML 安全检查：
   - 拒绝 `<script src=...>`；每个内联 `<script>` 的内容哈希必须在代码白名单里。允许的两个哈希：
     - `d63f12e445a8317edc925644d31dca93c3f4107b06dc74d5fed67ce62281b56f`
     - `43158db65a7984b9ac2044505ef49ae1565e1ffb13b0271acd987d093950b4c6`
   - 拒绝 `on*=` 事件属性。
   - 拒绝 `javascript:`、`http://`、`https://`、协议相对的 `//`、`@import`、`url(http`。
   - 拒绝 `<iframe>`、`<object>`、`<embed>`、`<form>`、`<base>`、`<meta http-equiv="refresh">`。
   - 允许 `href="#..."` 锚点和 `data:image/...`。
8. Pydantic 校验 manifest 字段；`analysis_type` 必须在注册表里。
9. 一个事务写入 `insight_reports` 与 `insight_report_contents`。

**幂等与冲突：**

- `(workspace_id, analysis_type, version)` 已存在且 `content_sha256` 相同：no-op，打印“已导入”。
- 已存在但 `content_sha256` 不同：退出非零，除非显式 `--replace`。
- `--replace` 只允许在版本不变时修标题、摘要、来源说明等元数据；正文哈希必须不变。正文变更必须换 `version`。
- `--dry-run` 只校验和打印，不写库。
- 目标工作区用 `--workspace-slug` 指定；`--actor-email` 可空，用于写 `created_by`。

**命令：**

```bash
python -m data_intelligence_hub.scripts.import_insight_report \
  --bundle tools/insight-reports/tiktok-viral-topic/2026-10-31 \
  --workspace-slug <workspace-slug> \
  --dry-run
```

去掉 `--dry-run` 后写库。导入器不是 HTTP 端点，不经过 API 鉴权；它用数据库连接和工作区 slug，属于一次性运维动作。

### 2.7 迁移与上线顺序

- 新迁移：`apps/api/alembic/versions/202610310068_insight_reports.py`
- `revision = "202610310068"`
- `down_revision = "202610290067"`（当前仓库 head）
- `upgrade`：建 `insight_reports`、两个索引、`insight_report_contents`、外键。
- `downgrade`：先删正文表，再删索引，最后删报告表。
- 纯增量，不改既有表。

上线顺序：

1. 备份数据库。
2. 确认生产实际 head：`uv run alembic heads`。生产 B 可能落后多个版本；先按现有发布流程补齐到同一 head，不要跳版。
3. `uv run alembic upgrade head`。
4. 部署 API 镜像（含新路由）。
5. 运行导入器，写入 1 份报告。
6. 部署 Web 镜像（含新页面和导航）。
7. 冒烟：列表、详情、正文、下载、五个降级态。

如果 Web 先上线，页面会对 `/api/insight/*` 得到 404，显示“无法连接服务器”。所以 API 必须先于 Web。

---

## 3. API 契约

### 3.1 通用约定

- 前缀：`/api/insight`。它与前端 basePath `/insight` 不冲突：前者是 API 服务路径，后者是 Next 路由前缀。
- 鉴权：读接口用 `get_auth_context`，与 `/api/reports` 一致。开发环境可以回退 demo；生产 `effective_demo_mode` 为假，fail-closed。
- 工作区：所有查询都带 `workspace_id = context.workspace.id`。跨工作区返回 404，不返回 403，避免泄露存在性。
- 错误信封：`{"detail": "人类可读文案", "code": "稳定错误码"}`。`x-request-id` 响应头沿用现有约定。
- 时间：ISO 8601 UTC，带 `Z`。
- ID：UUID 字符串。
- 列表默认 `limit=20`，最大 50。排序 `generated_at DESC, id DESC`。
- 正文永远不出现在列表和详情 JSON 里。只有 `/content` 返回正文。
- 本模块不接 `NEXT_PUBLIC_MOCK_API` 的假数据分支。mock 模式返回空状态，见 §4.9。

**端点清单：**

| Method | Path | 请求 | 成功响应 | 主要错误 |
| --- | --- | --- | --- | --- |
| GET | `/api/insight/analysis-types` | 无 | 200 JSON，分析类型与计数 | 401、500 |
| GET | `/api/insight/reports` | `analysis_type?`、`project_id?`、`limit?`、`cursor?` | 200 JSON，报告元数据列表 | 401、422、500 |
| GET | `/api/insight/reports/{report_id}` | 无 | 200 JSON，单份报告元数据 | 401、404、422、500 |
| GET | `/api/insight/reports/{report_id}/content` | `download?` | 200 `text/html` | 401、404、409、500 |

v1 没有 `POST`、`PUT`、`PATCH`、`DELETE`。生成端点留到方案 B，见 §3.7。

### 3.2 `GET /api/insight/analysis-types`

返回服务端注册的分析类型，以及当前工作区的报告计数。

**响应 200：**

```json
{
  "items": [
    {
      "key": "tiktok_viral_topic",
      "name": "TikTok 爆款选题分析",
      "description": "对已爆母婴与喂养视频做主题、吸引机制、可复刻性和评论需求分析。",
      "report_count": 1,
      "latest_report_at": "2026-10-31T00:00:00Z",
      "generation": {
        "available": false,
        "reason_code": "source_not_connected",
        "reason": "数据源未连接，无法生成新报告。当前只能查看归档报告。"
      }
    }
  ]
}
```

说明：

- 类型来自代码里的注册表，不建表。当前只有一个类型，没有管理界面，也没有按工作区启停的需求。超过 3 个类型或需要按工作区配置时，再加表。
- `report_count` 统计未下架的报告，包括 `content_missing`。正文缺失的报告仍然要出现在列表里，让用户知道它存在。
- 没有报告时，`report_count=0`，`latest_report_at=null`，类型仍然返回。
- `generation.available` 在 v1 恒为 `false`。`reason_code` 用 `source_not_connected`。这是产品声明，不是实时探测：它描述“这份报告的数据源没有接入生产”，不声称此刻的网络状态。
- 不要在 UI 里把它渲染成红灯错误。它是已知边界，用中性说明。

### 3.3 `GET /api/insight/reports`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `analysis_type` | string | 否 | 例如 `tiktok_viral_topic`。未知类型返回空列表，不报 404。 |
| `project_id` | uuid | 否 | 项目级报告过滤。工作区级报告（`project_id IS NULL`）始终包含。 |
| `limit` | int | 否 | 1..50，默认 20。 |
| `cursor` | string | 否 | 不透明游标。非法游标返回 422。 |

**响应 200：**

```json
{
  "items": [
    {
      "id": "0f7d9c2e-5a1b-4c3d-8e9f-1a2b3c4d5e6f",
      "analysis_type": "tiktok_viral_topic",
      "title": "下周拍什么：288 条母婴爆款的选题报告",
      "summary": "下周优先拍产品清单、教程、身份共鸣三类常青内容；万圣节内容应从全年选题中剔除。",
      "status": "ready",
      "version": "2026-10-31",
      "data_scope": {
        "window_label": "2026-10",
        "window_end": "2026-10-28",
        "sample_size": 288,
        "sampling": "392 个 hashtag × 43 天，每个 tag 取榜单 top20",
        "source": {
          "environment": "local docker / abi_migtest",
          "database": "abitest",
          "last_write_at": "2026-10-28",
          "tables": [
            {"schema": "raw", "name": "si_tiktok_video", "rows": 31366},
            {"schema": "raw", "name": "si_tiktok_comment", "rows": 47073},
            {"schema": "raw", "name": "si_tiktok_hashtag_snapshot", "rows": 102153},
            {"schema": "raw", "name": "si_metric_snapshot", "rows": 4856},
            {"schema": "raw", "name": "si_author_video_snapshot", "rows": 904}
          ]
        }
      },
      "source_status": "snapshot_only",
      "source_note": "报告基于本地 abi_migtest 快照生成；生产环境未接入该数据源。",
      "generated_at": "2026-10-31T00:00:00Z",
      "imported_at": "2026-10-31T10:00:00Z",
      "created_by": null,
      "has_content": true,
      "content_format": "html",
      "content_bytes": 181984,
      "content_sha256": "f7f7c4f0b5483e789740345cff7c115100283b5ec1847cd181ef55e7f00b50dc"
    }
  ],
  "next_cursor": null
}
```

说明：

- `status=withdrawn` 的行不返回。`content_missing` 会返回，前端显示“正文缺失”。
- `has_content=false` 时，`content_format`、`content_bytes`、`content_sha256` 为 `null`。
- `next_cursor` 是 `(generated_at, id)` 的 base64url 编码；没有更多时为 `null`。
- 列表不返回 `content_html`。这是契约，不是实现细节。
- 没有报告时返回 `{"items": [], "next_cursor": null}`，HTTP 200。空不是错误。

### 3.4 `GET /api/insight/reports/{report_id}`

返回与列表项相同的对象。没有正文。

错误：

- 报告不存在、跨工作区、已下架：404 `insight_report_not_found`。
- 正文缺失：200，`status=content_missing`，`has_content=false`。详情页仍要显示元数据，并在正文区显示 fail-closed 面板。
- 非法 UUID：422 `validation_error`。

### 3.5 `GET /api/insight/reports/{report_id}/content`

返回存储的 HTML 正文。

**响应 200：**

- `Content-Type: text/html; charset=utf-8`
- `Content-Length: 181984`
- `Content-Security-Policy: sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; script-src 'none'; base-uri 'none'; form-action 'none'`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `Cache-Control: private, max-age=300`
- `ETag: "f7f7c4f0b5483e789740345cff7c115100283b5ec1847cd181ef55e7f00b50dc"`
- `Content-Disposition: inline; filename="tiktok-viral-topic-2026-10-31.html"`

`?download=1` 时把 `Content-Disposition` 改为 `attachment`，其余不变。

**处理顺序：**

1. 按工作区查报告。不存在、跨工作区、`withdrawn`：404。
2. `LEFT JOIN` 正文表。没有行：409 `insight_report_content_missing`。
3. 读取 `content_html`，按 UTF-8 编码，计算 SHA-256，与 `content_sha256` 比较。不一致：409 `insight_report_integrity_failed`，日志记录 `report_id`、期望哈希、实际哈希、`request_id`，响应不返回实际哈希。
4. 如果请求头 `If-None-Match` 与 ETag 匹配，返回 304。
5. 返回正文。

**安全说明：**

- 内容端点直接打开时，CSP 的 `sandbox` 和 `script-src 'none'` 阻止脚本执行。
- 工作台内嵌视图不直接用这个响应头；它把 HTML 拉下来，放进 `iframe srcdoc`，由客户端注入一条允许两段白名单脚本的 CSP。见 §5.4。
- 不在服务端改写 HTML。存储的字节、`content_bytes`、`content_sha256` 三者一致。

### 3.6 错误码

新增前端稳定错误码，加入 `apps/web/src/lib/api/client.ts` 的 `ApiErrorCode` 与 `stableApiErrorCodes`：

| HTTP | `code` | 触发 | 前端行为 |
| --- | --- | --- | --- |
| 401 | `authentication_required` | 无有效 Cookie | 跳转登录，带 `next` |
| 403 | `workspace_not_found` | 严格工作区依赖专用：`get_authenticated_context` 在有效 token 但无可用工作区时返回。本页四个端点走 `get_auth_context`，实际不会产出 403——无工作区时先退回 `401 authentication_required`。前端保留 403 分支只是与共享错误码表对齐，不应当作可达路径来设计交互。 |
| 404 | `insight_report_not_found` | 不存在、跨工作区、已下架 | 详情错误态；“报告不存在或已被移除。” |
| 409 | `insight_report_content_missing` | 正文表没有行 | fail-closed 面板；“报告正文未导入。” |
| 409 | `insight_report_integrity_failed` | 正文 SHA-256 不一致 | fail-closed 面板；“报告正文校验失败。” |
| 422 | `validation_error` | `limit`、`cursor`、UUID 非法 | 行内参数错误 |
| 500 | `internal_server_error` | 数据库或未知错误 | 页面 banner + 重试 |

说明：

- 不要用 `internal_server_error` 表示正文缺失。正文缺失是已知状态，前端要显示不同的文案和操作。
- 不要用 404 表示正文缺失。元数据存在，用户应该看到它存在，只是正文不可读。
- 422 沿用现有 FastAPI 校验形状；前端已有解析逻辑。

### 3.7 未来生成接口（v1 不实现）

v1 没有 `POST /api/insight/reports`。调用会得到 405。不要加一个永远返回 501 的占位端点。占位端点是一个承诺，也是攻击面。

B 立项时再加：

```text
POST /api/insight/reports
  body: {"analysis_type": "tiktok_viral_topic", "data_window": {...}}
  202:  {"run_id": "...", "status": "queued"}

GET /api/insight/reports/runs/{run_id}
  200:  {"run_id": "...", "status": "queued|running|ready|failed",
         "progress": 0..100, "error_code": null, "report_id": null}
```

生成器成功后写同一张 `insight_reports` + `insight_report_contents`，`status=ready`。失败写一条 `status=failed` 的运行记录，不写报告正文。读 API 不变。

这证明 A 是 B 的子集：A 不需要改表，也不需要改页面骨架。

---

## 4. 降级设计

### 4.1 先分开三条路径

| 路径 | 依赖 | 数据源断开时 |
| --- | --- | --- |
| 查看 | Web -> API -> Postgres | 正常。正文已入库，不碰 `abi_migtest`。 |
| 生成 | 不存在（v1） | 没有入口，不产生错误。 |
| 存储 | Postgres 正文表 | 正文缺失或哈希不一致时 fail-closed。 |

关键结论：**数据源不可用不是查看页的错误。** 它只影响未来生成。页面不能因为数据源断开就把已归档报告藏起来，也不能显示一个假的“分析中”。

### 4.2 状态矩阵

| # | 状态 | 触发 | 用户看到 | 交互 |
| --- | --- | --- | --- | --- |
| 1 | 正常：数据源未连接，有报告 | v1 生产默认 | 报告列表 + 中性来源说明 | 查看、下载可用；无生成按钮 |
| 2 | 正常：数据源已连接，生成未开放 | 未来 | 同一页面，文案改为“生成能力尚未开放” | 仍无生成按钮 |
| 3 | 空：没有报告 | 报告表为空或当前类型无报告 | 空态 + 来源说明 | 刷新；无生成按钮 |
| 4 | 空：没有分析类型 | 注册表为空（不应发生） | “还没有可用的分析类型” | 刷新；记录告警 |
| 5 | 正文缺失 | 正文表没有行 | 列表“正文缺失”；详情 fail-closed | 重新加载、复制报告 ID、返回 |
| 6 | 完整性失败 | SHA-256 不一致 | 详情 fail-closed | 重新加载、复制报告 ID、返回 |
| 7 | API 不可达 | 网络或 5xx | 页面 banner + 重试 | 重试 |
| 8 | 未登录 | API 401 | 登录过期提示 | 重新登录 |
| 9 | 本地 mock 模式 | `NEXT_PUBLIC_MOCK_API=true` | “本地测试模式没有归档报告” | 无假报告 |
| 10 | 已下架 | `status=withdrawn` | 列表隐藏；详情 404 | 返回列表 |

### 4.3 正常态：数据源未连接，已有报告

**列表页顶部说明条（中性色，不是红色）：**

> 数据源未连接，无法生成新报告。
> 当前可查看已归档的 1 份报告。

第二行的“1”来自 `report_count`，不是硬编码。

**分析类型卡：**

> TikTok 爆款选题分析
> 母婴 / 喂养 · 288 条样本 · 1 份报告

标签：`数据快照`、`只读`。

**详情页来源说明：**

> 数据源未连接，无法生成新报告。
> 当前展示 2026-10-31 归档的版本。查看正文不依赖数据源。

**交互：**

- 说明条常驻，不可关闭。它不是错误，不需要用户确认。
- 页面不渲染“开始分析”按钮。不是禁用，是不存在。
- “查看报告”和“下载 HTML”始终可用。
- “刷新”只刷新列表，不触发分析。

### 4.4 正常态：数据源已连接，生成未开放

这是未来代码路径，v1 不会出现。文案：

> 数据源已连接。当前版本仍只支持查看归档报告，生成能力尚未开放。

仍然没有生成按钮。只有在 `generation.available=true` 时，页面才渲染生成入口。

### 4.5 空列表

**右侧面板：**

> **还没有归档报告**
> 报告需要先在数据源所在环境生成，再导入工作台。页面不会实时分析。
> 数据源未连接，暂时不能生成新报告。

**交互：**

- 主操作只有“刷新”。
- 左侧分析类型仍然显示。空的是报告列表，不是整个页面。
- 不显示示例报告，不显示骨架屏占位卡。
- 不把空列表显示成错误。HTTP 200 + `items=[]` 是正常状态。

### 4.6 正文缺失

**列表卡：**

- 状态胶囊：`正文缺失`（amber）。
- 标题、摘要、数据范围仍然显示。
- 操作：`查看详情`。

**详情页：**

> **报告正文未导入**
> 报告的元数据已入库，正文记录不存在或未写入。系统已停止展示这份报告。
> 报告 ID：`{id}` · 版本：`{version}`

**操作：**

- `重新加载`（如果管理员刚完成导入）
- `复制报告 ID`（复制成功显示“已复制”）
- `返回列表`

**禁止：**

- 不渲染空 iframe。
- 不显示“报告加载中”然后永远转圈。
- 不显示半份报告。

### 4.7 完整性失败

**详情页：**

> **报告正文校验失败**
> 正文的 SHA-256 与入库记录不一致。系统已停止展示，避免显示被改动的报告。
> 报告 ID：`{id}` · 版本：`{version}`

**操作：**

- `重新加载`
- `复制报告 ID`
- `返回列表`

**行为：**

- 正文端点返回 409，前端不把已下载的部分 HTML 放进 iframe。
- 服务端日志记录期望哈希、实际哈希、报告 ID、请求 ID。
- 不自动“修复”或“忽略”哈希。校验失败就是失败。

### 4.8 API 不可达与未登录

**列表页 banner：**

> 无法连接服务器。报告列表没有加载。

操作：`重试`。

**详情页：**

> 无法加载报告。网络或服务异常，请稍后重试。

操作：`重试`、`返回列表`。

**401：**

> 登录已过期，请重新登录。

操作：`重新登录`，链接到 `/login?next=/new`。middleware 通常会在页面渲染前处理，这里是页面加载后 API 返回 401 的兜底。

**403：**

> 当前工作区不可用。请切换工作区或联系管理员。

不要把这三种状态混成一句“加载失败”。用户需要知道是网络、登录还是权限。

### 4.9 本地 mock 模式

`NEXT_PUBLIC_MOCK_API=true` 时，不返回虚构报告。页面显示：

> **本地测试模式没有归档报告**
> 测试模式不返回示例报告，避免把假数据当成真实分析。请连接真实 API，或用导入脚本写入测试报告。

**实现约束：**

- 不往 `apps/web/src/lib/api/mock.ts` 加 TikTok 假报告。
- `src/lib/api/insight.ts` 在 mock 模式下：`listInsightAnalysisTypes` 返回注册表里的类型，`report_count=0`，`generation.reason_code='mock_mode'`；`listInsightReports` 返回空列表和 `mock: true`。
- 详情页在 mock 模式下直接显示同一个 mock 空态，不发请求，也不显示 404。
- E2E 只验证空态、错误态和导航；真实报告用集成环境验证。

### 4.10 不做什么

1. 不显示禁用的“开始分析”按钮。
2. 不显示“分析中”进度条。
3. 不用 mock 数据填页面。
4. 不生成空报告来占位。
5. 不回退到 `/api/reports` 的日报。
6. 不在哈希失败时渲染部分正文。
7. 不在没有真实探测时声称“数据源已连接”。
8. 不把数据源不可用和 API 不可达写成同一条错误。

---

## 5. 页面结构

### 5.1 `/insight/new` 列表页

**文件：** `apps/web/src/app/new/page.tsx`（服务端组件，只包 `AppShell`）

```tsx
<AppShell
  title="新建洞察"
  description="选题分析与归档报告"
  brief="查看已生成的分析报告，确认数据范围与结论。当前版本不执行新分析。"
  signals={["分析类型", "归档报告", "数据范围"]}
>
  <InsightNewWorkspace />
</AppShell>
```

**客户端组件：** `apps/web/src/components/insight/insight-new-workspace.tsx`

布局：

```text
┌──────────────────────────────────────────────────────────────┐
│ 新建洞察                                                      │
│ 选题分析与归档报告                                             │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ 数据源未连接，无法生成新报告。当前可查看已归档的 1 份报告。 │ │
│ └──────────────────────────────────────────────────────────┘ │
│ ┌──────────────┬───────────────────────────────────────────┐ │
│ │ 分析类型      │ TikTok 爆款选题分析                        │ │
│ │              │ 对已爆母婴/喂养视频做主题、机制、可复刻性   │ │
│ │ ● TikTok ... │ 和评论需求分析。                            │ │
│ │   288 条样本  │ [数据快照] [只读] [1 份报告]                │ │
│ │   1 份报告    │                                            │ │
│ │              │ 已归档报告                                  │ │
│ │              │ ┌────────────────────────────────────────┐ │ │
│ │              │ │ 下周拍什么：288 条母婴爆款的选题报告      │ │ │
│ │              │ │ 下周优先拍产品清单、教程、身份共鸣三类... │ │ │
│ │              │ │ 2026-10 · 288 条样本 · 2026-10-31       │ │ │
│ │              │ │ [可查看]                查看报告 →       │ │ │
│ │              │ └────────────────────────────────────────┘ │ │
│ │              │                                            │ │
│ │              │ 分析口径                                    │ │
│ │              │ 样本 288 条 · 采样 392 hashtag × 43 天      │ │
│ │              │ 来源 5 张 raw 表 · 数据截止 2026-10-28      │ │
│ └──────────────┴───────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**首屏放什么：**

1. 一行能力说明。用户先知道这是只读归档，不会误以为点进去会开始分析。
2. 左侧一个选中的分析类型。只有一个类型时，用 master-detail 的选中行，不用“三列卡片网格放一张卡”的半成品布局。
3. 右侧最新的报告卡。标题、一句话结论、数据窗口、样本量、状态、查看入口。
4. 下方分析口径。解释样本怎么来的，避免报告看起来像凭空出现。

**只有一个类型怎么不像半成品：**

- 用左栏列表 + 右栏详情，而不是一张孤零零的卡片。列表一的选中态是正常交互，不是占位。
- 右栏填入真实内容：类型说明、报告卡、分析口径。不是空面板。
- 不显示“更多类型敬请期待”。没有的东西不出现。
- 类型栏的宽度固定 17rem，和 `--sidebar-width` 同一量级；右栏自适应。以后加类型只增加左栏行，不改布局。

**空列表：**

- 右栏用 `WorkbenchEmptyState`（完整形态），标题“还没有归档报告”，正文见 §4.5。
- 左栏保留类型和选中态。
- 分析口径仍然显示。它说明这个类型需要什么数据，不是空占位。

**加载：**

- 列表加载时显示 `WorkbenchEmptyState compact` 或一行“加载报告中”。不引入骨架屏库。
- 类型和报告可以并行请求；两个 loading 布尔，一个错误字符串，沿用 `reports-workspace.tsx` 的模式。
- `mounted` 标志防止卸载后 setState。
- `clearProjectFilterApplied()`：本页不按项目过滤，报告是工作区级资产。项目选择器仍显示，但不影响列表。

### 5.2 `/insight/new/[reportId]` 详情页

**文件：** `apps/web/src/app/new/[reportId]/page.tsx`（服务端组件）

```tsx
export default async function InsightReportDetailPage({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId } = await params;
  return (
    <AppShell
      title="报告详情"
      description="归档报告正文与数据范围"
      brief="报告来自已生成快照。页面只读，不执行分析。"
      signals={["数据快照", "正文只读", "来源可追溯"]}
    >
      <InsightReportDetailWorkspace reportId={reportId} />
    </AppShell>
  );
}
```

布局：

```text
返回 新建洞察

TikTok 爆款选题分析                              [下载 HTML]
下周拍什么：288 条母婴爆款的选题报告
[数据快照] [可查看] [版本 2026-10-31]

┌ 来源说明 ──────────────────────────────────────────────────┐
│ 数据源未连接，无法生成新报告。                                │
│ 当前展示 2026-10-31 归档的版本。查看正文不依赖数据源。        │
└────────────────────────────────────────────────────────────┘

数据窗口 2026-10（截至 2026-10-28）    样本 288 条
采样 392 个 hashtag × 43 天 top20      来源 5 张 raw 表
生成 2026-10-31                        导入 2026-10-31
正文 181,984 字节 · SHA-256 f7f7c4f0…

┌ 报告正文 ──────────────────────────────────────────────────┐
│                                                            │
│  iframe sandbox="allow-scripts"                            │
│  报告自己的 hero、目录、6 张 SVG、22 张表                    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**数据获取：**

1. 先 `getInsightReport(reportId)` 拉元数据，渲染头部和来源说明。
2. 元数据成功后，再 `getInsightReportContent(reportId)` 拉正文。
3. 元数据失败：整页错误态，不请求正文。
4. 正文失败：保留头部，正文区显示 fail-closed 面板。
5. 正文加载中：正文区显示“正在加载报告正文…”，不挂空 iframe。

**头部操作：**

- `下载 HTML`：调用 `/content?download=1`。失败时在按钮旁显示行内错误，不弹窗。
- `返回列表`：`Link href="/new"`。
- 不显示“重新分析”“分享”等 v1 没有的动作。

**元数据：**

- 数据窗口、样本量、采样口径、来源环境、来源库、源表行数、生成时间、导入时间、正文大小和短哈希。
- 源表行数从 `data_scope.source.tables` 读取，不在前端写死。
- 短哈希显示前 8 位，完整值放在 `title` 或复制按钮里。

### 5.3 数据与状态管理

- 全部客户端取数，沿用 `reports-workspace.tsx` 的模式。没有 server component 取数，没有 React Query 使用点。
- `src/lib/api/insight.ts` 导出：
  - `listInsightAnalysisTypes(): Promise<InsightAnalysisType[]>`
  - `listInsightReports(input): Promise<{ items: InsightReportSummary[]; nextCursor: string | null }>`
  - `getInsightReport(id): Promise<InsightReportDetail>`
  - `getInsightReportContent(id): Promise<string>`
- `src/types/insight.ts` 定义 camelCase 领域类型；API 模块把 snake_case 映射过来。
- `getInsightReportContent` 用一个新的 `apiFetchText`（放在 `client.ts`，复用错误解析）。不要用 `apiFetch`，它假定 JSON。
- mock 模式不造假数据，见 §4.9。

### 5.4 HTML 渲染方案

**选择：认证拉取 + `iframe srcdoc` + sandbox + CSP。**

不用另外三种：

1. **不用 `dangerouslySetInnerHTML`。** 报告有完整的 `<html>/<head>/<style>`，注入到应用 DOM 会污染全局样式；脚本会在应用源里执行。
2. **不用 Markdown 渲染器。** 六张 SVG 和 22 张表只在 HTML 里；`report.md` 与 HTML 不完全一致。引入 Markdown 库还会违反“不引入新依赖”。
3. **不用 `iframe src` 直连 API。** API 与 Web 可能跨站，iframe 里的 Cookie 受 SameSite 限制；`srcdoc` 在认证 fetch 之后渲染，行为稳定。

**iframe 属性：**

```tsx
<iframe
  title={`报告正文：${report.title}`}
  srcDoc={htmlWithCsp}
  sandbox="allow-scripts"
  referrerPolicy="no-referrer"
  className="h-[calc(100vh-18rem)] min-h-[640px] w-full rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-white"
/>
```

- 只给 `allow-scripts`。不给 `allow-same-origin`、`allow-top-navigation`、`allow-popups`、`allow-forms`、`allow-modals`。
- 没有 `allow-same-origin`，文档是 opaque origin，脚本不能读父页面、Cookie、localStorage。
- 固定高度 + 内部滚动。父页面读不到 iframe 的 `contentDocument`，不做自动高度。
- 移动端高度用 `70vh`，最小 520px；报告自己的响应式 CSS 负责排版。

**客户端 CSP 注入：**

```ts
const REPORT_CSP = [
  "default-src 'none'",
  "style-src 'unsafe-inline'",
  "img-src data:",
  "script-src 'unsafe-inline'",
  "connect-src 'none'",
  "font-src 'none'",
  "frame-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");

function withReportCsp(html: string): string {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${REPORT_CSP}">`;
  return html.replace(/<head(\s[^>]*)?>/i, (match) => `${match}${meta}`);
}
```

- CSP 在 `srcdoc` 里生效，阻止外部请求和表单提交。
- 允许内联样式（报告的 `<style>`）和内联脚本（两段白名单脚本）。
- 不影响存储的 HTML 字节和 `content_sha256`；这是渲染时的字符串变换。

**为什么允许两段脚本：**

- 报告里有 2 段内联脚本，分别 1,762 和 1,764 字节。
- 第一段做目录高亮（IntersectionObserver）；第二段做移动端表格卡片化（加 `data-label` 和 `.ready`）。
- 没有这两段，报告仍可读，但移动端 22 张表会退化成横向滚动。保留它们，体验更接近独立 HTML。
- 风险控制：
  - 导入时按脚本内容哈希白名单，只允许这两个哈希。manifest 不能授权脚本。
  - 拒绝所有 `on*=` 事件属性。
  - 拒绝外链、表单、iframe、object、embed、meta refresh。
  - iframe 是 opaque origin，CSP 禁止 `connect-src` 和外部 `img-src`。
- 如果安全评审要求零脚本，把 `sandbox` 改成 `sandbox=""`、CSP 的 `script-src` 改成 `'none'`。报告仍可读，移动端表格横向滚动。这是一个可逆的开关，不影响 API 和存储。

**不引入依赖：**

- 不用 `dompurify`、`sanitize-html`、`react-markdown`、`rehype`。
- 导入校验用 Python 标准库 `html.parser` + `hashlib`。
- 前端用原生 `fetch`、`iframe`、`Blob`（如需下载）。

### 5.5 样式

- 新页面统一用 `var(--...)` 令牌：`bg-[var(--surface-primary)]`、`text-[var(--text-secondary)]`、`border-[var(--border-subtle)]`、`rounded-[var(--radius-3)]`。
- 不复用 `ReportDetailPanel` 的硬编码十六进制（`#C25B6E`、`#1D1D1F` 等）。那是旧一代配色，和 `AppShell` 的令牌不一致。
- 复用 `WorkbenchPanel`、`WorkbenchTag`、`WorkbenchStatusPill`、`WorkbenchActionButton`、`WorkbenchEmptyState`。
- 报告 iframe 内部是报告自己的配色（纸色、酒红），不继承应用令牌；因为它是一个独立文档，不会污染应用，也不受应用主题影响。
- iframe 外层加 `bg-white`，避免加载瞬间透出页面底色。
- `prefers-reduced-motion` 已由令牌处理；报告本身没有动画。

### 5.6 加载、错误与无障碍

- 列表加载：`WorkbenchEmptyState compact` 或一行“加载报告中”。
- 详情元数据加载：一行“加载报告中”。
- 正文加载：`role="status"` 的“正在加载报告正文…”。
- 错误：`role="alert"`，不要只靠颜色。
- iframe 必须有 `title`，说明这是哪份报告的正文。
- 状态胶囊带文字（`可查看`、`正文缺失`、`数据快照`），不只靠颜色。
- 左栏类型项用按钮或链接，选中态同时有文字和边框，不只靠背景色。
- 报告 HTML 自带 `lang="zh-CN"`、标题层级和 SVG `aria-label`，不要重写。

---

## 6. 与既有导航的关系

### 6.1 挂在哪里

挂在 `apps/web` 的“洞察与交付”一级项下，作为第一个二级项：

```ts
nav("/intelligence", "洞察与交付", ChartNoAxesCombined, [
  child("/new", "新建洞察"),
  child("/signals", "信号中心"),
  child("/reports", "报告中心"),
  child("/alerts", "预警中心"),
  child("/notifications", "站内通知"),
]),
```

文件：`apps/web/src/components/layout/navigation.ts`。

### 6.2 冻结契约核对

| 契约 | 位置 | 本设计是否违反 |
| --- | --- | --- |
| 根站一级导航只有 4 项：工作台、报告、连接器、设置 | `apps/scraper-console/src/lib/routes.ts:214` | 不违反。本设计不改 `apps/scraper-console`。 |
| `apps/web` 一级导航 7 项，label 数组被单测锁死 | `apps/web/tests/unit/navigation.test.ts:17` | 不违反。只加二级项。 |
| `apps/web` 一级导航长度 7 | `apps/web/tests/unit/navigation.test.ts:190` | 不违反。只加二级项。 |
| 二级项用 `expect.arrayContaining` 断言 | `apps/web/tests/unit/navigation.test.ts:33` | 不违反。新增项不会让既有断言失败。 |
| `/insight` 是 basePath，不是路由段 | `apps/web/next.config.ts:9` | 不违反。页面文件是 `src/app/new/page.tsx`。 |
| middleware 自动保护新页面 | `apps/web/src/middleware.ts` | 不违反。`/new` 自动纳入，无白名单。 |

回答“一级只有 4 个”的问题：

- 4 项冻结的是根站 `apps/scraper-console`，不是 `apps/web`。
- 即使按最严格口径理解，本设计也没有新增任何一级项。`apps/web` 仍是 7 个一级项，console 仍是 4 个。
- 新增的只是一个二级项和一个页面。

### 6.3 子路径高亮

当前 `isNavigationChildActive` 要求 `pathname` 与子项 href 完全相等：

```ts
if (target.pathname !== pathname) {
  return false;
}
```

这会导致 `/new/<uuid>` 不点亮“新建洞察”，也不点亮父项“洞察与交付”。

改成前缀匹配，query 仍然精确匹配：

```ts
const matchesPath =
  pathname === target.pathname || pathname.startsWith(`${target.pathname}/`);
if (!matchesPath) {
  return false;
}
```

影响：

- `/new/<uuid>` 点亮“新建洞察”和“洞察与交付”。
- `/reports/<uuid>` 会点亮“报告中心”，这是合理行为。
- `/automation/planner/foo` 会点亮 planner 子项，但 query 不匹配时仍然 false。
- 现有 294 个单测不需要改；新增一条：

```ts
expect(
  isNavigationItemActive("/new/0f7d9c2e-5a1b-4c3d-8e9f-1a2b3c4d5e6f", "", insights),
).toBe(true);
```

如果团队不接受改导航匹配逻辑，备选方案是把详情做成 `/new?report=<id>`，pathname 始终是 `/new`。代价是详情 URL 不够直观，且需要 query 同步。推荐前者。

### 6.4 不改什么

- 不改 `apps/scraper-console` 的 4 项一级导航。
- 不改 `apps/web` 的 7 项一级导航。
- 不改 `next.config.ts` 的 basePath。
- 不改 middleware 的 matcher。
- 不改现有 `/reports`、`/intelligence` 页面。
- 不把 `/new` 做成一级项。

---

## 7. 验收清单

### 7.1 数据与导入

- [ ] `uv run alembic upgrade head` 成功；在临时库上 `downgrade -1` 可回滚。
- [ ] 导入器 dry-run 通过，打印源哈希、归一化哈希、字节数。
- [ ] 篡改 `report.html` 后导入失败，退出非零，提示哈希不一致。
- [ ] 在 HTML 里插入未知 `<script>` 后导入失败，提示脚本不在白名单。
- [ ] 导入后正文不含 `/tmp/`。
- [ ] 重复导入同一版本：no-op。
- [ ] 同版本改正文：冲突；必须换版本。
- [ ] 跨工作区查询：404。

### 7.2 API

- [ ] `GET /api/insight/analysis-types` 返回 1 个类型，`report_count=1`，`generation.available=false`。
- [ ] `GET /api/insight/reports` 返回 1 条，响应里没有 `content_html`。
- [ ] `GET /api/insight/reports/{id}` 返回元数据。
- [ ] `GET /api/insight/reports/{id}/content` 返回 200、`text/html`、CSP、ETag、`Content-Length=181984`。
- [ ] `?download=1` 返回 attachment。
- [ ] 删除正文行：列表 `status=content_missing`，正文端点 409。
- [ ] 篡改正文行：正文端点 409 `insight_report_integrity_failed`，日志有期望/实际哈希。
- [ ] 无 Cookie：401；前端跳登录。
- [ ] 非法 `limit`/`cursor`：422。

### 7.3 页面

- [ ] `/insight/new` 首屏能看到能力说明、选中的分析类型、报告卡。
- [ ] 报告卡显示标题、一句话结论、2026-10、288 条样本、2026-10-31。
- [ ] 空数据库：显示“还没有归档报告”，不是错误页，不显示假卡。
- [ ] `/insight/new/<id>` 显示来源说明、元数据、正文 iframe。
- [ ] 报告内 6 张 SVG、22 张表正常渲染；目录高亮可用；移动端表格卡片化可用。
- [ ] 报告内无外部请求，无 CSP 违规，无 `/tmp/` 路径。
- [ ] 正文缺失：显示“报告正文未导入”，不挂空 iframe。
- [ ] 哈希失败：显示“报告正文校验失败”，不渲染部分正文。
- [ ] API 停掉：列表显示“无法连接服务器”，有“重试”。
- [ ] `NEXT_PUBLIC_MOCK_API=true`：显示“本地测试模式没有归档报告”，没有报告卡。
- [ ] 375px 宽度：左栏变横向，报告卡和详情单列，iframe 不溢出。

### 7.4 导航与测试

- [ ] `/insight/new` 点亮“洞察与交付 > 新建洞察”。
- [ ] `/insight/new/<id>` 点亮同一项。
- [ ] `apps/scraper-console` 导航无改动。
- [ ] `pnpm --dir apps/web test`：26+ 文件、294+ 用例全绿。
- [ ] `pnpm --dir apps/web lint`：无新增错误。
- [ ] `cd apps/api && uv run pytest`：全绿。
- [ ] `pnpm --dir apps/web build`：typedRoutes 生成 `/new` 和 `/new/[reportId]`。

### 7.5 生产 A 冒烟

- [ ] 迁移后表存在，索引存在。
- [ ] 导入目标工作区，打印报告 ID。
- [ ] 打开 `https://<host>/insight/new`，看到 1 份报告。
- [ ] 打开详情，报告正文完整渲染。
- [ ] 顶部来源说明显示“数据源未连接，无法生成新报告。”
- [ ] 页面没有“开始分析”按钮。
- [ ] 下载 HTML 可用，文件大小 181,984 字节。
- [ ] 关闭网络中的 API（或改错 API URL）后，页面显示连接错误，不显示假数据。

---

## 8. 实现文件清单

### 后端

| 文件 | 作用 |
| --- | --- |
| `apps/api/alembic/versions/202610310068_insight_reports.py` | 新表迁移 |
| `apps/api/src/data_intelligence_hub/models/insight_report.py` | `InsightReport`、`InsightReportContent` |
| `apps/api/src/data_intelligence_hub/repositories/insight_reports.py` | 工作区隔离查询、分页、正文读取 |
| `apps/api/src/data_intelligence_hub/schemas/insight_report.py` | 响应模型、`data_scope` 校验 |
| `apps/api/src/data_intelligence_hub/services/insight_report_catalog.py` | 分析类型注册表 |
| `apps/api/src/data_intelligence_hub/services/insight_report_service.py` | 列表、详情、正文、状态计算 |
| `apps/api/src/data_intelligence_hub/api/routes/insight.py` | 4 个只读端点 |
| `apps/api/src/data_intelligence_hub/main.py` | `include_router(insight_router, prefix="/api/insight")` |
| `apps/api/src/data_intelligence_hub/scripts/import_insight_report.py` | 导入器、校验、路径归一化 |
| `apps/api/tests/unit/test_insight_reports.py` | 服务与路由单测 |
| `apps/api/tests/unit/test_insight_report_import.py` | 导入器单测 |
| `apps/api/tests/unit/test_insight_report_queries.py` | 查询形状单测：断言列表/详情编译出的 SELECT 不含 `content_html`，正文查询才包含它 |

### 前端

| 文件 | 作用 |
| --- | --- |
| `apps/web/src/app/new/page.tsx` | 列表页服务端壳 |
| `apps/web/src/app/new/[reportId]/page.tsx` | 详情页服务端壳 |
| `apps/web/src/components/insight/insight-new-workspace.tsx` | 列表、类型栏、空态、错误态 |
| `apps/web/src/components/insight/insight-report-detail-workspace.tsx` | 详情、元数据、正文加载 |
| `apps/web/src/components/insight/insight-report-frame.tsx` | iframe、CSP 注入、fail-closed |
| `apps/web/src/lib/api/insight.ts` | API 客户端与映射 |
| `apps/web/src/types/insight.ts` | 领域类型 |
| `apps/web/src/lib/api/client.ts` | 新增 `apiFetchText` 与 4 个错误码 |
| `apps/web/src/components/layout/navigation.ts` | 新增“新建洞察”二级项 |
| `apps/web/tests/unit/insight-report-frame.test.ts` | CSP、sandbox、无 `allow-same-origin` |
| `apps/web/tests/unit/navigation.test.ts` | 新增二级项与子路径高亮 |
| `apps/web/tests/e2e/insight-new.spec.ts` | 空态、错误态、mock 态 |

### 报告包

| 文件 | 作用 |
| --- | --- |
| `tools/insight-reports/tiktok-viral-topic/2026-10-31/manifest.json` | 元数据、数据范围、哈希 |
| `tools/insight-reports/tiktok-viral-topic/2026-10-31/report.html` | 成品正文，182,450 字节源文件 |
| `tools/insight-reports/tiktok-viral-topic/2026-10-31/report.md` | 可编辑源，不导入 |

---

## 9. 开放问题与默认答案

| 问题 | v1 默认 | 何时改 |
| --- | --- | --- |
| 报告导入哪个工作区 | 运维参数 `--workspace-slug`，导入团队工作区 | 需要全员可见时，导入共享工作区；不做跨工作区 |
| 报告是否按项目过滤 | 否。工作区级资产，页面 `clearProjectFilterApplied()` | 出现项目级报告时，加 `project_id` 过滤和 `markProjectFilterApplied` |
| 是否支持多份报告 | 数据模型支持，页面列表支持 | 同类型新报告用新 `version` 导入 |
| 是否支持 PDF | 否 | 需要时加 `content_format='pdf'`，正文表加 blob 或对象存储 |
| 是否显示“重新生成” | 否 | 生成能力上线且 `generation.available=true` |
| 是否允许 mock 报告 | 否 | 永不。测试用导入器写真实测试数据 |
| 是否允许脚本 | 是，两段白名单 | 安全评审要求零脚本时改为 `sandbox=""` |
| 正文超 5 MB | 仍存 DB | 超 5 MB 或正文表超 1 GB 时迁对象存储 |

---

## 10. 一句话总结

`/insight/new` 的第一版是一个诚实的归档报告查看器：报告已入库，查看不依赖数据源；数据源未连接时，页面明说不能生成新报告，不显示假按钮、假进度、假数据；正文缺失或校验失败时停止展示。方案 B 等数据源、管线和报告撰写都产品化以后再立项，届时复用同一张表、同一个读 API 和同一个页面骨架。
