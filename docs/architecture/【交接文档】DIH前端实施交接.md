---
name: dih-frontend-handoff
description: DIH 前端实施交接文档，面向新会话。给出权威事实、后端可用面、任务清单与禁区。新开前端会话时先读这份。
---

# DIH 前端实施交接

> 写于 2026-10-16 · 基线分支 `feat/dih-p0-on-guardrails` · HEAD `7366a17`
> 依据文档：[整站能力整合方案](./【技术方案】DIH整站能力整合方案.md) · [视觉规范](./【设计规范】DIH首页与目录视觉规范.md) · [能力图谱](./【能力图谱】DIH-控制台能力地图.md) · [能力总账](./【能力总账】DIH-平台能力现状与维护手册.md)

## 0. 这份文档怎么用

你是接手 DIH 前端实施的新会话。这份文档给你三件东西：

1. **权威事实**：哪些功能真的做完了，数字是多少。第 2 节。
2. **实施对象**：改哪个目录。第 3 节。
3. **任务清单**：按优先级排好，每条都能独立开工。第 7 节。

第 6 节是禁区，开工前必读。第 8 节是必须由产品决策、你无法自己定的问题。

**这份文档里的数字都是 2026-10-16 实测的。** 若你开工时距此超过两周，重跑第 2 节的命令复核。

## 1. 一句话现状

后端能力已经就绪并且可查询。前端有一份能用的控制台，但它与后端契约脱节，用户会看到空表单和假数据。

具体说：目录里有 258 个端点，前端只有 162 条硬编码表单，其中 127 个端点渲染空表单。用户点下去，有的采回测试数据，有的报错。

这是你首要要修的东西。

## 2. 权威事实

### 2.1 目录规模

| 指标 | 值 | 说明 |
|---|---:|---|
| catalog 条目 | 286 | 含别名视图。旧文档叫「视图数」 |
| 唯一端点 | 258 | 按 `endpoint_type` 去重。**前端计数用这个** |
| 平台包 | 70 | |
| 采集器分组 | 36 | |
| catalog 摘要 | `1e5511964fd0c3c6…` | 见 `configs/platform-packages.lock.json` |

**不要用 286 当「可用功能数」。** 286 是视图数（同一端点在多个平台包下重复出现）。可用性看 2.3。

复核命令：

```bash
cd apps/scraper-console 2>/dev/null; cd /Users/lute/Project/data_scrapy-p0g
python3 -c "import json;d=json.load(open('generated/platform-packages.json'));print(d['capability_count'],d['unique_endpoint_count'],d['platform_count'])"
```

### 2.2 工具目录（新面，前端可直接用）

`GET /api/tools` 是 2026-10-16 新增的只读接口。它把目录投影成带类型的工具描述。

| 指标 | 值 |
|---|---:|
| 工具数 | 258 |
| 参数总数 | 650 |
| 其中有类型 | 294 |
| 静态可执行 | 257 |

**这是修复空表单的原料。** 每个参数带 `value_type`、`required`、`default`、`allowed_values`、`minimum`、`maximum`、`max_length`、`type_enforced`。

`type_enforced=false` 表示实现不校验该参数类型。前端不要据此假定非法输入会被拒。

详见 `apps/api/src/data_intelligence_hub/tool_catalog/public.py` 的 `PublicTool` 与 `PublicToolParameter`。

### 2.3 哪些功能真的能跑（关键）

策略层把 86 个采集器类型分成四档：

| 档次 | 类型数 | 端点 | 能否执行 |
|---|---:|---:|---|
| `provider_api` | 28 | 197 | 能。需平台密钥与额度 |
| `guarded_http` | 4 | 4 | 能，但需服务端逐域名批准。仓库内无批准记录 |
| `offline` | 1 | — | 能。无需网络 |
| `unsupported` | 53 | 57 | **不能。任何环境都不放行** |

规则在 `apps/api/src/data_intelligence_hub/collectors/outbound_policy.py`。

**前端必须用三态标记，不能只用「可用/不可用」两态：**

1. **永久不可达**（57 个端点）：任何参数都不解锁。不要显示补密钥或重试的提示。
2. **缺配置**（`config-gated`）：可以补密钥。提示补密钥。
3. **环境门控**：当前网络模式拒绝，换环境即通。

依据：`docs/standards/collection-outbound-safety.md:104` 要求界面显示阻断原因；能力总账第 23 行要求历史成功不能覆盖当前阻断。

`GET /api/tools` 的 `execution_kind`、`executable_now`、`permanently_blocked` 三个字段直接对应上面三态。

**别读静态文件 `generated/platform-packages.json` 判断可执行性。** 它由生成时的环境派生，检入版本反映的是离线环境，不是生产现状。读活接口。

### 2.4 测试状态

| 套件 | 结果 |
|---|---|
| 单元测试 | 1719 通过，0 失败 |
| 集成测试 | 383 通过，0 失败 |

两个套件全绿。**不要引入新失败。**

本日稍早集成测试还有 3 个失败，根因是三个后端真缺陷，已修（提交 `967532c`）。
原来的缺陷描述留在 5.2，供你了解这些端点的历史。

## 3. 实施对象

### 3.1 只改 `apps/scraper-console`

它是生产前端。edge nginx 把 `location /` 指向它（`configs/deploy/scrapy/edge-nginx.conf:56-57`）。

技术栈：Next.js 16 App Router、React 19、TanStack Query、TypeScript。

它现有 15 个页面：

| 路径 | 状态 |
|---|---|
| `/` | 重定向到 `/platforms` |
| `/platforms` | 已实现。平台能力中心，默认首页 |
| `/skills` `/skills/[platformId]` | 已实现。Skill 目录与详情 |
| `/projects` `/projects/[id]` | 已实现。详情页有两块假空态，见 5.1 |
| `/runs` | 已实现。运行记录 |
| `/collect/[run_id]` | 已实现。采集结果 |
| `/tasks` | 已实现。采集任务 |
| `/datasets` | 已实现。最完整的页面 |
| `/collector-docs` | 已实现。采集文档 |
| `/settings/credentials` | 已实现。凭证配置 |
| `/settings/account` | **占位空页。无入口** |
| `/dashboard` | 已实现。**但无入口** |
| `/raw-records` | 已实现。**但无入口** |

### 3.2 `apps/web` 不要动

它是第二套前端，29 个页面。**公网没有路由**——edge 只代理 console。

但它仍在构建、仍有容器、CI 仍有完整测试门。2026-08-16 的一次提交删掉了 nginx 里 web 的全部路由，提交信息声称 `git rm apps/web`，但实际只改了 nginx 配置一个文件。

**这是待决策项，见 8.1。** 在决策之前不要改它，也不要抄它的代码（它的珊瑚色 `#C96F5C` 不属于 console 的品牌）。

## 4. 后端可用面

212 条 API 路由。整站只有 `GET /api/auth/me` 会因未登录返回 401。

### 4.1 鉴权分级

| 级别 | 条数 | 行为 |
|---|---:|---|
| 严格登录 | 1 | `/api/auth/me`。其他全部免登录 |
| 软鉴权 | 149 | 有 cookie 用该用户，无 cookie 静默回退演示工作区 |
| 无鉴权 | 62 | 含所有写操作 |

**这是当前设计，不是缺陷。** 但你要知道：写操作（快速采集、任务执行、凭证管理、治理发布）全部可匿名调用。

### 4.2 前端最该用的接口

| 接口 | 返回 | 前端用途 |
|---|---|---|
| `GET /api/tools` | 258 个工具，带类型化参数 | **表单驱动**。首选 |
| `GET /api/tools/{tool_id}` | 单个工具 | 工具详情页 |
| `GET /api/collectors/catalog` | 286 端点，带 `required_params`/`optional_params` | 表单校验与能力卡 |
| `GET /api/collectors/docs` | 同上 + 最近测试结果 | 文档页 |
| `GET /api/platform-packages` | 70 个平台包 | 平台目录卡 |
| `GET /api/platform-packages/providers/status` | 每端点可用性证据 | **三态标记的唯一来源** |
| `GET /api/platform-packages/{id}/download` | zip 附件 | 技能包下载，无鉴权，可直接 `<a href>` |

`GET /api/tools` 支持筛选：`?query=`、`?risk_class=`、`?executable_now=`。

### 4.3 2026-10-16 新挂载的路由

三个模块此前实现了但从未挂载，端点全部 404。现已挂载，前端多出 25 个可用接口：

| 模块 | 端点数 | 前缀 |
|---|---:|---|
| `workflow_runs` | 14 | `/api/projects/{project_id}/...` |
| `capability_discovery` | 1 | `/api/capabilities/discovery` |
| `capability_governance` | 10 | `/api/capabilities/governance` |

## 5. 已完成的与没完成的

### 5.1 前端已知缺陷（你要修的）

按用户困惑程度排序。

**A. 快速采集表单与后端契约脱节（最高优先）**

`apps/scraper-console/src/components/platforms/quick-collect-drawer.tsx:24-664` 有一份 162 条硬编码参数表。问题：

- **126 个目录端点没有表项**，渲染空表单。其中 116 个必填参数非空。
- 提交空表单时，**52 个端点会静默采回测试数据**——例如 1688 搜索返回 `wireless earbuds`、Bing 返回 `python`、SpiderFoot 扫描 `example.com`。这些默认值来自后端 `quick_collect.py` 的测试兜底表（12 个来自 `_APIFY_ENDPOINT_DEFAULTS`，40 个来自 `_COLLECTOR_TEST_DEFAULTS`）。
- **5 个表项的键名与后端不符**，用户输入被丢弃或报 400：`apify_reddit_scraper`、`apify_shein_product_scraper`、`apify_google_trends_scraper`、`apify_rag_web_browser`、`apify_linkedin_profile_scraper`。
- **31 条表项是死代码**，对应的端点已不在目录里。

修法：改用 `GET /api/tools` 或 `/api/collectors/catalog` 驱动表单。两个接口都已有数据，无需后端改动。

**B. 目录有重复端点标识**

`public_feed` 出现 22 次、`generic_web` 出现 7 次。前端的 `key={ep.endpoint_type}` 会产生 React 重复 key 警告；选择集用 `Set<endpoint_type>`，勾选一个 RSS 源会同时勾中 22 行，批量队列随之展开成 22 次。

位置：`platforms/page.tsx:187`、`:392`、`:471-477`、`:486-492`。

修法：改用 `(endpoint_type, label)` 复合键，或让目录提供稳定的 `capability_id`。

**C. 项目详情页有两块假空态**

`projects/[id]/page.tsx:138-146` 的「最近运行」与 `:150-158` 的「数据集」写死显示「暂无」，从不请求。有数据也显示空。

数据集可直接用现有 `fetchDatasets({project_id})`。运行记录需要后端加过滤，或前端按项目任务循环。

**D. 三个页面没有入口**

`/dashboard`、`/raw-records`、`/settings/account` 在任何导航里都没有链接。前两个功能完整，第三个是空占位。

`/settings/account/page.tsx:10` 只有「账户设置建设中...」一句。侧边栏 `sidebar.tsx:7-19` 的两份导航数组都不含它们。

**E. 参数默认值提示没人渲染**

后端在 3 个接口里送了 22 条 `param_fields` 提示（如 `{"tag": "string (e.g. code.doc)"}`），前端类型都没声明这个字段。

它恰是修 A 的最低成本原料。

**F. 页面不读 URL 参数**

全 console 零处使用 `useSearchParams`。所有筛选状态在组件内 `useState`。后果：筛选条件不可分享、不可返回，抽屉不能深链。

对照：未路由的 `apps/web` 有 3 个文件用了这个 hook，可以抄写法。

**G. 小缺陷集合**

- `min=1` 挡住了 0.5 美元的预算默认值
- 批量采集的「取消」会推进队列
- 凭证删除无确认弹窗
- 分类筛选是子串匹配，7 个平台串类
- `/collect` 页面截断到 100 条但谎报总数

### 5.2 后端缺陷（2026-10-16 已修，提交 `967532c`）

这三条曾是集成测试最后 3 个失败的根因。**现已全部修好，测试全绿。**
保留在此是因为它们会影响你对这些端点行为的理解。

**A. `POST /api/intelligence/{id}/feedback` 曾必定 500**

`api/routes/intelligence.py` 曾把 `None` 当 `user_id` 传给服务层，而模型里
`user_id` 是 `nullable=False`。已改为取演示工作区的所有者。

**B. YouTube 读取计划的 422 曾回显用户密钥**

`social-provider-youtube-read-plan` 曾缺路径级脱敏处理器，框架默认 422
会把原始请求体回显，含用户传入的 `api_key`。已新增路径级处理器，
只对那一条路径生效；其他路径仍走默认处理器。

**C. 内部错误日志曾带出局部变量（含密钥）**

`structlog 26.1.0` 的 `ConsoleRenderer` 默认 `show_locals=True`，
会把异常帧的局部变量写进日志——各路由的 `_sanitized_exc_info`
挡不住 locals。已在 `core/logging.py` 关掉它。

**对前端的实际影响：** 这三条都在后端，你不必处理。提到它们是为了让你知道
`/api/intelligence/{id}/feedback` 与 YouTube 读取计划这两个端点的当前状态。

### 5.3 设计文档的空白

你开工前会有这些问题，目前没有答案：

| 空白 | 现状 |
|---|---|
| 组件清单 | 三套词表并存且不重合。`DESIGN.md`、视觉规范、整合方案各一套。同名的只有 AppShell 与 EvidenceDrawer |
| 状态矩阵 | 产品态词表 9 项与后端 `availability` 枚举 6 项之间无映射文档。`config-gated` 在产品词表里没有对应词 |
| 设计 token | 权威在 `opendesign/.../tokens/colors_and_type.css`。`apps/web` 用 `@import`，console 是内联复制。两者不是同一来源 |
| 新页面蓝图 | `/tools`、`/connect`、`/docs`、`/assets` 等只有一行描述 |
| 文案终稿 | 首页主句、FAQ、页脚链接都没有文本。规则要求不出现未核验的数字 |
| URL 参数 schema | 参数名、默认值、序列化格式未定义 |

另外，两份被引用的文件不存在：

- `opendesign/design-systems/data-intelligence-product/ui-kit-web/index.html` —— 被 `README.md:35` 引用。**它在主 worktree 磁盘上存在**（12,588 字节），只是被 `.gitignore:63` 的 `*.html` 规则挡住没入库。可从 `/Users/lute/Project/data_scrapy/opendesign/...` 拷回。
- `docs/product/data-intelligence-ui-ux-integrated-plan-2026-07-22.md` —— 被 `SKILL.md:17` 列为必读。全仓库与全部 git 历史都没有。它可能在被删的文档集里，见 6.5。

## 6. 禁区与约束

### 6.1 写作规范

仓库有写作标准：`docs/standards/writing-standard-ste.md`。按 ASD-STE100 等效规则写中文。

要点：短句、一句一个指令、主动语态、不用模糊词。界面文案与文档都适用。

### 6.2 不要改后端

本轮前端实施只改 `apps/scraper-console`。后端有任何需要，写进报告，不要自己改。

`apps/api` 是共享面，改动会触发跨端影响。

### 6.3 每步都跑测试

```bash
cd apps/api && ./.venv/bin/python -m pytest tests/unit -q      # 必须 1719 passed
```

前端改动后跑 console 自己的门：

```bash
cd apps/scraper-console && pnpm lint && pnpm build
```

### 6.4 已知的工具链陷阱

**写中文文件会留尾洞。** 用 Write/Edit 写含中文的文件后，`ruff` 可能报 `E902`。文件内容本身没坏，是 `st_size` 比实际内容大 4096 字节。

修法：用 Python 重写一次 inode。

```bash
python3 - <<'PY'
import os, hashlib
from pathlib import Path
p = Path("<文件路径>")
b = p.read_bytes(); d = hashlib.sha256(b).hexdigest()
t = str(p) + ".tmp"
with open(t, "wb") as fh:
    fh.write(b); fh.flush(); os.fsync(fh.fileno())
os.replace(t, p); os.chmod(p, 0o644)
print(len(p.read_bytes()), hashlib.sha256(p.read_bytes()).hexdigest() == d)
PY
```

`stat` 与 Python 读到的长度不一致，就是这个现象。

### 6.5 被删的文档可以恢复

`b339f45` 在 2026-08-16 删掉了 `docs/product/` 与 `docs/superpowers/`。这些文件在 git 历史里**搜不到**，但在一个 tree 引用里还在：

```bash
REF="refs/codex/turn-diffs/checkpoints/1d8131c1a9f36dc1b7bfde999d598d32a8f1318e41c623c5a23efb8fd5b12be3/437af0e437264d4697cec331e0c2bc927919017347515d9fe36ad633cbec5436/1786554237691/d4325cbd-5fd9-4885-8b98-76c8765d5a10"
git ls-tree -r --name-only "$REF" | grep -E "docs/(product|superpowers)"
git cat-file blob "$REF:<路径>" > <路径>
```

`git log --all` 与 `git log -S` 都找不到它，常规手段会误判「文档已丢失」。

## 7. 任务清单

按优先级排。每条都能独立开工。

### 批次 0：开工前先定（见第 8 节）

产品决策。你不该自己定。

### 批次 1：修表单（最高用户影响）

**1.1 用后端契约驱动快速采集表单**

- 目标：127 个端点的空表单变成可用表单
- 数据源：`GET /api/tools`（带类型的 294 个参数）或 `GET /api/collectors/catalog`
- 要处理：必填校验、类型校验、默认值预填、枚举下拉、数值上下界
- 要处理：`type_enforced=false` 的参数不做前端类型拦截
- 验收：任取一个目录端点，表单字段与后端 `required_params` 一致
- 顺带修：5 处键名错配、31 条死代码

**1.2 必填未填时禁用提交**

当前提交按钮只在项目未选时禁用。空表单可提交，这是 27 个端点静默采数据的原因。

**1.3 用默认值提示补插 placeholder**

渲染那 22 条 `param_fields`。

### 批次 2：修现有页面的假状态

**2.1 目录重复标识** —— 见 5.1 B。改用复合键

**2.2 项目详情页两块假空态** —— 见 5.1 C

**2.3 三个孤儿页入导航或下线** —— 见 5.1 D。先问产品

**2.4 筛选状态写入 URL** —— 见 5.1 F

### 批次 3：三态可执行性标记

**3.1 建立状态映射**

把后端 6 个 `availability` 枚举值 + `execution_kind` 映射到界面状态。这是 5.3 的空白，需要你补一份映射表。

**3.2 在能力卡与工具详情页展示三态**

- 永久不可达：不显示操作按钮
- 缺配置：显示「需配置密钥」并链接到凭证页
- 环境门控：显示阻断原因

依据：P1 验收「不展示不可执行功能的误导按钮」。

**3.3 展示阻断原因文本**

`/api/platform-packages/providers/status` 的 `policy_block_reason` 与 `missing_configuration` 要分开显示。

### 批次 4：IA 迁移（需批次 0 的决策）

整合方案 §4.3 有 15 条路由的重定向表。新 IA：

`/platforms` → `/tools`，`/skills` → `/tools`，`/collector-docs` → `/docs`，`/datasets` → `/assets`，新增 `/connect`、`/tools/[toolId]`。

**前置工作：** 当前 console 不读 URL 参数。方案说「保留筛选参数」实际是「从零新增 URL 状态承载」。按新增功能估工期，不要按兼容估。

### 批次 5：公开区首页

Monid 风格的首页。规范在视觉规范文档，品牌色已映射（蓝 `#0016d7` → 玫瑰 `#9b4355`）。

**依赖：** 文案终稿、组件清单、首页蓝图。都没定。

### 批次 6：债务清理

- 15 个无人消费的 API 字段：显示它们，或从后端删
- 2 个死 API 函数：`fetchTaskRuns`、`fetchExportJob`
- 162 条参数表的回归测试：加一条快照测试，比对目录端点与表单覆盖

## 8. 开工前必须定的决策

这四条我无法替产品决定。

### 8.1 `apps/web` 怎么处置

三个选项：路由它、下线它、删它。

**不要直接删。** 13 个以上的端点族目前只有 web 在调用（`/api/entities`、`/api/signals`、`/api/intelligence`、`/api/alert-rules`、`/api/reports`、`/api/toolkit` 等）。删之前必须做端点级调用方审计，确认 MCP、Skill、Agent 侧不依赖。

另外它的 24 个单测与 4 个 e2e 仍在 CI 里跑，是纯支出或保护，取决于这个决策。

### 8.2 token 单一来源

权威文件在 `opendesign/.../tokens/colors_and_type.css`。console 是内联复制。

要么让 console 也 `@import`，要么明确 console 的复制是接受的分叉。

**注意：** 公开区需要的 56px/40px 字号与 96px/120px 间距不在 token 文件里（最大 `--size-7: 32px`）。需要先扩展 token。

### 8.3 组件清单合并

三套词表选一套，或合并。同名的只有 AppShell 与 EvidenceDrawer。

合并后要给出 props、变体、状态与验收标准。

### 8.4 计数口径

能力图谱有一处把「286」与「209+21+17+10+1=258」写在同一格。前端展示「可用数量」时必须先定用哪个口径。

建议：**功能数用 258（唯一端点）**，视图数用 286。

## 9. 怎么复核这份文档

数字都会过期。开工前跑这几条：

```bash
cd /Users/lute/Project/data_scrapy-p0g/apps/api

# 目录规模
./.venv/bin/python -c "
import json; d=json.load(open('../../generated/platform-packages.json'))
print('条目',d['capability_count'],'唯一端点',d['unique_endpoint_count'],'平台',d['platform_count'])"

# 可执行性分层
./.venv/bin/python -c "
from collections import Counter
from data_intelligence_hub.collectors.registry import COLLECTOR_REGISTRY
from data_intelligence_hub.collectors.outbound_policy import execution_kind
print(Counter(execution_kind(t) for t in COLLECTOR_REGISTRY))"

# 测试状态
./.venv/bin/python -m pytest tests/unit -q          # 期望 1719 passed
./.venv/bin/python -m pytest tests/integration -q   # 期望 383 passed, 0 failed

# 路由数
./.venv/bin/python -c "
from data_intelligence_hub.main import app
print(len([r for r in app.routes if getattr(r,'path','').startswith('/api')]))"
```

## 10. 相关文档

| 文档 | 用途 |
|---|---|
| [整站能力整合方案](./【技术方案】DIH整站能力整合方案.md) | IA、页面路由表、分期验收。**状态行已过时**（写着「尚未进入实施」，但 P0 已有多个提交） |
| [首页与目录视觉规范](./【设计规范】DIH首页与目录视觉规范.md) | 品牌映射、字号、间距、验收 6 条 |
| [能力图谱](./【能力图谱】DIH-控制台能力地图.md) | 逐页能力清单。§4 是 10-09 历史层 |
| [能力总账](./【能力总账】DIH-平台能力现状与维护手册.md) | 状态分布、外访策略 |
| [Monid 逆向报告](./【逆向报告】Monid网站UI与能力逆向.md) | 首页结构与尺度 |
| [写作标准](../../standards/writing-standard-ste.md) | 中文写作规则 |
| `opendesign/design-systems/data-intelligence-product/DESIGN.md` | 设计系统（注意：它的 §13 蓝图是 apps/web 的屏幕，含新 IA 里不存在的 Planner） |
