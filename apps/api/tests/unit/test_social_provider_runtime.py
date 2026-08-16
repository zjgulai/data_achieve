from __future__ import annotations

import pytest

from data_intelligence_hub.schemas.social_provider import (
    SocialDatasetPreviewRequest,
    SocialExecutionDryRunRequest,
    SocialNormalizationPreviewRequest,
    SocialProviderAdapterPlanRequest,
    SocialProviderDependencyGateRequest,
    SocialProviderGateRequest,
    SocialProviderLiveApprovalTemplateRequest,
    SocialProviderReadinessRequest,
    SocialProviderSourceTemplateRequest,
    SocialRawPreviewRequest,
    SocialTaskRunApprovalTemplateRequest,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    SocialProviderCatalogLoadError,
    SocialProviderGateAuthorizationError,
    SocialProviderUnknownPlatformError,
)
from data_intelligence_hub.services.social_provider import (
    get_social_provider_catalog,
    prepare_social_dataset_preview,
    prepare_social_execution_dry_run,
    prepare_social_normalization_preview,
    prepare_social_provider_adapter_plan,
    prepare_social_provider_dependency_gate,
    prepare_social_provider_gate,
    prepare_social_provider_live_approval_template,
    prepare_social_provider_readiness,
    prepare_social_provider_source_template,
    prepare_social_raw_preview,
    prepare_social_task_run_approval_template,
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


def test_social_provider_catalog_is_projected_from_v2_without_live_side_effects() -> None:
    catalog = get_social_provider_catalog()

    assert catalog.schema_version == "external_provider_catalog.v1"
    assert catalog.provider_call is False
    assert len(catalog.providers) == 7
    assert all(provider.endpoint_contracts for provider in catalog.providers)


def test_social_provider_catalog_preserves_legacy_load_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from data_intelligence_hub.services import social_provider as service

    def raise_v2_load_error() -> None:
        raise CapabilityCatalogLoadError

    monkeypatch.setattr(
        service,
        "project_external_provider_catalog_v1",
        raise_v2_load_error,
    )
    with pytest.raises(SocialProviderCatalogLoadError):
        get_social_provider_catalog()


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
    assert readiness.schema_version == "social_provider_readiness.v2"
    assert readiness.declared_readiness is False
    assert readiness.readiness_basis == "caller_declared"
    assert readiness.execution_enabled is False
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
    assert readiness.schema_version == "social_provider_readiness.v2"
    assert readiness.declared_readiness is True
    assert readiness.readiness_basis == "caller_declared"
    assert readiness.execution_enabled is False
    assert readiness.provider_call_allowed is False
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

    assert gate.schema_version == "social_provider_gate.v2"
    assert gate.declared_readiness is True
    assert gate.readiness_basis == "caller_declared"
    assert gate.execution_enabled is False
    assert gate.provider_call_allowed is False
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
    source_create_payload = template.source_create_payload
    assert source_create_payload is not None
    assert source_create_payload["name"] == "Reddit search fixture source"
    assert source_create_payload["type"] == "manual_json"
    assert source_create_payload["config"]["entity_type"] == "social_provider_fixture"
    assert source_create_payload["config"]["json_data"]["provider_call"] is False
    assert source_create_payload["config"]["json_data"]["endpoints"] == ["search"]
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


def test_social_normalization_preview_youtube_post_and_voc_no_side_effects() -> None:
    preview = prepare_social_normalization_preview(
        SocialNormalizationPreviewRequest(
            platform="youtube",
            endpoint="videos.list",
            fixture_limit=1,
        ),
    )

    assert preview.schema_version == "social_normalization_preview.v1"
    assert preview.platform == "youtube"
    assert preview.provider_id == "youtube.v3"
    assert preview.fixture_only is True
    assert preview.provider_call_allowed is False
    assert preview.provider_call_attempted is False
    assert preview.credential_read_attempted is False
    assert preview.production_write_allowed is False
    assert preview.normalization_write_allowed is False
    assert preview.dataset_write_allowed is False
    assert len(preview.raw_records) == 1

    post_items = [
        item for item in preview.normalized_items if item.schema_version == "social_post.v1"
    ]
    voc_items = [
        item for item in preview.normalized_items if item.schema_version == "social_voc_item.v1"
    ]

    assert len(post_items) == 1
    assert len(voc_items) == 1
    assert post_items[0].raw_record_id == preview.raw_records[0].raw_record_id
    assert post_items[0].evidence_ref == preview.raw_records[0].evidence_ref
    assert post_items[0].author_policy == "hashed"
    assert post_items[0].payload["external_post_id"] == "yt_fixture_video_1"
    assert voc_items[0].payload["source_item_schema"] == "social_post.v1"
    assert voc_items[0].payload["raw_record_id"] == preview.raw_records[0].raw_record_id
    assert voc_items[0].payload["llm_call_attempted"] is False


def test_social_normalization_preview_reddit_comments_make_comment_and_voc() -> None:
    preview = prepare_social_normalization_preview(
        SocialNormalizationPreviewRequest(
            platform="reddit",
            endpoint="comments.new",
            fixture_limit=1,
        ),
    )

    comment_items = [
        item for item in preview.normalized_items if item.schema_version == "social_comment.v1"
    ]
    voc_items = [
        item for item in preview.normalized_items if item.schema_version == "social_voc_item.v1"
    ]

    assert preview.provider_call_attempted is False
    assert preview.production_write_allowed is False
    assert len(comment_items) == 1
    assert len(voc_items) == 1
    assert comment_items[0].raw_record_id == preview.raw_records[0].raw_record_id
    assert comment_items[0].payload["external_post_id"] == "reddit_fixture_post_1"
    assert comment_items[0].payload["external_comment_id"] == "reddit_fixture_post_1:comment:1"
    assert comment_items[0].payload["body"] == "Reddit fixture post 1"
    assert voc_items[0].payload["source_item_schema"] == "social_comment.v1"
    assert voc_items[0].evidence_ref == preview.raw_records[0].evidence_ref


def test_social_normalization_preview_blocks_live_and_retained_author_fields() -> None:
    preview = prepare_social_normalization_preview(
        SocialNormalizationPreviewRequest(
            platform="reddit",
            endpoint="search",
            authorized=True,
            approval_id="approval-ignored",
            include_live_comparison=True,
            author_policy="retained_with_approval",
        ),
    )

    assert preview.provider_call_allowed is False
    assert preview.provider_call_attempted is False
    assert preview.credential_read_attempted is False
    assert preview.production_write_allowed is False
    assert preview.normalization_write_allowed is False
    assert preview.dataset_write_allowed is False
    assert "live_comparison_requires_separate_l4_authorization" in preview.blocked_reasons
    assert "authorized_ignored_for_normalization_preview" in preview.blocked_reasons
    assert "approval_id_ignored_for_normalization_preview" in preview.blocked_reasons
    assert "author_retention_requires_separate_l4_authorization" in preview.blocked_reasons
    assert {item.author_policy for item in preview.normalized_items} == {"hashed"}


def test_social_dataset_preview_reddit_comments_returns_voc_rows() -> None:
    preview = prepare_social_dataset_preview(
        SocialDatasetPreviewRequest(
            platform="reddit",
            endpoint="comments.new",
            fixture_limit=2,
            dataset_name="Reddit comments VOC fixture",
        ),
    )

    assert preview.schema_version == "social_dataset_preview.v1"
    assert preview.platform == "reddit"
    assert preview.provider_id == "reddit.praw"
    assert preview.dataset_name == "Reddit comments VOC fixture"
    assert preview.dataset_type == "social_voc_fixture_preview"
    assert preview.dataset_schema_version == "social_voc_dataset.v1"
    assert preview.fixture_only is True
    assert preview.provider_call_allowed is False
    assert preview.provider_call_attempted is False
    assert preview.credential_read_attempted is False
    assert preview.production_write_allowed is False
    assert preview.dataset_write_allowed is False
    assert preview.dataset_created is False
    assert preview.dataset_version_created is False
    assert preview.export_created is False
    assert preview.row_count == 2
    assert preview.truncated is False
    assert len(preview.rows) == 2
    assert len(preview.normalized_items) == 4
    assert preview.rows[0].source_schema_version == "social_voc_item.v1"
    assert preview.rows[0].raw_record_id == preview.normalized_items[1].raw_record_id
    assert preview.rows[0].evidence_ref == preview.normalized_items[1].evidence_ref
    assert preview.rows[0].payload["text_excerpt"] == "Reddit fixture post 1"
    assert preview.rows[0].payload["provider_call"] is False
    assert preview.rows[0].payload["llm_call_attempted"] is False


def test_social_dataset_preview_youtube_limits_rows_without_write() -> None:
    preview = prepare_social_dataset_preview(
        SocialDatasetPreviewRequest(
            platform="youtube",
            endpoint="videos.list",
            fixture_limit=3,
            max_rows=2,
        ),
    )

    assert preview.row_count == 2
    assert preview.source_item_count == 3
    assert preview.truncated is True
    assert preview.rows[0].payload["platform"] == "youtube"
    assert preview.rows[0].payload["raw_record_id"] == preview.rows[0].raw_record_id
    assert preview.dataset_write_allowed is False
    assert preview.production_write_allowed is False


def test_social_dataset_preview_blocks_save_export_live_and_retained_author() -> None:
    preview = prepare_social_dataset_preview(
        SocialDatasetPreviewRequest(
            platform="reddit",
            endpoint="search",
            authorized=True,
            approval_id="approval-ignored",
            include_live_comparison=True,
            author_policy="retained_with_approval",
            save_requested=True,
            export_requested=True,
        ),
    )

    assert preview.provider_call_allowed is False
    assert preview.provider_call_attempted is False
    assert preview.credential_read_attempted is False
    assert preview.production_write_allowed is False
    assert preview.dataset_write_allowed is False
    assert preview.dataset_created is False
    assert preview.dataset_version_created is False
    assert preview.export_created is False
    assert "authorized_ignored_for_dataset_preview" in preview.blocked_reasons
    assert "approval_id_ignored_for_dataset_preview" in preview.blocked_reasons
    assert "live_comparison_requires_separate_l4_authorization" in preview.blocked_reasons
    assert "dataset_save_requires_separate_l4_authorization" in preview.blocked_reasons
    assert "dataset_export_requires_separate_l4_authorization" in preview.blocked_reasons
    assert "author_retention_requires_separate_l4_authorization" in preview.blocked_reasons
    assert {row.author_policy for row in preview.rows} == {"hashed"}


def test_social_task_run_approval_template_reddit_packet_no_write() -> None:
    template = prepare_social_task_run_approval_template(
        SocialTaskRunApprovalTemplateRequest(
            platform="reddit",
            endpoints=["comments.new"],
            intended_use="small scoped Reddit comments VOC fixture run",
            source_name="Reddit comments fixture source",
            task_name="Reddit comments fixture task",
            dataset_name="Reddit comments VOC fixture",
            credential_reference="secret:reddit-oauth-readonly",
            max_requests=5,
            max_items=20,
            max_rows=20,
            max_cost_usd=0,
        ),
    )

    assert template.schema_version == "social_task_run_approval_template.v1"
    assert template.platform == "reddit"
    assert template.provider_id == "reddit.praw"
    assert template.provider_call_allowed is False
    assert template.provider_call_attempted is False
    assert template.credential_read_attempted is False
    assert template.source_create_allowed is False
    assert template.task_create_allowed is False
    assert template.task_run_allowed is False
    assert template.dataset_write_allowed is False
    assert template.export_allowed is False
    assert template.production_write_allowed is False
    assert template.blocked_reasons == []
    packet = template.approval_packet
    assert packet["schema_version"] == "social_task_run_l4_approval_packet.v1"
    assert packet["authorized"] is False
    assert packet["provider_call"] is False
    assert packet["source_create"] is False
    assert packet["task_create"] is False
    assert packet["task_run"] is False
    assert packet["dataset_save"] is False
    assert packet["export_create"] is False
    assert packet["cleanup_required"] is True
    assert packet["credential_reference"] == "secret:reddit-oauth-readonly"
    assert packet["scope"]["endpoints"] == ["comments.new"]
    assert packet["budget"]["max_requests"] == 5
    assert packet["dataset"]["name"] == "Reddit comments VOC fixture"
    assert "confirm_no_ai_training" in template.required_confirmations
    assert template.next_required_authorization == "L4_social_task_run_authorization_required"


def test_social_task_run_approval_template_blocks_unknown_endpoint_and_missing_credential() -> None:
    template = prepare_social_task_run_approval_template(
        SocialTaskRunApprovalTemplateRequest(
            platform="youtube",
            endpoints=["videos.invalid"],
            intended_use="small scoped YouTube fixture run",
        ),
    )

    assert template.provider_call_allowed is False
    assert template.provider_call_attempted is False
    assert template.credential_read_attempted is False
    assert template.approval_packet["credential_reference"] is None
    assert "scope_missing:videos.invalid" in template.blocked_reasons
    assert "credential_reference_required_before_task_run" in template.blocked_reasons


def test_social_task_run_approval_template_records_requested_live_fields_without_execution() -> (
    None
):
    template = prepare_social_task_run_approval_template(
        SocialTaskRunApprovalTemplateRequest(
            platform="reddit",
            endpoints=["search"],
            intended_use="future owner-approved Reddit search run",
            credential_reference="env:REDDIT_READONLY_OAUTH",
            authorized=True,
            approval_id="approval-recorded-only",
            allow_ai_training=True,
            dataset_save_requested=True,
            export_requested=True,
        ),
    )

    assert template.provider_call_allowed is False
    assert template.provider_call_attempted is False
    assert template.source_create_allowed is False
    assert template.task_run_allowed is False
    assert template.dataset_write_allowed is False
    assert template.export_allowed is False
    assert template.approval_packet["authorized"] is False
    assert template.approval_packet["requested_authorized"] is True
    assert template.approval_packet["approval_id"] == "approval-recorded-only"
    assert template.approval_packet["requested_dataset_save"] is True
    assert template.approval_packet["requested_export"] is True
    assert "authorized_recorded_but_not_executed" in template.blocked_reasons
    assert "allow_ai_training_must_be_false" in template.blocked_reasons
    assert "dataset_save_requires_separate_l4_authorization" in template.blocked_reasons
    assert "dataset_export_requires_separate_l4_authorization" in template.blocked_reasons


def test_social_execution_dry_run_reddit_fixture_bundle_no_write() -> None:
    dry_run = prepare_social_execution_dry_run(
        SocialExecutionDryRunRequest(
            platform="reddit",
            endpoint="comments.new",
            fixture_limit=2,
            dataset_name="Reddit comments VOC fixture",
            source_name="Reddit comments fixture source",
            task_name="Reddit comments fixture task",
            intended_use="small scoped Reddit comments fixture dry-run",
            credential_reference="secret:reddit-oauth-readonly",
            max_requests=5,
            max_items=20,
            max_rows=20,
        ),
    )

    assert dry_run.schema_version == "social_execution_dry_run.v1"
    assert dry_run.platform == "reddit"
    assert dry_run.provider_id == "reddit.praw"
    assert dry_run.fixture_only is True
    assert dry_run.provider_call_allowed is False
    assert dry_run.provider_call_attempted is False
    assert dry_run.credential_read_attempted is False
    assert dry_run.source_create_allowed is False
    assert dry_run.task_create_allowed is False
    assert dry_run.task_run_allowed is False
    assert dry_run.dataset_write_allowed is False
    assert dry_run.export_allowed is False
    assert dry_run.production_write_allowed is False
    assert [stage.stage for stage in dry_run.execution_plan] == [
        "readiness",
        "raw_preview",
        "normalization_preview",
        "dataset_preview",
        "source_template",
        "task_run_approval_template",
    ]
    assert all(stage.provider_call is False for stage in dry_run.execution_plan)
    assert all(stage.production_write is False for stage in dry_run.execution_plan)
    assert dry_run.raw_preview.records[0].schema_version == "social_raw.v1"
    assert dry_run.normalization_preview.normalized_items
    assert dry_run.dataset_preview.row_count == 2
    assert dry_run.dataset_preview.dataset_write_allowed is False
    assert dry_run.source_template.source_create_payload is not None
    assert dry_run.source_template.source_create_allowed is False
    assert dry_run.task_run_approval_template.approval_packet["task_run"] is False
    assert dry_run.task_run_approval_template.approval_packet["dataset_save"] is False
    assert dry_run.next_required_authorization == "L4_social_execution_authorization_required"


def test_social_execution_dry_run_blocks_unknown_endpoint_without_execution() -> None:
    dry_run = prepare_social_execution_dry_run(
        SocialExecutionDryRunRequest(
            platform="youtube",
            endpoint="videos.invalid",
            intended_use="small scoped YouTube fixture dry-run",
        ),
    )

    assert dry_run.provider_call_allowed is False
    assert dry_run.provider_call_attempted is False
    assert dry_run.credential_read_attempted is False
    assert dry_run.raw_preview.records == []
    assert dry_run.normalization_preview.raw_records == []
    assert dry_run.dataset_preview.rows == []
    assert dry_run.source_template.source_create_payload is None
    assert "scope_missing:videos.invalid" in dry_run.blocked_reasons
    assert "credential_missing:api_key" in dry_run.blocked_reasons


def test_social_execution_dry_run_records_live_intent_as_blockers() -> None:
    dry_run = prepare_social_execution_dry_run(
        SocialExecutionDryRunRequest(
            platform="reddit",
            endpoint="search",
            intended_use="future owner-approved Reddit search run",
            credential_reference="env:REDDIT_READONLY_OAUTH",
            authorized=True,
            approval_id="approval-recorded-only",
            include_live_comparison=True,
            dataset_save_requested=True,
            export_requested=True,
            allow_ai_training=True,
            author_policy="retained_with_approval",
        ),
    )

    assert dry_run.provider_call_allowed is False
    assert dry_run.provider_call_attempted is False
    assert dry_run.source_create_allowed is False
    assert dry_run.task_run_allowed is False
    assert dry_run.dataset_write_allowed is False
    assert dry_run.export_allowed is False
    assert "authorized_ignored_for_execution_dry_run" in dry_run.blocked_reasons
    assert "approval_id_ignored_for_execution_dry_run" in dry_run.blocked_reasons
    assert "live_comparison_requires_separate_l4_authorization" in dry_run.blocked_reasons
    assert "allow_ai_training_must_be_false" in dry_run.blocked_reasons
    assert "dataset_save_requires_separate_l4_authorization" in dry_run.blocked_reasons
    assert "dataset_export_requires_separate_l4_authorization" in dry_run.blocked_reasons
    assert "author_retention_requires_separate_l4_authorization" in dry_run.blocked_reasons


def test_social_provider_unknown_platform_is_rejected() -> None:
    with pytest.raises(SocialProviderUnknownPlatformError):
        get_social_provider_catalog(platform="no-such-platform")
