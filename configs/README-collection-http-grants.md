# 受控 HTTP 采集的域名授权配置

## 用途

`collection_http_grants` 是服务端配置。请求参数不能授予网络访问。

只有四个受控 HTTP 采集器读取这份配置：

- `generic_web`
- `public_feed`
- `ecommerce_product_page`
- `ecommerce_product_discovery`

每个采集器必须有一项配置。配置为空时，这四个采集器拒绝执行。

## 文件

`configs/collection-http-grants.example.json` 是示例文件。示例主机只用于说明格式。上线前必须替换为已获授权的站点。

## 格式

文件内容是 JSON 数组。每项是一个对象。

| 字段 | 必填 | 规则 |
| --- | --- | --- |
| `collector_type` | 是 | 必须是上面四个采集器之一。同一 collector_type 只能出现一次。 |
| `hosts` | 是 | 必须包含 1 到 5 个精确主机名。 |
| `expires_at` | 是 | 必须是 ISO-8601 时间字符串。必须带时区。必须是未来时间。推荐用 `Z` 结尾的 UTC 时间。 |
| `max_requests` | 否 | 必须是 1 到 50 的整数。默认 50。表示一次采集的请求上限。 |
| `max_domains` | 否 | 必须是 1 到 5 的整数。默认 5。表示一次采集的域名上限。不得小于 `hosts` 的数量。 |
| `timeout_seconds` | 否 | 必须是大于 0 且不超过 60 的数字。默认 60。表示一次采集的总时长上限。 |

`hosts` 的每个值必须满足下面的条件：

- 必须是公网主机名。
- 不得是 IP 地址。
- 不得含协议、路径、端口或通配符。
- 不得以 `.localhost`、`.local` 或 `.onion` 结尾。

## 使用方法

1. 复制示例文件。替换 `hosts` 与 `expires_at`。
2. 把 JSON 压缩为一行，写入环境变量 `COLLECTION_HTTP_GRANTS`。`.env` 中的多行值会被截断。
3. 设置 `COLLECTION_NETWORK_MODE=restricted`。
4. 重启 API 进程。

`.env` 示例：

```dotenv
COLLECTION_NETWORK_MODE=restricted
COLLECTION_HTTP_GRANTS=[{"collector_type":"public_feed","hosts":["feeds.bbci.co.uk"],"expires_at":"2027-12-31T23:59:59Z"}]
```

## 启动校验

`create_app()` 调用 `validate_collection_http_grants()`。它校验整个数组。

配置有问题时，应用记录 warning 事件 `collection_http_grants_invalid`。事件包含 `issue_count` 与 `issues` 两个字段。`issues` 列出全部问题。每条问题指明数组下标、字段名和期望值。

配置有问题不会阻止应用启动。生产环境可能暂时没有授权。

## 运行期校验

`http_grant()` 在每次采集前再次校验。无效或过期的配置抛出 `CollectionPolicyDenied`，错误码是 `collection_policy_denied`。

同一 collector_type 出现两项时，`http_grant()` 报「缺少唯一的服务端域名批准配置」。

## 安全边界

- grant 只批准固定公网主机名。每个请求发出前都检查主机。重定向逐跳检查。
- 请求数、域名数和总时长都受上限约束。超出时错误码是 `outbound_budget_exceeded`。
- grant 不解除法律、站点条款和 robots.txt 的约束。运营方必须先取得站点许可，再填写主机。
- 配置文件只含域名和时间。不得写入密钥、Cookie 或登录凭据。
- 过期后必须更新配置。系统不使用过期的 grant。
