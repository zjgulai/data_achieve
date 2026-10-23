# SP-12 数说意图层与确认卡实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让数说把自然语言转换为经过预检的采集提案，并通过一次性 token 与飞书确认卡安全执行；统一回复格式，单条回复不超过 6000 字符。

**Architecture:** `intents.py` 只负责提案解析；新增 `proposal_store.py` 管理单进程、5 分钟、一次性 token；`capabilities.py` 提供结构化预检与采集结果；新增 `cards.py` 和 `replies.py` 生成纯数据卡片与文本；`router.py` 增加卡片回调并把执行放入后台任务。每个用户会话只保留一个提案，新提案替换旧提案。API 重启后待确认提案失效。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、httpx、pytest/pytest-asyncio、飞书 Interactive Card、现有 platform package/provider status 服务。

## Global Constraints

- 只部署生产 A：`ubuntu@43.163.92.244`。
- 不部署生产 B。
- 不重建 edge；发布只重建 api，必要时只执行 `restart edge`。
- 本功能不新增数据库迁移。
- 自然语言场景不能直接触发采集。
- 显式 `采集 <端点> key=value` 可直接执行，但必须通过同一预检。
- 每个 `chat_id + open_id` 只保留一个待确认提案；新提案替换旧提案。
- token TTL 固定为 300 秒，只能消费一次。
- 数量默认 10，硬上限 50。
- 只有实时状态为 `verified` 的端点可执行。
- 费用未知时允许确认后执行；必须显示“费用未知，按上游实际计费”。
- 回复正文与 ack 均不得超过 6000 字符。
- API 重启后待确认提案失效；用户已接受该限制。
- URL challenge 继续只回显 challenge，不强制比对 Verification Token。
- 开始任何代码编辑前，按 `CLAUDE.md` 对目标符号运行 GitNexus impact；提交前运行完整 detect-changes，`partial` 或 `truncated` 不算通过。
- 工作区存在并行会话时，每次编辑前重新读取目标文件；不得覆盖未知改动。

---

## 文件结构

### 新建文件

- `apps/api/src/data_intelligence_hub/agents/shusuo/proposal_store.py`
  - `PendingProposal`、token 生成、替换、查询、消费、取消、过期清理与容量限制。
- `apps/api/src/data_intelligence_hub/agents/shusuo/cards.py`
  - 纯函数生成提案卡、处理中卡、成功卡、失败卡、取消卡、过期卡。
- `apps/api/src/data_intelligence_hub/agents/shusuo/replies.py`
  - 统一文本模板、记录摘要、脱敏、`fit_text()`。
- `apps/api/tests/unit/test_shusuo_proposal_store.py`
  - token 生命周期、用户/会话绑定、替换、过期、容量。
- `apps/api/tests/unit/test_shusuo_cards.py`
  - 卡片字段、按钮值、费用未知警告、敏感数据不入卡片。
- `apps/api/tests/unit/test_shusuo_replies.py`
  - 6000 字符、脱敏、成功/失败模板、最多三条摘要。

### 修改文件

- `apps/api/src/data_intelligence_hub/agents/shusuo/intents.py`
  - 移除内置 `_PENDING`；扩展 `Proposal`；严格数量与 URL 解析；修 Amazon 参数。
- `apps/api/src/data_intelligence_hub/agents/shusuo/capabilities.py`
  - 增加 `PreflightResult`、`preflight_proposal()`、强制刷新状态；扩展 `CollectOutcome`。
- `apps/api/src/data_intelligence_hub/agents/shusuo/commands.py`
  - 支持 token 参数；intent 只生成提案；显式采集先预检；统一回复。
- `apps/api/src/data_intelligence_hub/agents/shusuo/lark_client.py`
  - 增加 `reply_card()`，复用 `update_card()`。
- `apps/api/src/data_intelligence_hub/agents/shusuo/router.py`
  - 文本入口传 `chat_id/open_id/message_id`；发送确认卡；增加 `/card-action`；后台确认执行并更新卡片。
- `apps/api/tests/unit/test_shusuo_router.py`
  - 更新现有确认测试，补预检、文本降级、回调安全和端到端单次执行测试。
- `docs/architecture/【方案】数说飞书机器人能力图谱与意图映射.md`
  - 记录确认卡架构、回调 URL、300 秒 TTL、重启失效限制。
- `docs/tickets/SP-Agent-TODO-2026-10-21.{md,json}`
  - 仅在生产验收完成后更新 SP-12 状态与证据。

---

### Task 1: 建立一次性提案存储

**Files:**
- Create: `apps/api/src/data_intelligence_hub/agents/shusuo/proposal_store.py`
- Create: `apps/api/tests/unit/test_shusuo_proposal_store.py`
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/intents.py:10-104`

**Interfaces:**
- Consumes: `intents.Proposal`
- Produces:

```python
@dataclass(frozen=True, slots=True)
class PendingProposal:
    token: str
    chat_id: str
    open_id: str
    proposal: Proposal
    params_hash: str
    created_at: float
    expires_at: float
    message_id: str | None = None
    card_message_id: str | None = None

class ProposalLookup(StrEnum):
    ACTIVE = "active"
    MISSING = "missing"
    EXPIRED = "expired"
    REPLACED = "replaced"
    FORBIDDEN = "forbidden"

def replace_pending(chat_id: str, open_id: str, proposal: Proposal, *, now: float | None = None) -> PendingProposal

def peek_pending(token: str | None, chat_id: str, open_id: str, *, now: float | None = None) -> tuple[ProposalLookup, PendingProposal | None]

def consume_pending(token: str | None, chat_id: str, open_id: str, *, now: float | None = None) -> tuple[ProposalLookup, PendingProposal | None]

def cancel_pending(token: str | None, chat_id: str, open_id: str, *, now: float | None = None) -> ProposalLookup

def attach_message_ids(token: str, *, message_id: str | None = None, card_message_id: str | None = None) -> None

def clear_all() -> None
```

- [ ] **Step 1: 运行 impact 并保存结论**

```bash
cd /Users/lute/Project/data_scrapy
node .gitnexus/run.cjs impact "build_proposal" --direction upstream --repo .
```

期望：LOW；直接调用者为 `commands.execute`。若索引给出 `UNKNOWN`，再运行：

```bash
grep -R "build_proposal\|set_pending\|take_pending\|clear_pending" -n apps/api/src apps/api/tests
```

- [ ] **Step 2: 写 token 生命周期失败测试**

```python
# apps/api/tests/unit/test_shusuo_proposal_store.py
from data_intelligence_hub.agents.shusuo import intents, proposal_store


def _proposal() -> intents.Proposal:
    return intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"query": "AI", "max_items": 10},
        title="Reddit 搜索：AI",
        estimated_items=10,
        cost_notice="费用未知，按上游实际计费",
    )


def test_new_proposal_replaces_old_token() -> None:
    proposal_store.clear_all()
    first = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    second = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=101)

    old_status, _ = proposal_store.peek_pending(first.token, "chat-1", "ou-1", now=102)
    new_status, pending = proposal_store.peek_pending(second.token, "chat-1", "ou-1", now=102)

    assert old_status is proposal_store.ProposalLookup.REPLACED
    assert new_status is proposal_store.ProposalLookup.ACTIVE
    assert pending == second


def test_token_is_bound_to_chat_and_user() -> None:
    proposal_store.clear_all()
    pending = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    status, result = proposal_store.peek_pending(pending.token, "chat-2", "ou-1", now=101)
    assert status is proposal_store.ProposalLookup.FORBIDDEN
    assert result is None


def test_token_expires_after_300_seconds() -> None:
    proposal_store.clear_all()
    pending = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    status, result = proposal_store.peek_pending(pending.token, "chat-1", "ou-1", now=401)
    assert status is proposal_store.ProposalLookup.EXPIRED
    assert result is None


def test_token_can_be_consumed_only_once() -> None:
    proposal_store.clear_all()
    pending = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    first, proposal = proposal_store.consume_pending(pending.token, "chat-1", "ou-1", now=101)
    second, repeated = proposal_store.consume_pending(pending.token, "chat-1", "ou-1", now=102)
    assert first is proposal_store.ProposalLookup.ACTIVE
    assert proposal is not None
    assert second is proposal_store.ProposalLookup.MISSING
    assert repeated is None
```

- [ ] **Step 3: 运行测试并确认失败**

```bash
cd apps/api
uv run pytest tests/unit/test_shusuo_proposal_store.py -q
```

期望：导入 `proposal_store` 失败。

- [ ] **Step 4: 实现内存存储**

实现要求：

```python
PENDING_TTL_SECONDS = 300
MAX_PENDING_PROPOSALS = 1024
_TOKEN_BYTES = 8

_PENDING_BY_TOKEN: dict[str, PendingProposal] = {}
_ACTIVE_TOKEN_BY_CONTEXT: dict[tuple[str, str], str] = {}
_REPLACED_TOKENS: dict[str, float] = {}
```

- token 使用 `secrets.token_hex(_TOKEN_BYTES).upper()`。
- `params_hash` 使用 `json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` 的 SHA-256。
- `replace_pending` 先把旧 token 记到 `_REPLACED_TOKENS`，再存新 token。
- `clear_expired()` 同时清理 active 和 replaced token。
- 裸 token 为 `None` 时，只有当前上下文恰好一个 active token 才解析成功。
- 达到容量上限时先清过期项；仍满则淘汰最早创建项。

- [ ] **Step 5: 从 `intents.py` 删除旧 pending 存储**

删除：

```python
PENDING_TTL_SECONDS
_PENDING
set_pending
take_pending
clear_pending
```

保留 `Proposal` 与意图解析。

- [ ] **Step 6: 运行 token 测试**

```bash
uv run pytest tests/unit/test_shusuo_proposal_store.py -q
```

期望：4 项以上全部通过。

- [ ] **Step 7: 运行文件完整性检查并提交**

```bash
cd /Users/lute/Project/data_scrapy
python3 scripts/check_file_integrity.py
git add apps/api/src/data_intelligence_hub/agents/shusuo/intents.py \
  apps/api/src/data_intelligence_hub/agents/shusuo/proposal_store.py \
  apps/api/tests/unit/test_shusuo_proposal_store.py
git commit -m "feat(shusuo): add one-time proposal tokens"
```

---

### Task 2: 强化意图解析与提案模型

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/intents.py`
- Modify: `apps/api/tests/unit/test_shusuo_router.py:320-373`

**Interfaces:**
- Consumes: 无新接口。
- Produces:

```python
@dataclass(frozen=True)
class Proposal:
    endpoint_type: str
    params: dict[str, Any]
    title: str
    note: str = ""
    estimated_items: int = DEFAULT_MAX_ITEMS
    cost_notice: str = "费用未知，按上游实际计费"
```

- [ ] **Step 1: 写严格解析失败测试**

在 `test_shusuo_router.py` 增加：

```python
def test_intent_rejects_limit_above_50() -> None:
    result = shusuo_intents.build_proposal("搜 reddit AI max_items=51")
    assert result == "数量必须在 1 到 50 之间。"


def test_intent_rejects_fake_tiktok_domain() -> None:
    result = shusuo_intents.build_proposal(
        "评论 https://evil-tiktok.com/@user/video/123"
    )
    assert isinstance(result, str)
    assert "只支持 TikTok、Reddit、YouTube" in result


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_intent_parses_youtube_variants(url: str, video_id: str) -> None:
    proposal = shusuo_intents.build_proposal(f"评论 {url}")
    assert not isinstance(proposal, str)
    assert proposal.params["video_id"] == video_id


def test_intent_price_uses_object_array() -> None:
    proposal = shusuo_intents.build_proposal("价格 B000000001")
    assert not isinstance(proposal, str)
    assert proposal.params["products"] == [
        {"url": "https://www.amazon.com/dp/B000000001"}
    ]
```

- [ ] **Step 2: 运行新测试并确认失败**

```bash
cd apps/api
uv run pytest tests/unit/test_shusuo_router.py \
  -k "limit_above_50 or fake_tiktok or youtube_variants or price_uses_object" -q
```

- [ ] **Step 3: 实现严格数量解析**

把 `_limit` 改为：

```python
def _limit(tokens: list[str]) -> tuple[list[str], int] | str:
    ...
```

- 没有数量时返回 10。
- 数量不是整数或不在 1..50 时返回固定提示。
- 各 proposal builder 必须处理 `_limit` 返回字符串的分支。

- [ ] **Step 4: 实现 host 与 YouTube ID 助手**

```python
def _host_matches(host: str, domain: str) -> bool:
    normalized = host.partition(":")[0].rstrip(".").casefold()
    return normalized == domain or normalized.endswith(f".{domain}")


def _youtube_video_id(value: str) -> str:
    ...
```

`_youtube_video_id` 支持短链、watch、shorts、embed。无 scheme 时先补 `https://`。

- [ ] **Step 5: 修 Amazon 参数与 Proposal 元数据**

- `products` 改为 `[ {"url": url} ]`。
- 每个 Proposal 写 `estimated_items`。
- 费用具体值未知时沿用默认 `cost_notice`。

- [ ] **Step 6: 运行完整意图测试**

```bash
uv run pytest tests/unit/test_shusuo_router.py -k "intent" -q
```

- [ ] **Step 7: 提交**

```bash
cd /Users/lute/Project/data_scrapy
git add apps/api/src/data_intelligence_hub/agents/shusuo/intents.py \
  apps/api/tests/unit/test_shusuo_router.py
git commit -m "fix(shusuo): validate intent parameters and urls"
```

---

### Task 3: 增加结构化预检

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/capabilities.py:47-331`
- Modify: `apps/api/tests/unit/test_shusuo_router.py:296-320`

**Interfaces:**
- Consumes: `intents.Proposal`
- Produces:

```python
@dataclass(frozen=True)
class PreflightResult:
    allowed: bool
    availability: str
    normalized_params: dict[str, Any]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    cost_notice: str = ""

async def live_status(*, force: bool = False) -> dict[str, EndpointAvailability]

async def preflight_proposal(
    proposal: Proposal,
    *,
    force_status: bool = False,
) -> PreflightResult
```

- [ ] **Step 1: 对 `live_status` 与 `collect` 跑 impact**

```bash
cd /Users/lute/Project/data_scrapy
node .gitnexus/run.cjs impact "live_status" --direction upstream --repo .
node .gitnexus/run.cjs impact \
  "Function:apps/api/src/data_intelligence_hub/agents/shusuo/capabilities.py:collect" \
  --direction upstream --repo .
```

期望：影响集中在 Shusuo 模块。若状态是 UNKNOWN，用 grep 补调用点。

- [ ] **Step 2: 写预检失败测试**

```python
@pytest.mark.asyncio
async def test_preflight_allows_verified_unknown_cost(monkeypatch) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"query": "AI", "max_items": 10},
        title="Reddit 搜索",
        estimated_items=10,
    )
    endpoint = _endpoint(required_params=("query",), optional_params=("max_items",))
    monkeypatch.setattr(shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint))
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(return_value={endpoint.endpoint_type: _availability("verified")}),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is True
    assert "费用未知" in result.warnings


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["config-gated", "disabled", "degraded", "empty", "untested"])
async def test_preflight_rejects_non_verified(monkeypatch, status: str) -> None:
    ...
    assert result.allowed is False


@pytest.mark.asyncio
async def test_preflight_rejects_missing_and_unknown_params(monkeypatch) -> None:
    proposal = ... params={"unknown": 1}
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert "缺少必填参数：query" in result.errors
    assert "未知参数：unknown" in result.errors
```

测试辅助 `_endpoint()` 返回完整 `PackageEndpoint`，`_availability()` 返回 `EndpointAvailability`。

- [ ] **Step 3: 运行预检测试并确认失败**

```bash
cd apps/api
uv run pytest tests/unit/test_shusuo_router.py -k "preflight" -q
```

- [ ] **Step 4: 实现强制状态刷新**

把 `live_status()` 改成 `live_status(force=False)`。`force=True` 时跳过 60 秒缓存，但成功后仍更新缓存。

- [ ] **Step 5: 实现 `preflight_proposal`**

规则：

- `get_capability()` 找不到时返回 `allowed=False`。
- 必填参数按 `required_params` 检查非空值。
- 参数允许集为 `required_params + optional_params + {maxItems, max_items, max_total_charge_usd, run_timeout_seconds}`。
- 未知参数拒绝。
- `max_items/maxItems/num_results/commentsPerPost/maxItems` 等数量键统一检查 1..50；不要改名，保留采集器期望的键。
- 实时状态缺失时使用静态 `endpoint.status`；两者都不是明确 verified 时拒绝。
- 只允许 `verified`。
- `cost_hint` 为空或只写“按量/上游计费”时，加费用未知警告。
- 不向用户暴露 `policy_block_reason` 原文，只返回“当前受安全策略限制”。

- [ ] **Step 6: 让显式 `collect` 使用预检**

在 `commands.execute` 的 `collect` 分支，先构造 Proposal，再调用 `preflight_proposal(force_status=True)`。失败时返回统一错误文本，不调用 `capabilities.collect`。

- [ ] **Step 7: 运行预检与显式采集测试**

```bash
uv run pytest tests/unit/test_shusuo_router.py -k "preflight or explicit_collect" -q
```

- [ ] **Step 8: 提交**

```bash
cd /Users/lute/Project/data_scrapy
git add apps/api/src/data_intelligence_hub/agents/shusuo/capabilities.py \
  apps/api/src/data_intelligence_hub/agents/shusuo/commands.py \
  apps/api/tests/unit/test_shusuo_router.py
git commit -m "feat(shusuo): add proposal preflight"
```

---

### Task 4: 增加统一回复模板

**Files:**
- Create: `apps/api/src/data_intelligence_hub/agents/shusuo/replies.py`
- Create: `apps/api/tests/unit/test_shusuo_replies.py`
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/capabilities.py:53-56,291-331,334-390`
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/router.py:229-232`

**Interfaces:**
- Consumes: `QuickCollectResponse`、`CollectOutcome`、`Proposal`、`PreflightResult`
- Produces:

```python
MAX_REPLY_CHARS = 6000
MAX_TITLE_CHARS = 120
MAX_URL_CHARS = 200
MAX_RECORD_PREVIEWS = 3

def fit_text(text: str, *, limit: int = MAX_REPLY_CHARS) -> str

def proposal_text(pending: PendingProposal, preflight: PreflightResult) -> str

def collect_success_text(outcome: CollectOutcome) -> str

def collect_failure_text(outcome: CollectOutcome) -> str

def preflight_error_text(result: PreflightResult) -> str

def pending_status_text(status: ProposalLookup) -> str
```

扩展：

```python
@dataclass(frozen=True)
class CollectOutcome:
    ok: bool
    text: str
    endpoint_type: str = ""
    task_run_id: str = ""
    records_count: int = 0
    duration_ms: int | None = None
    total_cost_usd: str | None = None
    records: tuple[dict[str, Any], ...] = ()
    error_message: str | None = None
```

- [ ] **Step 1: 写回复失败测试**

```python
def test_fit_text_caps_to_6000_and_redacts_secret() -> None:
    text = "token=secret-value " + "x" * 7000
    result = replies.fit_text(text)
    assert len(result) <= 6000
    assert "secret-value" not in result


def test_success_template_returns_at_most_three_records() -> None:
    outcome = CollectOutcome(
        ok=True,
        text="",
        endpoint_type="tikhub_reddit_search",
        task_run_id="run-id",
        records_count=10,
        duration_ms=1234,
        records=tuple({"content": {"title": f"row {i}"}} for i in range(5)),
    )
    result = replies.collect_success_text(outcome)
    assert "row 0" in result
    assert "row 2" in result
    assert "row 3" not in result
    assert len(result) <= 6000


def test_error_template_does_not_render_exception_class() -> None:
    outcome = CollectOutcome(ok=False, text="", error_message="RuntimeError: token=abc")
    result = replies.collect_failure_text(outcome)
    assert "RuntimeError" not in result
    assert "abc" not in result
```

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd apps/api
uv run pytest tests/unit/test_shusuo_replies.py -q
```

- [ ] **Step 3: 实现脱敏与截断**

复用仓库已有脱敏 helper；若没有适用公开 helper，在 `replies.py` 内实现最小规则：Bearer、token/secret/password/cookie/api_key 键值替换为 `[redacted]`，再截断。

- [ ] **Step 4: 扩展 `CollectOutcome` 并填充结构化字段**

`capabilities.collect` 从 `QuickCollectResponse` 填：

- `task_run_id`
- `records_count`
- `timing.duration_ms`
- `usage.total_cost_usd`
- `records`
- `error_message`

运行详情链接改为 `/runs/{task_run_id}`，不再使用旧 `/collect/`。

- [ ] **Step 5: 用回复模板替代散落字符串**

`commands.py` 与 `router.py` 的用户可见回复统一过 `fit_text`。删除 router 私有 `_truncate`，或改成对 `fit_text` 的薄包装。

- [ ] **Step 6: 运行回复与现有 Shusuo 测试**

```bash
uv run pytest tests/unit/test_shusuo_replies.py tests/unit/test_shusuo_router.py -q
```

- [ ] **Step 7: 提交**

```bash
cd /Users/lute/Project/data_scrapy
git add apps/api/src/data_intelligence_hub/agents/shusuo/replies.py \
  apps/api/src/data_intelligence_hub/agents/shusuo/capabilities.py \
  apps/api/src/data_intelligence_hub/agents/shusuo/router.py \
  apps/api/tests/unit/test_shusuo_replies.py \
  apps/api/tests/unit/test_shusuo_router.py
git commit -m "feat(shusuo): unify proposal and result replies"
```

---

### Task 5: 生成确认卡并支持卡片回复

**Files:**
- Create: `apps/api/src/data_intelligence_hub/agents/shusuo/cards.py`
- Create: `apps/api/tests/unit/test_shusuo_cards.py`
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/lark_client.py:104-153`
- Modify: `apps/api/tests/unit/test_shusuo_router.py`

**Interfaces:**
- Consumes: `PendingProposal`、`PreflightResult`、`CollectOutcome`
- Produces:

```python
def proposal_card(pending: PendingProposal, preflight: PreflightResult) -> dict[str, Any]
def processing_card(pending: PendingProposal) -> dict[str, Any]
def success_card(pending: PendingProposal, outcome: CollectOutcome) -> dict[str, Any]
def failure_card(pending: PendingProposal, message: str) -> dict[str, Any]
def cancelled_card(pending: PendingProposal) -> dict[str, Any]
def expired_card() -> dict[str, Any]

async def reply_card(message_id: str, card: dict[str, Any]) -> str
```

- [ ] **Step 1: 写卡片失败测试**

```python
def test_proposal_card_has_confirm_cancel_and_no_params() -> None:
    card = cards.proposal_card(pending, preflight)
    actions = card["elements"][-1]["actions"]
    values = [item["value"] for item in actions]
    assert values == [
        {"action": "confirm", "token": pending.token},
        {"action": "cancel", "token": pending.token},
    ]
    serialized = json.dumps(card, ensure_ascii=False)
    assert "费用未知，按上游实际计费" in serialized
    assert json.dumps(pending.proposal.params, ensure_ascii=False) not in serialized


@pytest.mark.asyncio
async def test_reply_card_posts_interactive_reply(monkeypatch) -> None:
    request = AsyncMock(return_value={"message_id": "card-message"})
    monkeypatch.setattr(lark_client, "_request", request)
    message_id = await lark_client.reply_card("source-message", {"schema": "2.0"})
    assert message_id == "card-message"
    request.assert_awaited_once()
```

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd apps/api
uv run pytest tests/unit/test_shusuo_cards.py -q
```

- [ ] **Step 3: 实现卡片纯函数**

- 使用飞书卡片 schema 2.0。
- 参数只显示白名单摘要，不把完整 JSON 放入按钮 value。
- token 只出现在按钮 value 与卡片底部短码中。
- 标题、说明和参数摘要先过 `fit_text` 的短限制。

- [ ] **Step 4: 实现 `reply_card`**

请求：

```python
POST /im/v1/messages/{message_id}/reply
{
  "msg_type": "interactive",
  "content": json.dumps(card, ensure_ascii=False)
}
```

- [ ] **Step 5: 运行卡片与客户端测试**

```bash
uv run pytest tests/unit/test_shusuo_cards.py tests/unit/test_shusuo_router.py -q
```

- [ ] **Step 6: 提交**

```bash
cd /Users/lute/Project/data_scrapy
git add apps/api/src/data_intelligence_hub/agents/shusuo/cards.py \
  apps/api/src/data_intelligence_hub/agents/shusuo/lark_client.py \
  apps/api/tests/unit/test_shusuo_cards.py \
  apps/api/tests/unit/test_shusuo_router.py
git commit -m "feat(shusuo): add proposal confirmation cards"
```

---

### Task 6: 接通文本提案、token 确认和卡片降级

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/commands.py:109-197`
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/router.py:139-209`
- Modify: `apps/api/tests/unit/test_shusuo_router.py:375-407`

**Interfaces:**
- Consumes: Tasks 1-5 的 `proposal_store`、`preflight_proposal`、cards、replies。
- Produces:

```python
@dataclass(frozen=True)
class Reply:
    text: str
    ack: str | None = None
    card: dict[str, Any] | None = None
    pending_token: str | None = None

async def execute(
    command: Command,
    *,
    chat_id: str = "",
    open_id: str = "",
    message_id: str = "",
) -> Reply
```

- [ ] **Step 1: 更新 parse_command 失败测试**

```python
def test_parse_confirm_and_cancel_keep_token() -> None:
    assert commands.parse_command("确认 ABC123").argument == "ABC123"
    assert commands.parse_command("取消 ABC123").argument == "ABC123"
```

- [ ] **Step 2: 写提案替换和单次执行测试**

```python
@pytest.mark.asyncio
async def test_intent_returns_card_without_collecting(monkeypatch) -> None:
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    reply = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
        message_id="om-1",
    )
    assert reply.card is not None
    assert reply.pending_token
    collect.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_consumes_before_collect_and_rejects_repeat(monkeypatch) -> None:
    ...
    first = await commands.execute(Command("confirm", token), chat_id="chat-1", open_id="ou-1")
    second = await commands.execute(Command("confirm", token), chat_id="chat-1", open_id="ou-1")
    assert first.text != second.text
    collect.assert_awaited_once()
```

- [ ] **Step 3: 运行测试并确认失败**

```bash
cd apps/api
uv run pytest tests/unit/test_shusuo_router.py \
  -k "keep_token or returns_card or consumes_before_collect" -q
```

- [ ] **Step 4: 修改 command 解析与执行**

- confirm/cancel 的 `argument` 保留 token。
- intent 分支：构建 proposal → preflight → replace_pending → 生成 card/text。
- confirm 分支：peek → `preflight(force_status=True)` → consume → collect。
- cancel 分支：cancel_pending。
- 显式 collect 分支：构造 Proposal → 强制预检 → collect。
- 所有 `Reply.text` 与 `Reply.ack` 经 `fit_text`。

- [ ] **Step 5: 修改文本消息发送流程**

`_handle_envelope` 调用：

```python
reply = await commands.execute(
    command,
    chat_id=chat_id,
    open_id=open_id,
    message_id=message_id,
)
```

发送顺序：

1. 有 ack 时先发送 ack。
2. 有 card 时尝试 `reply_card`。
3. 卡片成功后 `attach_message_ids`。
4. 卡片失败时发送 `reply.text`，文本必须含 token。
5. 无 card 时发送 text。

- [ ] **Step 6: 运行完整 Shusuo 测试**

```bash
uv run pytest tests/unit/test_shusuo_router.py \
  tests/unit/test_shusuo_proposal_store.py \
  tests/unit/test_shusuo_cards.py \
  tests/unit/test_shusuo_replies.py -q
```

- [ ] **Step 7: 提交**

```bash
cd /Users/lute/Project/data_scrapy
git add apps/api/src/data_intelligence_hub/agents/shusuo/commands.py \
  apps/api/src/data_intelligence_hub/agents/shusuo/router.py \
  apps/api/tests/unit/test_shusuo_router.py
git commit -m "feat(shusuo): require proposal confirmation tokens"
```

---

### Task 7: 增加安全的卡片回调

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/router.py`
- Modify: `apps/api/src/data_intelligence_hub/agents/shusuo/cards.py`
- Modify: `apps/api/tests/unit/test_shusuo_router.py`

**Interfaces:**
- Consumes: `proposal_store.peek_pending/consume_pending/cancel_pending`、`commands.execute`、`lark_client.update_card`。
- Produces:

```text
POST /api/agents/shusuo/card-action
```

以及：

```python
CALLBACK_ACTION_ALLOWLIST = frozenset({"confirm", "cancel"})

async def shusuo_card_action(
    request: Request,
    background_tasks: BackgroundTasks,
    x_lark_signature: str | None = Header(default=None),
    x_lark_request_timestamp: str | None = Header(default=None),
    x_lark_request_nonce: str | None = Header(default=None),
) -> Response
```

- [ ] **Step 1: 写回调安全失败测试**

```python
def _signed_card_action(payload: dict[str, Any], encrypt_key: str) -> tuple[str, dict[str, str]]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    timestamp = "1700000000"
    nonce = "nonce"
    signature = hashlib.sha256(
        f"{timestamp}{nonce}{encrypt_key}{body}".encode()
    ).hexdigest()
    return body, {
        "X-Lark-Request-Timestamp": timestamp,
        "X-Lark-Request-Nonce": nonce,
        "X-Lark-Signature": signature,
        "Content-Type": "application/json",
    }


def test_card_action_rejects_bad_signature() -> None:
    response = client.post(CARD_ACTION_PATH, json={"action": {"value": {"action": "confirm"}}})
    assert response.status_code == 403


def test_card_action_rejects_unknown_action() -> None:
    ... action="delete_all" ...
    assert response.status_code == 400


def test_card_action_rejects_non_owner(monkeypatch) -> None:
    ... pending owner ou-1, operator ou-2 ...
    assert response.status_code == 403


def test_card_action_rejects_empty_allowlist(monkeypatch) -> None:
    ... allowed_open_ids=frozenset() ...
    assert response.status_code == 403
```

- [ ] **Step 2: 写成功、取消、重复点击测试**

```python
def test_card_confirm_executes_once(monkeypatch) -> None:
    ...
    first = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    second = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert collect.await_count == 1


def test_card_cancel_does_not_collect(monkeypatch) -> None:
    ...
    collect.assert_not_awaited()
```

- [ ] **Step 3: 运行回调测试并确认失败**

```bash
cd apps/api
uv run pytest tests/unit/test_shusuo_router.py -k "card_action or card_confirm or card_cancel" -q
```

- [ ] **Step 4: 实现回调解析与安全校验**

顺序：

1. 读取原始 body。
2. 处理 `url_verification` challenge。
3. 若有 `encrypt`，要求 encrypt key、验签、解密。
4. 非加密请求也必须有有效签名；使用 Shusuo 的 `verify_signature(encrypt_key=...)`。
5. 要求 Verification Token 已配置且匹配 payload。
6. App ID 匹配。
7. action 在 allowlist。
8. `allowed_open_ids` 为空时拒绝；操作人必须在白名单。
9. 提取 `operator.open_id`、token、context 与 message_id。
10. 校验 pending 归属。
11. 三秒内返回 toast。
12. `BackgroundTasks` 执行 confirm/cancel 并更新卡片。

不要照搬 TikTok CDO 的 token 签名公式。Shusuo 必须复用 `crypto.verify_signature` 的 encrypt-key 公式。

- [ ] **Step 5: 实现后台卡片更新**

confirm：

- 更新为处理中卡。
- 强制预检。
- 消费 token。
- 采集。
- 更新成功或失败卡。

cancel：

- 取消 token。
- 更新为取消卡。

`update_card` 失败只记录日志；不得恢复 token 或重复采集。

- [ ] **Step 6: 运行回调与全量 Shusuo 测试**

```bash
uv run pytest tests/unit/test_shusuo_router.py \
  tests/unit/test_shusuo_proposal_store.py \
  tests/unit/test_shusuo_cards.py \
  tests/unit/test_shusuo_replies.py -q
```

- [ ] **Step 7: 提交**

```bash
cd /Users/lute/Project/data_scrapy
git add apps/api/src/data_intelligence_hub/agents/shusuo/router.py \
  apps/api/src/data_intelligence_hub/agents/shusuo/cards.py \
  apps/api/tests/unit/test_shusuo_router.py
git commit -m "feat(shusuo): handle secure confirmation card actions"
```

---

### Task 8: 文档、全量验证与图变更审查

**Files:**
- Modify: `docs/architecture/【方案】数说飞书机器人能力图谱与意图映射.md`
- Modify: `docs/superpowers/specs/2026-10-23-shusuo-intent-confirmation-card-design.md`（仅当实现与设计有明确偏差）
- Test: `apps/api/tests/unit/test_shusuo_*.py`

**Interfaces:**
- Consumes: Tasks 1-7 的最终接口。
- Produces: 可部署且文档一致的 SP-12 变更集。

- [ ] **Step 1: 更新能力图谱**

写明：

- 卡片回调 URL：`/api/agents/shusuo/card-action`。
- token TTL 300 秒。
- 每会话单提案，新提案替换旧提案。
- API 重启后提案失效。
- 费用未知允许确认后执行；数量上限 50。
- 只有 verified 端点可确认。

- [ ] **Step 2: 运行定向测试**

```bash
cd apps/api
uv run pytest \
  tests/unit/test_shusuo_router.py \
  tests/unit/test_shusuo_proposal_store.py \
  tests/unit/test_shusuo_cards.py \
  tests/unit/test_shusuo_replies.py -q
```

期望：全部通过。

- [ ] **Step 3: 运行 API 全量测试**

```bash
uv run pytest -q
```

期望：除已知需要本机 Postgres 的既有 `test_platform_package_routes_list_detail_and_playbook` 外，无新增失败。若该测试失败，单独重跑并确认仍是 `127.0.0.1:5432` 连接失败。

- [ ] **Step 4: 运行静态检查**

```bash
uv run ruff check \
  src/data_intelligence_hub/agents/shusuo \
  tests/unit/test_shusuo_router.py \
  tests/unit/test_shusuo_proposal_store.py \
  tests/unit/test_shusuo_cards.py \
  tests/unit/test_shusuo_replies.py

uv run mypy src/data_intelligence_hub/agents/shusuo
```

- [ ] **Step 5: 运行文件完整性与图变更检查**

```bash
cd /Users/lute/Project/data_scrapy
python3 scripts/check_file_integrity.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

要求：完整性通过；detect-changes 不是 `partial` 或 `truncated`。若风险 HIGH/CRITICAL，停止发布并报告受影响流程。

- [ ] **Step 6: 提交文档和验证结果**

```bash
git add docs/architecture/【方案】数说飞书机器人能力图谱与意图映射.md \
  apps/api/src/data_intelligence_hub/agents/shusuo \
  apps/api/tests/unit/test_shusuo_*.py
git commit -m "docs(shusuo): document intent confirmation flow"
```

---

### Task 9: 飞书后台配置与生产 A 发布

**Files:**
- No source edits expected.
- Update after verification: `docs/tickets/SP-Agent-TODO-2026-10-21.{md,json}`

**Interfaces:**
- Consumes: 已合并到 `main` 的 SP-12 代码。
- Produces: 生产 A 可用确认卡链路。

- [ ] **Step 1: 配置飞书卡片回调**

在飞书开发者后台把卡片回调地址设为：

```text
https://scrapy.luteos.com/api/agents/shusuo/card-action
```

确认应用仍订阅 `im.message.receive_v1`。不要修改 App ID、Verification Token 或 Encrypt Key。

- [ ] **Step 2: 运行发布前只读预检**

```bash
cd /Users/lute/Project/data_scrapy
bash scripts/preflight-production.sh
```

期望：`ALL CHECKS PASSED`。本地分支必须包含 `origin/main`。

- [ ] **Step 3: 备份生产 A**

```bash
ssh -i zhoujian_pachong.pem ubuntu@43.163.92.244
stamp=$(date +%Y%m%dT%H%M%S)
backup=/opt/backups/data-achieve-scrapy/$stamp
sudo mkdir -p "$backup"
sudo chown ubuntu:ubuntu "$backup"
docker exec data_achieve_scrapy_db sh -lc \
  'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$backup/postgres.sql.gz"
sudo cp /opt/data-achieve-scrapy/.env.production "$backup/env.production"
cd /opt/data-achieve-scrapy/app
git rev-parse HEAD > "$backup/head.txt"
```

本功能无迁移，但仍备份数据库与 env。

- [ ] **Step 4: 同步、构建和只重建 API**

```bash
cd /opt/data-achieve-scrapy/app
git fetch origin main
git merge --ff-only FETCH_HEAD
ENVF=/opt/data-achieve-scrapy/.env.production
CF=configs/deploy/scrapy/docker-compose.yml
docker compose --env-file "$ENVF" -f "$CF" config --quiet
docker compose --env-file "$ENVF" -f "$CF" build api
docker compose --env-file "$ENVF" -f "$CF" up -d api
```

禁止 `docker compose down`，禁止重建 edge。

- [ ] **Step 5: 发布后健康检查**

```bash
docker ps --filter name=data_achieve_scrapy_api --format '{{.Status}}'
docker inspect data_achieve_scrapy_edge \
  --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}'
curl -fsS https://scrapy.luteos.com/api/health
curl -fsS https://scrapy.luteos.com/api/agents/shusuo/health
```

要求：API healthy；edge 包含 `172.20.0.16`；数说 `ready=true`、allowlist 非零。

- [ ] **Step 6: 生产验收**

依次验证：

1. 发“搜 reddit AI”，收到确认卡，尚未产生采集。
2. 再发“搜 youtube AI”，旧卡片点击后提示已被替换。
3. 新卡片点击确认，只产生一次运行。
4. 重复点击确认，不产生第二次运行。
5. 发提案后点击取消，不产生运行。
6. 等待 5 分钟后点击确认，提示已过期。
7. 让非发起人点击，提示只有发起人可操作。
8. 发显式 `采集 <端点> key=value`，确认它经过预检后执行。
9. 用超长结果验证回复不超过 6000 字符。
10. 重启 API 后点击旧卡片，提示提案已失效。

- [ ] **Step 7: 回滚方案**

如果 API 启动失败：

```bash
cd /opt/data-achieve-scrapy/app
git checkout <backup-head>
ENVF=/opt/data-achieve-scrapy/.env.production
CF=configs/deploy/scrapy/docker-compose.yml
docker compose --env-file "$ENVF" -f "$CF" build api
docker compose --env-file "$ENVF" -f "$CF" up -d api
```

无需数据库回滚。本功能无迁移。不要重建 edge。

如果仅卡片回调失败，代码不回滚：文本 token 降级路径仍可用。修正飞书后台回调配置后重新验收。

- [ ] **Step 8: 更新 ticket 和日报**

只有上述验收全部通过后：

- SP-12 状态改为“已完成”。
- 写入实际完成时间与生产证据。
- 更新飞书多维表格。
- 私信周健，包含确认、取消、替换、过期、越权和单次执行的证据。

- [ ] **Step 9: 提交 ticket 证据**

```bash
git add docs/tickets/SP-Agent-TODO-2026-10-21.md \
  docs/tickets/SP-Agent-TODO-2026-10-21.json
git commit -m "docs(tickets): SP-12 production acceptance"
git push origin HEAD:main
```
