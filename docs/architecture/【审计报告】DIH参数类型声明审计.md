---
name: dih-param-type-audit
description: DIH 参数类型声明与实际校验的交叉审计：86 个采集器类型中 44 个存在不一致。设计参数 schema、补类型规格或改动采集器参数校验时先读这份，避免采信已证不可信的声明。
---

# DIH 参数类型声明审计

> 审计日期：2026-10-15 · 范围：86 个已注册 collector_type
> 方法：8 个采集器族并行审计，每族经对抗性复核（16 个代理，0 错误）
> 结论：**声明不可直接采信**，须以 `validate_config` 实现为准
> 相邻文档：[整站能力整合方案](./【技术方案】DIH整站能力整合方案.md) · [能力总账](./【能力总账】DIH-平台能力现状与维护手册.md)

## 1. 为什么要读这份

`services/collector_catalog.py` 的 `COLLECTOR_CATALOG` 对 99 个 `collector_type`
声明了 `config_schema`，含 201 个带类型属性。

**这份 schema 从不参与运行时校验**，只被入库并随 `GET /collectors` 返回。
本审计逐条核对了它与实际 `validate_config` 的关系。

**结论：86 个类型中 44 个存在声明与实现不一致，共 86 处。**
直接把它接入校验会拒绝合法调用、放行非法调用。

## 2. 不一致的分布

| 性质 | 数量 | 含义 |
|---|---:|---|
| `type` | 29 | 声明类型与实际校验不符 |
| `undeclared` | 26 | 代码读取并生效，但声明里没有 |
| `name` | 21 | 参数名不一致 |
| `shape` | 7 | 形状不符（如声明 string 实际要 list） |
| `required` | 3 | 必填性不符 |

按采集器族：

| 族 | 类型数 | 有不一致 | 主要问题 |
|---|---:|---:|---|
| misc | 19 | 13 | 命名 10、未声明 8 |
| osint | 23 | 13 | 类型 7、形状 6 |
| social-cn | 11 | 8 | 命名 9、未声明 9 |
| web-and-extract | 11 | 4 | 类型 4、未声明 3 |
| exa | 4 | 4 | 类型 3、未声明 2 |
| apify | 1 | 1 | 类型 4 |
| tikhub | 1 | 1 | 类型 5、未声明 2 |
| **package-registries** | **16** | **0** | 声明与实现一致 |

**16 个包注册类类型是唯一可批量采信的一组。**

## 3. 三个系统性问题

### 3.1 命名分裂：`limit` 与 `max_items`

`config_schema` 声明 `limit: integer`，实现读的是 `max_items`。
**声明 `limit` 的类型有 17 个，没有一个声明 `max_items`。**

同一仓库内还有第二份声明：端点元数据
（`api/routes/collectors.py`）写的是 `optional_params=["max_items"]`。
即**端点元数据与实现一致，`config_schema` 是陈旧的孤立声明**。

同类：`weibo_user_posts` 的必填参数，声明 `user_id`、实现读 `uid`。

### 3.2 声明结构不支持范围与枚举

`config_schema` 只有 `{"required": [...], "properties": {"名": "类型"}}`，
**没有 `min` / `max` / `enum`**。

因此代码里真实存在的约束在目录中完全不可见：

| 约束 | 位置 |
|---|---|
| `public_feed` 的 `max_items` 1–100 | `collectors/public_feed.py` |
| `ecommerce_product_discovery` 的 `max_products` 1–200 | 同类文件 |
| `firecrawl_crawl` 的 `max_pages` 1–500 | `collectors/firecrawl_collector.py` |
| `firecrawl_batch_scrape` 的 `urls` ≤100 | 同类文件 |
| 各 `extract_mode` / `return_format` / `platform_hint` 枚举 | 各采集器 |

消费方（UI、文档）据此会误判可接受取值。

### 3.3 强转代替校验

多处用 `int(...)` 强转代替 `isinstance` 检查，于是数字字符串、浮点、
甚至 `True`（Python 中 `isinstance(True, int)` 为真）都能通过：

- `firecrawl_crawl` 的 `max_pages`
- `twscrape_search` / `twscrape_user_tweets` 的 `limit`
- `bestblogs_articles` 的 `min_score`
- `aliens_eye_recurse` 的 `depth`
- `robin_darkweb_search` 的 `max_results`

**缓解事实**：`services/collector_service.py` 用 `except Exception` 兜住
并记为 failed TaskRun，不会造成未处理崩溃。
产品链路上多数不可达，因为 catalog 层会先拦。
但「直达类实例」与「直写库」路径下可达。

## 4. 已确认的产品缺陷

### 4.1 `playwright_browser` 的 `wait_selector` 对外公告但不可用

**已于 2026-10-15 修复**（见提交 fix(collectors): playwright_browser 的
wait_selector 经 API 传入被静默丢弃）。

服务层 `_validate_playwright_browser_config` 的返回白名单只含
`url` / `wait_for` / `extract_mode`，**遗漏 `wait_selector`**。
该返回值被直接持久化为 `source.config` 与 `task.config`，
所以经 API 传入的值永远到不了采集器。

而端点元数据对外公告 `optional_params=["wait_for", "wait_selector"]`，
类内 `validate_config` 也支持它——两者因此无法生效。

修法：校验并透传；非字符串或空白串拒绝；未传归一为 `None`。

### 4.2 Apify 端点的超时覆盖不生效

`apify_actor` 的服务层返回白名单固定为
`{actor_id, actor_input, max_items, max_total_charge_usd}`，**无 `run_timeout_seconds`**。

后果链：丢弃后回落 endpoint 默认；`SLOW_ENDPOINT_TIMEOUT_SECONDS`
无 apify 键；最终用 `DEFAULT_COLLECTION_TIMEOUT_SECONDS=300.0`。
而构造处默认 600——**内层自等 600s 会被外层 300s 先取消**。

同类：`tikhub_social`、`exa_*` 也丢该参数；`passthrough` 类型保留。
**此项未修。**

## 5. 对参数 schema 设计的影响

**不要把 `COLLECTOR_CATALOG` 的声明当作校验来源。**

修正后的做法：

1. **以 `validate_config` 实现为事实源。**
   每条规格都要与实际校验核对，不能凭声明推断。
2. **包注册类 16 个类型可批量采信**，但仍须从实现补齐上下界。
3. **扩展契约以支持 `min` / `max` / `enum`。**
   现有结构不支持，是必须补的能力。
4. **端点元数据与 `config_schema` 是两份独立声明。**
   多数情况下元数据与实现一致，但仍须逐条核对，不可假设。
5. **收敛两处重复校验。**
   本缺陷即由「服务层与类层各写一份」造成，改一处易漏另一处。
   收敛会增加改动面，须单独评估。

## 6. 未覆盖项

- 未核验 62 个 `tikhub_social` 端点枚举的逐项正确性。
- 未核验 95 个 `apify_actor` 端点各自的上游 schema 与声明是否对应。
- 未追踪类级 `CollectorError` 与目录级 `CollectorConfigError` 的错误映射差异。
- 未系统比对端点元数据与 `config_schema` 两份声明本身的一致性。
- 全部结论均为静态源码核对，未做生产实测。
