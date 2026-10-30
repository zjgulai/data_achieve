"""Validation: schema, 30 invariants, anti-patterns and post-render checks.

Implements SOP skill ``voc-validation-handoff``.  Two layers:

1. ``validate_report_data`` runs the machine-readable schema, the Data
   Contract §7 invariants and the anti-pattern word scan before HTML is
   written.
2. ``validate_html`` runs the render-contract checks on the final HTML:
   exhibit seven-piece shell, readout counts, source-foot keys, drawers,
   status legend, no external resources, no unresolved tokens.

The validator is fail-closed.  A failed check is never downgraded to a
warning.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import contract, evidence


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class Suite:
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append(Check(name, bool(passed), detail))

    def extend(self, other: "Suite") -> None:
        self.checks.extend(other.checks)

    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.passed]

    def to_dict(self) -> dict[str, Any]:
        return {"status": "PASS" if self.passed else "FAIL", "checks": [check.to_dict() for check in self.checks]}


# ---------------------------------------------------------------------------
# minimal JSON Schema validator (stdlib only)
# ---------------------------------------------------------------------------
class SchemaValidator:
    def __init__(self, schema: dict[str, Any]):
        self.schema = schema

    def _resolve(self, ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise contract.ContractError(f"unsupported $ref: {ref}")
        node: Any = self.schema
        for token in ref[2:].split("/"):
            node = node[token.replace("~1", "/").replace("~0", "~")]
        return node

    def validate(self, instance: Any, schema: dict[str, Any] | None = None, path: str = "$") -> list[str]:
        schema = schema or self.schema
        errors: list[str] = []
        if "$ref" in schema:
            return self.validate(instance, self._resolve(schema["$ref"]), path)
        if "anyOf" in schema:
            subs = [self.validate(instance, sub, path) for sub in schema["anyOf"]]
            if all(subs):
                errors.append(f"{path}: no anyOf branch matched")
            return errors
        expected_type = schema.get("type")
        if expected_type is not None:
            types = expected_type if isinstance(expected_type, list) else [expected_type]
            if not any(self._is_type(instance, name) for name in types):
                return [f"{path}: expected type {expected_type}, got {type(instance).__name__}"]
        if "const" in schema and instance != schema["const"]:
            errors.append(f"{path}: expected const {schema['const']!r}")
        if "enum" in schema and instance not in schema["enum"]:
            errors.append(f"{path}: {instance!r} not in enum")
        if isinstance(instance, str):
            if len(instance) < schema.get("minLength", 0):
                errors.append(f"{path}: string shorter than {schema['minLength']}")
            if "maxLength" in schema and len(instance) > schema["maxLength"]:
                errors.append(f"{path}: string longer than {schema['maxLength']}")
            if "pattern" in schema and not re.search(schema["pattern"], instance):
                errors.append(f"{path}: does not match pattern {schema['pattern']}")
        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if "minimum" in schema and instance < schema["minimum"]:
                errors.append(f"{path}: value below minimum {schema['minimum']}")
            if "maximum" in schema and instance > schema["maximum"]:
                errors.append(f"{path}: value above maximum {schema['maximum']}")
        if isinstance(instance, list):
            if len(instance) < schema.get("minItems", 0):
                errors.append(f"{path}: fewer than {schema['minItems']} items")
            if "maxItems" in schema and len(instance) > schema["maxItems"]:
                errors.append(f"{path}: more than {schema['maxItems']} items")
            item_schema = schema.get("items")
            if item_schema:
                for index, item in enumerate(instance):
                    errors.extend(self.validate(item, item_schema, f"{path}[{index}]"))
        if isinstance(instance, dict):
            if len(instance) < schema.get("minProperties", 0):
                errors.append(f"{path}: fewer than {schema['minProperties']} properties")
            required = schema.get("required", [])
            for key in required:
                if key not in instance:
                    errors.append(f"{path}: missing required {key}")
            properties = schema.get("properties", {})
            for key, value in instance.items():
                if key in properties:
                    errors.extend(self.validate(value, properties[key], f"{path}.{key}"))
                else:
                    additional = schema.get("additionalProperties", True)
                    if additional is False:
                        errors.append(f"{path}: unexpected property {key}")
                    elif isinstance(additional, dict):
                        errors.extend(self.validate(value, additional, f"{path}.{key}"))
        return errors

    @staticmethod
    def _is_type(value: Any, name: str) -> bool:
        if name == "object":
            return isinstance(value, dict)
        if name == "array":
            return isinstance(value, list)
        if name == "string":
            return isinstance(value, str)
        if name == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if name == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if name == "boolean":
            return isinstance(value, bool)
        if name == "null":
            return value is None
        return True


def load_schema() -> dict[str, Any]:
    # Prefer the package-local copy so a shared top-level schema cannot
    # change this pipeline's machine contract.
    local = Path(__file__).resolve().parent / "schema.json"
    path = local if local.exists() else Path(__file__).resolve().parent.parent / "schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _walk_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            out.extend(_walk_strings(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            out.extend(_walk_strings(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        out.append((path, value))
    return out


def _walk_dicts(value: Any, path: str = "$") -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, dict):
        out.append((path, value))
        for key, item in value.items():
            out.extend(_walk_dicts(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            out.extend(_walk_dicts(item, f"{path}[{index}]"))
    return out


def _collect_source_paths(value: Any) -> list[tuple[str, str]]:
    out = []
    for path, node in _walk_dicts(value):
        source_path = node.get("source_path")
        if isinstance(source_path, str):
            out.append((path, source_path))
    return out


def _sum_values(mapping: dict[str, Any]) -> int:
    total = 0
    for item in mapping.values():
        if isinstance(item, dict):
            value = item.get("value", item.get("count", 0))
        else:
            value = item
        if isinstance(value, (int, float)):
            total += int(value)
    return total


def _gate_map(data: dict[str, Any]) -> dict[str, str]:
    return {item["gate_id"]: item["status"] for item in data["evidence"]["gate"].get("gates", [])}


# ---------------------------------------------------------------------------
# report-data validation
# ---------------------------------------------------------------------------
def validate_report_data(
    data: dict[str, Any],
    *,
    resolver: Any | None = None,
    taxonomy: dict[str, Any] | None = None,
) -> Suite:
    suite = Suite()

    # schema
    schema_errors = SchemaValidator(load_schema()).validate(data)
    suite.add("SCHEMA-01", not schema_errors, "; ".join(schema_errors[:8]) if schema_errors else "machine schema satisfied")

    suite.add("ROOT-01", data.get("schema_version") == contract.SCHEMA_VERSION, f"schema_version={data.get('schema_version')}")
    suite.add("ROOT-02", data.get("report_mode") in {"progress_snapshot", "insight_report", "strategy_report"}, f"mode={data.get('report_mode')}")
    for key in ("report_id", "as_of", "generated_at", "language", "evidence", "report", "artifacts"):
        suite.add(f"ROOT-{key}", key in data, f"missing {key}" if key not in data else "present")

    # sections
    sections = data["report"].get("sections", [])
    expected = contract.SECTION_SPEC
    suite.add("INV-20", len(sections) == 11 and [s.get("id") for s in sections] == [s["id"] for s in expected], f"sections={[s.get('id') for s in sections]}")
    for index, section in enumerate(sections):
        for key in ("index", "id", "kicker", "title", "status", "blocks"):
            suite.add(f"SEC-{index}-{key}", key in section, f"missing {key}")
        title = section.get("title")
        title_text = title.get("text", "") if isinstance(title, dict) else str(title)
        suite.add(f"SEC-{index}-TITLE", 8 <= len(title_text) <= 60, f"title length {len(title_text)}")

    # claims
    claims = data["report"].get("claims", [])
    suite.add("CLAIMS-01", len(claims) >= 1, f"claims={len(claims)}")
    claim_ids: set[str] = set()
    for claim in claims:
        cid = claim.get("claim_id", "?")
        suite.add(f"CLAIM-{cid}-ID", bool(re.fullmatch(r"C[0-9]{2}", cid)), cid)
        suite.add(f"CLAIM-{cid}-SECTION", claim.get("section") in contract.SECTION_IDS, str(claim.get("section")))
        suite.add(f"CLAIM-{cid}-GRADE", claim.get("grade") in contract.STATUS_ORDER, str(claim.get("grade")))
        suite.add(f"CLAIM-{cid}-UNIQUE", cid not in claim_ids, "duplicate claim id")
        claim_ids.add(cid)
        for key in ("observed", "interpretation", "counterevidence", "decision_implication"):
            value = claim.get(key)
            text = value.get("text", "") if isinstance(value, dict) else str(value or "")
            suite.add(f"CLAIM-{cid}-{key}", len(text.strip()) >= 8, f"length {len(text)}")
        suite.add(f"CLAIM-{cid}-NUMBERS", len(claim.get("numbers", [])) >= 1, f"numbers={len(claim.get('numbers', []))}")
        try:
            computed = evidence.assign_grade(evidence.grade_input_from_dict(claim.get("grade_inputs", {})))
            suite.add(f"INV-16-{cid}", computed == claim.get("grade"), f"computed={computed} declared={claim.get('grade')}")
        except Exception as exc:  # noqa: BLE001 - validation must report, not crash
            suite.add(f"INV-16-{cid}", False, str(exc))

    # exhibits
    exhibits = []
    for section in sections:
        for block in section.get("blocks", []):
            if block.get("type") == "exhibit":
                exhibits.append(block)
    suite.add("INV-21", len(exhibits) >= 1, f"exhibits={len(exhibits)}")
    numbers = [block.get("number") for block in exhibits]
    suite.add("EXHIBIT-UNIQUE", len(numbers) == len(set(numbers)), str(numbers))
    suite.add("EXHIBIT-RANGE", all(re.fullmatch(r"(0[1-9]|10)", str(n)) for n in numbers), str(numbers))
    for block in exhibits:
        number = block.get("number", "?")
        required = ("type", "number", "title", "scope", "evidence_status", "chart", "readout", "source_foot", "drawer", "data_table", "definitions")
        missing = [key for key in required if key not in block]
        suite.add(f"INV-18-{number}", not missing, f"missing {missing}")
        title = block.get("title")
        title_text = title.get("text", "") if isinstance(title, dict) else str(title)
        suite.add(f"EXHIBIT-{number}-TITLE", bool(re.search(r"[0-9]", title_text)), "title must contain a number")
        suite.add(f"EXHIBIT-{number}-SCOPE", len(str(block.get("scope", ""))) >= 8, "scope too short")
        for key in ("observed", "interpretation", "counterevidence", "decision_implication"):
            value = block.get("readout", {}).get(key)
            text = value.get("text", "") if isinstance(value, dict) else str(value or "")
            suite.add(f"EXHIBIT-{number}-READOUT-{key}", len(text.strip()) >= 8, f"length {len(text)}")
        foot = block.get("source_foot", {})
        suite.add(f"INV-19-{number}", all(key in foot for key in ("basis", "unit", "limit", "status")), str(list(foot)))
        suite.add(f"EXHIBIT-{number}-DRAWER", bool(block.get("drawer", {}).get("summary")) and bool(block.get("drawer", {}).get("content")), "drawer empty")
        suite.add(f"EXHIBIT-{number}-DEFS", len(block.get("definitions", [])) >= 1, "definitions empty")
        chart = block.get("chart", {})
        suite.add(f"EXHIBIT-{number}-CHART", chart.get("type") in {"nested_bar", "diverging_bar", "frame_grid", "co_occurrence_matrix", "quadrant_2x2", "coverage_bars", "social_flow", "variant_grid", "maturity_matrix", "lineage_waterfall"}, str(chart.get("type")))
        suite.add(f"EXHIBIT-{number}-NOTES", len(chart.get("notes", [])) >= 1, "chart notes empty")

    # gap blocks
    for section in sections:
        for block in section.get("blocks", []):
            if block.get("type") == "gap":
                suite.add(f"GAP-{section.get('id')}-READOUT", all(key in block.get("readout", {}) for key in ("observed", "interpretation", "counterevidence", "decision_implication")), "gap readout incomplete")
                suite.add(f"GAP-{section.get('id')}-FOOT", all(key in block.get("source_foot", {}) for key in ("basis", "unit", "limit", "status")), "gap source_foot incomplete")

    # prohibited outputs
    prohibited = data["report"].get("prohibited_outputs", [])
    suite.add("INV-22", len(prohibited) >= 1, f"prohibited={len(prohibited)}")
    labels = " ".join(item.get("label", "") for item in prohibited)
    for token in ("总体情绪率", "饼图", "跨 frame", "annotation", "星级", "ROI", "医学", "覆盖"):
        suite.add(f"PROHIBITED-{token}", token in labels, f"missing {token}")

    # corpus / coverage invariants
    corpus = data["evidence"]["corpus"]
    coverage = data["evidence"]["coverage"]
    suite.add("INV-03", corpus["canonical_records"]["value"] <= corpus["occurrences"]["value"] <= corpus["raw_objects"]["value"], f"{corpus['raw_objects']['value']} / {corpus['occurrences']['value']} / {corpus['canonical_records']['value']}")
    suite.add("INV-04", corpus["frame_memberships"]["value"] >= corpus["canonical_records"]["value"], f"{corpus['frame_memberships']['value']} >= {corpus['canonical_records']['value']}")
    for index, row in enumerate(corpus.get("reconciliation", [])):
        reasons_total = sum(row.get("reasons", {}).values())
        expected_deduction = row["deducted"] if row["deducted"] >= 0 else -row["deducted"]
        suite.add(f"INV-01-{index}", reasons_total == expected_deduction, f"reasons={reasons_total} deducted={row['deducted']}")
        suite.add(f"INV-02-{index}", row["input_count"] - row["deducted"] == row["output_count"], f"{row['input_count']} - {row['deducted']} != {row['output_count']}")
    aspect_total = coverage["aspect_annotation_count"]["value"]
    suite.add("INV-05", _sum_values(coverage["aspect_code_counts"]) == aspect_total, f"{_sum_values(coverage['aspect_code_counts'])} vs {aspect_total}")
    suite.add("INV-06", _sum_values(coverage["aspect_polarity_counts"]) == aspect_total, f"{_sum_values(coverage['aspect_polarity_counts'])} vs {aspect_total}")
    code_count = (taxonomy or {}).get("codes") and len(taxonomy["codes"]) or data["evidence"]["taxonomy"].get("code_count", 0)
    suite.add("INV-07", len(coverage["aspect_code_counts"]) == code_count or bool(coverage.get("aspect_code_observed_subset")), f"{len(coverage['aspect_code_counts'])} of {code_count}")
    suite.add("INV-08", _sum_values(coverage["expectation_gap_counts"]) == coverage["independent_content_units"]["value"], f"{_sum_values(coverage['expectation_gap_counts'])} vs {coverage['independent_content_units']['value']}")

    # variants / mixed / lenses / need states
    identity = data["evidence"]["identity"]
    variants = data["evidence"]["variants"]
    suite.add("INV-10", len(variants.get("items", [])) == identity.get("family_children"), f"{len(variants.get('items', []))} vs {identity.get('family_children')}")
    suite.add("INV-11", sum(1 for item in variants.get("items", []) if item.get("is_target")) == 1, "target count")
    review_total = 0
    for item in variants.get("items", []):
        block = item.get("review_count")
        if isinstance(block, dict) and isinstance(block.get("value"), (int, float)):
            review_total += int(block["value"])
    source_total = (identity.get("product_rating") or {}).get("review_count") or 0
    suite.add("INV-12", review_total <= source_total, f"{review_total} <= {source_total}")
    mixed = data["evidence"].get("mixed")
    if mixed:
        suite.add("INV-09", sum(sum(row.values()) for row in mixed.get("matrix", {}).values()) == mixed["mixed_records"]["value"], "matrix sum")
    else:
        suite.add("INV-09", True, "mixed absent; section gap")
    taxonomy_codes = {code.get("code") for code in data["evidence"]["taxonomy"].get("codes", [])}
    suite.add("INV-13", all(item.get("code") in taxonomy_codes for item in data["evidence"].get("key_aspects", [])), "key aspect outside taxonomy")
    lens_ids = [lens.get("id") for lens in data["evidence"].get("cluster_lenses", [])]
    suite.add("INV-14", len(lens_ids) == len(set(lens_ids)) and set(lens_ids) <= {"natural", "diagnostic", "qualitative_seed"}, str(lens_ids))
    need_states = data["evidence"].get("need_states", [])
    suite.add("INV-15", all(re.match(r"^Q[1-4] · ", item.get("quadrant", "")) for item in need_states) and len({item.get("id") for item in need_states}) == len(need_states), f"need_states={len(need_states)}")

    # claim / reasoning / gates
    claims_ok = all(
        all(key in claim.get("readout", claim) for key in ("observed", "interpretation", "counterevidence", "decision_implication"))
        for claim in claims
    )
    suite.add("INV-17", claims_ok, "claim four questions")
    for path, node in _walk_dicts(data):
        if "text" in node and "authored_by" in node:
            suite.add(f"INV-24-{path}", node.get("claim_id") is not None and bool(node.get("data_refs")), "text provenance missing claim_id/data_refs")
            break
    gates = _gate_map(data)
    mode = data.get("report_mode")
    suite.add("INV-25", mode == "progress_snapshot" or gates.get("G7") == "PASS", f"mode={mode} G7={gates.get('G7')}")
    metric_rows = data["evidence"]["corpus"]["metric_rows"]["value"]
    suite.add("INV-26", metric_rows == 0 or gates.get("G7") == "PASS", f"metric_rows={metric_rows} G7={gates.get('G7')}")
    for path, node in _walk_dicts(data):
        chart = node.get("chart") if isinstance(node, dict) else None
        if not isinstance(chart, dict):
            continue
        if chart.get("encoding") == "share_with_denominator":
            suite.add(f"INV-27-{path}", isinstance(chart.get("denominator"), int) and chart["denominator"] > 0, "share without denominator")
        if len(chart.get("frame_scope", [])) > 1:
            suite.add(f"INV-28-{path}", chart.get("encoding") != "share_with_denominator", "cross-frame share")
    suite.add("INV-29", "mapping_confidence" not in json.dumps(coverage, ensure_ascii=False), "mapping_confidence used as sample")

    # source paths
    artifacts_by_path = {item.get("path"): item for item in data.get("artifacts", [])}
    source_paths = _collect_source_paths(data)
    unresolved = []
    missing_artifacts = []
    for path, source_path in source_paths:
        name, _ = contract.parse_source_path(source_path)
        if name not in artifacts_by_path:
            missing_artifacts.append(f"{name} ({path})")
        if resolver is not None:
            try:
                resolver.resolve(source_path)
            except Exception as exc:  # noqa: BLE001
                unresolved.append(f"{source_path}: {exc}")
    suite.add("INV-23-ARTIFACTS", not missing_artifacts, "; ".join(missing_artifacts[:5]))
    suite.add("INV-23-RESOLVE", not unresolved, "; ".join(unresolved[:5]))

    # anti-pattern scan (exclude prohibited_outputs)
    scan_data = json.loads(json.dumps(data, ensure_ascii=False))
    scan_data["report"]["prohibited_outputs"] = []
    hits = []
    for path, text in _walk_strings(scan_data):
        for term in contract.ANTI_PATTERN_TERMS:
            if term in text:
                hits.append(f"{term} @ {path}")
    suite.add("INV-30", not hits, "; ".join(hits[:8]))

    return suite


# ---------------------------------------------------------------------------
# HTML validation
# ---------------------------------------------------------------------------
def _extract(pattern: str, text: str, flags: int = re.S) -> list[str]:
    return re.findall(pattern, text, flags)


def validate_html(html: str) -> Suite:
    suite = Suite()
    suite.add("V-01", len(re.findall(r"<h1\b", html)) == 1, f"h1={len(re.findall(r'<h1\\b', html))}")
    section_count = len(re.findall(r'<section class="section"', html))
    h2_count = len(re.findall(r"<h2>", html))
    suite.add("V-02", section_count == 11 and h2_count == 11, f"sections={section_count} h2={h2_count}")

    exhibits = re.findall(r'<figure class="exhibit".*?</figure>', html, re.S)
    figures = len(re.findall(r"<figure\b", html))
    suite.add("V-03", len(exhibits) >= 1 and figures == len(exhibits), f"exhibits={len(exhibits)} figures={figures}")

    for index, block in enumerate(exhibits, 1):
        pieces = {
            "exhibit-head": 'class="exhibit-head"' in block,
            "exhibit-scope": 'class="exhibit-scope"' in block,
            "evidence-badge": "evidence-badge" in block,
            "exhibit-body": 'class="exhibit-body"' in block,
            "exhibit-readout": 'class="exhibit-readout"' in block,
            "source-foot": 'class="source-foot"' in block,
            "evidence-drawer": '<details class="evidence-drawer"' in block,
        }
        suite.add(f"V-04-{index}", all(pieces.values()), str([k for k, v in pieces.items() if not v]))
        suite.add(f"V-05-{index}", block.count('class="readout-item"') == 4, f"readout={block.count('class=\"readout-item\"')}")
        foot = re.search(r'<div class="source-foot">.*?</div>', block, re.S)
        suite.add(f"V-06-{index}", bool(foot) and foot.group(0).count("<b>") == 4, f"foot_b={foot.group(0).count('<b>') if foot else 0}")
        suite.add(f"V-07-{index}", '<details class="evidence-drawer"' in block, "drawer missing")
        attrs = dict(re.findall(r'data-(basis|unit|limit|status)="([^"]*)"', block))
        suite.add(f"V-15-{index}", all(attrs.get(key) for key in ("basis", "unit", "limit", "status")), str(attrs))

    claims = re.findall(r'<article class="claim".*?</article>', html, re.S)
    for index, block in enumerate(claims, 1):
        suite.add(f"V-05-CLAIM-{index}", block.count('class="readout-item"') == 4, f"readout={block.count('class=\"readout-item\"')}")
        foot = re.search(r'<div class="source-foot">.*?</div>', block, re.S)
        suite.add(f"V-06-CLAIM-{index}", bool(foot) and foot.group(0).count("<b>") == 4, "claim foot keys")

    gaps = re.findall(r'<div class="gap-block".*?</div>\s*</div>', html, re.S)
    for index, block in enumerate(gaps, 1):
        suite.add(f"V-05-GAP-{index}", block.count('class="readout-item"') == 4, f"readout={block.count('class=\"readout-item\"')}")

    legend = re.search(r'<table class="status-legend">.*?</table>', html, re.S)
    suite.add("V-08", bool(legend) and len(re.findall(r"<tr>", legend.group(0))) == 7, "status legend rows")
    last_section = html.rfind('<section class="section"')
    prohibited = html.find('<section class="prohibited"')
    footer = html.find('<footer')
    suite.add("V-09", prohibited > last_section and (footer < 0 or prohibited < footer), "prohibited position")

    external_patterns = [r"<link\b", r"<script\s+src", r"@import", r"@font-face", r"url\(", r"http://", r"https://", r"<img\b", r"<iframe\b", r"<canvas\b", r"<svg\b"]
    external_hits = [pattern for pattern in external_patterns if re.search(pattern, html, re.I)]
    suite.add("V-10", not external_hits, str(external_hits))
    suite.add("V-11", "{{" not in html, "unresolved template token")

    # Remove prohibited block before scanning banned words.
    scan_html = html
    if prohibited >= 0:
        end = html.find("</section>", prohibited)
        if end >= 0:
            scan_html = html[:prohibited] + html[end + len("</section>") :]
    banned_hits = [term for term in contract.ANTI_PATTERN_TERMS if term in scan_html]
    suite.add("V-12", not banned_hits, str(banned_hits))

    ids = re.findall(r'<section class="section" id="([^"]+)"', html)
    suite.add("V-13", ids == contract.SECTION_IDS, str(ids))
    numbers = re.findall(r'id="exhibit-([0-9]{2})"', html)
    suite.add("V-14", len(numbers) == len(set(numbers)) and all(re.fullmatch(r"(0[1-9]|10)", n) for n in numbers), str(numbers))

    chart_tags = re.findall(r'<div class="chart [^"]*"[^>]*>', html)
    suite.add("V-16", all("role=" in tag and "aria-label=" in tag for tag in chart_tags), f"charts={len(chart_tags)}")
    suite.add("V-17", html.count('<table class="variant-table">') == 1, "variant table count")
    suite.add("V-18", "@media print" in html and "details{display:block}" in html.replace("\n", "").replace(" ", ""), "print details rule")
    suite.add("V-19", not re.search(r"\son(click|load|error|change|input)\s*=", html, re.I), "inline event handler")
    suite.add("V-20", "font-variant-numeric:tabular-nums" in html, "tabular nums missing")
    return suite
