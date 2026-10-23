# 数说飞书机器人群聊 @ 门禁加固实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 加固数说飞书机器人的会话门禁：私聊正常回答，群聊仅在 @ 当前机器人时回答，缺失或未知 `chat_type` 时静默忽略。

**Architecture:** 新建无 I/O 的 `gate.py`，将会话类型与 mention 判定集中为纯函数。`router.py` 继续负责获取机器人 open_id、记录结构化日志和编排命令；URL verification、认证、加密、allowlist 与事件去重保持原路径。生产发布只替换 API 容器并重启现有 edge 容器，使 edge 内的 nginx 重新解析 API 地址；不得重建 edge。

**Tech Stack:** Python 3.12、FastAPI、Pydantic Settings、httpx、structlog、pytest、Docker Compose、GitNexus。

## Global Constraints

- 群聊只有 `mentions[].id.open_id` 精确命中当前机器人 open_id 时才继续处理。
- 私聊 `chat_type == "p2p"` 不要求 mention，也不得查询机器人 open_id。
- `chat_type` 缺失、空串或未知值时必须静默忽略。
- `@all` 与 @ 其他成员不得触发回答。
- `mentions` 缺失、`null`、非数组或元素畸形时不得抛异常。
- 机器人自己发送的消息必须在 open_id 查询前短路。
- URL verification、verification token、`app_id`、加密、签名、allowlist 与 `event_id` 去重语义不得改变。
- 不新增环境变量、依赖、数据库迁移或前端改动。
- 所有新增日志使用 `structlog`；不得启用全仓标准库 INFO 日志。
- 写中文文件后必须用临时文件、`fsync()` 与 `os.replace()` 重写，并确认 NUL 字节数为 0。
- 编辑既有函数前必须运行 GitNexus `impact`。`risk: UNKNOWN` 时必须用文本搜索补证。
- 每个任务先写失败测试，再写最小实现，再运行验证，再提交。

---

## File Structure

- Create: `apps/api/src/data_intelligence_hub/agents/shusuo/gate.py`
  - 只定义门禁枚举和纯函数。
  - 不导入 FastAPI、httpx、配置、命令或飞书客户端。
- Create: `apps/api/tests/unit/test_shusuo_gate.py`
  - 覆盖纯函数的全部会话类型与畸形 mention 输入。
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/router.py`
  - 调用纯函数。
  - 仅群聊查询机器人 open_id。
  - 用 `structlog` 记录门禁决策。
- Modify: `apps/api/tests/unit/test_shusuo_router.py`
  - 覆盖执行短路、open_id 查询、加密消息、去重、allowlist 与文本清洗。
- Modify: `apps/api/tests/unit/test_shusuo_lark_client.py`（若文件不存在则创建）
  - 覆盖 `get_bot_open_id()` 成功、缓存、API 错误与 HTTP 异常。
- Modify: `docs/workflows/workflow-shusuo-feishu-bot-stable.md`
  - 记录 fail-closed 语义、验收步骤与排障方法。
- Modify: `docs/superpowers/specs/2026-10-23-shusuo-group-mention-gate-design.md`
  - 仅修正发布术语：重启 edge 使 edge nginx 重新解析 API，不是共享网关重新解析 API。

---

### Task 1: 建立纯函数门禁

**Files:**
- Create: `apps/api/src/data_intelligence_hub/agents/shusuo/gate.py`
- Create: `apps/api/tests/unit/test_shusuo_gate.py`

**Interfaces:**
- Consumes: 原始 `chat_type: object`、`mentions: object`、`bot_open_id: str | None`。
- Produces:
  - `MessageGateDecision(StrEnum)`
  - `decide_message_gate(*, chat_type: object, mentions: object, bot_open_id: str | None) -> MessageGateDecision`

- [ ] **Step 1: 确认新模块没有现有调用方**

运行：

```bash
cd /Users/lute/Project/data_scrapy
node .gitnexus/run.cjs query "shusuo message gate chat_type mentions" --repo .
grep -rn "MessageGateDecision\|decide_message_gate" apps/api/src apps/api/tests || true
```

预期：没有同名实现。记录现有门禁只位于 `router.py`。

- [ ] **Step 2: 写纯函数失败测试**

创建 `apps/api/tests/unit/test_shusuo_gate.py`：

```python
from __future__ import annotations

import pytest

from data_intelligence_hub.agents.shusuo.gate import (
    MessageGateDecision,
    decide_message_gate,
)


@pytest.mark.parametrize(
    ("chat_type", "mentions", "bot_open_id", "expected"),
    [
        ("p2p", None, None, MessageGateDecision.ALLOW_P2P),
        (
            "group",
            [{"id": {"open_id": "ou_bot"}}],
            "ou_bot",
            MessageGateDecision.ALLOW_GROUP_MENTION,
        ),
        ("group", [], "ou_bot", MessageGateDecision.IGNORE_GROUP_NO_MENTION),
        (
            "group",
            [{"id": {"open_id": "ou_other"}}],
            "ou_bot",
            MessageGateDecision.IGNORE_GROUP_NO_MENTION,
        ),
        (
            "group",
            [
                {"id": {"open_id": "ou_other"}},
                {"id": {"open_id": "ou_bot"}},
            ],
            "ou_bot",
            MessageGateDecision.ALLOW_GROUP_MENTION,
        ),
        (
            "group",
            [{"key": "@_all", "id": {}}],
            "ou_bot",
            MessageGateDecision.IGNORE_GROUP_NO_MENTION,
        ),
        (
            "group",
            None,
            "ou_bot",
            MessageGateDecision.IGNORE_GROUP_NO_MENTION,
        ),
        (
            "group",
            "not-a-list",
            "ou_bot",
            MessageGateDecision.IGNORE_GROUP_NO_MENTION,
        ),
        (
            "group",
            [None, {}, {"id": "bad"}, {"id": {}}],
            "ou_bot",
            MessageGateDecision.IGNORE_GROUP_NO_MENTION,
        ),
        (
            "group",
            [{"id": {"open_id": "ou_bot"}}],
            "",
            MessageGateDecision.IGNORE_BOT_ID_UNAVAILABLE,
        ),
        (None, [], None, MessageGateDecision.IGNORE_UNKNOWN_CHAT_TYPE),
        ("", [], None, MessageGateDecision.IGNORE_UNKNOWN_CHAT_TYPE),
        ("topic", [], None, MessageGateDecision.IGNORE_UNKNOWN_CHAT_TYPE),
    ],
)
def test_decide_message_gate(
    chat_type: object,
    mentions: object,
    bot_open_id: str | None,
    expected: MessageGateDecision,
) -> None:
    assert (
        decide_message_gate(
            chat_type=chat_type,
            mentions=mentions,
            bot_open_id=bot_open_id,
        )
        is expected
    )
```

- [ ] **Step 3: 运行测试并确认红灯**

运行：

```bash
cd /Users/lute/Project/data_scrapy/apps/api
uv run pytest tests/unit/test_shusuo_gate.py -q
```

预期：FAIL，提示 `data_intelligence_hub.agents.shusuo.gate` 不存在。

- [ ] **Step 4: 写最小纯函数实现**

创建 `apps/api/src/data_intelligence_hub/agents/shusuo/gate.py`：

```python
"""数说飞书消息的会话门禁。

本模块只做纯数据判断。它不读配置、不发请求、不写日志、不发送回复。
"""

from __future__ import annotations

from enum import StrEnum


class MessageGateDecision(StrEnum):
    ALLOW_P2P = "allow_p2p"
    ALLOW_GROUP_MENTION = "allow_group_mention"
    IGNORE_GROUP_NO_MENTION = "ignore_group_no_mention"
    IGNORE_UNKNOWN_CHAT_TYPE = "ignore_unknown_chat_type"
    IGNORE_BOT_ID_UNAVAILABLE = "ignore_bot_id_unavailable"


def _mentions_bot(mentions: object, bot_open_id: str) -> bool:
    if not isinstance(mentions, list):
        return False
    for mention in mentions:
        if not isinstance(mention, dict):
            continue
        mention_id = mention.get("id")
        if not isinstance(mention_id, dict):
            continue
        if str(mention_id.get("open_id", "")) == bot_open_id:
            return True
    return False


def decide_message_gate(
    *,
    chat_type: object,
    mentions: object,
    bot_open_id: str | None,
) -> MessageGateDecision:
    if chat_type == "p2p":
        return MessageGateDecision.ALLOW_P2P
    if chat_type != "group":
        return MessageGateDecision.IGNORE_UNKNOWN_CHAT_TYPE
    if not bot_open_id:
        return MessageGateDecision.IGNORE_BOT_ID_UNAVAILABLE
    if _mentions_bot(mentions, bot_open_id):
        return MessageGateDecision.ALLOW_GROUP_MENTION
    return MessageGateDecision.IGNORE_GROUP_NO_MENTION
```

- [ ] **Step 5: 字节级重写并检查 NUL**

运行：

```bash
cd /Users/lute/Project/data_scrapy
python3 - <<'PY'
import os
from pathlib import Path

for name in (
    "apps/api/src/data_intelligence_hub/agents/shusuo/gate.py",
    "apps/api/tests/unit/test_shusuo_gate.py",
):
    path = Path(name)
    data = path.read_bytes().rstrip(b"\x00")
    if b"\x00" in data:
        raise SystemExit(f"embedded NUL: {name}")
    if not data.endswith(b"\n"):
        data += b"\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
PY
```

- [ ] **Step 6: 运行测试和 lint，确认绿灯**

运行：

```bash
cd /Users/lute/Project/data_scrapy/apps/api
uv run pytest tests/unit/test_shusuo_gate.py -q
uv run ruff check --no-cache \
  src/data_intelligence_hub/agents/shusuo/gate.py \
  tests/unit/test_shusuo_gate.py
uv run ruff check --no-cache --select E902 .
```

预期：13 个参数化场景全部通过；ruff 无错误。

- [ ] **Step 7: 提交纯函数门禁**

```bash
cd /Users/lute/Project/data_scrapy
git add \
  apps/api/src/data_intelligence_hub/agents/shusuo/gate.py \
  apps/api/tests/unit/test_shusuo_gate.py
git commit -m "feat(shusuo): 抽出飞书消息门禁纯函数"
```

---

### Task 2: 在 webhook 编排层接入 fail-closed 门禁

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/router.py:139-209`
- Modify: `apps/api/tests/unit/test_shusuo_router.py:425-495`

**Interfaces:**
- Consumes:
  - `decide_message_gate(*, chat_type: object, mentions: object, bot_open_id: str | None) -> MessageGateDecision`
  - `lark_client.get_bot_open_id() -> str`
- Produces: `_handle_envelope()` 的新会话语义。外部 HTTP 接口与返回结构不变。

- [ ] **Step 1: 运行 GitNexus 影响分析**

运行：

```bash
cd /Users/lute/Project/data_scrapy
node .gitnexus/run.cjs impact "_handle_envelope" --direction upstream --repo .
node .gitnexus/run.cjs impact "shusuo_webhook" --direction upstream --repo .
```

预期：索引可能返回 `risk: UNKNOWN`，因为 BackgroundTasks 与 FastAPI 框架调用不易解析。必须补文本搜索：

```bash
grep -rn "_handle_envelope\|shusuo_webhook" \
  apps/api/src apps/api/tests --include='*.py'
```

记录：生产调用方为 `background_tasks.add_task(_handle_envelope, envelope)`；测试直接调用 `_handle_envelope()`。

- [ ] **Step 2: 扩展测试 helper 以观察命令执行和 open_id 查询**

在 `tests/unit/test_shusuo_router.py` 的 `_run_group_case` 附近新增：

```python
from dataclasses import dataclass


@dataclass
class GroupCaseResult:
    replies: list[str]
    executed: list[commands.Command]
    bot_open_id_calls: int


async def _run_message_case(
    monkeypatch,
    envelope: dict[str, object],
    *,
    bot_open_id: str = "ou_bot",
    bot_open_id_error: Exception | None = None,
) -> GroupCaseResult:
    replies: list[str] = []
    executed: list[commands.Command] = []
    calls = 0

    async def fake_reply(message_id: str, text: str) -> str:
        replies.append(text)
        return "om_reply"

    async def fake_bot_open_id() -> str:
        nonlocal calls
        calls += 1
        if bot_open_id_error is not None:
            raise bot_open_id_error
        return bot_open_id

    async def fake_execute(
        command: commands.Command,
        context_key: str = "",
    ) -> commands.Reply:
        executed.append(command)
        return commands.Reply(text="ok")

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply)
    monkeypatch.setattr(shusuo_router.lark_client, "get_bot_open_id", fake_bot_open_id)
    monkeypatch.setattr(shusuo_router.commands, "execute", fake_execute)
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()
    await shusuo_router._handle_envelope(envelope)
    return GroupCaseResult(replies, executed, calls)
```

- [ ] **Step 3: 写路由层失败测试**

新增测试：

```python
async def test_group_without_mention_does_not_execute(monkeypatch) -> None:
    result = await _run_message_case(monkeypatch, _group_envelope())
    assert result.replies == []
    assert result.executed == []
    assert result.bot_open_id_calls == 1


async def test_group_mentioning_other_user_is_ignored(monkeypatch) -> None:
    envelope = _group_envelope(
        mentions=[{"id": {"open_id": "ou_other"}, "name": "其他人"}]
    )
    result = await _run_message_case(monkeypatch, envelope)
    assert result.replies == []
    assert result.executed == []


async def test_group_with_multiple_mentions_including_bot_is_answered(monkeypatch) -> None:
    envelope = _group_envelope(
        mentions=[
            {"id": {"open_id": "ou_other"}},
            {"id": {"open_id": "ou_bot"}},
        ]
    )
    result = await _run_message_case(monkeypatch, envelope)
    assert len(result.executed) == 1
    assert result.replies == ["ok"]


async def test_missing_chat_type_is_ignored(monkeypatch) -> None:
    envelope = _group_envelope()
    message = envelope["event"]["message"]
    message.pop("chat_type")
    result = await _run_message_case(monkeypatch, envelope)
    assert result.replies == []
    assert result.executed == []
    assert result.bot_open_id_calls == 0


async def test_unknown_chat_type_is_ignored(monkeypatch) -> None:
    envelope = _group_envelope()
    envelope["event"]["message"]["chat_type"] = "topic"
    result = await _run_message_case(monkeypatch, envelope)
    assert result.replies == []
    assert result.executed == []
    assert result.bot_open_id_calls == 0


async def test_p2p_does_not_query_bot_identity(monkeypatch) -> None:
    envelope = _p2p_envelope("帮助")
    result = await _run_message_case(monkeypatch, envelope)
    assert len(result.executed) == 1
    assert result.bot_open_id_calls == 0


async def test_bot_message_does_not_query_bot_identity(monkeypatch) -> None:
    envelope = _group_envelope(
        mentions=[{"id": {"open_id": "ou_bot"}}]
    )
    envelope["event"]["sender"]["sender_type"] = "app"
    result = await _run_message_case(monkeypatch, envelope)
    assert result.replies == []
    assert result.executed == []
    assert result.bot_open_id_calls == 0


async def test_group_bot_identity_failure_is_silent(monkeypatch) -> None:
    envelope = _group_envelope(
        mentions=[{"id": {"open_id": "ou_bot"}}]
    )
    result = await _run_message_case(
        monkeypatch,
        envelope,
        bot_open_id_error=RuntimeError("bot info unavailable"),
    )
    assert result.replies == []
    assert result.executed == []
```

如果没有 `_p2p_envelope()`，在测试文件中新增返回明确 `chat_type="p2p"` 的 helper。旧测试中缺 `chat_type` 的用户消息也必须补成 `p2p`。

- [ ] **Step 4: 运行路由测试并确认红灯**

```bash
cd /Users/lute/Project/data_scrapy/apps/api
uv run pytest tests/unit/test_shusuo_router.py -q
```

预期：缺失/未知 `chat_type` 用例失败；群聊畸形 mention 用例可能触发现有 `AttributeError`；命令执行断言暴露现有覆盖缺口。

- [ ] **Step 5: 将 router logger 切换为 structlog**

修改 `router.py` imports：

```python
import structlog

from .gate import MessageGateDecision, decide_message_gate
```

删除：

```python
import logging
```

修改 logger：

```python
logger = structlog.get_logger(__name__)
```

理由：应用只配置 structlog。保留标准库 logger 会让 debug/info 在生产不可见。

- [ ] **Step 6: 接入纯函数门禁**

用以下逻辑替换 `router.py:161-172` 的内联门禁：

```python
        chat_type = message.get("chat_type")
        bot_open_id: str | None = None
        if chat_type == "group":
            try:
                bot_open_id = await lark_client.get_bot_open_id()
            except Exception as exc:  # noqa: BLE001 - 群聊必须 fail-closed
                logger.warning(
                    "shusuo_bot_identity_unavailable",
                    message_id=message_id,
                    error_type=type(exc).__name__,
                )
                return

        decision = decide_message_gate(
            chat_type=chat_type,
            mentions=message.get("mentions"),
            bot_open_id=bot_open_id,
        )
        if decision not in {
            MessageGateDecision.ALLOW_P2P,
            MessageGateDecision.ALLOW_GROUP_MENTION,
        }:
            log_method = (
                logger.warning
                if decision
                in {
                    MessageGateDecision.IGNORE_UNKNOWN_CHAT_TYPE,
                    MessageGateDecision.IGNORE_BOT_ID_UNAVAILABLE,
                }
                else logger.debug
            )
            log_method(
                "shusuo_message_ignored",
                message_id=message_id,
                chat_type=str(chat_type or ""),
                decision=decision.value,
            )
            return
```

不得记录消息正文、token、open_id 或完整 envelope。

- [ ] **Step 7: 调整 structlog 调用方式**

将本文件中标准库占位格式日志改成结构化字段。例如：

```python
logger.info(
    "shusuo_event_received",
    event_type=event_type,
    event_id=str(header.get("event_id", "")),
)
```

兜底异常改成：

```python
logger.exception(
    "shusuo_event_failed",
    error_type=type(exc).__name__,
)
```

不要把异常文本或消息正文写入日志。

- [ ] **Step 8: 字节级重写并运行测试**

```bash
cd /Users/lute/Project/data_scrapy
python3 - <<'PY'
import os
from pathlib import Path

for name in (
    "apps/api/src/data_intelligence_hub/agents/shusuo/router.py",
    "apps/api/tests/unit/test_shusuo_router.py",
):
    path = Path(name)
    data = path.read_bytes().rstrip(b"\x00")
    if b"\x00" in data:
        raise SystemExit(f"embedded NUL: {name}")
    if not data.endswith(b"\n"):
        data += b"\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
PY

cd apps/api
uv run pytest tests/unit/test_shusuo_gate.py tests/unit/test_shusuo_router.py -q
uv run ruff check --no-cache \
  src/data_intelligence_hub/agents/shusuo/gate.py \
  src/data_intelligence_hub/agents/shusuo/router.py \
  tests/unit/test_shusuo_gate.py \
  tests/unit/test_shusuo_router.py
uv run ruff check --no-cache --select E902 .
```

预期：全部通过。

- [ ] **Step 9: 提交路由接线**

```bash
cd /Users/lute/Project/data_scrapy
git add \
  apps/api/src/data_intelligence_hub/agents/shusuo/router.py \
  apps/api/tests/unit/test_shusuo_router.py
git commit -m "fix(shusuo): 未知会话类型采用 fail-closed"
```

---

### Task 3: 补齐机器人身份、加密、去重和文本清洗回归

**Files:**
- Create or Modify: `apps/api/tests/unit/test_shusuo_lark_client.py`
- Modify: `apps/api/tests/unit/test_shusuo_router.py`
- Modify: `apps/api/tests/unit/test_shusuo_gate.py`

**Interfaces:**
- Consumes:
  - `lark_client.get_bot_open_id() -> str`
  - `_is_duplicate(event_id: str) -> bool`
  - `commands.clean_text(text: str) -> str`
- Produces: 回归测试，不新增生产接口。

- [ ] **Step 1: 运行影响分析**

```bash
cd /Users/lute/Project/data_scrapy
node .gitnexus/run.cjs impact "get_bot_open_id" --direction upstream --repo .
node .gitnexus/run.cjs impact "clean_text" --direction upstream --repo .
```

预期：两者 risk 为 LOW。记录直接调用者。

- [ ] **Step 2: 给机器人身份缓存写失败测试**

创建或扩展 `tests/unit/test_shusuo_lark_client.py`：

```python
async def test_get_bot_open_id_caches_success(monkeypatch) -> None:
    lark_client._bot_cache["open_id"] = ""
    token_calls = 0
    request_calls = 0

    async def fake_token() -> str:
        nonlocal token_calls
        token_calls += 1
        return "token"

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"code": 0, "bot": {"open_id": "ou_bot"}}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            nonlocal request_calls
            request_calls += 1
            return Response()

    monkeypatch.setattr(lark_client, "get_tenant_token", fake_token)
    monkeypatch.setattr(lark_client.httpx, "AsyncClient", lambda **kwargs: Client())

    assert await lark_client.get_bot_open_id() == "ou_bot"
    assert await lark_client.get_bot_open_id() == "ou_bot"
    assert token_calls == 1
    assert request_calls == 1
```

再增加：

- 飞书返回 `code != 0` 时返回空串且不缓存。
- `raise_for_status()` 抛异常时向上传播。
- 每个用例清空 `_bot_cache["open_id"]`。

- [ ] **Step 3: 增加加密群聊门禁测试**

复用测试文件现有 `_encrypt()` 与 `_sign()` helper。

新增：

- 加密群聊 + @bot：解密后执行命令并回复。
- 加密群聊无 mention：HTTP 200，但不执行、不回复。
- 加密群聊未知 `chat_type`：HTTP 200，但不执行、不回复。
- 坏签名继续返回 403。
- `url_verification` 相关现有测试保持通过。

使用 `TestClient(app)`，因为要覆盖 webhook 解密、验签和 `BackgroundTasks`。

- [ ] **Step 4: 增加 event_id 去重测试**

在测试 autouse fixture 中清理 `_seen_events`：

```python
@pytest.fixture(autouse=True)
def _clear_state():
    get_shushuo_config.cache_clear()
    shusuo_router._seen_events.clear()
    yield
    shusuo_router._seen_events.clear()
    get_shushuo_config.cache_clear()
```

新增：同一个非空 `event_id` 连发两次，只执行一次。

保留空 `event_id` 的现状测试：两次都处理。不要在本任务改去重语义。

- [ ] **Step 5: 补文本清洗测试**

扩展现有测试：

```python
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("@_user_1 帮助", "帮助"),
        ("@_user_1 @_user_2 帮助", "帮助"),
        ("@_all 帮助", "帮助"),
        ("  @_user_1   帮助  ", "帮助"),
    ],
)
def test_clean_text_removes_all_mentions(raw: str, expected: str) -> None:
    assert commands.clean_text(raw) == expected
```

- [ ] **Step 6: 运行回归矩阵**

```bash
cd /Users/lute/Project/data_scrapy/apps/api
uv run pytest \
  tests/unit/test_shusuo_gate.py \
  tests/unit/test_shusuo_router.py \
  tests/unit/test_shusuo_lark_client.py \
  -q
uv run pytest tests/unit -q
uv run ruff check --no-cache src/data_intelligence_hub/agents/shusuo tests/unit/test_shusuo*.py
uv run ruff check --no-cache --select E902 .
```

预期：数说专项与全量 unit 全部通过。

- [ ] **Step 7: 提交回归测试**

```bash
cd /Users/lute/Project/data_scrapy
git add \
  apps/api/tests/unit/test_shusuo_gate.py \
  apps/api/tests/unit/test_shusuo_router.py \
  apps/api/tests/unit/test_shusuo_lark_client.py
git commit -m "test(shusuo): 补齐群聊门禁回归矩阵"
```

---

### Task 4: 更新操作文档并完成本地发布门禁

**Files:**
- Modify: `docs/workflows/workflow-shusuo-feishu-bot-stable.md`
- Modify: `docs/superpowers/specs/2026-10-23-shusuo-group-mention-gate-design.md`

**Interfaces:**
- Consumes: Tasks 1-3 的实际行为与日志事件名。
- Produces: 发布与排障文档，不改变运行时。

- [ ] **Step 1: 更新稳定工作流文档**

补充以下内容：

```markdown
### 群聊门禁

- 私聊：不要求 @。
- 群聊：只有 mentions 中当前机器人的 open_id 命中时回答。
- 缺失或未知 chat_type：静默忽略。
- @all 或只 @ 其他成员：静默忽略。
- bot open_id 查询失败：群聊静默，私聊不受影响。
```

增加日志事件：

- `shusuo_message_ignored`
- `shusuo_bot_identity_unavailable`
- `shusuo_command_handled`

不得写入 token、open_id 或消息正文。

- [ ] **Step 2: 修正设计规格的 edge 术语**

将 `docs/superpowers/specs/2026-10-23-shusuo-group-mention-gate-design.md` 发布步骤改为：

> 重启 edge，使 edge 的 nginx 重新解析 API 容器地址。共享网关缓存的 edge 固定 IP 保持不变。

不得写成「共享网关重新解析 API」。

- [ ] **Step 3: 字节级重写并做文档自检**

```bash
cd /Users/lute/Project/data_scrapy
python3 - <<'PY'
import os
from pathlib import Path

for name in (
    "docs/workflows/workflow-shusuo-feishu-bot-stable.md",
    "docs/superpowers/specs/2026-10-23-shusuo-group-mention-gate-design.md",
):
    path = Path(name)
    data = path.read_bytes().rstrip(b"\x00")
    if b"\x00" in data:
        raise SystemExit(f"embedded NUL: {name}")
    if not data.endswith(b"\n"):
        data += b"\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
PY

python3 scripts/check_file_integrity.py
git diff --check
grep -nE "TBD|TODO|待定|待确认" \
  docs/workflows/workflow-shusuo-feishu-bot-stable.md \
  docs/superpowers/specs/2026-10-23-shusuo-group-mention-gate-design.md || true
```

预期：无 NUL、无尾洞、无未处理占位符。

- [ ] **Step 4: 运行最终本地门禁**

```bash
cd /Users/lute/Project/data_scrapy/apps/api
uv run pytest tests/unit/test_shusuo_gate.py tests/unit/test_shusuo_router.py tests/unit/test_shusuo_lark_client.py -q
uv run pytest tests/unit -q
uv run ruff check --no-cache src/data_intelligence_hub/agents/shusuo tests/unit/test_shusuo*.py
uv run ruff check --no-cache --select E902 .
uv run alembic heads
```

预期：

- 数说专项测试全部通过。
- 全量 unit 无失败。
- ruff 无新增错误。
- Alembic head 与 origin/main 一致；本功能不新增迁移。

- [ ] **Step 5: 运行提交前图分析**

```bash
cd /Users/lute/Project/data_scrapy
node .gitnexus/run.cjs detect-changes --scope compare --base-ref origin/main --repo .
```

若输出 `partial: true` 或 `truncated: true`，不得把它当作干净检查。记录风险，并用文本搜索补充关键调用方。

- [ ] **Step 6: 提交文档与最终验证记录**

```bash
cd /Users/lute/Project/data_scrapy
git add \
  docs/workflows/workflow-shusuo-feishu-bot-stable.md \
  docs/superpowers/specs/2026-10-23-shusuo-group-mention-gate-design.md
git commit -m "docs(shusuo): 记录群聊门禁与发布验收"
```

---

### Task 5: 发布生产 A 并执行人工验收

**Files:**
- No source changes.
- Operational target: production A `ubuntu@43.163.92.244`。

**Interfaces:**
- Consumes: 已合入 `origin/main` 的功能提交。
- Produces: 生产 A 的运行行为与验收记录。

- [ ] **Step 1: 确认 main 与本地一致**

```bash
cd /Users/lute/Project/data_scrapy
git switch main
git fetch origin main
git merge --ff-only FETCH_HEAD
git status --short
git rev-parse --short HEAD
```

预期：工作区干净。本地 HEAD 与 `origin/main` 一致。

- [ ] **Step 2: 运行发布前只读检查**

```bash
cd /Users/lute/Project/data_scrapy
bash scripts/preflight-production.sh
bash scripts/check-edge-fixed-ip.sh
bash scripts/reload-scrapy-gateway.sh --dry-run
```

如果 `preflight-production.sh` 的 schema 期望落后，先在 main 修文档/脚本或通过明确环境变量指定当前 head。不得忽略 schema 错误。

记录发布前锚点：

```bash
ssh -i /Users/lute/Project/data_scrapy/zhoujian_pachong.pem \
  ubuntu@43.163.92.244 '
  docker image inspect --format "{{.Id}}" data_achieve_scrapy_api:latest
  docker inspect --format "{{.Id}} {{.State.StartedAt}} {{.RestartCount}}" \
    data_achieve_scrapy_edge
  docker inspect --format \
    "{{range $n,$v := .NetworkSettings.Networks}}{{$n}}={{$v.IPAddress}} {{end}}" \
    data_achieve_scrapy_edge
  git -C /opt/data-achieve-scrapy/app rev-parse --short HEAD
'
```

- [ ] **Step 3: 只构建并替换 API**

在生产 A 执行：

```bash
ssh -i /Users/lute/Project/data_scrapy/zhoujian_pachong.pem \
  ubuntu@43.163.92.244

cd /opt/data-achieve-scrapy/app
git fetch origin main
git merge --ff-only FETCH_HEAD

ENVF=/opt/data-achieve-scrapy/.env.production
CF=/opt/data-achieve-scrapy/app/configs/deploy/scrapy/docker-compose.yml

docker compose --env-file "$ENVF" -f "$CF" config --quiet
docker compose --env-file "$ENVF" -f "$CF" build api
docker compose --env-file "$ENVF" -f "$CF" up -d --no-deps api
docker compose --env-file "$ENVF" -f "$CF" restart edge
```

解释：

- `up -d --no-deps api` 只替换 API。
- `restart edge` 不重建 edge 容器。它只让 edge nginx 重新解析新的 API 容器地址。
- 不得运行 `docker compose down`。
- 不得运行 `docker compose up -d edge` 或 `--force-recreate edge`。
- 不得重启共享网关 `ai_video_nginx`。
- 本功能没有迁移，不执行 `alembic upgrade head`。只读确认 `alembic current` 即可。

- [ ] **Step 4: 等待 API 健康并验证固定 IP**

```bash
for i in $(seq 1 36); do
  status=$(docker inspect --format '{{.State.Health.Status}}' data_achieve_scrapy_api)
  echo "$i api=$status"
  [ "$status" = healthy ] && break
  sleep 5
done

curl -sS https://scrapy.luteos.com/api/health
curl -sS https://scrapy.luteos.com/api/agents/shusuo/health

docker inspect --format \
  '{{range $n,$v := .NetworkSettings.Networks}}{{$n}}={{$v.IPAddress}} {{end}}' \
  data_achieve_scrapy_edge
```

预期：

- API healthy。
- 公网 health 200。
- 数说 health `ready=true`。
- edge 仍含 `lighthouse_ai_video_net=172.20.0.16`。

- [ ] **Step 5: 在专用测试群做人工矩阵**

按顺序执行并记录 message_id、时间和结果：

1. 群聊普通文本，不 @：机器人静默。
2. 群聊 @ 其他成员：机器人静默。
3. 群聊 @all：机器人静默。
4. 群聊 @ 数说机器人并发送「帮助」：机器人回复。
5. 群聊同时 @ 数说与其他成员：机器人回复。
6. 私聊发送「帮助」：机器人回复。

不得在正式业务群做破坏性采集命令。只发送「帮助」。

- [ ] **Step 6: 核对日志**

```bash
ssh -i /Users/lute/Project/data_scrapy/zhoujian_pachong.pem \
  ubuntu@43.163.92.244 '
  docker logs --since 30m data_achieve_scrapy_api 2>&1 |
    grep -E "shusuo_message_ignored|shusuo_bot_identity_unavailable|shusuo_command_handled" |
    tail -100

  docker logs --since 30m data_achieve_scrapy_api 2>&1 |
    grep -E "Traceback|shusuo_event_failed| 5[0-9][0-9] " |
    tail -50
'
```

预期：

- 群聊未 @ 有 `shusuo_message_ignored`。
- 未 @ 的 message_id 没有 `shusuo_command_handled`。
- @ 数说和私聊有 `shusuo_command_handled`。
- 无 traceback、无 5xx。

- [ ] **Step 7: 必要时回滚**

若私聊失效、群聊未 @ 仍回复、或 API 出现 5xx：

```bash
ENVF=/opt/data-achieve-scrapy/.env.production
CF=/opt/data-achieve-scrapy/app/configs/deploy/scrapy/docker-compose.yml

ROLLBACK_TAG=$(cat /opt/backups/dih-shusuo-api-rollback-tag.txt)
docker image inspect "$ROLLBACK_TAG" >/dev/null
docker tag "$ROLLBACK_TAG" data_achieve_scrapy_api:latest
docker compose --env-file "$ENVF" -f "$CF" up -d --no-deps api
docker compose --env-file "$ENVF" -f "$CF" restart edge
curl -sS https://scrapy.luteos.com/api/health
```

回滚不执行数据库 downgrade。

- [ ] **Step 8: 写发布记录**

记录：

- 部署 commit。
- 发布前 API 镜像 ID。
- edge 发布前后容器 ID与固定 IP。
- 六个人工验收场景结果。
- 日志检查结果。
- 是否回滚。

不记录 token、密码、用户消息正文或 open_id。
