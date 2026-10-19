---
name: workflow-shusuo-feishu-bot-stable
description: 数说飞书机器人的接入、事件回调配置、生产部署与排障手册。
---

# 数说飞书机器人：接入与运维

> 应用：`数说`（`cli_aa10f960fbb99cb3`）· 生产 A `https://scrapy.luteos.com`
> 回调地址：`POST /api/agents/shusuo/webhook`
> 代码：`apps/api/src/data_intelligence_hub/agents/shusuo/`

## 1. 架构

```
飞书用户 → 数说机器人 → POST /api/agents/shusuo/webhook
                              │
                              ├─ URL 校验（url_verification）
                              ├─ 验签 + AES 解密（Encrypt Key）
                              ├─ 事件去重（event_id，10 分钟）
                              └─ 3 秒内返回 {"code":0}
                                       │ BackgroundTasks
                                       ▼
                       命令解析（帮助/平台/能力/详情/采集/总览）
                                       │
                                       ├─ 能力目录 platform_packages
                                       ├─ 实时可用性 get_provider_status（60 秒缓存）
                                       └─ 采集 collect_capability（与 MCP 同一服务层）
                                       │
                                       ▼
                        飞书回复：POST /im/v1/messages/{message_id}/reply
```

关键点：

- 飞书要求 3 秒内返回 HTTP 200。处理方法放进 `BackgroundTasks`。
- 同一 `event_id` 只处理一次，避免飞书重推导致重复采集。
- 采集前检查实时可用性：`config-gated`、`policy_block_reason` 非空、`disabled` 一律拒绝。
- 默认写入项目 `7fd6ed55-7b0c-5482-92f3-d03130168b70`（竞品网站采集哨兵）。

## 2. 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `LARK_SHUSUO_APP_ID` | 是 | `cli_aa10f960fbb99cb3` |
| `LARK_SHUSUO_APP_SECRET` | 是 | 应用密钥 |
| `LARK_SHUSUO_VERIFICATION_TOKEN` | 建议 | 与飞书「加密策略」中的 Verification Token 一致 |
| `LARK_SHUSUO_ENCRYPT_KEY` | 建议 | 与飞书「加密策略」中的 Encrypt Key 一致；配置后事件为密文 |
| `SHUSUO_DEFAULT_PROJECT_ID` | 否 | 默认采集项目 |
| `SHUSUO_CONSOLE_BASE_URL` | 否 | 默认 `https://scrapy.luteos.com`，用于回结果链接 |
| `SHUSUO_ALLOWED_OPEN_IDS` | 否 | 逗号分隔白名单；当前生产 A 已配置 8 位群成员 |

生产 A 的值放在 `/opt/data-achieve-scrapy/.env.production`。compose 的 `api.environment`
必须列出这些键（`configs/deploy/scrapy/docker-compose.yml`）；只改 env 文件不生效。

## 3. 飞书事件订阅配置

事件订阅必须用 **v7** 接口。v6 的 `PATCH /application/v6/applications/:app_id`
只更新应用分组信息，不会写请求地址。

```http
PATCH https://open.feishu.cn/open-apis/application/v7/applications/cli_aa10f960fbb99cb3/config
Authorization: Bearer <tenant_access_token>
Content-Type: application/json

{
  "event": {
    "subscription_type": "webhook",
    "request_url": "https://scrapy.luteos.com/api/agents/shusuo/webhook"
  },
  "event_and_callback_encrypt_strategy": {
    "encryption_key": "<Encrypt Key，1-32 字符>",
    "verification_token": "<Verification Token，1-32 字符>"
  }
}
```

所需权限：`application:application:patch`。授权深链：

```
https://open.feishu.cn/app/cli_aa10f960fbb99cb3/auth?q=application:application:patch&op_from=openapi&token_type=tenant
```

注意：

- `event.request_url` 会即时校验。校验失败返回 `210042`。
- 校验请求可能用**旧** Encrypt Key 和旧 token。因此：
  - 服务端必须已经配置正确的 Encrypt Key；
  - URL 校验请求不强制比对 Verification Token（本实现只告警，仍回显 challenge），
    否则会形成 210042 死锁。
- `event.add_events` 可省略；已订阅的事件保持不变。需要新增时传
  `{"add_events":["im.message.receive_v1"]}`。
- 修改 Encrypt Key 会改变后续事件的加密密钥。修改后同步更新
  `LARK_SHUSUO_ENCRYPT_KEY` 并重启 api。

## 4. 部署

> **部署范围（2026-10-19 决定）**：只在生产 A `scrapy.luteos.com` 部署。生产 B
> `scrapy.lute-tlz-dddd.top` 暂不部署。飞书事件请求地址只能指向一个 URL，当前指向 A；
> 若以后要让 B 接事件，需要另一个飞书应用或切换请求地址。


```bash
# 服务器
cd /opt/data-achieve-scrapy/app
git -c http.version=HTTP/1.1 fetch origin <branch>
git merge --ff-only FETCH_HEAD
sudo docker compose -f configs/deploy/scrapy/docker-compose.yml \
  --env-file /opt/data-achieve-scrapy/.env.production up -d --build api
```

验收：

```bash
curl -s https://scrapy.luteos.com/api/agents/shusuo/health
# {"app_id":"cli_...","ready":true,"encrypt_enabled":true,
#  "verification_token_configured":true,...}

curl -s -X POST https://scrapy.luteos.com/api/agents/shusuo/webhook \
  -H 'Content-Type: application/json' \
  -d '{"type":"url_verification","challenge":"probe"}'
# {"challenge":"probe"}
```

端到端：在飞书单聊数说（群里要 @数说）发送「帮助」。

## 5. 命令

| 命令 | 作用 |
|---|---|
| `帮助` | 命令说明 |
| `总览` | 能力统计（实时可用性口径） |
| `平台 [关键词]` | 平台包列表 |
| `能力 <平台或关键词>` | 端点列表，带可用性 |
| `详情 <端点>` | 参数、最近实测、坑点、策略限制 |
| `采集 <端点> [key=value ...]` | 立即采集，返回记录数与运行链接 |
| `结果 <run_id>` | 查看一次运行的前 5 条原始记录 |
| `搜 [平台] <关键词>` | 社媒搜索；省略平台走 Exa |
| `评论 <URL>` | TikTok / Reddit / YouTube 评论 |
| `账号 <平台> <handle>` | TikTok / Instagram / X 资料 |
| `热点 [平台]` | 抖音 / X / YouTube / Reddit |
| `新闻 <关键词>` | 新闻搜索 |
| `选品 <关键词>` | AliExpress 选品 |
| `价格 <URL 或 ASIN>` | Amazon 价格追踪 |
| `确认` / `取消` | 执行或放弃当前场景提案 |

场景命令只生成提案，回复「确认」后才执行采集；提案 10 分钟有效。

示例：

```
能力 github
详情 tikhub_reddit_search
采集 tikhub_reddit_search keyword=AI max_items=5
```

参数规则：`key=value`；`true/false` 转布尔；整数、小数转数字；以 `[` 或 `{`
开头的值按 JSON 解析。

## 5.1 自由文本问答

未识别的文本会调用 DeepSeek 只读问答：只回答问题，不执行采集；调用失败或未配置
`DEEPSEEK_API_KEY` 时回退到帮助菜单。配置项沿用 `DEEPSEEK_API_KEY`、
`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`（compose 已注入）。

## 6. 排障

| 现象 | 原因 | 处置 |
|---|---|---|
| 飞书保存地址报 `210042` | URL 校验失败 | 看 edge 日志是否有 `POST /api/agents/shusuo/webhook` |
| 日志 `encrypt key is not configured`，响应 400、长度 50 | 飞书事件是密文，服务端没有 Encrypt Key | 配置 `LARK_SHUSUO_ENCRYPT_KEY` |
| 日志 `invalid verification token`，响应 403 | 事件 token 与服务端不一致 | 对齐飞书「加密策略」与 env，然后重启 |
| `code: 99991672` | 缺少 `application:application:patch` | 打开授权深链并开通 |
| 回调 200 但没有回复 | 事件类型不是 `im.message.receive_v1`（例如 `task.task.update_tenant_v1`） | 在单聊或群里 @机器人 发文字 |
| 采集被拒 `config-gated` | 缺 Provider 配置或外访策略限制 | 用「详情」看 `missing_configuration` / `policy_block_reason` |
| 采集成功但 0 条 | 上游改版或种子参数不合适 | 先看原始响应；状态会显示「可用但最近为空」 |

诊断日志（标准 logging，进 `docker logs`）：

```
shusuo_event_received event_type=... event_id=...
shusuo_message_received message_type=... chat_id=... open_id=...
shusuo_command_handled command=... argument=...
shusuo_collect_failed endpoint_type=...
```

## 7. 安全

- `url_verification` 只回显 challenge，不产生副作用；事件强制校验 token。
- 配置 Encrypt Key 时，校验 `X-Lark-Signature = SHA256(timestamp + nonce + EncryptKey + body)`。
- `SHUSUO_ALLOWED_OPEN_IDS` 按用户限制；当前已加入群内 8 位成员。新增成员时改 env 并重启 api。
- 采集会消耗上游额度。当前只有显式 `采集` 命令会触发，不会根据自由文本自动采集。
