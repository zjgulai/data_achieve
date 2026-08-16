from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from pydantic import JsonValue

from data_intelligence_hub.models.workflow_plan import WorkflowVersion
from data_intelligence_hub.schemas.workflow_planner import (
    PlanningInput,
    WorkflowPlanFingerprintPayload,
    WorkflowPlanPreview,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    build_preview_fingerprint_payload,
    compute_preview_fingerprint,
)
from data_intelligence_hub.services.workflow_planner.normalization import (
    normalize_planning_input,
)


class WorkflowVersionSnapshotInvalidError(ValueError):
    """Persisted frozen WorkflowVersion facts do not agree."""


class WorkflowVersionExpectedFingerprintConflictError(ValueError):
    """The caller's expected fingerprint differs from the stored Version identity."""


class WorkflowVersionOwnerMismatchError(ValueError):
    """The requested tenant/Plan/Version identity does not own this Version."""


@dataclass(frozen=True, slots=True)
class ValidatedWorkflowVersionSnapshot:
    preview: WorkflowPlanPreview
    fingerprint_payload: WorkflowPlanFingerprintPayload
    editable_input: PlanningInput


def _snapshot_invalid(cause: Exception | None = None) -> WorkflowVersionSnapshotInvalidError:
    error = WorkflowVersionSnapshotInvalidError(
        "workflow_plan_version_fingerprint_mismatch"
    )
    if cause is not None:
        error.__cause__ = cause
    return error


def _stored_object(value: JsonValue | None, *, field: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError(f"workflow_plan_fingerprint_{field}_invalid")
    return value


def _stored_list(value: JsonValue | None, *, field: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ValueError(f"workflow_plan_fingerprint_{field}_invalid")
    return value


def _stored_string(value: JsonValue | None, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"workflow_plan_fingerprint_{field}_invalid")
    return value


def _stored_optional_string(value: JsonValue | None, *, field: str) -> str | None:
    if value is None:
        return None
    return _stored_string(value, field=field)


def _stored_string_list(value: JsonValue | None, *, field: str) -> list[str]:
    items = _stored_list(value, field=field)
    if not all(isinstance(item, str) for item in items):
        raise ValueError(f"workflow_plan_fingerprint_{field}_invalid")
    return cast(list[str], items)


def _scope_override(effective: list[str], defaults: list[str]) -> list[str]:
    return [] if effective == defaults else effective


def _editable_input(
    fingerprint_payload: WorkflowPlanFingerprintPayload,
) -> PlanningInput:
    stored = fingerprint_payload.fingerprint_input
    default_languages = _stored_string_list(
        stored.get("default_languages"),
        field="default_languages",
    )
    default_regions = _stored_string_list(
        stored.get("default_regions"),
        field="default_regions",
    )
    default_platforms = _stored_string_list(
        stored.get("default_platforms"),
        field="default_platforms",
    )

    scopes: list[dict[str, object]] = []
    for index, raw_scope in enumerate(_stored_list(stored.get("scopes"), field="scopes")):
        scope = _stored_object(raw_scope, field="scope")
        effective_languages = _stored_string_list(
            scope.get("effective_languages"),
            field="scope_effective_languages",
        )
        effective_regions = _stored_string_list(
            scope.get("effective_regions"),
            field="scope_effective_regions",
        )
        effective_platforms = _stored_string_list(
            scope.get("effective_platforms"),
            field="scope_effective_platforms",
        )
        scopes.append(
            {
                "scope_ref": f"scope-{index + 1}",
                "scope_type": _stored_string(scope.get("scope_type"), field="scope_type"),
                "canonical_term": _stored_optional_string(
                    scope.get("canonical_term"),
                    field="scope_canonical_term",
                ),
                "aliases": _stored_string_list(scope.get("aliases"), field="scope_aliases"),
                "include_terms": _stored_string_list(
                    scope.get("include_terms"),
                    field="scope_include_terms",
                ),
                "exclude_terms": _stored_string_list(
                    scope.get("exclude_terms"),
                    field="scope_exclude_terms",
                ),
                "official_accounts": _stored_string_list(
                    scope.get("official_accounts"),
                    field="scope_official_accounts",
                ),
                "seed_urls": _stored_string_list(
                    scope.get("seed_urls"),
                    field="scope_seed_urls",
                ),
                "languages": _scope_override(effective_languages, default_languages),
                "regions": _scope_override(effective_regions, default_regions),
                "platforms": _scope_override(effective_platforms, default_platforms),
                "match_mode": _stored_string(
                    scope.get("match_mode"),
                    field="scope_match_mode",
                ),
            }
        )

    editable_payload: dict[str, object] = {
        "flow_mode": _stored_string(stored.get("flow_mode"), field="flow_mode"),
        "scopes": scopes,
        "default_languages": default_languages,
        "default_regions": default_regions,
        "default_platforms": default_platforms,
        "delivery_intent": stored.get("delivery_intent"),
        "policy_profile": _stored_string(
            stored.get("policy_profile"),
            field="policy_profile",
        ),
        "purpose": _stored_string(stored.get("purpose"), field="purpose"),
        "required_fields": _stored_string_list(
            stored.get("required_fields"),
            field="required_fields",
        ),
        "optional_fields": _stored_string_list(
            stored.get("optional_fields"),
            field="optional_fields",
        ),
        "budget_ceiling": stored.get("budget_ceiling"),
        "rate_limit_intent": stored.get("rate_limit_intent"),
        "retention_intent": stored.get("retention_intent"),
        "allow_partial_degradation": stored.get("allow_partial_degradation"),
    }
    schedule_intent = stored.get("schedule_intent")
    if schedule_intent is not None:
        editable_payload["schedule_intent"] = schedule_intent
    return PlanningInput.model_validate(editable_payload)


def _validate_expected_owner(
    version: WorkflowVersion,
    *,
    expected_workspace_id: UUID | None,
    expected_project_id: UUID | None,
    expected_workflow_plan_id: UUID | None,
    expected_workflow_version_id: UUID | None,
) -> None:
    expected_pairs = (
        (expected_workspace_id, version.workspace_id),
        (expected_project_id, version.project_id),
        (expected_workflow_plan_id, version.workflow_plan_id),
        (expected_workflow_version_id, version.id),
    )
    if any(expected is not None and expected != actual for expected, actual in expected_pairs):
        raise WorkflowVersionOwnerMismatchError("workflow_version_owner_mismatch")


def validate_workflow_version_snapshot(
    version: WorkflowVersion,
    *,
    expected_workspace_id: UUID | None = None,
    expected_project_id: UUID | None = None,
    expected_workflow_plan_id: UUID | None = None,
    expected_workflow_version_id: UUID | None = None,
    expected_preview_fingerprint: str | None = None,
) -> ValidatedWorkflowVersionSnapshot:
    _validate_expected_owner(
        version,
        expected_workspace_id=expected_workspace_id,
        expected_project_id=expected_project_id,
        expected_workflow_plan_id=expected_workflow_plan_id,
        expected_workflow_version_id=expected_workflow_version_id,
    )
    if (
        expected_preview_fingerprint is not None
        and expected_preview_fingerprint != version.preview_fingerprint
    ):
        raise WorkflowVersionExpectedFingerprintConflictError(
            "workflow_version_fingerprint_conflict"
        )

    try:
        preview = WorkflowPlanPreview.model_validate(version.plan_payload)
        fingerprint_payload = WorkflowPlanFingerprintPayload.model_validate(
            version.fingerprint_payload
        )
        rebuilt_fingerprint_payload = build_preview_fingerprint_payload(
            planner_contract_version=preview.planner_contract_version,
            fingerprint_input=fingerprint_payload.fingerprint_input,
            catalog_snapshot_id=preview.catalog_snapshot_id,
            policy_version=preview.policy_version,
            mode_template_version=preview.mode_template_version,
            query_versions=preview.query_versions,
            candidate_fixture_version=fingerprint_payload.candidate_fixture_version,
            query_terms=preview.query_terms,
            steps=preview.steps,
            compiled_queries=preview.compiled_queries,
            route_plans=preview.route_plans,
            coverage=preview.coverage,
            budget_summary=preview.budget_summary,
            limitations=preview.limitations,
            semantic_decision_trace=preview.decision_trace.semantic_entries,
        )
        preview_query_versions = {
            platform.value: query_version
            for platform, query_version in preview.query_versions.items()
        }
        fingerprint_query_versions = {
            platform.value: query_version
            for platform, query_version in fingerprint_payload.query_versions.items()
        }
        if (
            rebuilt_fingerprint_payload != fingerprint_payload
            or compute_preview_fingerprint(fingerprint_payload)
            != version.preview_fingerprint
            or compute_preview_fingerprint(rebuilt_fingerprint_payload)
            != version.preview_fingerprint
            or preview.preview_fingerprint != version.preview_fingerprint
            or preview.project_id != version.project_id
            or version.planning_status != preview.planning_status.value
            or version.planner_contract_version != preview.planner_contract_version
            or version.planner_contract_version
            != fingerprint_payload.planner_contract_version
            or version.catalog_snapshot_id != preview.catalog_snapshot_id
            or version.catalog_snapshot_id != fingerprint_payload.catalog_snapshot_id
            or version.policy_version != preview.policy_version
            or version.policy_version != fingerprint_payload.policy_version
            or version.mode_template_version != preview.mode_template_version
            or version.mode_template_version != fingerprint_payload.mode_template_version
            or version.query_versions != preview_query_versions
            or version.query_versions != fingerprint_query_versions
            or version.normalized_input != preview.normalized_input.model_dump(mode="json")
            or preview.flow_mode.value
            != _stored_string(
                fingerprint_payload.fingerprint_input.get("flow_mode"),
                field="flow_mode",
            )
        ):
            raise _snapshot_invalid()
        editable_input = _editable_input(fingerprint_payload)
        if (
            normalize_planning_input(editable_input).fingerprint_input
            != fingerprint_payload.fingerprint_input
        ):
            raise _snapshot_invalid()
    except WorkflowVersionSnapshotInvalidError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise _snapshot_invalid(exc) from exc

    return ValidatedWorkflowVersionSnapshot(
        preview=preview,
        fingerprint_payload=fingerprint_payload,
        editable_input=editable_input,
    )


__all__ = [
    "ValidatedWorkflowVersionSnapshot",
    "WorkflowVersionExpectedFingerprintConflictError",
    "WorkflowVersionOwnerMismatchError",
    "WorkflowVersionSnapshotInvalidError",
    "validate_workflow_version_snapshot",
]
