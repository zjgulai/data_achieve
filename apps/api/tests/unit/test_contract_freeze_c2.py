from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = PROJECT_ROOT / "docs/design/【契约冻结】v1-表名-枚举-接口.md"
REGISTRY_PATH = PROJECT_ROOT / "configs/contracts/v1.1.0/registry.json"

REQUIRED_AUDIT_ACTIONS = (
    "auth.login.succeeded",
    "auth.login.failed",
    "auth.logout.succeeded",
    "task.created",
    "task.cancelled",
    "task.retried",
    "budget.price.changed",
    "budget.limit.changed",
    "budget.blocked",
    "claim.review.approved",
    "claim.review.rejected",
    "config.switch.changed",
    "delivery.published",
    "delivery.projection.viewed",
    "privacy.projection.applied",
)


def _registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _table(registry: dict[str, Any], name: str) -> dict[str, Any]:
    for table in registry["tables"]:
        if table["name"] == name:
            return table
    raise AssertionError(f"table not registered: {name}")


def test_c2_contract_entries_are_registered() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    required = (
        "`project_members`",
        "`audit_events`",
        "`workspace_members.role`",
        "/api/projects/{project_id}/members",
        "/api/audit-events",
        "/api/audit-events/verify",
        "WORKSPACE_RBAC_ENFORCED",
        "project_access_forbidden",
        "workspace_last_owner_required",
        "workspace_owner_required",
        "workspace_role_invalid",
        "上一事件哈希",
        "`prev_hash`",
        "`event_hash`",
        "`created_by_user_id`",
        "错误信封",
        "report_reviewer_assignments",
        "expires_at",
        "reviewer_assignment_required",
        "reviewer_assignment_invalid",
        "reviewer_assignment_expired",
        "审计动作注册表",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"C2 contract entries missing: {missing}"


def test_c2_registry_entries_exist() -> None:
    registry = _registry()
    names = {table["name"] for table in registry["tables"]}
    assert {"workspace_members", "project_members", "audit_events"} <= names
    paths = {item["path"] for item in registry["paths"]}
    assert {
        "/api/projects/{project_id}/members",
        "/api/projects/{project_id}/members/{user_id}",
        "/api/workspaces/current/members/{user_id}",
        "/api/audit-events",
        "/api/audit-events/verify",
    } <= paths
    codes = {item["code"] for item in registry["error_codes"]}
    assert {
        "project_access_forbidden",
        "workspace_last_owner_required",
        "workspace_owner_required",
        "workspace_role_invalid",
    } <= codes


def test_internal_reviewer_assignment_is_registered_with_expiry() -> None:
    registry = _registry()
    table = _table(registry, "report_reviewer_assignments")
    columns = {column["name"] for column in table["columns"]}
    assert {
        "id",
        "workspace_id",
        "project_id",
        "report_id",
        "artifact_id",
        "reviewer_user_id",
        "assignment_scope",
        "status",
        "assigned_by",
        "assigned_at",
        "expires_at",
        "revoked_at",
    } <= columns
    expires = next(
        column for column in table["columns"] if column["name"] == "expires_at"
    )
    assert expires["nullable"] is False

    enums = {item["name"]: item["values"] for item in registry["enums"]}
    assert enums["report_reviewer_assignments.assignment_scope"] == [
        "report_read",
        "report_review",
    ]
    assert "reviewer" not in enums["workspace_members.role"]

    paths = {(item["method"], item["path"]) for item in registry["paths"]}
    assert ("POST", "/api/reports/{report_id}/reviewers") in paths
    assert ("DELETE", "/api/reports/{report_id}/reviewers/{user_id}") in paths

    codes = {item["code"] for item in registry["error_codes"]}
    assert {
        "reviewer_assignment_required",
        "reviewer_assignment_invalid",
        "reviewer_assignment_expired",
    } <= codes


def test_c1_contract_lists_every_required_audit_action() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    missing = [action for action in REQUIRED_AUDIT_ACTIONS if action not in text]
    assert not missing, f"audit actions missing from C1 contract: {missing}"


def test_c2_contract_declares_single_owner_source() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "唯一授权事实源" in text
    assert "`workspaces.owner_id` 不是授权事实源" in text
