"""数说一次性提案存储的契约测试。"""

from __future__ import annotations

import hashlib
import json

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


def test_params_hash_is_canonical_json_sha256() -> None:
    proposal_store.clear_all()
    expected = hashlib.sha256(
        json.dumps(
            {"query": "AI", "max_items": 10},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    pending = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    assert pending.params_hash == expected


def test_params_hash_ignores_key_order() -> None:
    proposal_store.clear_all()
    left = proposal_store.replace_pending(
        "chat-1",
        "ou-1",
        intents.Proposal(endpoint_type="e", params={"b": 1, "a": 2}, title="t"),
        now=100,
    )
    right = proposal_store.replace_pending(
        "chat-2",
        "ou-1",
        intents.Proposal(endpoint_type="e", params={"a": 2, "b": 1}, title="t"),
        now=100,
    )
    assert left.params_hash == right.params_hash


def test_bare_token_resolves_single_active_proposal() -> None:
    proposal_store.clear_all()
    pending = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    status, found = proposal_store.peek_pending(None, "chat-1", "ou-1", now=101)
    assert status is proposal_store.ProposalLookup.ACTIVE
    assert found == pending

    proposal_store.consume_pending(None, "chat-1", "ou-1", now=102)
    status, found = proposal_store.peek_pending(None, "chat-1", "ou-1", now=103)
    assert status is proposal_store.ProposalLookup.MISSING
    assert found is None


def test_cancel_pending_removes_active_token() -> None:
    proposal_store.clear_all()
    pending = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    assert proposal_store.cancel_pending(pending.token, "chat-1", "ou-1", now=101) is (
        proposal_store.ProposalLookup.ACTIVE
    )
    status, _ = proposal_store.peek_pending(pending.token, "chat-1", "ou-1", now=102)
    assert status is proposal_store.ProposalLookup.MISSING
    assert proposal_store.cancel_pending("no-such-token", "chat-1", "ou-1", now=103) is (
        proposal_store.ProposalLookup.MISSING
    )


def test_attach_message_ids_updates_active_proposal() -> None:
    proposal_store.clear_all()
    pending = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    proposal_store.attach_message_ids(pending.token, message_id="om_a", card_message_id="om_b")
    status, found = proposal_store.peek_pending(pending.token, "chat-1", "ou-1", now=101)
    assert status is proposal_store.ProposalLookup.ACTIVE
    assert found is not None
    assert found.message_id == "om_a"
    assert found.card_message_id == "om_b"
    proposal_store.attach_message_ids("missing-token", message_id="om_c")


def test_clear_expired_removes_stale_active_and_replaced_tokens() -> None:
    proposal_store.clear_all()
    first = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    second = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=101)

    status, _ = proposal_store.peek_pending(first.token, "chat-1", "ou-1", now=402)
    assert status is proposal_store.ProposalLookup.REPLACED
    status, _ = proposal_store.peek_pending(second.token, "chat-1", "ou-1", now=402)
    assert status is proposal_store.ProposalLookup.EXPIRED

    proposal_store.clear_expired(now=500)
    status, _ = proposal_store.peek_pending(first.token, "chat-1", "ou-1", now=501)
    assert status is proposal_store.ProposalLookup.MISSING
    status, _ = proposal_store.peek_pending(second.token, "chat-1", "ou-1", now=501)
    assert status is proposal_store.ProposalLookup.MISSING


def test_replace_pending_sweeps_stale_replaced_tokens() -> None:
    """发新提案即清一轮过期：低流量下 replaced 记录也会被回收，不再依赖容量触发。"""
    proposal_store.clear_all()
    first = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=101)
    status, _ = proposal_store.peek_pending(first.token, "chat-1", "ou-1", now=102)
    assert status is proposal_store.ProposalLookup.REPLACED

    # 402 > 101 + 300：replaced 记录已过窗口；下一次 replace_pending 触发清扫。
    proposal_store.replace_pending("chat-2", "ou-2", _proposal(), now=402)
    status, _ = proposal_store.peek_pending(first.token, "chat-1", "ou-1", now=403)
    assert status is proposal_store.ProposalLookup.MISSING


def test_capacity_evicts_oldest_proposal() -> None:
    proposal_store.clear_all()
    first = proposal_store.replace_pending("chat-first", "ou-first", _proposal(), now=0)
    for index in range(proposal_store.MAX_PENDING_PROPOSALS):
        proposal_store.replace_pending(f"chat-{index}", f"ou-{index}", _proposal(), now=1)

    status, _ = proposal_store.peek_pending(first.token, "chat-first", "ou-first", now=2)
    assert status is proposal_store.ProposalLookup.MISSING
    status, _ = proposal_store.peek_pending("no-such-token", "chat-1", "ou-1", now=2)
    assert status is proposal_store.ProposalLookup.MISSING


def test_restore_pending_puts_back_consumed_proposal() -> None:
    """原子预留回滚：consume 后 restore，同 token、同内容、TTL 端点不变。"""
    proposal_store.clear_all()
    pending = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    consumed_status, consumed = proposal_store.consume_pending(
        pending.token, "chat-1", "ou-1", now=110
    )
    assert consumed is not None
    status, _ = proposal_store.peek_pending(pending.token, "chat-1", "ou-1", now=111)
    assert status is proposal_store.ProposalLookup.MISSING

    proposal_store.restore_pending(consumed, now=112)
    status, restored = proposal_store.peek_pending(
        pending.token, "chat-1", "ou-1", now=113
    )
    assert status is proposal_store.ProposalLookup.ACTIVE
    assert restored is not None
    assert restored.token == pending.token
    assert restored.proposal == pending.proposal
    # TTL 端点不变：created_at=100，expires_at=400，399 秒时仍 ACTIVE
    status, _ = proposal_store.peek_pending(pending.token, "chat-1", "ou-1", now=399)
    assert status is proposal_store.ProposalLookup.ACTIVE
    status, _ = proposal_store.peek_pending(pending.token, "chat-1", "ou-1", now=401)
    assert status is proposal_store.ProposalLookup.EXPIRED


def test_restore_pending_skips_when_newer_proposal_exists() -> None:
    """预留期间用户发了新提案：restore 让位，不覆盖新提案。"""
    proposal_store.clear_all()
    pending = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=100)
    _, consumed = proposal_store.consume_pending(pending.token, "chat-1", "ou-1", now=110)
    newer = proposal_store.replace_pending("chat-1", "ou-1", _proposal(), now=120)
    assert consumed is not None
    proposal_store.restore_pending(consumed, now=121)

    status, active = proposal_store.peek_pending(newer.token, "chat-1", "ou-1", now=122)
    assert status is proposal_store.ProposalLookup.ACTIVE
    assert active is not None
    assert active.token == newer.token
    status, _ = proposal_store.peek_pending(pending.token, "chat-1", "ou-1", now=122)
    assert status is proposal_store.ProposalLookup.MISSING
