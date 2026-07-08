from __future__ import annotations

import pytest

from data_intelligence_hub.schemas.social_provider import (
    SocialProviderAdapterPlanRequest,
    SocialProviderDependencyGateRequest,
    SocialProviderGateRequest,
    SocialProviderLiveApprovalTemplateRequest,
    SocialProviderReadinessRequest,
    SocialProviderSourceTemplateRequest,
    SocialRawPreviewRequest,
)
from data_intelligence_hub.services.exceptions import (
    SocialProviderGateAuthorizationError,
    SocialProviderUnknownPlatformError,
)
from data_intelligence_hub.services.social_provider import (
    get_social_provider_catalog,
    prepare_social_provider_adapter_plan,
    prepare_social_provider_dependency_gate,
    prepare_social_provider_gate,
    prepare_social_provider_live_approval_template,
    prepare_social_provider_readiness,
    prepare_social_provider_source_template,
    prepare_social_raw_preview,
)


def test_social_provider_catalog_contains_overseas_targets() -> None:
    catalog = get_social_provider_catalog()

    assert catalog.schema_version == "external_provider_catalog.v1"
    platforms = [provider.platform for provider in catalog.providers]
    assert set(platforms) >= {
        "youtube",
        "reddit",
        "x",
        "instagram",
        "threads",
        "tiktok",
        "linkedin",
    }


def test_social_provider_catalog_filter_platform_keeps_request_scope() -> None:
    catalog = get_social_provider_catalog(platform="youtube")

    assert catalog.providers
    assert len(catalog.providers) == 1
    assert catalog.providers[0].platform == "youtube"


def test_social_provider_catalog_filter_resource_group() -> None:
    catalog = get_social_provider_catalog(resource_group="video_detail")

    assert catalog.providers
    assert any(item.platform == "youtube" for item in catalog.providers)


def test_social_provider_catalog_exposes_selected_sdk_metadata() -> None:
    catalog = get_social_provider_catalog(platform="youtube")

    sdk_selection = catalog.providers[0].sdk_selection
    assert sdk_selection is not None
    assert sdk_selection.package == "google-api-python-client"
    assert sdk_selection.status == "selected"


def test_social_provider_readiness_blocks_missing_credentials() -> None:
    readiness = prepare_social_provider_readiness(
        SocialProviderReadinessRequest(
            platform="youtube", endpoints=["search.list", "videos.list"]
        ),
    )

    assert readiness.readiness is False
    assert readiness.provider_call_allowed is False
    assert readiness.provider_call_attempted is False
    assert readiness.missing_credentials == ["api_key"]
    assert readiness.missing_scope == []
    assert "credential_missing:api_key" in readiness.blocked_reasons


def test_social_provider_readiness_rejects_unknown_endpoint() -> None:
    readiness = prepare_social_provider_readiness(
        SocialProviderReadinessRequest(
            platform="youtube",
            endpoints=["search.list", "videos.invalid"],
            credentials_ready={"api_key": True},
        ),
    )

    assert readiness.readiness is False
    assert readiness.provider_call_allowed is False
    assert readiness.missing_scope == ["videos.invalid"]


def test_social_provider_readiness_successfully_checks_policy_without_ai_training() -> None:
    readiness = prepare_social_provider_readiness(
        SocialProviderReadinessRequest(
            platform="reddit",
            endpoints=["hot.list", "new.list", "search"],
            credentials_ready={"oauth_token": True, "client_id": True, "client_secret": True},
        ),
    )

    assert readiness.readiness is True
    assert readiness.provider_call_allowed is True
    assert readiness.provider_call_attempted is False
    assert readiness.policy_blockers == []


def test_social_provider_gate_blocks_without_authorization() -> None:
    with pytest.raises(SocialProviderGateAuthorizationError):
        prepare_social_provider_gate(
            SocialProviderGateRequest(
                authorized=False,
                platform="youtube",
                endpoints=["search.list"],
                credentials_ready={"api_key": True},
                approval_id="test-approval",
            ),
        )


def test_social_provider_gate_returns_fixture_run_scope() -> None:
    gate = prepare_social_provider_gate(
        SocialProviderGateRequest(
            authorized=True,
            platform="youtube",
            endpoints=["search.list", "videos.list"],
            credentials_ready={"api_key": True},
            approval_id="batch-a",
            max_requests=10,
        ),
    )

    assert gate.provider_call_allowed is True
    assert gate.provider_call_attempted is False
    assert gate.run_scope == "fixture_gate_only"
    assert gate.production_write_allowed is False


def test_social_provider_live_approval_template_requires_l4_fields() -> None:
    template = prepare_social_provider_live_approval_template(
        SocialProviderLiveApprovalTemplateRequest(
            platform="youtube",
            endpoints=["videos.list"],
            intended_use="small scoped read-only YouTube validation",
        ),
    )

    assert template.provider_call_allowed is False
    assert template.provider_call_attempted is False
    assert template.dependency_install_allowed is False
    assert template.production_write_allowed is False
    assert template.approval_packet["provider_call"] is False
    assert template.approval_packet["optional_dependency_extra"] == "social-youtube"
    assert "credential_reference_required_before_live" in template.blocked_reasons


def test_social_provider_dependency_gate_blocks_without_authorization() -> None:
    gate = prepare_social_provider_dependency_gate(
        SocialProviderDependencyGateRequest(
            platform="reddit",
            install_scope="local_dev_optional_dependency",
        ),
    )

    assert gate.dependency_install_allowed is False
    assert gate.dependency_install_executed is False
    assert gate.provider_call_attempted is False
    assert gate.credential_read_attempted is False
    assert "authorization_required" in gate.blocked_reasons
    assert gate.installation_plan["pyproject_extra"] == "social-reddit"


def test_social_provider_dependency_gate_returns_install_plan_when_authorized() -> None:
    gate = prepare_social_provider_dependency_gate(
        SocialProviderDependencyGateRequest(
            platform="youtube",
            authorized=True,
            approval_id="approval-local-deps",
            confirm_dependency_review=True,
            install_scope="local_dev_optional_dependency",
        ),
    )

    assert gate.dependency_install_allowed is True
    assert gate.dependency_install_executed is False
    assert gate.live_adapter_enabled is False
    assert gate.provider_call_attempted is False
    assert gate.installation_plan["package"] == "google-api-python-client"
    assert gate.installation_plan["install_command"] == [
        "python",
        "-m",
        "pip",
        "install",
        ".[social-youtube]",
    ]


def test_social_provider_adapter_plan_youtube_fixture_replay_no_side_effects() -> None:
    plan = prepare_social_provider_adapter_plan(
        SocialProviderAdapterPlanRequest(
            platform="youtube",
            endpoints=["videos.list"],
            fixture_limit=2,
        ),
    )

    assert plan.schema_version == "social_provider_adapter_plan.v1"
    assert plan.platform == "youtube"
    assert plan.provider_id == "youtube.v3"
    assert plan.sdk_selection is not None
    assert plan.sdk_selection.package == "google-api-python-client"
    assert plan.adapter_module == "data_intelligence_hub.social_api.youtube.google_api_client"
    assert plan.dependency_import_name == "googleapiclient"
    assert plan.fixture_replay_supported is True
    assert plan.provider_call_allowed is False
    assert plan.provider_call_attempted is False
    assert plan.credential_read_attempted is False
    assert plan.live_client_created is False
    assert plan.production_write_allowed is False
    assert plan.planned_operations == [
        {
            "operation_id": "fixture:youtube.v3:videos.list",
            "endpoint": "videos.list",
            "sdk_package": "google-api-python-client",
            "request_mode": "fixture_replay",
            "fixture_record_count": 2,
            "provider_call": False,
        }
    ]


def test_social_provider_adapter_plan_blocks_reddit_live_and_credentials() -> None:
    plan = prepare_social_provider_adapter_plan(
        SocialProviderAdapterPlanRequest(
            platform="reddit",
            endpoints=["search"],
            mode="live_dry_run",
            authorized=True,
            credential_reference="env:REDDIT_CLIENT_ID",
        ),
    )

    assert plan.provider_call_allowed is False
    assert plan.provider_call_attempted is False
    assert plan.credential_read_attempted is False
    assert plan.live_client_created is False
    assert "live_adapter_requires_separate_l4_authorization" in plan.blocked_reasons
    assert "authorized_ignored_for_fixture_adapter_plan" in plan.blocked_reasons
    assert "credential_reference_ignored_for_fixture_adapter_plan" in plan.blocked_reasons
    assert plan.next_required_authorization == "L4_social_api_live_adapter_gate_required"


def test_social_provider_adapter_plan_blocks_unknown_endpoint() -> None:
    plan = prepare_social_provider_adapter_plan(
        SocialProviderAdapterPlanRequest(
            platform="youtube",
            endpoints=["videos.invalid"],
        ),
    )

    assert plan.adapter_ready is False
    assert plan.provider_call_allowed is False
    assert plan.planned_operations == []
    assert "scope_missing:videos.invalid" in plan.blocked_reasons


def test_social_provider_source_template_returns_manual_json_candidate_without_write() -> None:
    template = prepare_social_provider_source_template(
        SocialProviderSourceTemplateRequest(
            platform="reddit",
            endpoints=["search"],
            source_name="Reddit search fixture source",
        ),
    )

    assert template.schema_version == "social_provider_source_template.v1"
    assert template.platform == "reddit"
    assert template.provider_id == "reddit.praw"
    assert template.source_type == "manual_json"
    assert template.template_strategy == "manual_json_authorized_import"
    assert template.source_create_allowed is False
    assert template.source_created is False
    assert template.task_created is False
    assert template.provider_call_attempted is False
    assert template.credential_read_attempted is False
    assert template.production_write_allowed is False
    assert template.fixture_only is True
    assert template.source_create_payload["name"] == "Reddit search fixture source"
    assert template.source_create_payload["type"] == "manual_json"
    assert template.source_create_payload["config"]["entity_type"] == "social_provider_fixture"
    assert template.source_create_payload["config"]["json_data"]["provider_call"] is False
    assert template.source_create_payload["config"]["json_data"]["endpoints"] == ["search"]
    assert template.next_required_authorization == "L4_social_api_source_create_gate_required"


def test_social_provider_source_template_blocks_unknown_endpoint_and_live_fields() -> None:
    template = prepare_social_provider_source_template(
        SocialProviderSourceTemplateRequest(
            platform="youtube",
            endpoints=["videos.invalid"],
            authorized=True,
            approval_id="approval-ignored",
            credential_reference="env:YOUTUBE_API_KEY",
        ),
    )

    assert template.source_create_allowed is False
    assert template.source_create_payload is None
    assert "scope_missing:videos.invalid" in template.blocked_reasons
    assert "authorized_ignored_for_source_template_preview" in template.blocked_reasons
    assert "approval_id_ignored_for_source_template_preview" in template.blocked_reasons
    assert "credential_reference_ignored_for_source_template_preview" in template.blocked_reasons


def test_social_raw_preview_returns_fixture_records_without_provider_call() -> None:
    preview = prepare_social_raw_preview(
        SocialRawPreviewRequest(
            platform="youtube",
            endpoint="videos.list",
            fixture_limit=2,
        ),
    )

    assert preview.fixture_only is True
    assert preview.provider_call_allowed is False
    assert preview.provider_call_attempted is False
    assert preview.production_write_allowed is False
    assert len(preview.records) == 2
    assert preview.records[0].schema_version == "social_raw.v1"
    assert preview.records[0].payload["provider_call"] is False


def test_social_raw_preview_blocks_unknown_endpoint_without_records() -> None:
    preview = prepare_social_raw_preview(
        SocialRawPreviewRequest(
            platform="reddit",
            endpoint="invalid.endpoint",
        ),
    )

    assert preview.records == []
    assert "scope_missing:invalid.endpoint" in preview.blocked_reasons


def test_social_raw_preview_rejects_live_comparison_by_default() -> None:
    preview = prepare_social_raw_preview(
        SocialRawPreviewRequest(
            platform="reddit",
            endpoint="search",
            include_live_comparison=True,
            authorized=True,
            approval_id="approval-ignored",
        ),
    )

    assert preview.provider_call_allowed is False
    assert preview.provider_call_attempted is False
    assert "live_comparison_requires_separate_l4_authorization" in preview.blocked_reasons
    assert "approval_id_ignored_for_fixture_preview" in preview.blocked_reasons


def test_social_provider_unknown_platform_is_rejected() -> None:
    with pytest.raises(SocialProviderUnknownPlatformError):
        get_social_provider_catalog(platform="no-such-platform")
