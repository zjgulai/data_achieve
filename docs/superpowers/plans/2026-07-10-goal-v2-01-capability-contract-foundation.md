---
title: GOAL-V2-01 能力合同与 Catalog 底座 Implementation Plan
doc_type: implementation_plan
topic: goal-v2-01-capability-contract-foundation
status: approved
evidence_level: L1-public-or-runtime
provider_call: false
production_boundary: production unchanged
private_deploy_boundary: self_hosted_collectors
created: 2026-07-10
updated: 2026-07-10
owner: self
source: codex
---

# GOAL-V2-01 能力合同与 Catalog 底座 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 V2.0 统一能力词表、Pydantic 合同、规范化海外社媒 Catalog 与 `external_provider_catalog.v1` 兼容投影，同时保持全部 Provider、Credential、数据库和生产边界不变。

**Architecture:** 使用一个版本化 JSON Fixture 作为 GOAL-V2-01 的运行时单一事实源。新 `capability_catalog.v1` 服务负责严格校验与过滤；现有 Social Provider 服务通过兼容投影继续返回 `external_provider_catalog.v1`，因此已有 Readiness、Gate、Adapter Plan 和 Preview 不需要重写。数据库持久化、Matrix API 和前端矩阵属于 GOAL-V2-02。

**Tech Stack:** Python 3.12、Pydantic 2、FastAPI 既有合同、pytest、ruff、mypy、标准库 JSON/Hashlib；不新增运行时依赖。

---

## 1. 规格与边界

**Source of truth:**

- `docs/product/product-prd-social-media-automation-platform-v2.md`
- `docs/superpowers/specs/2026-07-10-social-media-automation-platform-v2-design.md`

**本 Goal 覆盖 PRD：**

- `CAP-002`、`CAP-003`、`CAP-005`、`CAP-006`、`CAP-007`
- `PAD-001` 的 Catalog 合同部分
- `PAD-003` 的 Fixture Replay 前置合同
- `GOV-005`

**固定边界：**

```text
provider_call=false
provider_call_attempted=false
credential_read_attempted=false
live_client_created=false
production_write_allowed=false
database_migration=false
new_api_route=false
production unchanged
```

除非步骤显式执行 `cd apps/api`，所有 Git 与文件操作命令均从仓库根目录运行；每个代码块视为独立 shell 会话，不继承上一个代码块的工作目录。

## 2. Scope Check

GOAL-V2-01 只完成文件型能力合同底座：

1. 7 个平台、6 个访问通道、8 类资源、7 类操作和 7 种状态。
2. `CapabilityImplementation`、`CapabilityAssertion`、`CapabilityConstraint`、`CapabilityEvidence` 和八维评分合同。
3. 规范化 `capability_catalog.v1` Fixture。
4. 现有 `external_provider_catalog.v1` 兼容投影。
5. Schema、Fixture、Service 和现有 Route 回归测试。

以下内容明确留给后续 Goal：

- SQLAlchemy 模型和 Alembic 迁移：GOAL-V2-02。
- `/api/capabilities/*` 与 Matrix Read Model：GOAL-V2-02。
- MonitoringScope、WorkflowPlan 和 Resolver：GOAL-V2-03。
- Browser Capability Discovery：GOAL-V2-04。
- Provider Client、Credential 和 Live Run：GOAL-V2-05。

## 3. 最终文件结构

**Create:**

- `apps/api/src/data_intelligence_hub/schemas/capability_catalog.py`
  - V2.0 枚举、能力对象和 Catalog 顶层合同。
- `apps/api/src/data_intelligence_hub/services/capability_catalog.py`
  - 严格 Fixture Loader、平台过滤和 V1 兼容投影。
- `apps/api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json`
  - 唯一运行时 Catalog 事实源。
- `apps/api/tests/unit/test_capability_catalog.py`
  - Schema、Fixture、Loader、过滤和投影测试。
- `apps/api/tests/fixtures/external_provider_catalog_v1.json`
  - 历史 V1 输入，仅用于兼容回归测试。

**Modify:**

- `apps/api/src/data_intelligence_hub/services/exceptions.py`
  - 增加 Capability Catalog 专用异常。
- `apps/api/src/data_intelligence_hub/services/social_provider.py`
  - 移除旧 JSON Loader，读取 V2 兼容投影。
- `apps/api/tests/unit/test_social_provider_runtime.py`
  - 增加 V1 投影边界断言。
- `docs/api/api-contract-social-api-overseas-provider-catalog-draft-20260708.md`
  - 记录 V2 单一事实源与兼容关系。

**Move（Task 4 切换 Loader 时原子完成）：**

- From: `apps/api/src/data_intelligence_hub/services/fixtures/social_provider_catalog_overseas.json`
- To: `apps/api/tests/fixtures/external_provider_catalog_v1.json`

## Task 1: 定义统一能力合同

**Files:**

- Create: `apps/api/src/data_intelligence_hub/schemas/capability_catalog.py`
- Create: `apps/api/tests/unit/test_capability_catalog.py`

- [ ] **Step 1: 写入枚举和引用完整性测试**

创建 `apps/api/tests/unit/test_capability_catalog.py`：

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityAssertion,
    CapabilityCatalog,
    CapabilityEvidence,
    CapabilityImplementation,
    CapabilityOperation,
    CapabilityScoreProfile,
    CapabilityStatus,
    DeliveryForm,
    DeploymentMode,
    EvidenceType,
    PlatformId,
    ResourceType,
)


def build_catalog() -> CapabilityCatalog:
    observed_at = datetime(2026, 7, 10, tzinfo=UTC)
    implementation = CapabilityImplementation(
        schema_version="capability_implementation.v1",
        implementation_id="youtube.v3",
        provider_id="youtube.v3",
        platform=PlatformId.YOUTUBE,
        access_channel=AccessChannel.OFFICIAL_AUTHORIZED_API,
        delivery_form=DeliveryForm.SDK,
        deployment_mode=DeploymentMode.OFFICIAL_CLOUD,
        data_domains=["video_detail"],
        resource_groups=["video_detail"],
        official_docs=["https://developers.google.com/youtube/v3/docs"],
        sdk_selection=None,
        live_adapter_strategy="manual_review",
        auth_mode="API key",
        quota_hint={},
        cost_hint={},
        policy_flags=["no_login_state"],
        blocked_actions=["private_message"],
        stability="high",
        self_host_priority="p0",
        api_version="v3",
        required_credentials=["api_key"],
        supported_endpoints=["videos.list"],
        lifecycle_status="active",
    )
    evidence = CapabilityEvidence(
        schema_version="capability_evidence.v1",
        evidence_id="evidence:youtube-docs",
        evidence_type=EvidenceType.OFFICIAL_DOC,
        source_url="https://developers.google.com/youtube/v3/docs",
        source_version="v3",
        observed_at=observed_at,
        content_hash="a" * 64,
        hash_scope="source_reference_only",
        evidence_grade="L1-public-or-runtime",
        provider_call_attempted=False,
        credential_read_attempted=False,
        live_client_created=False,
        production_write_attempted=False,
    )
    assertion = CapabilityAssertion(
        schema_version="capability_assertion.v1",
        assertion_id="youtube.v3:content:resolve_detail:video_detail",
        implementation_id="youtube.v3",
        resource_type=ResourceType.CONTENT,
        operation=CapabilityOperation.RESOLVE_DETAIL,
        support_status=CapabilityStatus.CANDIDATE,
        source_resource_group="video_detail",
        region_scope=["manual_review"],
        purpose_scope=["commercial_review_required"],
        auth_scope=["api_key"],
        field_contract={"required": [], "optional": [], "status": "manual_review"},
        constraints=[],
        score_profile=CapabilityScoreProfile(
            coverage=3,
            freshness=3,
            history=2,
            reliability=5,
            schema_stability=5,
            cost_efficiency=3,
            maintainability=4,
            evidence_confidence=3,
        ),
        evidence_refs=["evidence:youtube-docs"],
        last_verified_at=observed_at,
    )
    return CapabilityCatalog(
        schema_version="capability_catalog.v1",
        evidence_level="L1-public-or-runtime",
        provider_call=False,
        production_write_allowed=False,
        generated_at=observed_at,
        implementations=[implementation],
        assertions=[assertion],
        evidence=[evidence],
    )


def test_capability_taxonomy_is_locked_to_prd_v2() -> None:
    assert {item.value for item in PlatformId} == {
        "youtube", "reddit", "x", "instagram", "threads", "tiktok", "linkedin"
    }
    assert len(ResourceType) == 8
    assert len(CapabilityOperation) == 7
    assert len(CapabilityStatus) == 7
    assert len(AccessChannel) == 6


def test_capability_catalog_accepts_valid_references() -> None:
    catalog = build_catalog()
    assert catalog.provider_call is False
    assert catalog.production_write_allowed is False
    assert catalog.assertions[0].evidence_refs == ["evidence:youtube-docs"]


def test_capability_catalog_rejects_unknown_implementation_reference() -> None:
    payload = build_catalog().model_dump(mode="json")
    payload["assertions"][0]["implementation_id"] = "missing.provider"
    with pytest.raises(ValidationError, match="unknown implementation_id"):
        CapabilityCatalog.model_validate(payload)


def test_capability_catalog_rejects_unknown_evidence_reference() -> None:
    payload = build_catalog().model_dump(mode="json")
    payload["assertions"][0]["evidence_refs"] = ["evidence:missing"]
    with pytest.raises(ValidationError, match="unknown evidence_ref"):
        CapabilityCatalog.model_validate(payload)


def test_capability_catalog_rejects_duplicate_assertion_id() -> None:
    payload = build_catalog().model_dump(mode="json")
    payload["assertions"].append(payload["assertions"][0])
    with pytest.raises(ValidationError, match="duplicate assertion_id"):
        CapabilityCatalog.model_validate(payload)
```

- [ ] **Step 2: 运行测试，确认合同模块尚未存在**

Run:

```bash
cd apps/api
uv run pytest tests/unit/test_capability_catalog.py -q
```

Expected: collection stops because `data_intelligence_hub.schemas.capability_catalog` does not exist.

- [ ] **Step 3: 实现完整 Pydantic 合同**

创建 `apps/api/src/data_intelligence_hub/schemas/capability_catalog.py`：

```python
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlatformId(StrEnum):
    YOUTUBE = "youtube"
    REDDIT = "reddit"
    X = "x"
    INSTAGRAM = "instagram"
    THREADS = "threads"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"


class AccessChannel(StrEnum):
    OFFICIAL_AUTHORIZED_API = "official_authorized_api"
    LICENSED_PARTNER_DATA_SERVICE = "licensed_partner_data_service"
    PUBLIC_WEB_FEED = "public_web_feed"
    AUTHORIZED_BROWSER = "authorized_browser"
    MANAGED_OPAQUE_COLLECTOR = "managed_opaque_collector"
    AUTHORIZED_EXPORT_IMPORT = "authorized_export_import"


class ResourceType(StrEnum):
    CONTENT = "content"
    CONVERSATION = "conversation"
    CREATOR = "creator"
    TOPIC = "topic"
    METRICS = "metrics"
    MEDIA_LIVE = "media_live"
    COMMERCE_ADS = "commerce_ads"
    RELATIONSHIP_GRAPH = "relationship_graph"


class CapabilityOperation(StrEnum):
    RESOLVE_DETAIL = "resolve_detail"
    SEARCH_DISCOVER = "search_discover"
    LIST_ENUMERATE = "list_enumerate"
    MONITOR_INCREMENTAL = "monitor_incremental"
    BACKFILL_HISTORY = "backfill_history"
    BATCH_PARSE = "batch_parse"
    EXPORT_DOWNLOAD = "export_download"


class CapabilityStatus(StrEnum):
    UNKNOWN = "unknown"
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNSUPPORTED = "unsupported"
    DEPRECATED = "deprecated"


class DeliveryForm(StrEnum):
    ENDPOINT = "endpoint"
    SDK = "sdk"
    ACTOR = "actor"
    COLLECTOR = "collector"
    PARSER = "parser"
    WORKFLOW = "workflow"
    SKILL = "skill"
    MCP = "mcp"
    AGENT = "agent"


class DeploymentMode(StrEnum):
    OFFICIAL_CLOUD = "official_cloud"
    MANAGED_SAAS = "managed_saas"
    BYOK = "byok"
    SELF_HOSTED = "self_hosted"
    BROWSER_RUNTIME = "browser_runtime"
    MANUAL_IMPORT = "manual_import"


class EvidenceType(StrEnum):
    OFFICIAL_DOC = "official_doc"
    PUBLIC_MARKET = "public_market"
    REPOSITORY = "repository"
    FIXTURE = "fixture"
    AUTHORIZED_RUNTIME = "authorized_runtime"


class ConstraintSeverity(StrEnum):
    BLOCKING = "blocking"
    MAJOR = "major"
    MINOR = "minor"


class CapabilitySdkSelection(ContractModel):
    package: str
    import_name: str | None = None
    source_url: str
    status: Literal["selected", "candidate", "manual_review", "blocked"]
    reason: str


class CapabilityScoreProfile(ContractModel):
    coverage: int = Field(ge=1, le=5)
    freshness: int = Field(ge=1, le=5)
    history: int = Field(ge=1, le=5)
    reliability: int = Field(ge=1, le=5)
    schema_stability: int = Field(ge=1, le=5)
    cost_efficiency: int = Field(ge=1, le=5)
    maintainability: int = Field(ge=1, le=5)
    evidence_confidence: int = Field(ge=1, le=5)


class CapabilityConstraint(ContractModel):
    constraint_type: Literal["policy", "blocked_action", "quota", "purpose", "region"]
    severity: ConstraintSeverity
    code: str
    details: dict[str, Any] = Field(default_factory=dict)


class CapabilityEvidence(ContractModel):
    schema_version: Literal["capability_evidence.v1"]
    evidence_id: str
    evidence_type: EvidenceType
    source_url: str
    source_version: str
    observed_at: datetime
    content_hash: str = Field(min_length=64, max_length=64)
    hash_scope: Literal["source_reference_only", "retrieved_content"]
    evidence_grade: str
    provider_call_attempted: bool = False
    credential_read_attempted: bool = False
    live_client_created: bool = False
    production_write_attempted: bool = False


class CapabilityImplementation(ContractModel):
    schema_version: Literal["capability_implementation.v1"]
    implementation_id: str
    provider_id: str
    platform: PlatformId
    access_channel: AccessChannel
    delivery_form: DeliveryForm
    deployment_mode: DeploymentMode
    data_domains: list[str]
    resource_groups: list[str]
    official_docs: list[str]
    sdk_selection: CapabilitySdkSelection | None = None
    live_adapter_strategy: str
    auth_mode: str
    quota_hint: dict[str, Any]
    cost_hint: dict[str, Any]
    policy_flags: list[str]
    blocked_actions: list[str]
    stability: Literal["high", "medium", "low"]
    self_host_priority: str
    api_version: str
    required_credentials: list[str]
    supported_endpoints: list[str]
    lifecycle_status: Literal["active", "limited", "deprecated"]


class CapabilityAssertion(ContractModel):
    schema_version: Literal["capability_assertion.v1"]
    assertion_id: str
    implementation_id: str
    resource_type: ResourceType
    operation: CapabilityOperation
    support_status: CapabilityStatus
    source_resource_group: str
    region_scope: list[str]
    purpose_scope: list[str]
    auth_scope: list[str]
    field_contract: dict[str, Any]
    constraints: list[CapabilityConstraint]
    score_profile: CapabilityScoreProfile
    evidence_refs: list[str] = Field(min_length=1)
    last_verified_at: datetime


class CapabilityCatalog(ContractModel):
    schema_version: Literal["capability_catalog.v1"]
    evidence_level: str
    provider_call: Literal[False] = False
    production_write_allowed: Literal[False] = False
    generated_at: datetime
    implementations: list[CapabilityImplementation]
    assertions: list[CapabilityAssertion]
    evidence: list[CapabilityEvidence]

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        implementation_ids = [item.implementation_id for item in self.implementations]
        assertion_ids = [item.assertion_id for item in self.assertions]
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(implementation_ids) != len(set(implementation_ids)):
            raise ValueError("duplicate implementation_id")
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ValueError("duplicate assertion_id")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("duplicate evidence_id")

        implementation_set = set(implementation_ids)
        evidence_set = set(evidence_ids)
        for assertion in self.assertions:
            if assertion.implementation_id not in implementation_set:
                raise ValueError(
                    f"unknown implementation_id: {assertion.implementation_id}"
                )
            for evidence_ref in assertion.evidence_refs:
                if evidence_ref not in evidence_set:
                    raise ValueError(f"unknown evidence_ref: {evidence_ref}")
        return self
```

- [ ] **Step 4: 运行合同测试**

Run:

```bash
cd apps/api
uv run pytest tests/unit/test_capability_catalog.py -q
uv run ruff check src/data_intelligence_hub/schemas/capability_catalog.py tests/unit/test_capability_catalog.py
uv run mypy src/data_intelligence_hub/schemas/capability_catalog.py tests/unit/test_capability_catalog.py
```

Expected: 5 tests pass; ruff and mypy exit 0.

- [ ] **Step 5: 提交合同切片**

```bash
git add apps/api/src/data_intelligence_hub/schemas/capability_catalog.py apps/api/tests/unit/test_capability_catalog.py
git diff --cached --check
git commit -m "feat: define capability catalog contracts"
```

## Task 2: 迁移为规范化 Catalog Fixture

**Files:**

- Copy for regression: `apps/api/src/data_intelligence_hub/services/fixtures/social_provider_catalog_overseas.json`
  to `apps/api/tests/fixtures/external_provider_catalog_v1.json`
- Create: `apps/api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json`
- Modify: `apps/api/tests/unit/test_capability_catalog.py`
- Temporary: `scripts/migrate-capability-catalog-v2.py`，生成后删除

- [ ] **Step 1: 增加规范化 Fixture 测试**

在 `apps/api/tests/unit/test_capability_catalog.py` 追加：

```python
from pathlib import Path


CAPABILITY_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json"
)


def test_overseas_capability_fixture_is_complete_and_side_effect_free() -> None:
    catalog = CapabilityCatalog.model_validate_json(
        CAPABILITY_FIXTURE.read_text(encoding="utf-8")
    )
    assert catalog.schema_version == "capability_catalog.v1"
    assert catalog.provider_call is False
    assert catalog.production_write_allowed is False
    assert len(catalog.implementations) == 7
    assert len(catalog.assertions) == 35
    assert {item.platform for item in catalog.implementations} == set(PlatformId)
    assert {item.support_status for item in catalog.assertions} == {
        CapabilityStatus.CANDIDATE
    }
    assert all(item.evidence_refs for item in catalog.assertions)
    assert all(not item.provider_call_attempted for item in catalog.evidence)
    assert all(not item.credential_read_attempted for item in catalog.evidence)
    assert all(not item.live_client_created for item in catalog.evidence)
    assert all(not item.production_write_attempted for item in catalog.evidence)
```

- [ ] **Step 2: 运行测试，确认 V2 Fixture 尚未存在**

Run:

```bash
cd apps/api
uv run pytest tests/unit/test_capability_catalog.py::test_overseas_capability_fixture_is_complete_and_side_effect_free -q
```

Expected: test stops because `capability_catalog_overseas_v2.json` is absent.

- [ ] **Step 3: 复制历史 V1 Fixture，暂时保留旧运行时文件**

```bash
mkdir -p apps/api/tests/fixtures
cp apps/api/src/data_intelligence_hub/services/fixtures/social_provider_catalog_overseas.json apps/api/tests/fixtures/external_provider_catalog_v1.json
```

此时不删除旧运行时 Fixture，确保 Task 2 和 Task 3 的中间提交仍能通过既有 Social Provider 回归。Task 4 在兼容投影接管 Loader 的同一提交中删除旧文件，完成最终 move。

- [ ] **Step 4: 创建一次性迁移脚本**

创建 `scripts/migrate-capability-catalog-v2.py`：

```python
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog  # noqa: E402

INPUT = ROOT / "apps/api/tests/fixtures/external_provider_catalog_v1.json"
OUTPUT = (
    ROOT
    / "apps/api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json"
)

RESOURCE_MAP = {
    "content_search": ("content", "search_discover"),
    "channel_profile": ("creator", "resolve_detail"),
    "video_detail": ("content", "resolve_detail"),
    "comment_threads": ("conversation", "list_enumerate"),
    "live_stream_snapshot": ("media_live", "monitor_incremental"),
    "post_search": ("content", "search_discover"),
    "subreddit_snapshot": ("topic", "monitor_incremental"),
    "comment_snapshot": ("conversation", "resolve_detail"),
    "comment_tree": ("conversation", "list_enumerate"),
    "user_profile_public": ("creator", "resolve_detail"),
    "video_snapshot": ("content", "resolve_detail"),
    "video_comment": ("conversation", "list_enumerate"),
    "hashtag_rank": ("topic", "monitor_incremental"),
    "creator_profile": ("creator", "resolve_detail"),
    "search": ("content", "search_discover"),
    "user_profile": ("creator", "resolve_detail"),
    "post_lookup": ("content", "resolve_detail"),
    "realtime_trends": ("topic", "monitor_incremental"),
    "metrics": ("metrics", "monitor_incremental"),
    "media_feed": ("content", "list_enumerate"),
    "user_pages": ("creator", "resolve_detail"),
    "mentions": ("content", "search_discover"),
    "comments": ("conversation", "list_enumerate"),
    "insights": ("metrics", "monitor_incremental"),
    "thread_feed": ("content", "list_enumerate"),
    "replies": ("conversation", "list_enumerate"),
    "company_updates": ("content", "list_enumerate"),
    "post_feed": ("content", "list_enumerate"),
    "ugc_posts": ("content", "resolve_detail"),
    "social_actions": ("metrics", "resolve_detail"),
    "organization_pages": ("creator", "resolve_detail"),
}

RELIABILITY_SCORE = {"high": 5, "medium": 3, "low": 2}
MAINTAINABILITY_SCORE = {
    "selected": 4,
    "candidate": 3,
    "manual_review": 2,
    "blocked": 1,
}


def evidence_id(source_url: str) -> str:
    digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:20]
    return f"evidence:{digest}"


def purpose_scope(policy_flags: list[str]) -> list[str]:
    flags = set(policy_flags)
    if "research_only" in flags:
        return ["research_only"]
    if {"business_account_required", "page_level_authorization"} & flags:
        return ["owned_assets_only"]
    return ["commercial_review_required"]


def constraints(provider: dict[str, Any]) -> list[dict[str, Any]]:
    items = [
        {
            "constraint_type": "policy",
            "severity": "blocking",
            "code": flag,
            "details": {},
        }
        for flag in provider["policy_flags"]
    ]
    items.extend(
        {
            "constraint_type": "blocked_action",
            "severity": "blocking",
            "code": action,
            "details": {},
        }
        for action in provider["blocked_actions"]
    )
    items.append(
        {
            "constraint_type": "quota",
            "severity": "major",
            "code": "catalog_quota_hint",
            "details": provider["quota_hint"],
        }
    )
    return items


def main() -> None:
    legacy = json.loads(INPUT.read_text(encoding="utf-8"))
    generated_at = f"{legacy['generated_at']}T00:00:00Z"
    implementations: list[dict[str, Any]] = []
    assertions: list[dict[str, Any]] = []
    evidence_by_id: dict[str, dict[str, Any]] = {}

    providers = legacy["catalog"]["providers"]
    known_resource_groups = {
        resource_group
        for provider in providers
        for resource_group in provider["resource_groups"]
    }
    unknown = known_resource_groups - set(RESOURCE_MAP)
    if unknown:
        raise ValueError(f"unmapped resource groups: {sorted(unknown)}")

    for provider in providers:
        sdk = provider.get("sdk_selection")
        sdk_status = sdk["status"] if sdk else "manual_review"
        cost_hint = provider["quota_hint"].get("cost", {})
        implementations.append(
            {
                "schema_version": "capability_implementation.v1",
                "implementation_id": provider["provider_id"],
                "provider_id": provider["provider_id"],
                "platform": provider["platform"],
                "access_channel": "official_authorized_api",
                "delivery_form": "sdk" if sdk else "endpoint",
                "deployment_mode": "official_cloud",
                "data_domains": provider["data_domain"],
                "resource_groups": provider["resource_groups"],
                "official_docs": provider.get("official_docs", []),
                "sdk_selection": sdk,
                "live_adapter_strategy": provider.get(
                    "live_adapter_strategy", "manual_review"
                ),
                "auth_mode": provider["auth_mode"],
                "quota_hint": provider["quota_hint"],
                "cost_hint": cost_hint,
                "policy_flags": provider["policy_flags"],
                "blocked_actions": provider["blocked_actions"],
                "stability": provider["stability"],
                "self_host_priority": provider["self_host_priority"],
                "api_version": provider["api_version"],
                "required_credentials": provider.get("required_credentials", []),
                "supported_endpoints": provider.get("supported_endpoints", []),
                "lifecycle_status": "active",
            }
        )

        provider_evidence_refs: list[str] = []
        for source_url in provider.get("official_docs", []):
            item_id = evidence_id(source_url)
            provider_evidence_refs.append(item_id)
            evidence_by_id[item_id] = {
                "schema_version": "capability_evidence.v1",
                "evidence_id": item_id,
                "evidence_type": "official_doc",
                "source_url": source_url,
                "source_version": provider["api_version"],
                "observed_at": generated_at,
                "content_hash": hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
                "hash_scope": "source_reference_only",
                "evidence_grade": legacy["evidence_level"],
                "provider_call_attempted": False,
                "credential_read_attempted": False,
                "live_client_created": False,
                "production_write_attempted": False,
            }

        for resource_group in provider["resource_groups"]:
            resource_type, operation = RESOURCE_MAP[resource_group]
            reliability = RELIABILITY_SCORE[provider["stability"]]
            assertions.append(
                {
                    "schema_version": "capability_assertion.v1",
                    "assertion_id": (
                        f"{provider['provider_id']}:{resource_type}:"
                        f"{operation}:{resource_group}"
                    ),
                    "implementation_id": provider["provider_id"],
                    "resource_type": resource_type,
                    "operation": operation,
                    "support_status": "candidate",
                    "source_resource_group": resource_group,
                    "region_scope": ["manual_review"],
                    "purpose_scope": purpose_scope(provider["policy_flags"]),
                    "auth_scope": provider.get("required_credentials", []),
                    "field_contract": {
                        "required": [],
                        "optional": [],
                        "status": "manual_review",
                    },
                    "constraints": constraints(provider),
                    "score_profile": {
                        "coverage": 3,
                        "freshness": 3,
                        "history": 2,
                        "reliability": reliability,
                        "schema_stability": reliability,
                        "cost_efficiency": 3,
                        "maintainability": MAINTAINABILITY_SCORE[sdk_status],
                        "evidence_confidence": 3,
                    },
                    "evidence_refs": provider_evidence_refs,
                    "last_verified_at": generated_at,
                }
            )

    payload = {
        "schema_version": "capability_catalog.v1",
        "evidence_level": legacy["evidence_level"],
        "provider_call": False,
        "production_write_allowed": False,
        "generated_at": generated_at,
        "implementations": implementations,
        "assertions": assertions,
        "evidence": list(evidence_by_id.values()),
    }
    validated = CapabilityCatalog.model_validate(payload)
    OUTPUT.write_text(
        json.dumps(validated.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 生成并验证 V2 Fixture**

Run:

```bash
uv run --project apps/api python scripts/migrate-capability-catalog-v2.py
cd apps/api
uv run pytest tests/unit/test_capability_catalog.py -q
```

Expected: 6 tests pass; generated catalog has 7 implementations and 35 candidate assertions.

- [ ] **Step 6: 删除一次性迁移脚本**

使用 `apply_patch` 删除 `scripts/migrate-capability-catalog-v2.py`。新 Capability Catalog 服务只允许读取或修改 `capability_catalog_overseas_v2.json`；旧 Social Provider Loader 在 Task 4 切换前仍临时读取历史运行时 Fixture，随后该文件被删除并仅保留测试副本。

- [ ] **Step 7: 提交规范化 Fixture**

```bash
git add apps/api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json apps/api/tests/fixtures/external_provider_catalog_v1.json apps/api/tests/unit/test_capability_catalog.py
git diff --cached --check
git commit -m "feat: add canonical capability catalog fixture"
```

## Task 3: 实现严格 Catalog Loader 与过滤

**Files:**

- Create: `apps/api/src/data_intelligence_hub/services/capability_catalog.py`
- Modify: `apps/api/src/data_intelligence_hub/services/exceptions.py`
- Modify: `apps/api/tests/unit/test_capability_catalog.py`

- [ ] **Step 1: 增加 Loader、过滤和无效 Fixture 测试**

在 `apps/api/tests/unit/test_capability_catalog.py` 追加：

```python
from data_intelligence_hub.services.capability_catalog import (
    clear_capability_catalog_cache,
    get_capability_catalog,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    CapabilityCatalogUnknownPlatformError,
)


def test_capability_catalog_loader_filters_platform_and_prunes_references() -> None:
    catalog = get_capability_catalog(platform="youtube")
    assert [item.platform for item in catalog.implementations] == [PlatformId.YOUTUBE]
    assert {item.implementation_id for item in catalog.assertions} == {"youtube.v3"}
    referenced_evidence = {
        ref for assertion in catalog.assertions for ref in assertion.evidence_refs
    }
    assert {item.evidence_id for item in catalog.evidence} == referenced_evidence


def test_capability_catalog_loader_rejects_unknown_platform() -> None:
    with pytest.raises(CapabilityCatalogUnknownPlatformError):
        get_capability_catalog(platform="missing-platform")


def test_capability_catalog_loader_wraps_invalid_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from data_intelligence_hub.services import capability_catalog as service

    invalid_fixture = tmp_path / "invalid.json"
    invalid_fixture.write_text('{"schema_version":"invalid"}', encoding="utf-8")
    monkeypatch.setattr(service, "CATALOG_PATH", invalid_fixture)
    clear_capability_catalog_cache()
    with pytest.raises(CapabilityCatalogLoadError):
        get_capability_catalog()
    clear_capability_catalog_cache()
```

- [ ] **Step 2: 运行测试，确认 Service 尚未存在**

Run:

```bash
cd apps/api
uv run pytest tests/unit/test_capability_catalog.py -q
```

Expected: collection stops because `data_intelligence_hub.services.capability_catalog` does not exist.

- [ ] **Step 3: 增加专用 Service 异常**

在 `apps/api/src/data_intelligence_hub/services/exceptions.py` 的 Social Provider 异常前加入：

```python
class CapabilityCatalogLoadError(ServiceError):
    message = "capability_catalog_load_failed"


class CapabilityCatalogUnknownPlatformError(ServiceError):
    message = "capability_catalog_unknown_platform"
```

- [ ] **Step 4: 实现 Loader 与过滤**

创建 `apps/api/src/data_intelligence_hub/services/capability_catalog.py`：

```python
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityCatalog,
    PlatformId,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    CapabilityCatalogUnknownPlatformError,
)

CATALOG_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "capability_catalog_overseas_v2.json"
)


@lru_cache(maxsize=1)
def _load_capability_catalog() -> CapabilityCatalog:
    try:
        return CapabilityCatalog.model_validate_json(
            CATALOG_PATH.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        raise CapabilityCatalogLoadError from exc


def clear_capability_catalog_cache() -> None:
    _load_capability_catalog.cache_clear()


def get_capability_catalog(platform: str | None = None) -> CapabilityCatalog:
    catalog = _load_capability_catalog()
    if platform is None:
        return catalog

    try:
        platform_id = PlatformId(platform.strip().lower())
    except ValueError as exc:
        raise CapabilityCatalogUnknownPlatformError from exc

    implementations = [
        item for item in catalog.implementations if item.platform == platform_id
    ]
    if not implementations:
        raise CapabilityCatalogUnknownPlatformError

    implementation_ids = {item.implementation_id for item in implementations}
    assertions = [
        item
        for item in catalog.assertions
        if item.implementation_id in implementation_ids
    ]
    evidence_refs = {
        evidence_ref
        for assertion in assertions
        for evidence_ref in assertion.evidence_refs
    }
    evidence = [
        item for item in catalog.evidence if item.evidence_id in evidence_refs
    ]
    return catalog.model_copy(
        update={
            "implementations": implementations,
            "assertions": assertions,
            "evidence": evidence,
        }
    )
```

- [ ] **Step 5: 运行 Loader 测试和静态检查**

Run:

```bash
cd apps/api
uv run pytest tests/unit/test_capability_catalog.py -q
uv run ruff check src/data_intelligence_hub/services/capability_catalog.py src/data_intelligence_hub/services/exceptions.py tests/unit/test_capability_catalog.py
uv run mypy src/data_intelligence_hub/services/capability_catalog.py tests/unit/test_capability_catalog.py
```

Expected: 9 tests pass; ruff and mypy exit 0.

- [ ] **Step 6: 提交 Loader 切片**

```bash
git add apps/api/src/data_intelligence_hub/services/capability_catalog.py apps/api/src/data_intelligence_hub/services/exceptions.py apps/api/tests/unit/test_capability_catalog.py
git diff --cached --check
git commit -m "feat: load canonical capability catalog"
```

## Task 4: 提供 V1 兼容投影并替换旧 Loader

**Files:**

- Modify: `apps/api/src/data_intelligence_hub/services/capability_catalog.py`
- Modify: `apps/api/src/data_intelligence_hub/services/social_provider.py`
- Delete: `apps/api/src/data_intelligence_hub/services/fixtures/social_provider_catalog_overseas.json`
- Modify: `apps/api/tests/unit/test_capability_catalog.py`
- Modify: `apps/api/tests/unit/test_social_provider_runtime.py`
- Test: `apps/api/tests/integration/test_social_provider_routes.py`

- [ ] **Step 1: 增加 V1 历史 Fixture 对等测试**

在 `apps/api/tests/unit/test_capability_catalog.py` 追加：

```python
import json

from data_intelligence_hub.services.capability_catalog import (
    project_external_provider_catalog_v1,
)

LEGACY_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures/external_provider_catalog_v1.json"
)


def test_external_provider_catalog_v1_projection_preserves_provider_contract() -> None:
    expected = json.loads(LEGACY_FIXTURE.read_text(encoding="utf-8"))
    projected = project_external_provider_catalog_v1()

    assert projected.schema_version == "external_provider_catalog.v1"
    assert projected.provider_call is False
    assert [item.provider_id for item in projected.providers] == [
        item["provider_id"] for item in expected["catalog"]["providers"]
    ]
    for actual, legacy in zip(
        projected.providers,
        expected["catalog"]["providers"],
        strict=True,
    ):
        assert actual.platform == legacy["platform"]
        assert actual.data_domain == legacy["data_domain"]
        assert actual.resource_groups == legacy["resource_groups"]
        assert actual.auth_mode == legacy["auth_mode"]
        assert actual.quota_hint == legacy["quota_hint"]
        assert actual.policy_flags == legacy["policy_flags"]
        assert actual.blocked_actions == legacy["blocked_actions"]
        assert actual.supported_endpoints == legacy["supported_endpoints"]
        assert [item.endpoint_id for item in actual.endpoint_contracts] == legacy[
            "supported_endpoints"
        ]
```

先将 `apps/api/tests/unit/test_social_provider_runtime.py` 现有的 `services.exceptions` import 扩展，加入 `CapabilityCatalogLoadError` 与 `SocialProviderCatalogLoadError`；然后在 Catalog 测试后追加：

```python
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
```

- [ ] **Step 2: 运行测试，确认兼容投影尚未实现**

Run:

```bash
cd apps/api
uv run pytest tests/unit/test_capability_catalog.py::test_external_provider_catalog_v1_projection_preserves_provider_contract tests/unit/test_social_provider_runtime.py::test_social_provider_catalog_is_projected_from_v2_without_live_side_effects tests/unit/test_social_provider_runtime.py::test_social_provider_catalog_preserves_legacy_load_error -q
```

Expected: collection stops because `project_external_provider_catalog_v1` does not exist or the moved V1 runtime Fixture can no longer be loaded.

- [ ] **Step 3: 实现 V1 投影函数**

在 `apps/api/src/data_intelligence_hub/services/capability_catalog.py` 增加 imports：

```python
from data_intelligence_hub.schemas.social_provider import (
    SocialProviderCatalogItem,
    SocialProviderCatalogResponse,
    SocialProviderEndpointItem,
    SocialProviderSdkSelection,
)
```

并在文件末尾增加：

```python
def project_external_provider_catalog_v1() -> SocialProviderCatalogResponse:
    catalog = get_capability_catalog()
    providers = []
    for item in catalog.implementations:
        sdk_selection = None
        if item.sdk_selection is not None:
            sdk_selection = SocialProviderSdkSelection(
                package=item.sdk_selection.package,
                import_name=item.sdk_selection.import_name,
                source_url=item.sdk_selection.source_url,
                status=item.sdk_selection.status,
                reason=item.sdk_selection.reason,
            )
        providers.append(
            SocialProviderCatalogItem(
                provider_id=item.provider_id,
                platform=item.platform.value,
                data_domain=item.data_domains,
                resource_groups=item.resource_groups,
                official_docs=item.official_docs,
                sdk_selection=sdk_selection,
                live_adapter_strategy=item.live_adapter_strategy,
                auth_mode=item.auth_mode,
                quota_hint=item.quota_hint,
                policy_flags=item.policy_flags,
                blocked_actions=item.blocked_actions,
                stability=item.stability,
                self_host_priority=item.self_host_priority,
                api_version=item.api_version,
                required_credentials=item.required_credentials,
                supported_endpoints=item.supported_endpoints,
                endpoint_contracts=[
                    SocialProviderEndpointItem(endpoint_id=endpoint)
                    for endpoint in item.supported_endpoints
                ],
            )
        )
    return SocialProviderCatalogResponse(
        schema_version="external_provider_catalog.v1",
        evidence_level=catalog.evidence_level,
        provider_call=False,
        generated_at=catalog.generated_at.date().isoformat(),
        providers=providers,
    )
```

- [ ] **Step 4: 将 Social Provider Service 改为兼容投影**

在 `apps/api/src/data_intelligence_hub/services/social_provider.py`：

1. 删除 `json`、`dataclass`、`Path`、`SocialProviderEndpointItem`、`SocialProviderSdkSelection` imports。
2. 删除 `CATALOG_PATH`、`_CatalogEnvelope`、`_CATALOG_CACHE`、`_to_text_list`、`_to_endpoint_items`、`_build_sdk_selection`、`_build_catalog_item` 和 `_load_catalog`。
3. 保留现有 `SocialProviderCatalogLoadError` import，并增加：

```python
from data_intelligence_hub.services.capability_catalog import (
    project_external_provider_catalog_v1,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    SocialProviderCatalogLoadError,
    SocialProviderGateAuthorizationError,
    SocialProviderUnknownPlatformError,
)
```

`CapabilityCatalogLoadError` 是 V2 内部错误；现有 Route 只捕获 `SocialProviderCatalogLoadError`，因此兼容服务必须转换异常，不能让既有 API 变成未处理的 500。

4. 用以下实现替换 `get_social_provider_catalog` 的函数体：

```python
def get_social_provider_catalog(
    platform: str | None = None,
    data_domain: str | None = None,
    resource_group: str | None = None,
) -> SocialProviderCatalogResponse:
    try:
        catalog = project_external_provider_catalog_v1()
    except CapabilityCatalogLoadError as exc:
        raise SocialProviderCatalogLoadError from exc
    filtered = list(catalog.providers)

    if platform is not None:
        requested_platform = _normalize_platform(platform)
        filtered = [item for item in filtered if item.platform == requested_platform]
        if not filtered:
            raise SocialProviderUnknownPlatformError

    if data_domain is not None:
        requested_domain = data_domain.strip().lower()
        filtered = [
            item
            for item in filtered
            if requested_domain in {domain.lower() for domain in item.data_domain}
        ]
    if resource_group is not None:
        requested_resource_group = resource_group.strip().lower()
        filtered = [
            item
            for item in filtered
            if requested_resource_group
            in {group.lower() for group in item.resource_groups}
        ]

    return catalog.model_copy(update={"providers": filtered})
```

5. 使用 `apply_patch` 删除 `apps/api/src/data_intelligence_hub/services/fixtures/social_provider_catalog_overseas.json`。只有在兼容投影与现有 Social Provider 回归测试均可运行后才执行删除。

- [ ] **Step 5: 运行兼容与现有社媒测试**

Run:

```bash
cd apps/api
uv run pytest tests/unit/test_capability_catalog.py tests/unit/test_social_provider_runtime.py tests/integration/test_social_provider_routes.py -q
```

Expected: all selected tests pass;现有 Route 的 schema、provider 数量、筛选、Readiness 和 Gate 行为保持一致。

- [ ] **Step 6: 运行静态检查**

Run:

```bash
cd apps/api
uv run ruff check src/data_intelligence_hub/services/capability_catalog.py src/data_intelligence_hub/services/social_provider.py tests/unit/test_capability_catalog.py tests/unit/test_social_provider_runtime.py
uv run mypy src/data_intelligence_hub/services/capability_catalog.py src/data_intelligence_hub/services/social_provider.py tests/unit/test_capability_catalog.py tests/unit/test_social_provider_runtime.py
```

Expected: both commands exit 0.

- [ ] **Step 7: 提交兼容层切片**

```bash
git add -- apps/api/src/data_intelligence_hub/services/capability_catalog.py apps/api/src/data_intelligence_hub/services/social_provider.py apps/api/src/data_intelligence_hub/services/fixtures/social_provider_catalog_overseas.json apps/api/tests/unit/test_capability_catalog.py apps/api/tests/unit/test_social_provider_runtime.py
git diff --cached --check
git commit -m "refactor: project social providers from capability catalog"
```

## Task 5: 同步合同文档并完成 Goal 验收

**Files:**

- Modify: `docs/api/api-contract-social-api-overseas-provider-catalog-draft-20260708.md`
- Modify: `docs/superpowers/plans/2026-07-10-goal-v2-01-capability-contract-foundation.md`

- [ ] **Step 1: 更新 API 合同事实源说明**

在 `docs/api/api-contract-social-api-overseas-provider-catalog-draft-20260708.md` 的“边界与前提”后增加：

```markdown
### V2.0 Catalog 迁移

- 运行时单一事实源：`services/fixtures/capability_catalog_overseas_v2.json`。
- 规范合同：`capability_catalog.v1`。
- 现有 `GET /api/automation/social-provider-catalog` 继续返回 `external_provider_catalog.v1`，由 V2 Catalog 投影生成。
- 历史 V1 Fixture 只保留在 `tests/fixtures/external_provider_catalog_v1.json`，用于兼容回归。
- GOAL-V2-01 不新增数据库表、API route、Provider Client 或 Credential 读取。
- 全部 Assertion 初始状态为 `candidate`；`verified` 需要后续核验证据。
```

同时完成两项替换：

1. 将 frontmatter `updated` 改为 `2026-07-10`。
2. 将原有“基准 catalog 已落地在 `services/fixtures/social_provider_catalog_overseas.json`”事实说明替换为“规范运行时 Catalog 位于 `services/fixtures/capability_catalog_overseas_v2.json`；历史 V1 Fixture 位于 `tests/fixtures/external_provider_catalog_v1.json`，不再由运行时读取”。

- [ ] **Step 2: 运行 Goal 级 API 验证**

Run:

```bash
cd apps/api
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run alembic heads
```

Expected: all commands exit 0; Alembic head remains `202606110026` because this Goal has no migration.

- [ ] **Step 3: 运行仓库完整验证**

Run from repository root:

```bash
bash scripts/verify-mvp.sh
```

Expected: API ruff/mypy/pytest/Alembic and Web lint/unit/build/E2E all complete successfully.

- [ ] **Step 4: 验证边界与单一事实源**

Run:

```bash
rg -n 'social_provider_catalog_overseas\.json' apps/api/src apps/api/tests docs/api
rg -n 'provider_call": true|credential_read_attempted": true|live_client_created": true|production_write_allowed": true' apps/api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json
git diff --check
```

Expected:

- 第一条只命中历史说明或兼容测试路径，不命中运行时 Loader。
- 第二条无输出。
- `git diff --check` 无输出。

- [ ] **Step 5: 更新本计划的执行证据**

完成执行时，在本文末尾追加：

```markdown
## Execution Evidence

- implementation_status: complete
- provider_call: false
- credential_read_attempted: false
- live_client_created: false
- production_write_allowed: false
- alembic_head: 202606110026
- targeted_tests: passed
- full_verify_mvp: passed
- goal_base_sha: 512fdbf
- commit_shas_command: git log --reverse --format=%H 512fdbf..HEAD
```

执行者运行 `commit_shas_command`，并将命令的逐行完整输出追加在该代码块之后。任一边界值发生变化时停止本 Goal 并重新审批。

- [ ] **Step 6: 提交合同文档与执行证据**

```bash
git add docs/api/api-contract-social-api-overseas-provider-catalog-draft-20260708.md docs/superpowers/plans/2026-07-10-goal-v2-01-capability-contract-foundation.md
git diff --cached --check
git commit -m "docs: close capability contract foundation"
```

## 4. Goal Exit Gate

GOAL-V2-01 只有在以下条件全部满足时才能完成：

- `capability_catalog.v1` 通过 Pydantic 严格校验。
- 7 个 Implementation 和 35 个 Candidate Assertion 完整。
- 8 类资源、7 类操作、7 种状态和 6 个访问通道与 PRD 一致。
- Runtime 只读取 `capability_catalog_overseas_v2.json`。
- `external_provider_catalog.v1` Route 回归通过。
- Readiness、Gate、Adapter Plan 和 Preview 行为保持兼容。
- 无新依赖、无数据库迁移、无新 API Route。
- `provider_call=false`、`credential_read_attempted=false`、`live_client_created=false`、`production_write_allowed=false`。
- Targeted API checks 与 `scripts/verify-mvp.sh` 全部通过。
- 所有提交只包含本 Goal 文件，既有未跟踪草稿和 `output/`、`ref/` 保持未纳入。

## 5. 回滚方案

1. 逐个 revert 本 Goal 的原子提交，顺序与提交时间相反。
2. V1 历史 Fixture 从 `apps/api/tests/fixtures/external_provider_catalog_v1.json` 恢复到原 runtime 路径。
3. `social_provider.py` 恢复旧 Loader 后重跑 Social Provider unit/integration tests。
4. 本 Goal 不含数据库迁移、外部调用或生产变更，因此无需数据回填和 Provider 清理。
