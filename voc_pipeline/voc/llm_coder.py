"""LLM single coder adapter.

The coding sub-contract writes one frozen JSONL artifact per run.  This module
only adapts that artifact to the ``CodedRecord`` interface used by the rest of
the pipeline; it does not call a model and it never reads the gold set.

The rule coder remains in :mod:`voc.coder` as the comparison baseline.  The
switch lives in :func:`voc.build.build` (default ``llm``); set
``VOC_CODER=rule`` or pass ``--coder rule`` to rebuild with the lexicon coder.
Pass ``--coder llm-v2`` to replay the re-coded v2 artifact; the default stays
on the frozen v1 artifact so published numbers do not move.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .canonical import CanonicalRecord
from .coder import (
    EXPERIENCE_SCOPES,
    Annotation,
    CodedRecord,
    assess_experience_scope,
    emits_aspects,
    experience_source as derive_experience_source,
    has_evaluation,
    help_seeking as is_help_seeking,
    in_experience_cohort,
    is_on_topic,
)
from .taxonomy import ASPECTS, CODED_ARTIFACT_TAXONOMY_VERSION, CONTEXTS

CODER_ID = "llm-v1"
CODER_ID_V2 = "llm-v2"
DEFAULT_CODED_PATH = Path("llm-coding") / "coded" / "ALL.jsonl"
V2_CODED_PATH = Path("llm-coding-v2") / "coded" / "ALL.jsonl"
DEFAULT_EVAL_PATH = Path("llm-coding") / "eval-result-high.json"
V2_EVAL_PATH = Path("llm-coding-v2") / "eval-result-high.json"
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = ROOT / "artifacts" / "run-20261029"

# Precision threshold the report applies to each source separately.  A merged
# number cannot pass this test: TikTok Shop reaches it, Reddit does not.
PRECISION_THRESHOLD_PCT = 90.0

# Confidence gate.  ``high`` is the published default.  The gold-set evaluation
# is reported per source, because TikTok Shop reaches 90.5% strict precision
# while Reddit stays at 50.0% with only 4 high-confidence aspects.  ``all``
# keeps every aspect and is the regression mode that reproduces the pre-gate
# numbers (79.7% / 60.0%).
CONFIDENCE_ENV = "VOC_MIN_CONFIDENCE"
DEFAULT_MIN_CONFIDENCE = "high"
CONFIDENCE_THRESHOLDS = ("high", "medium", "all")
CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
CONFIDENCE_DROP_REASON = "below_confidence_threshold"
DROPPED_FILENAME = "confidence-dropped.jsonl"

_ASPECT_CODES = {code.code for code in ASPECTS}
_CONTEXT_CODES = {code.code for code in CONTEXTS}
_POLARITIES = {
    "positive",
    "qualified_positive",
    "negative",
    "qualified_negative",
    "mixed",
    "unknown",
}

# E-merge §2.2: the on-topic set is owned by :mod:`voc.coder`.  The legacy
# ``brand_category`` value is not produced by the current canonicaliser; a
# old artifact that still carries it is mapped to ``exact_current_family``
# and logged (E-merge §2.1/§3.4).
_LEGACY_PRODUCT_MATCH = {"brand_category": "exact_current_family"}

# Records the contract §5.2 rejects after manual review.  They are listed
# here so the audit file can prove the rejection survived the rebuild.
_SCOPE_FALSE_POSITIVES = (
    {
        "canonical_id": "c-1uuim67",
        "reason": "evidence clause is a symptom; the anchor came from the previous sentence",
    },
)

# The contract collapses journey and outcome to a small enum.  ``purchase``
# has no direct JNY.* code; CONSIDERATION is the pre-use stage, which also
# keeps purchase-decision records out of the C11 "experience" count.
_JOURNEY_MAP = {
    "first_use": "JNY.FIRST_FITTING",
    "repeat_use": "JNY.USE",
    "return": "JNY.RETURN",
    "selection": "JNY.SIZE_SELECTION",
    "purchase": "JNY.CONSIDERATION",
}
_OUTCOME_MAP = {
    "relief": "OUT.RELIEF",
    "no_relief": "OUT.NO_BENEFIT",
}

# ``medical_self_report`` is one boolean in the contract, while the taxonomy
# has three medical codes.  Pick the narrowest code the record text supports;
# the flag itself, not the code label, drives C08.
_MEDICAL_SAFETY_RE = re.compile(
    r"\b(?:pressure on (?:my )?(?:belly|baby)|unsafe(?: for (?:the )?baby)?|too much pressure)\b",
    re.IGNORECASE,
)
_MEDICAL_HISTORY_RE = re.compile(
    r"\b(?:spd|pgp|pubic symphysis|polyhydramnios|placenta|diastasis)\b",
    re.IGNORECASE,
)


def coded_path(run_dir: Path) -> Path:
    """Default artifact path inside one run directory."""
    return Path(run_dir) / DEFAULT_CODED_PATH


def coded_path_v2(run_dir: Path) -> Path:
    """Re-coded v2 artifact path inside one run directory."""
    return Path(run_dir) / V2_CODED_PATH


def dropped_path(run_dir: Path) -> Path:
    """Audit file listing every aspect dropped by the confidence gate."""
    return Path(run_dir) / DROPPED_FILENAME


def scope_audit_path(run_dir: Path) -> Path:
    """Audit file for the scope/product-match split (E-merge §3.4)."""
    return Path(run_dir) / "scope-audit.json"


def scope_conflicts_path(run_dir: Path) -> Path:
    """Deprecated alias kept for callers that still use the old name."""
    return scope_audit_path(run_dir)


def compat_experience_diff_path(run_dir: Path) -> Path:
    """Per-record diff between the old published ``experience`` and cohort."""
    return Path(run_dir) / "compat-experience-diff.json"


def eval_result_path(run_dir: Path) -> Path:
    """Frozen per-source evaluation artifact for the high-confidence gate."""
    return Path(run_dir) / DEFAULT_EVAL_PATH


def eval_result_path_v2(run_dir: Path) -> Path:
    """Frozen per-source evaluation artifact for the re-coded v2 artifact."""
    return Path(run_dir) / V2_EVAL_PATH


def load_eval_precision(run_dir: Path, path: Path | None = None) -> dict[str, Any] | None:
    """Read per-source strict precision from ``eval-result-high.json``.

    ``path`` overrides the v1 default so the v2 coder reads its own evaluation
    instead of borrowing v1's precision table.

    The report must publish TikTok Shop, Reddit and the merged row separately.
    A merged number alone is not a usable accuracy basis, so this function
    keeps the three rows apart and attaches the high-confidence aspect count
    that makes the Reddit sample's small size visible.

    A missing file returns ``None``: rule-coder runs and unit tests have no
    LLM evaluation artifact, and the renderer then uses its frozen fallback.
    A present but malformed file raises ``ValueError``; it must never fall back
    to stale constants and silently publish the wrong precision.
    """
    path = Path(path) if path is not None else eval_result_path(run_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    high = data.get("high_only")
    strict = high.get("strict") if isinstance(high, dict) else None
    if not isinstance(strict, dict):
        raise ValueError(f"{path}: missing high_only.strict table")
    keys = {
        "tiktok_shop": "TikTok",
        "reddit": "Reddit",
        "all": "ALL",
    }
    labels = {"tiktok_shop": "TikTok Shop", "reddit": "Reddit", "all": "合并"}
    sources: dict[str, dict[str, Any]] = {}
    for source, table_key in keys.items():
        row = strict.get(table_key)
        if not isinstance(row, dict):
            raise ValueError(f"{path}: missing high_only.strict.{table_key}")
        for field in ("coder_aspects", "gold_aspects", "true_positives", "precision_pct", "recall_pct"):
            if row.get(field) is None:
                raise ValueError(f"{path}: high_only.strict.{table_key} missing {field}")
        sources[source] = {
            "label": labels[source],
            "high_aspects": int(row["coder_aspects"]),
            "gold_aspects": int(row["gold_aspects"]),
            "true_positives": int(row["true_positives"]),
            "precision_pct": float(row["precision_pct"]),
            "recall_pct": float(row["recall_pct"]),
        }
    return {
        "gate": ((data.get("filter") or {}).get("confidence") or "high"),
        "rule": "strict",
        "match": "code+polarity",
        "threshold_pct": PRECISION_THRESHOLD_PCT,
        "generated_at": data.get("generated_at"),
        "gold_set": data.get("gold_set"),
        "evaluated_file": data.get("evaluated_file"),
        # v2 can only inherit the v1 table when no human gold exists.  Carry the
        # verification block so the renderer can say so instead of presenting
        # inherited numbers as v2 precision.
        "verification": data.get("verification"),
        "gold_set_abstentions": data.get("gold_set_abstentions"),
        "sources": sources,
    }


def resolve_min_confidence(value: str | None = None) -> str:
    """Resolve the confidence threshold from an explicit value or the environment.

    The default is ``high`` (the user's decision).  ``all`` disables the gate
    and preserves the pre-gate output exactly.  Unknown values fail closed
    instead of silently keeping every aspect.
    """
    raw = value if value is not None else os.environ.get(CONFIDENCE_ENV)
    if raw is None or not str(raw).strip():
        return DEFAULT_MIN_CONFIDENCE
    normalized = str(raw).strip().lower()
    if normalized not in CONFIDENCE_THRESHOLDS:
        raise ValueError(
            f"invalid confidence threshold {raw!r}; expected one of {CONFIDENCE_THRESHOLDS}"
        )
    return normalized


def _confidence_label(confidence: Any, canonical_id: str) -> str:
    """Normalize and validate an aspect confidence value.

    A missing or unrecognized value is an artifact defect: treating it as
    ``high`` would publish unvetted evidence, and treating it as dropped
    would hide the defect inside an abstention count.
    """
    label = str(confidence or "").strip().lower()
    if label not in CONFIDENCE_RANK:
        raise ValueError(
            f"{canonical_id}: invalid aspect confidence {confidence!r}; "
            f"expected one of {sorted(CONFIDENCE_RANK)}"
        )
    return label


def write_confidence_dropped(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """Rewrite the audit file, so a clean run leaves an empty file, not a stale one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_scope_audit(
    path: Path,
    records: list[CanonicalRecord],
    rows: dict[str, dict[str, Any]],
    coded: list[CodedRecord],
    audit: dict[str, list[dict[str, Any]]],
    coder_id: str = CODER_ID,
) -> None:
    """Write the E-merge audit file (schema v2).

    The old ``scope-conflicts.json`` measured a disagreement that no longer
    exists: ``product_match`` and ``experience_scope`` are orthogonal.  The
    new file keeps the four lists the contract defines:

    * ``off_target_evaluations``: scope full/partial but off-target.
    * ``downgrades``: old gate true, new scope none.
    * ``admit_candidates``: old gate false, new scope full/partial, on-topic.
    * ``scope_false_positives``: manual review rejected the assessment.
    """
    by_id = {record.canonical_id: record for record in records}
    coded_by_id = {record.canonical_id: record for record in coded}
    scope_false_positives = []
    for item in _SCOPE_FALSE_POSITIVES:
        canonical_id = item["canonical_id"]
        coded_rec = coded_by_id.get(canonical_id)
        scope_false_positives.append(
            {
                **item,
                "verified_scope": coded_rec.experience_scope if coded_rec else None,
                "verified_product_match": (
                    coded_rec.product_match if coded_rec else None
                ),
            }
        )
    payload = {
        "schema": "voc-scope-audit/2",
        "contract_version": "E-merge/1",
        "coder_id": coder_id,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "records_total": len(records),
        "on_topic_records": sum(1 for item in coded if is_on_topic(item.product_match)),
        "in_experience_cohort": sum(1 for item in coded if item.in_cohort),
        "scope_counts": dict(Counter(item.experience_scope for item in coded)),
        "product_match_counts": dict(Counter(item.product_match for item in coded)),
        "off_target_evaluations": audit.get("off_target_evaluations", []),
        "downgrades": audit.get("downgrades", []),
        "admit_candidates": audit.get("admit_candidates", []),
        "scope_false_positives": scope_false_positives,
        "declared_scope_mismatches": audit.get("declared_scope_mismatches", []),
        "legacy_product_match": audit.get("legacy_product_match", []),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def write_compat_experience_diff(
    path: Path,
    records: list[CanonicalRecord],
    rows: dict[str, dict[str, Any]],
    coded: list[CodedRecord],
    coder_id: str = CODER_ID,
) -> None:
    """Diff the old published ``experience`` against the new cohort.

    E-merge §3.2 forbids silently replacing the field.  The old value is the
    A2 output ``frozen is_product_experience AND scope != none``; the new
    value is ``in_cohort``.  Every difference is listed with its reason.
    """
    by_id = {record.canonical_id: record for record in records}
    rows_out: list[dict[str, Any]] = []
    for coded_rec in coded:
        row = rows.get(coded_rec.canonical_id)
        if row is None:
            old_experience = False
            old_reason = "missing_row"
        else:
            frozen = bool(row.get("is_product_experience"))
            old_experience = frozen and coded_rec.experience_scope != "none"
            old_reason = str(row.get("experience_reason") or "")
        if old_experience == coded_rec.in_cohort:
            continue
        if old_experience and not is_on_topic(coded_rec.product_match):
            reason = "off_target_product_match"
        elif old_experience and coded_rec.experience_scope == "none":
            reason = "downgraded_to_none"
        elif not old_experience and coded_rec.in_cohort:
            reason = "admitted_on_topic_evaluation"
        else:
            reason = "cohort_mismatch"
        record = by_id.get(coded_rec.canonical_id)
        rows_out.append(
            {
                "canonical_id": coded_rec.canonical_id,
                "source": record.source if record else None,
                "frames": list(record.frames) if record else [],
                "product_match": coded_rec.product_match,
                "old_experience": old_experience,
                "old_reason": old_reason,
                "new_in_cohort": coded_rec.in_cohort,
                "new_scope": coded_rec.experience_scope,
                "change_reason": reason,
            }
        )
    payload = {
        "schema": "voc-compat-experience-diff/1",
        "contract_version": "E-merge/1",
        "coder_id": coder_id,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "records_total": len(coded),
        "differences": len(rows_out),
        "rows": rows_out,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def load_coded(path: Path) -> dict[str, dict[str, Any]]:
    """Read the frozen JSONL into ``canonical_id -> row``.

    Duplicate ids and unparsable lines fail closed: a partially read artifact
    would silently lower recall and make the published precision meaningless.
    """
    rows: dict[str, dict[str, Any]] = {}
    with Path(path).open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            canonical_id = row.get("canonical_id")
            if not canonical_id:
                raise ValueError(f"{path}:{lineno}: missing canonical_id")
            if canonical_id in rows:
                raise ValueError(f"{path}:{lineno}: duplicate canonical_id {canonical_id}")
            rows[canonical_id] = row
    if not rows:
        raise ValueError(f"{path}: no coded records")
    return rows


def _source_text(record: CanonicalRecord) -> str:
    title = record.title or ""
    text = record.text or ""
    return f"{title}. {text}" if title else text


def _resolve_span(record: CanonicalRecord, evidence_span: str) -> tuple[int, int, str]:
    """Map a contract span to offsets in the pipeline's source text.

    The contract requires an exact substring of title or text and forbids
    spans that cross the title/text boundary, so a plain ``find`` on the same
    concatenation the rule coder uses is sufficient.  A miss is an artifact
    defect, not an abstention: raise instead of quietly dropping an aspect.
    """
    if not evidence_span:
        raise ValueError(f"{record.canonical_id}: empty evidence_span")
    if len(evidence_span) > 120:
        raise ValueError(
            f"{record.canonical_id}: evidence_span longer than 120 chars: {evidence_span!r}"
        )
    source = _source_text(record)
    start = source.find(evidence_span)
    if start < 0:
        raise ValueError(
            f"{record.canonical_id}: evidence_span not found in source text: {evidence_span!r}"
        )
    return start, start + len(evidence_span), evidence_span


def _medical_code(text: str) -> str:
    if _MEDICAL_SAFETY_RE.search(text):
        return "MED.PRESSURE_SAFETY"
    if _MEDICAL_HISTORY_RE.search(text):
        return "MED.MEDICAL_HISTORY"
    return "MED.PAIN_SELF_REPORT"


def _annotation(
    record: CanonicalRecord,
    axis: str,
    code: str,
    polarity: str,
    evidence_span: str = "",
    span_start: int = 0,
    span_end: int = 0,
) -> Annotation:
    return Annotation(
        record.canonical_id,
        axis,
        code,
        polarity,
        evidence_span,
        taxonomy_version=CODED_ARTIFACT_TAXONOMY_VERSION,
        coder_id=CODER_ID,
        span_start=span_start,
        span_end=span_end,
        span_text=evidence_span,
    )


def _empty_record(record: CanonicalRecord) -> CodedRecord:
    """Records the contract skipped because title and text are both empty."""
    return CodedRecord(
        canonical_id=record.canonical_id,
        product_match=_normalise_product_match(record.product_match),
        experience_scope="none",
        experience_reason="no_experience_text",
        text_present=False,
        product_match_source=record.product_match_source,
        product_match_override_reason=record.product_match_override_reason,
    )


def _normalise_product_match(value: str) -> str:
    """Map a legacy product-match value to the E-merge enum."""
    return _LEGACY_PRODUCT_MATCH.get(value, value)


def _audit_entry(
    record: CanonicalRecord,
    assessment: Any,
    *,
    frozen: bool,
    scope: str,
    product_match: str,
    reason: str,
    declared_value: str | None,
) -> dict[str, Any]:
    return {
        "canonical_id": record.canonical_id,
        "source": record.source,
        "product_match": product_match,
        "on_topic": is_on_topic(product_match),
        "frames": list(record.frames or []),
        "frozen_is_product_experience": frozen,
        "frozen_experience_reason": str(reason or ""),
        "declared_experience_scope": declared_value,
        "assessed_scope": scope,
        "assessed_reason": assessment.reason,
        "evaluations": assessment.evaluations,
        "attributes": assessment.attributes,
        "evidence_share": round(assessment.evidence_share, 4),
        "in_cohort": in_experience_cohort(product_match, scope),
        "aspects_suppressed": not emits_aspects(
            product_match, scope, record.text or ""
        ),
        "evidence_clauses": list(assessment.evidence),
    }


def code_record(
    record: CanonicalRecord,
    row: dict[str, Any],
    *,
    min_confidence: str | None = None,
    dropped: list[dict[str, Any]] | None = None,
    audit: dict[str, list[dict[str, Any]]] | None = None,
) -> CodedRecord:
    """Adapt one coded row to the pipeline's ``CodedRecord``.

    Aspects below ``min_confidence`` are not annotations.  They become
    ``unknown_aspects`` entries with reason ``below_confidence_threshold`` and,
    when ``dropped`` is supplied, an audit row is appended for every one.

    E-merge §2: ``experience_scope`` is the only authority for the experience
    layer.  It is assessed from the record body for every row.  The old
    ``is_product_experience`` boolean is read only to classify the audit
    (downgrade / admit candidate / off-target evaluation); it never gates
    aspects.  ``product_match`` decides whether the record can emit aspects at
    all.
    """
    minimum = resolve_min_confidence(min_confidence)
    # Audit-only signal.  Never used as a gate (E-merge §3.1 step 4).
    frozen_experience = bool(row.get("is_product_experience"))
    frozen_reason = str(row.get("experience_reason") or "")
    experience_reason = frozen_reason
    aspect_rows = row.get("aspects") or []
    help_seeking = is_help_seeking(record)
    # Validate a declared scope as an audit cross-check.  The assessment
    # still owns the value: the v2 artifact used the old (help-seeking) rule,
    # so trusting its declared scope would reproduce the title-shaped bias
    # (A2 §6.4).  A malformed value fails closed.
    declared_scope = row.get("experience_scope")
    declared_value = None
    if declared_scope is not None:
        declared_value = str(declared_scope).strip().lower()
        if declared_value not in EXPERIENCE_SCOPES:
            raise ValueError(
                f"{record.canonical_id}: invalid experience_scope {declared_scope!r}; "
                f"expected one of {EXPERIENCE_SCOPES}"
            )
    assessment = assess_experience_scope(record)
    assessed_scope = assessment.scope
    product_match = _normalise_product_match(record.product_match)
    if product_match != record.product_match and audit is not None:
        audit.setdefault("legacy_product_match", []).append(
            {
                "canonical_id": record.canonical_id,
                "value": record.product_match,
                "mapped_to": product_match,
            }
        )
    if record.source == "tiktok_shop" and (
        frozen_experience or has_evaluation(assessed_scope)
    ):
        # A2 §2.4: the verified-purchase review set is product-bound by
        # construction and stays at ``full``.  This is a source-scoped rule,
        # not a generic ``true -> full`` mapping: a frozen-false TikTok row
        # with no evaluation (for example a relayed gift with no product
        # judgement) keeps the assessment's ``none``.
        experience_scope = "full"
    else:
        experience_scope = assessed_scope
    if declared_value is not None and declared_value != experience_scope:
        if audit is not None:
            audit.setdefault("declared_scope_mismatches", []).append(
                {
                    "canonical_id": record.canonical_id,
                    "declared_scope": declared_value,
                    "assessed_scope": experience_scope,
                    "reason": "declared scope is audit-only; assessment owns the value",
                }
            )
    if experience_scope == "none":
        if not is_on_topic(product_match):
            experience_reason = "product_mismatch"
        else:
            experience_reason = (
                "help_seeking" if help_seeking else assessment.reason
            )
    # Audit categories from E-merge §3.1 step 4 and §3.4.
    if audit is not None:
        if experience_scope != "none" and not is_on_topic(product_match):
            # Every off-target evaluation belongs in this ledger, whether the
            # old gate agreed or not.  c-pgsk2oe is frozen true but its
            # product is off-target; it must not disappear from the audit.
            audit.setdefault("off_target_evaluations", []).append(
                _audit_entry(
                    record, assessment, frozen=frozen_experience,
                    scope=experience_scope, product_match=product_match,
                    reason=frozen_reason, declared_value=declared_value,
                )
            )
        elif not frozen_experience and experience_scope != "none":
            audit.setdefault("admit_candidates", []).append(
                _audit_entry(
                    record, assessment, frozen=False, scope=experience_scope,
                    product_match=product_match, reason=frozen_reason,
                    declared_value=declared_value,
                )
            )
        elif frozen_experience and experience_scope == "none":
            audit.setdefault("downgrades", []).append(
                _audit_entry(
                    record, assessment, frozen=True, scope=experience_scope,
                    product_match=product_match, reason=frozen_reason,
                    declared_value=declared_value,
                )
            )
    experience_source = (
        derive_experience_source(record, str(row.get("notes") or ""))
        if has_evaluation(experience_scope)
        else "first_person"
    )
    # B16 ``c-7659258409535112974`` is a purchaser relaying a family member's
    # use.  The frozen row says ``first_person_use``, which contradicts the
    # derived ``relayed`` source.  Reconcile the label here, at the adapter
    # boundary, so the two published fields never disagree.
    if (
        has_evaluation(experience_scope)
        and experience_source == "relayed"
        and experience_reason == "first_person_use"
    ):
        experience_reason = "relayed_third_party"
    out = CodedRecord(
        canonical_id=record.canonical_id,
        product_match=product_match,
        experience_reason=experience_reason,
        experience_scope=experience_scope,
        experience_source=experience_source,
        text_present=bool((record.text or "").strip()),
        product_match_source=record.product_match_source,
        product_match_override_reason=record.product_match_override_reason,
    )
    source = _source_text(record)

    for aspect in aspect_rows if out.emit_aspects else []:
        code = aspect.get("code")
        polarity = aspect.get("polarity")
        if code not in _ASPECT_CODES:
            raise ValueError(f"{record.canonical_id}: unknown aspect code {code!r}")
        if polarity not in _POLARITIES:
            raise ValueError(f"{record.canonical_id}: unknown polarity {polarity!r}")
        span_start, span_end, evidence_span = _resolve_span(
            record, str(aspect.get("evidence_span") or "")
        )
        if minimum != "all":
            confidence = _confidence_label(aspect.get("confidence"), record.canonical_id)
            if CONFIDENCE_RANK[confidence] < CONFIDENCE_RANK[minimum]:
                out.unknown_aspects.append(
                    {
                        "code": code,
                        "reason": CONFIDENCE_DROP_REASON,
                        "confidence": confidence,
                        "span_start": span_start,
                        "span_end": span_end,
                        "evidence_span": evidence_span,
                    }
                )
                if dropped is not None:
                    dropped.append(
                        {
                            "canonical_id": record.canonical_id,
                            "code": code,
                            "polarity": polarity,
                            "confidence": confidence,
                            "evidence_span": evidence_span,
                            "reason": CONFIDENCE_DROP_REASON,
                            "threshold": minimum,
                        }
                    )
                continue
        if polarity in {"mixed", "unknown"}:
            # The rule coder abstains on a mixed clause and records the
            # reason; an ``unknown`` vote is also an abstention, never a
            # negative.  ``mixed_clause`` keeps direction_stats' existing
            # treatment of mixed records intact.
            out.unknown_aspects.append(
                {
                    "code": code,
                    "reason": "mixed_clause" if polarity == "mixed" else "unknown_polarity",
                    "span_start": span_start,
                    "span_end": span_end,
                    "evidence_span": evidence_span,
                }
            )
            continue
        out.annotations.append(
            _annotation(record, "aspect", code, polarity, evidence_span, span_start, span_end)
        )

    # Contexts are descriptive and carry no evidence span in the contract.
    for code in row.get("contexts") or []:
        if code not in _CONTEXT_CODES:
            raise ValueError(f"{record.canonical_id}: unknown context code {code!r}")
        out.annotations.append(_annotation(record, "context", code, "present"))

    if has_evaluation(experience_scope):
        journey = row.get("journey")
        if journey:
            journey_code = _JOURNEY_MAP.get(str(journey))
            if journey_code is None:
                raise ValueError(f"{record.canonical_id}: unknown journey {journey!r}")
            out.annotations.append(_annotation(record, "journey", journey_code, "present"))
            out.journey_stage = journey_code
        outcome = row.get("outcome")
        if outcome:
            outcome_code = _OUTCOME_MAP.get(str(outcome))
            if outcome_code is None:
                raise ValueError(f"{record.canonical_id}: unknown outcome {outcome!r}")
            out.annotations.append(_annotation(record, "outcome", outcome_code, "present"))
            out.outcome = outcome_code

    if row.get("medical_self_report"):
        medical_code = _medical_code(source)
        out.annotations.append(_annotation(record, "medical", medical_code, "present"))
        out.medical_flags.append(medical_code)
        out.claim_relation = "review_required"

    out.codes_hit = sorted({annotation.code for annotation in out.annotations})
    return out


def code_corpus(
    records: list[CanonicalRecord],
    *,
    run_dir: Path | None = None,
    coded_file: Path | None = None,
    min_confidence: str | None = None,
    dropped_file: Path | None = None,
    scope_audit_file: Path | None = None,
    scope_conflicts_file: Path | None = None,
    compat_diff_file: Path | None = None,
    coder_id: str = CODER_ID,
) -> list[CodedRecord]:
    """Code every canonical record from the frozen LLM artifact.

    The artifact covers every record with text.  Records with both title and
    text empty were skipped by the contract and become non-experience rows,
    matching the pipeline's ``no_experience_text`` rule.

    ``min_confidence`` defaults to ``VOC_MIN_CONFIDENCE`` and then to
    ``high``.  Every aspect the gate drops is written to
    ``confidence-dropped.jsonl`` in the run directory (or ``dropped_file``),
    so the abstention is auditable per record, code, polarity and span.

    ``experience_scope`` is assessed for every record.  The audit file
    ``scope-audit.json`` (E-merge §3.4) records off-target evaluations,
    downgrades, admit candidates and manual rejections.  The per-record diff
    against the old published ``experience`` boolean goes to
    ``compat-experience-diff.json``.  ``scope_conflicts_file`` is accepted as
    a deprecated alias for ``scope_audit_file``.
    """
    minimum = resolve_min_confidence(min_confidence)
    if coded_file is None:
        coded_file = coded_path(run_dir if run_dir is not None else DEFAULT_RUN_DIR)
    rows = load_coded(coded_file)

    record_ids = {record.canonical_id for record in records}
    extra = sorted(set(rows) - record_ids)
    if extra:
        raise ValueError(f"{coded_file}: coded ids not in canonical corpus: {extra[:5]}")
    missing_with_text = sorted(
        record.canonical_id
        for record in records
        if record.canonical_id not in rows and _source_text(record).strip()
    )
    if missing_with_text:
        raise ValueError(f"{coded_file}: text records missing from artifact: {missing_with_text[:5]}")

    dropped: list[dict[str, Any]] = []
    audit: dict[str, list[dict[str, Any]]] = {
        "off_target_evaluations": [],
        "downgrades": [],
        "admit_candidates": [],
        "declared_scope_mismatches": [],
        "legacy_product_match": [],
    }
    coded: list[CodedRecord] = []
    for record in records:
        if record.canonical_id not in rows:
            coded.append(_empty_record(record))
        else:
            coded.append(
                code_record(
                    record,
                    rows[record.canonical_id],
                    min_confidence=minimum,
                    dropped=dropped,
                    audit=audit,
                )
            )

    if dropped_file is None:
        dropped_file = dropped_path(run_dir if run_dir is not None else DEFAULT_RUN_DIR)
    write_confidence_dropped(dropped_file, dropped)
    if scope_audit_file is None:
        scope_audit_file = scope_conflicts_file
    if scope_audit_file is None and run_dir is not None:
        scope_audit_file = scope_audit_path(run_dir)
    if scope_audit_file is not None:
        write_scope_audit(scope_audit_file, records, rows, coded, audit, coder_id)
    if compat_diff_file is None and run_dir is not None:
        compat_diff_file = compat_experience_diff_path(run_dir)
    if compat_diff_file is not None:
        write_compat_experience_diff(compat_diff_file, records, rows, coded, coder_id)
    return coded
