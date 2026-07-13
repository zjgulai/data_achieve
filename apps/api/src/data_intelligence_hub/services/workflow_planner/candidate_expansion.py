from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from data_intelligence_hub.schemas.workflow_planner import (
    FlowMode,
    NormalizedMonitoringScope,
    QueryTerm,
    WorkflowPlannerContract,
)
from data_intelligence_hub.services.workflow_planner.normalization import normalize_text

DEFAULT_CANDIDATE_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "candidate_expansions_v1.json"
)


class CandidateExpansionEntry(WorkflowPlannerContract):
    term: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    source: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    conflict_codes: list[str]


class CandidateExpansionFixture(WorkflowPlannerContract):
    schema_version: Literal["workflow_candidate_expansion_fixture.v1"]
    version: str = Field(min_length=1)
    entries: dict[str, list[CandidateExpansionEntry]]


class CandidateExpansionAdapter(Protocol):
    @property
    def version(self) -> str: ...

    def expand(
        self,
        scope: NormalizedMonitoringScope,
        *,
        flow_mode: FlowMode,
    ) -> list[QueryTerm]: ...


@dataclass(frozen=True)
class FixtureCandidateExpansionAdapter:
    fixture: CandidateExpansionFixture

    @property
    def version(self) -> str:
        return self.fixture.version

    @classmethod
    def from_default_fixture(cls) -> FixtureCandidateExpansionAdapter:
        fixture = CandidateExpansionFixture.model_validate_json(
            DEFAULT_CANDIDATE_FIXTURE_PATH.read_text(encoding="utf-8")
        )
        return cls(fixture=fixture)

    def expand(
        self,
        scope: NormalizedMonitoringScope,
        *,
        flow_mode: FlowMode,
    ) -> list[QueryTerm]:
        del flow_mode
        if scope.canonical_term is None:
            return []

        entries = self.fixture.entries.get(normalize_text(scope.canonical_term), [])
        if not entries:
            return []

        scope_ref = sorted(scope.source_scope_refs)[0]
        excluded_terms = {normalize_text(term) for term in scope.exclude_terms}
        candidates: list[QueryTerm] = []
        for entry in entries:
            normalized_term = normalize_text(entry.term)
            conflict_codes = sorted(set(entry.conflict_codes))
            rejected = (
                normalized_term in excluded_terms
                or "excluded_term_overlap" in conflict_codes
            )
            if normalized_term in excluded_terms and "excluded_term_overlap" not in conflict_codes:
                conflict_codes.append("excluded_term_overlap")
                conflict_codes.sort()
            candidates.append(
                QueryTerm(
                    term=entry.term,
                    normalized_term=normalized_term,
                    scope_ref=scope_ref,
                    scope_key=scope.scope_key,
                    origin="fixture_candidate_expansion",
                    status="rejected" if rejected else "candidate",
                    reason=entry.reason,
                    source=entry.source,
                    score=entry.score,
                    conflict_codes=conflict_codes,
                )
            )

        return sorted(
            candidates,
            key=lambda term: (
                term.scope_key,
                term.normalized_term,
                term.origin,
                term.term,
                term.source,
            ),
        )
