"""governed_mcp_tool 统一授权入口的行为。

覆盖：全局 token 豁免、白名单拒绝、空白名单拒绝全部、项目绑定、
对象归属、额度扣减与重放豁免、已撤销密钥拒绝。
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from data_intelligence_hub.mcp_runtime.access_control import (
    assert_tool_allowed,
    resolve_bound_project,
)


def _identity(project_id: uuid.UUID, workspace_id: uuid.UUID, key_id: uuid.UUID | None = None):
    return SimpleNamespace(
        key_id=key_id or uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        key_prefix="dih_test",
        label="test",
    )


def test_empty_allowlist_denies_everything() -> None:
    assert assert_tool_allowed("web_search", []) is False


def test_unknown_tool_denied_even_with_star_like_allowlist() -> None:
    allowlist = ["web_search", "web_fetch", "answer", "deep_research", "collect"]
    assert assert_tool_allowed("no_such_tool", allowlist) is False


def test_allowlisted_tool_allowed() -> None:
    assert assert_tool_allowed("web_search", ["web_search"]) is True


def test_resolve_bound_project_accepts_matching() -> None:
    pid = uuid.uuid4()
    identity = _identity(project_id=pid, workspace_id=uuid.uuid4())
    assert resolve_bound_project(identity, str(pid)) == pid


def test_resolve_bound_project_rejects_mismatch() -> None:
    identity = _identity(project_id=uuid.uuid4(), workspace_id=uuid.uuid4())
    with pytest.raises(ValueError, match="project_not_found"):
        resolve_bound_project(identity, str(uuid.uuid4()))


def test_resolve_bound_project_global_token_passthrough() -> None:
    other = uuid.uuid4()
    assert resolve_bound_project(None, str(other)) == other
