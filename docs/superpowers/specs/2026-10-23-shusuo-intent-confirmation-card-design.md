---
name: shusuo-intent-confirmation-card-design
description: SP-12 数说意图层、一次性确认 token、飞书确认卡、预检和统一回复模板设计。
---

# SP-12 数说意图层与确认卡设计

## 1. 目标

数说把自然语言场景转换为采集提案。自然语言不能直接触发采集。用户必须通过飞书确认卡或文本 token 确认。

本期目标：

1. 接通并强化 `intents.build_proposal`。
2. 提案执行前做参数与实时状态预检。
3. 增加一次性确认 token，TTL 为 300 秒。
4. 增加飞书确认卡与卡片回调。
5. 统一提案、成功、失败和错误回复。
6. 所有单条回复不超过 6000 字符。

不新增数据库迁移。API 重启后未确认提案失效，用户必须重新发起。用户已接受该限制。

## 2. 已确认的产品口径

1. 采用内存 token + 飞书交互卡片。
2. 每个 `chat_id + open_id` 只保留一个待确认提案。
3. 新提案替换旧提案，旧 token 立即失效。
4. 费用未知时允许确认后执行。
5. 费用未知的卡片必须显示“费用未知，按上游实际计费”。
6. 默认数量为 10，硬上限为 50。
7. 自然语言场景必须确认。
8. 显式 `采集 <端点> key=value` 保持直接执行，但必须通过同一预检。
9. 文本 `确认 <token>` 和 `取消 <token>` 作为卡片失败时的降级入口。

## 3. 架构

### 3.1 `intents.py`

`build_proposal` 只把文本转换为 `Proposal` 或澄清提示。它不得访问网络、数据库或执行采集。

`Proposal` 字段：

- `endpoint_type`
- `params`
- `title`
- `note`
- `estimated_items`
- `cost_notice`

规则：

1. 数量默认 10，范围 1 到 50。非法值不自动截断，返回修改提示。
2. URL host 必须精确匹配目标域名，或是目标域名的子域名。拒绝 `evil-tiktok.com` 一类伪域名。
3. YouTube 支持 `youtu.be/<id>`、`watch?v=`、`/shorts/`、`/embed/`。
4. Amazon 价格参数使用采集器要求的对象数组。
5. 缺平台、URL、账号或关键词时，每次只询问一个必要参数。
6. 低置信度自由文本走只读问答，不生成采集操作。

### 3.2 `proposal_store.py`

新增独立的内存提案存储。

`PendingProposal` 字段：

- `token`
- `chat_id`
- `open_id`
- `proposal`
- `params_hash`
- `created_at`
- `expires_at`
- `message_id`
- `card_message_id`

接口：

- `replace_pending(chat_id, open_id, proposal)`
- `peek_pending(token, chat_id, open_id)`
- `consume_pending(token, chat_id, open_id)`
- `cancel_pending(token, chat_id, open_id)`
- `clear_expired()`

约束：

1. token 用密码学安全随机数生成。
2. token 绑定 `chat_id + open_id + endpoint_type + params_hash`。
3. TTL 固定为 300 秒。
4. 新提案替换同会话旧提案。
5. `consume_pending` 先删除再返回，保证单进程内只消费一次。
6. 存储有全局容量上限。每次读写清理过期项。
7. 日志只记录 token 摘要，不记录完整 token 或完整参数。

### 3.3 `capabilities.py`

新增结构化 `preflight_proposal()`。

`PreflightResult` 字段：

- `allowed`
- `availability`
- `errors`
- `warnings`
- `normalized_params`
- `cost_notice`

检查顺序：

1. 端点存在。
2. 必填参数齐全。
3. 没有未知参数。
4. 数量在 1 到 50。
5. 当前实时状态为 `verified`。
6. `disabled`、`config-gated`、`degraded`、`empty`、`untested` 和策略阻断均拒绝。
7. 状态读取失败时不能 fail-open。静态状态也未知时拒绝确认，并提示稍后重试。
8. 费用未知时增加警告，但允许提案和确认。

发卡片前预检一次。用户确认时强制刷新实时状态并再次预检。确认时预检失败不消费 token。

显式 `采集` 命令也使用这套预检。

### 3.4 `cards.py`

新增纯函数生成飞书卡片 JSON。函数不访问数据库或网络。

卡片显示：

- 意图标题
- 端点
- 参数摘要
- 预计记录数
- 费用提示
- 失效时间
- 确认按钮
- 取消按钮

按钮 value 只包含 action 和 token：

```json
{
  "action": "confirm",
  "token": "..."
}
```

完整参数只保存在服务端，不能放入卡片。

### 3.5 `commands.py`

`parse_command` 支持：

- `确认 <token>`
- `取消 <token>`
- 裸 `确认` 和裸 `取消`，用于兼容单个待确认提案

`execute` 增加 `open_id`，并按以下流程处理：

#### 自然语言意图

1. 构建提案。
2. 预检。
3. 替换旧提案。
4. 返回卡片和文本降级内容。
5. 不执行采集。

#### 确认

1. `peek_pending` 校验 token、会话、用户和过期时间。
2. 强制刷新状态并再次预检。
3. 预检失败时不消费 token。
4. 预检成功后先原子消费 token。
5. 调用采集。
6. 采集失败不恢复 token，防止重复计费。

#### 取消

按 token 取消。重复取消或失效 token 返回已失效提示。

### 3.6 `router.py`

文本消息调用 `commands.execute` 时传入 `chat_id` 与 `open_id`。

新增：

```text
POST /api/agents/shusuo/card-action
```

处理顺序：

1. 读取原始 body。
2. 处理 URL challenge。
3. 加密事件先验签再解密。
4. 校验 Verification Token 和 App ID。
5. action 只允许 `confirm` 与 `cancel`。
6. 校验操作人在白名单。
7. 校验操作人是提案发起人。
8. 校验 token 未过期、未消费、未被替换。
9. 三秒内返回处理中 toast。
10. 后台任务再次预检、消费 token、执行采集并更新原卡片。

卡片发送失败时退回文本 token。

URL challenge 仍只回显 challenge，不强制比对 Verification Token，避免飞书配置死锁。

### 3.7 `lark_client.py`

增加或复用：

- `reply_card(message_id, card)`
- `update_card(message_id, card)`

卡片请求失败必须抛结构化错误。调用方负责降级文本或记录错误。

### 3.8 `replies.py`

新增统一回复模板：

- 提案
- 采集成功
- 采集失败
- 参数或状态错误
- 提案过期
- 提案已取消
- 提案已消费或被替换

采集结果包含：

- 状态
- 端点
- 记录数
- run ID
- 运行详情链接
- 耗时
- 用量和成本
- 最多三条记录摘要
- 下一步建议

`fit_text()` 统一执行：

1. 先脱敏，再截断。
2. 回复正文不超过 6000 字符。
3. ack 也不超过 6000 字符。
4. 单行标题不超过 120 字符。
5. URL 不超过 200 字符。
6. 不返回异常类名、堆栈、Cookie、Secret 或内部策略拒绝原文。

## 4. 错误处理

| 场景 | 用户提示 | token 处理 |
| --- | --- | --- |
| token 过期 | 提案已过期，请重新发起 | 清理 |
| token 已消费 | 提案已执行或已失效 | 不执行 |
| 新提案替换旧提案 | 该提案已被新提案替换 | 不执行 |
| 非发起人点击 | 只有提案发起人可以操作 | 不消费 |
| 不在白名单 | 没有使用权限 | 不消费 |
| 端点状态变化 | 当前不可执行，并给下一步 | 不消费 |
| 参数预检失败 | 显示缺失或错误参数 | 不消费 |
| 卡片发送失败 | 返回文本 token | 保留 |
| 上游采集失败 | 原因摘要与重试建议 | 已消费，不自动重试 |
| 重复点击 | 已处理 | 不重复调用 |
| API 重启 | 提案已失效，请重新发起 | 状态已丢失 |

开始调用上游前必须先消费 token。

## 5. 安全约束

1. 卡片回调 fail-closed。
2. 普通事件必须匹配 Verification Token。
3. App ID 必须匹配。
4. action 必须在白名单内。
5. token 必须绑定当前用户和会话。
6. 卡片执行入口在白名单为空时拒绝操作。
7. 日志不能写完整 token、完整参数或凭据。
8. 按钮 value 不能携带完整参数。
9. 重复回调不能重复执行上游。

## 6. 测试

### 6.1 意图解析

- 七类场景生成正确提案。
- 缺参数时只问一个问题。
- 数量默认 10，最大 50。
- 非法数量被拒绝。
- 伪造域名被拒绝。
- YouTube 常见 URL 形态均可识别。
- 自由问答不触发采集。

### 6.2 token

- 新提案替换旧提案。
- token 绑定用户与会话。
- 五分钟过期。
- 只能消费一次。
- 重复点击不执行。
- 越权用户不能确认。
- API 重启后提案失效。

### 6.3 预检

- verified 允许。
- 其余状态拒绝。
- 必填参数和未知参数校验。
- 数量边界校验。
- 费用未知允许，但出现警告。
- 确认时重新读取状态。

### 6.4 卡片与回调

- 卡片字段与按钮正确。
- 卡片失败降级文本。
- confirm 和 cancel 回调成功。
- 无效签名、错误 App ID、错误 token、越权用户被拒绝。
- 更新卡片失败不重复采集。

### 6.5 回复

- 成功、失败、过期、取消模板统一。
- 文本不超过 6000 字符。
- 样例最多三条。
- 敏感字段和内部错误不泄漏。

## 7. 发布

1. 仅部署生产 A `43.163.92.244`。
2. 部署前备份数据库和 env。本功能无迁移。
3. 只重建 API，不重建 edge。
4. 在飞书后台配置卡片回调：
   `https://scrapy.luteos.com/api/agents/shusuo/card-action`
5. 验收确认、取消、替换、过期、越权、重复点击、超长结果和显式采集。
6. 更新 SP-Agent-TODO 与飞书日报。

## 8. 明确不做

1. 不建确认表。
2. 不支持跨 API 重启恢复提案。
3. 不做每日额度与 host 预检；留给 SP-13。
4. 不做 LLM 规划器。
5. 不做执行中的上游取消。
6. 不做费用价格簿；费用未知时以确认卡和数量上限控制风险。
