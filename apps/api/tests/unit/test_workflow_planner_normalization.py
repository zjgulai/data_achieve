from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.workflow_planner import PlanningInput
from data_intelligence_hub.services.exceptions import WorkflowPlannerInputError
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    canonical_json_bytes,
    sha256_id,
)
from data_intelligence_hub.services.workflow_planner.normalization import (
    build_scope_key,
    classify_seed_url,
    normalize_planning_input,
    normalize_seed_url,
    normalize_text,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"


def load_request(name: str = "periodic_monitoring_request_v1.json") -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")),
    )


def build_seed_only_batch(seed_url: str) -> dict[str, Any]:
    payload = load_request("batch_research_request_v1.json")
    scope = payload["scopes"][0]
    scope["canonical_term"] = None
    scope["aliases"] = []
    scope["include_terms"] = []
    scope["official_accounts"] = []
    scope["seed_urls"] = [seed_url]
    scope["platforms"] = []
    payload["default_platforms"] = []
    return payload


def assert_reference_free(value: object) -> None:
    forbidden = {
        "scope_ref",
        "source_scope_refs",
        "project_id",
        "generated_at",
        "request_id",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for nested in value.values():
            assert_reference_free(nested)
    elif isinstance(value, list | tuple):
        for nested in value:
            assert_reference_free(nested)


def test_text_normalization_is_nfkc_trimmed_and_casefolded() -> None:
    assert normalize_text("  ＡＣＭＥ  ") == "acme"


def test_seed_url_normalization_is_local_canonical_and_fragment_free() -> None:
    assert normalize_seed_url(
        " HTTPS://WWW.YouTube.com/watch?b=2&a=1&a=0#fragment "
    ) == "https://www.youtube.com/watch?a=0&a=1&b=2"


@pytest.mark.parametrize(
    "seed_url",
    [
        "ftp://www.youtube.com/demo",
        "https:///missing-host",
        "https://user@www.youtube.com/demo",
        "https://user:password@www.youtube.com/demo",
    ],
)
def test_seed_url_normalization_rejects_unsupported_or_userinfo_urls(
    seed_url: str,
) -> None:
    with pytest.raises(ValueError):
        normalize_seed_url(seed_url)


def test_seed_url_classification_uses_exact_host_membership() -> None:
    assert classify_seed_url("https://youtu.be/demo") == "youtube"
    assert classify_seed_url("https://www.reddit.com/r/demo") == "reddit"
    assert classify_seed_url("https://reddit.com.evil.example/r/demo") is None
    assert classify_seed_url("https://example.com/demo") is None


def test_canonical_json_and_sha256_are_stable() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'
    assert sha256_id({"b": 2, "a": 1}) == sha256_id({"a": 1, "b": 2})
    assert sha256_id({"a": 1}).startswith("sha256:")


def test_scope_key_ignores_scope_ref_and_input_order() -> None:
    payload = load_request()
    first = normalize_planning_input(PlanningInput.model_validate(payload))

    payload["scopes"][0]["scope_ref"] = "another-ref"
    payload["scopes"][0]["aliases"] = ["  ＡＣＭＥ  ", "acme"]
    payload["scopes"][0]["seed_urls"] = [
        "https://www.youtube.com/watch?v=demo#ignored"
    ]
    second = normalize_planning_input(PlanningInput.model_validate(payload))

    assert first.normalized_input.scopes[0].scope_key == second.normalized_input.scopes[0].scope_key
    assert first.fingerprint_input == second.fingerprint_input


def test_build_scope_key_uses_only_canonical_semantics() -> None:
    left = {"scope_type": "brand", "aliases": ["acme", "example"]}
    right = {"aliases": ["acme", "example"], "scope_type": "brand"}
    assert build_scope_key(left) == build_scope_key(right)


def test_normalized_input_preserves_first_display_text_and_order() -> None:
    payload = load_request()
    payload["scopes"][0]["aliases"] = ["  ＡＣＭＥ  ", "acme", " Other "]
    payload["scopes"][0]["languages"] = [" EN ", "en", " zh-Hans "]
    result = normalize_planning_input(PlanningInput.model_validate(payload))

    scope = result.normalized_input.scopes[0]
    assert scope.canonical_term == "Acme"
    assert scope.aliases == ["ACME", "Other"]
    assert scope.effective_languages == ["EN", "zh-Hans"]

    semantic_scope = next(
        item
        for item in cast(list[dict[str, Any]], result.fingerprint_input["scopes"])
        if item["scope_key"] == scope.scope_key
    )
    assert semantic_scope["canonical_term"] == "acme"
    assert semantic_scope["aliases"] == ["acme", "other"]
    assert semantic_scope["effective_languages"] == ["en", "zh-hans"]


def test_scope_override_replaces_global_defaults() -> None:
    payload = load_request()
    payload["default_languages"] = ["en", "fr"]
    payload["default_regions"] = ["US", "CA"]
    payload["scopes"][0]["languages"] = ["de"]
    payload["scopes"][0]["regions"] = ["DE"]
    payload["scopes"][0]["platforms"] = ["reddit"]
    result = normalize_planning_input(PlanningInput.model_validate(payload))

    first, second = result.normalized_input.scopes
    assert first.effective_languages == ["de"]
    assert first.effective_regions == ["DE"]
    assert first.effective_platforms == ["reddit"]
    assert second.effective_languages == ["en", "fr"]
    assert second.effective_regions == ["US", "CA"]
    assert second.effective_platforms == ["youtube"]


def test_global_defaults_remain_separate_fingerprint_inputs() -> None:
    payload = load_request()
    payload["default_languages"] = ["fr", "en"]
    payload["default_regions"] = ["CA", "US"]
    payload["default_platforms"] = ["reddit", "youtube"]
    payload["scopes"][0]["languages"] = ["de"]
    payload["scopes"][0]["regions"] = ["DE"]
    payload["scopes"][0]["platforms"] = ["x"]

    fingerprint_input = normalize_planning_input(
        PlanningInput.model_validate(payload)
    ).fingerprint_input

    assert fingerprint_input["default_languages"] == ["en", "fr"]
    assert fingerprint_input["default_regions"] == ["ca", "us"]
    assert fingerprint_input["default_platforms"] == ["youtube", "reddit"]


def test_periodic_seed_url_can_derive_effective_platform() -> None:
    payload = load_request()
    payload["default_platforms"] = []
    payload["scopes"] = [payload["scopes"][0]]
    payload["scopes"][0]["platforms"] = []
    payload["scopes"][0]["seed_urls"] = ["https://youtu.be/demo"]

    result = normalize_planning_input(PlanningInput.model_validate(payload))

    assert result.normalized_input.scopes[0].effective_platforms == ["youtube"]


def test_periodic_unclassified_seed_without_platform_is_exact_field_error() -> None:
    payload = load_request()
    payload["default_platforms"] = []
    payload["scopes"] = [payload["scopes"][0]]
    payload["scopes"][0]["platforms"] = []
    payload["scopes"][0]["seed_urls"] = ["https://example.com/demo"]

    with pytest.raises(WorkflowPlannerInputError) as captured:
        normalize_planning_input(PlanningInput.model_validate(payload))

    assert captured.value.issues == [
        {
            "loc": ["body", "scopes", 0, "platforms"],
            "msg": "periodic_effective_platform_required",
            "type": "value_error",
        }
    ]


@pytest.mark.parametrize(
    ("scope_type", "expected"),
    [
        ("brand", "phrase"),
        ("category", "hybrid"),
        ("competitor", "phrase"),
        ("topic", "phrase"),
        ("campaign", "phrase"),
    ],
)
def test_match_mode_defaults_are_scope_type_specific(
    scope_type: str,
    expected: str,
) -> None:
    payload = load_request()
    scope = payload["scopes"][0]
    scope["scope_type"] = scope_type
    scope["match_mode"] = None
    payload["scopes"] = [scope]

    result = normalize_planning_input(PlanningInput.model_validate(payload))

    assert result.normalized_input.scopes[0].match_mode == expected


def test_excluded_terms_take_precedence_in_semantic_trace() -> None:
    payload = load_request()
    payload["scopes"][0]["aliases"] = ["Acme sale"]
    payload["scopes"][0]["include_terms"] = ["Jobs", "New release"]
    payload["scopes"][0]["exclude_terms"] = [" jobs "]

    result = normalize_planning_input(PlanningInput.model_validate(payload))

    conflicts = [
        entry for entry in result.semantic_entries if entry.code == "excluded_term_precedence"
    ]
    assert len(conflicts) == 1
    assert conflicts[0].details == {
        "normalized_term": "jobs",
        "origins": ["include"],
    }
    assert result.normalized_input.scopes[0].include_terms == ["Jobs", "New release"]


def test_semantic_duplicate_scopes_collapse_and_keep_ref_mappings() -> None:
    payload = load_request()
    first = payload["scopes"][0]
    duplicate = deepcopy(first)
    duplicate["scope_ref"] = "scope-duplicate"
    duplicate["canonical_term"] = "  ＡＣＭＥ "
    duplicate["aliases"] = ["acme"]
    duplicate["seed_urls"] = ["https://WWW.YOUTUBE.COM/watch?v=demo#ignored"]
    payload["scopes"] = [first, duplicate]

    result = normalize_planning_input(PlanningInput.model_validate(payload))

    assert len(result.normalized_input.scopes) == 1
    assert result.normalized_input.scopes[0].source_scope_refs == [
        "scope-1",
        "scope-duplicate",
    ]
    assert [mapping.scope_ref for mapping in result.scope_ref_map] == [
        "scope-1",
        "scope-duplicate",
    ]
    assert [entry.code for entry in result.input_diagnostics].count(
        "duplicate_scope_collapsed"
    ) == 1
    assert len(cast(list[object], result.fingerprint_input["scopes"])) == 1


def test_explicit_platforms_do_not_expand_from_seed_urls() -> None:
    payload = load_request()
    payload["scopes"] = [payload["scopes"][0]]
    payload["scopes"][0]["platforms"] = ["reddit"]
    payload["scopes"][0]["seed_urls"] = ["https://youtu.be/demo"]

    result = normalize_planning_input(PlanningInput.model_validate(payload))

    assert result.normalized_input.scopes[0].effective_platforms == ["reddit"]
    diagnostic = next(
        entry for entry in result.input_diagnostics if entry.code == "platform_not_selected"
    )
    assert diagnostic.details["classified_platform"] == "youtube"


def test_batch_keyword_scope_cannot_borrow_a_seed_url_platform() -> None:
    payload = load_request("batch_research_request_v1.json")
    payload["default_platforms"] = []
    payload["scopes"][0]["platforms"] = []
    payload["scopes"][0]["seed_urls"] = ["https://youtu.be/demo"]

    with pytest.raises(ValidationError, match="batch_query_platform_required"):
        PlanningInput.model_validate(payload)


def test_batch_seed_only_known_url_derives_platform() -> None:
    payload = build_seed_only_batch("https://www.reddit.com/r/demo")

    result = normalize_planning_input(PlanningInput.model_validate(payload))

    assert result.normalized_input.scopes[0].effective_platforms == ["reddit"]


def test_batch_seed_only_unclassified_url_is_retained_with_diagnostic() -> None:
    payload = build_seed_only_batch("https://example.com/research/demo")

    result = normalize_planning_input(PlanningInput.model_validate(payload))

    assert result.normalized_input.scopes[0].effective_platforms == []
    assert result.normalized_input.scopes[0].seed_urls == [
        "https://example.com/research/demo"
    ]
    diagnostic = next(
        entry for entry in result.input_diagnostics if entry.code == "seed_url_unclassified"
    )
    assert diagnostic.details["seed_url"] == "https://example.com/research/demo"


@pytest.mark.parametrize("scope_type", ["brand", "category", "competitor"])
def test_canonical_scope_types_require_canonical_term(scope_type: str) -> None:
    payload = load_request()
    payload["scopes"] = [payload["scopes"][0]]
    payload["scopes"][0]["scope_type"] = scope_type
    payload["scopes"][0]["canonical_term"] = None

    with pytest.raises(ValidationError, match="canonical_term_required"):
        PlanningInput.model_validate(payload)


@pytest.mark.parametrize("scope_type", ["topic", "campaign"])
def test_topic_and_campaign_allow_seed_url_only(scope_type: str) -> None:
    payload = build_seed_only_batch("https://example.com/research/demo")
    payload["scopes"][0]["scope_type"] = scope_type

    result = normalize_planning_input(PlanningInput.model_validate(payload))

    assert result.normalized_input.scopes[0].canonical_term is None


def test_scope_count_accepts_20_and_rejects_21() -> None:
    payload = load_request()
    base = payload["scopes"][0]
    payload["scopes"] = [
        {**deepcopy(base), "scope_ref": f"scope-{index}"} for index in range(20)
    ]
    assert len(PlanningInput.model_validate(payload).scopes) == 20

    payload["scopes"].append({**deepcopy(base), "scope_ref": "scope-20"})
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)


def test_term_count_accepts_50_and_rejects_51() -> None:
    payload = load_request()
    payload["scopes"][0]["aliases"] = [f"alias-{index}" for index in range(50)]
    assert len(PlanningInput.model_validate(payload).scopes[0].aliases) == 50

    payload["scopes"][0]["aliases"].append("alias-50")
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)


def test_seed_url_count_accepts_100_and_rejects_101() -> None:
    payload = load_request()
    payload["scopes"] = [payload["scopes"][0]]
    payload["scopes"][0]["seed_urls"] = [
        f"https://youtu.be/demo?index={index}" for index in range(100)
    ]
    assert len(PlanningInput.model_validate(payload).scopes[0].seed_urls) == 100

    payload["scopes"][0]["seed_urls"].append("https://youtu.be/overflow")
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)


def test_periodic_schedule_is_required_by_request_contract() -> None:
    payload = load_request()
    payload["schedule_intent"] = None

    with pytest.raises(ValidationError, match="periodic_schedule_required"):
        PlanningInput.model_validate(payload)


def test_fingerprint_input_is_recursively_reference_free() -> None:
    result = normalize_planning_input(PlanningInput.model_validate(load_request()))

    assert_reference_free(result.fingerprint_input)
