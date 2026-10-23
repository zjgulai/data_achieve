# 数说飞书机器人群聊 @ 门禁加固设计

## 1. 目标

数说飞书机器人必须按会话类型决定是否回答：

- 私聊事件：正常回答，不要求 @。
- 群聊事件：只有消息明确 @ 当前机器人时才回答。
- `chat_type` 缺失或未知：静默忽略。
- 机器人自己发送的消息：静默忽略。

本设计加固现有实现。现有提交 `7fbefe1` 已实现群聊 @ 门禁。本次不重写 webhook、命令执行或飞书客户端。

## 2. 范围

### 2.1 包含

- 抽出可独立测试的消息门禁函数。
- 对缺失或未知 `chat_type` 采用 fail-closed 策略。
- 补齐群聊 @、私聊、畸形事件、加密事件与去重测试。
- 增加门禁判定的可观测日志。
- 验证生产 A 的群聊和私聊行为。

### 2.2 不包含

- 不修改 URL verification 行为。
- 不修改 verification token、`app_id`、加密或签名校验。
- 不修改 allowlist 语义。
- 不修改命令解析、采集执行或回复格式。
- 不修改 TikTok CDO 机器人。
- 不新增环境变量或运行时开关。
- 不新增数据库迁移。

## 3. 现有行为

事件入口为：

```text
POST /api/agents/shusuo/webhook
```

当前处理顺序：

```text
解析请求
→ 解密与验签
→ URL verification
→ token / app_id 校验
→ event_id 去重
→ 后台处理
→ 事件类型过滤
→ 过滤机器人消息
→ 群聊 @ 门禁
→ allowlist
→ 文本解析
→ 命令执行
→ 回复
```

现有群聊门禁使用 `message.chat_type == "group"`。它会读取 `message.mentions`，并将 `mentions[].id.open_id` 与当前机器人的 open_id 比较。

当前缺口：

- 缺少 `chat_type` 时，事件会绕过群聊门禁并按私聊处理。
- 未知 `chat_type` 也会按私聊处理。
- `mentions` 的畸形输入覆盖不足。
- `get_bot_open_id()` 的失败与缓存行为覆盖不足。
- 群聊未 @ 时只断言「没有回复」，未断言「没有执行命令」。
- 加密消息事件尚未走完整的群聊门禁测试。

## 4. 方案选择

### 4.1 采用方案

抽出纯函数门禁，并在事件处理层调用。

建议接口：

```python
from enum import StrEnum
from typing import Any


class MessageGateDecision(StrEnum):
    ALLOW_P2P = "allow_p2p"
    ALLOW_GROUP_MENTION = "allow_group_mention"
    IGNORE_GROUP_NO_MENTION = "ignore_group_no_mention"
    IGNORE_UNKNOWN_CHAT_TYPE = "ignore_unknown_chat_type"
    IGNORE_BOT_ID_UNAVAILABLE = "ignore_bot_id_unavailable"


def decide_message_gate(
    *,
    chat_type: object,
    mentions: object,
    bot_open_id: str | None,
) -> MessageGateDecision:
    ...
```

纯函数返回决策，不执行网络请求，不写日志，不发送回复。

`router.py` 负责：

1. 只在 `chat_type == "group"` 时调用 `get_bot_open_id()`。
2. 将 open_id 和事件字段传给纯函数。
3. 根据决策写日志或继续执行。

### 4.2 不采用配置开关

不新增 `SHUSUO_UNKNOWN_CHAT_TYPE_POLICY`。

原因：

- 生产和本地不应有两套安全语义。
- 缺失或未知类型不是正常业务输入。
- 配置开关会增加测试矩阵和运维成本。
- 需要兼容旧夹具时，应修夹具，不应放宽生产行为。

## 5. 门禁规则

### 5.1 私聊

条件：

```text
chat_type == "p2p"
```

行为：允许继续处理。

私聊不需要 `mentions`。私聊路径不得调用 `get_bot_open_id()`。

### 5.2 群聊

条件：

```text
chat_type == "group"
```

机器人必须先取得自己的 open_id。

允许条件：

```text
mentions 中至少一项满足 mention.id.open_id == bot_open_id
```

以下情况静默忽略：

- `mentions` 缺失。
- `mentions` 为 `null`。
- `mentions` 不是数组。
- 数组元素不是对象。
- mention 缺少 `id`。
- mention 缺少 `open_id`。
- 只 @ 其他成员。
- 只 @all。
- open_id 为空。
- open_id 获取失败。

### 5.3 缺失或未知类型

以下情况静默忽略：

```text
chat_type is None
chat_type == ""
chat_type not in {"p2p", "group"}
```

这是 fail-closed 策略。

### 5.4 机器人消息

`sender.sender_type == "app"` 时继续使用现有短路逻辑。

该短路必须发生在 open_id 查询之前，避免机器人自己发送的消息触发额外网络请求。

## 6. 数据流

```text
Webhook envelope
  │
  ├─ URL verification ──────────────→ 回显 challenge
  │
  ├─ 普通事件认证与去重
  │
  └─ im.message.receive_v1
       │
       ├─ sender_type == app ───────→ 静默忽略
       │
       ├─ chat_type == p2p ─────────→ allowlist → parse → execute → reply
       │
       ├─ chat_type == group
       │    │
       │    ├─ 获取 bot open_id 失败 → warning → 静默忽略
       │    ├─ 未 @ bot ────────────→ debug → 静默忽略
       │    └─ 已 @ bot ────────────→ allowlist → clean → parse → execute → reply
       │
       └─ chat_type 缺失或未知 ────→ warning/debug → 静默忽略
```

## 7. 文本清洗

现有 `clean_text()` 继续删除飞书 mention 占位符：

```text
@_user_1
@_user_2
@_all
```

文本清洗只在门禁通过后执行。

群聊消息中可以同时 @ 多名成员。只要其中一项命中当前机器人，消息即可继续处理。清洗函数必须删除全部 mention 占位符，而不是只删除第一项。

## 8. 日志与错误语义

### 8.1 静默忽略

以下情况不回复群消息：

- 群聊未 @ 当前机器人。
- 缺失或未知 `chat_type`。
- `mentions` 畸形或缺少当前机器人。

日志级别：

- 群聊未 @：`debug`。
- 未知 `chat_type`：`warning`。日志记录安全类型，不记录完整消息正文。
- open_id 获取失败：`warning`。日志记录异常类型，不记录 token。

### 8.2 Webhook 响应

后台消息被静默忽略时，webhook HTTP 响应仍返回现有成功结构：

```json
{"code": 0}
```

原因：事件已被应用接收。没有业务回复不等于 webhook 处理失败。

### 8.3 open_id 获取失败

群聊路径采用 fail-closed：不回复。

私聊路径不依赖机器人 open_id，因此保持正常。

## 9. 兼容性

### 9.1 旧测试夹具

旧夹具若缺少 `chat_type`，必须补成明确的 `p2p` 或 `group`。

不得用「缺字段等同私聊」维持旧测试。

### 9.2 旧事件

系统不回放历史事件。变更只影响发布后收到的新事件。

若上游发送缺少 `chat_type` 的消息事件，系统会静默忽略。日志会记录该问题，供排查事件订阅版本或事件裁剪错误。

### 9.3 @all

`@all` 不等于 @ 当前机器人。只有当前机器人的 open_id 命中时才继续处理。

### 9.4 allowlist

门禁先于 allowlist。

群聊未 @ 时，不回复「没有权限」，避免在群中制造噪音。

群聊已 @ 且用户不在 allowlist 时，保持现有权限提示。

## 10. 测试设计

### 10.1 纯函数测试

必须覆盖：

1. `p2p` 且无 mentions：允许。
2. `group` 且 mention 命中机器人：允许。
3. `group` 且无 mentions：忽略。
4. `group` 且只 @ 其他用户：忽略。
5. `group` 且多个 mention 中包含机器人：允许。
6. `group` 且只有 @all：忽略。
7. `mentions=None`：忽略。
8. `mentions` 为字符串：忽略。
9. `mentions=[None, {}, {"id": {}}]`：忽略。
10. `bot_open_id=""`：忽略。
11. 缺失 `chat_type`：忽略。
12. 未知 `chat_type`：忽略。

### 10.2 路由级测试

必须覆盖：

- 群聊未 @：不调用 `commands.execute()`，不调用回复接口。
- 群聊 @ 当前机器人：执行一次，回复一次。
- 群聊 @ 其他人：不执行，不回复。
- 私聊：不调用 `get_bot_open_id()`，正常执行和回复。
- 机器人自己发送：不查询 open_id，不执行，不回复。
- 群聊 open_id 查询失败：不执行、不回复，记录 warning。
- 群聊非文本消息，且已 @：返回现有文字提示。
- 群聊白名单外用户，且已 @：返回现有权限提示。
- 群聊白名单外用户，未 @：静默忽略。
- 加密群聊有 @：解密后回答。
- 加密群聊无 @：解密后静默。
- 相同 `event_id` 重推：只执行一次。
- 未知 `event_type`：忽略。
- URL verification：保持原测试全部通过。

### 10.3 文本清洗测试

必须覆盖：

```text
@_user_1 @_user_2 帮助 → 帮助
@_all 帮助 → 帮助
```

## 11. 生产发布

### 11.1 变更性质

- 只改 API 代码和测试。
- 不改数据库。
- 不新增迁移。
- 不新增环境变量。
- 不改 console。

因此不需要数据库备份。

### 11.2 发布目标

只部署生产 A：`43.163.92.244`。

生产 B 不在本次范围。

### 11.3 部署步骤

1. 运行目标测试和全量 unit。
2. 运行生产 preflight。
3. 构建 api 镜像。
4. 使用 `docker compose up -d --no-deps api` 替换 api。
5. 重启 edge，使 edge 的 nginx 重新解析 API 容器地址。共享网关缓存的 edge 固定 IP 保持不变。
6. 不重建 edge。
7. 验证 `/api/health` 与数说 `/health`。

### 11.4 生产验收

在专用测试群中执行：

1. 发送普通文本，不 @ 机器人：机器人静默。
2. @ 其他成员：机器人静默。
3. @ 数说机器人并发送「帮助」：机器人回复。
4. 同时 @ 数说机器人和其他成员：机器人回复。
5. @all：机器人静默。
6. 私聊发送「帮助」：机器人回复。

检查日志：

- 有群聊未 @ 的 debug 记录。
- 没有命令执行记录。
- 没有 5xx。
- `bot_open_id` 查询成功或命中缓存。

## 12. 回滚

回滚只需要恢复上一版 api 镜像并重启 api 与 edge。

数据库无变更，不需要执行 downgrade。

回滚后，缺失或未知 `chat_type` 会恢复为按私聊处理。该行为会重新开放群聊绕过风险，回滚记录必须说明这一点。

## 13. 验收判据

以下条件必须全部满足：

- 群聊未 @ 当前机器人时，命令执行次数为 0，回复次数为 0。
- 群聊 @ 当前机器人时，命令执行一次并回复。
- 私聊无 @ 时正常回复。
- 缺失或未知 `chat_type` 时静默忽略。
- 畸形 `mentions` 不导致异常。
- 机器人自己的消息不触发 open_id 查询。
- URL verification、验签、解密、allowlist 和 event_id 去重测试全部通过。
- 生产 A 的群聊与私聊验收通过。

## 14. 风险

### 14.1 群聊静默失效

`get_bot_open_id()` 失败时，所有群聊都会静默。私聊不受影响。

缓解措施：

- 给 open_id 获取补直接测试。
- 记录 warning。
- 在 `/api/agents/shusuo/health` 增加 `bot_identity_ready` 字段，或在发布前独立预检 bot info。

`bot_identity_ready` 不属于本次最小改动。若需要，将它单独立项。

### 14.2 事件字段漂移

飞书若新增 `chat_type` 取值，系统会静默忽略，不会在群内误答。

日志必须让运维人员能发现该新类型。

### 14.3 多进程去重

现有 event_id 去重存于进程内。多 worker 或进程重启后仍可能重复处理。

本次不修改去重实现。它与 @ 门禁是独立问题。
