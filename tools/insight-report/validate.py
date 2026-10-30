#!/usr/bin/env python3
"""validate.py — fail-closed validator for VOC report data and rendered HTML.

Two modes:

  python3 validate.py --data out/report-data.json
  python3 validate.py --html out/report.html --data out/report-data.json

The validator never downgrades a failure to a warning. Missing required fields,
missing four-question readouts, missing source-foot keys, missing exhibit parts,
hero proof totals, and every anti-pattern in the contract stop the build.

Python 3 standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import ir_contract as C

SCHEMA_PATH = Path(__file__).with_name("schema.json")

ACTION_VERBS = (
    "验证", "补采", "停止", "回滚", "重跑", "拆分", "合并", "隔离", "标注",
    "复核", "使用", "保留", "建立", "检查", "记录", "转", "把", "先", "用",
    "将", "重做", "补", "停止", "冻结", "版本化",
)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------
@dataclass
class Issue:
    rule: str
    path: str
    message: str
    hint: str = ""


@dataclass
class Check:
    rule: str
    name: str
    issues: list[Issue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.issues


@dataclass
class Suite:
    checks: list[Check] = field(default_factory=list)

    def add(self, rule: str, name: str, issues: list[Issue] | None = None) -> None:
        self.checks.append(Check(rule, name, issues or []))

    def check(self, rule: str, name: str, ok: bool, path: str = "$", message: str = "", hint: str = "") -> None:
        self.add(rule, name, [] if ok else [Issue(rule, path, message or name, hint)])

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def as_dict(self) -> dict:
        return {
            "status": "PASS" if self.passed else "FAIL",
            "checks": [
                {
                    "rule": c.rule,
                    "name": c.name,
                    "passed": c.passed,
                    "errors": [i.__dict__ for i in c.issues],
                }
                for c in self.checks
            ],
            "failed_checks": [
                {"rule": c.rule, "name": c.name, "errors": [i.__dict__ for i in c.issues]}
                for c in self.checks if not c.passed
            ],
        }

    def print_human(self, title: str) -> None:
        print(f"== {title} ==")
        failed = 0
        for c in self.checks:
            if c.passed:
                print(f"PASS  [{c.rule}] {c.name}")
            else:
                failed += 1
                print(f"FAIL  [{c.rule}] {c.name}")
                for i in c.issues[:12]:
                    print(f"      at {i.path}")
                    print(f"      {i.message}")
                    if i.hint:
                        print(f"      hint: {i.hint}")
                if len(c.issues) > 12:
                    print(f"      ... {len(c.issues) - 12} more")
        total = len(self.checks)
        print(f"RESULT: {'PASS' if failed == 0 else 'FAIL'} ({total - failed}/{total} checks)")


# ---------------------------------------------------------------------------
# Tiny JSON Schema subset validator (draft 2020-12 subset)
# ---------------------------------------------------------------------------
def _type_ok(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _resolve_ref(ref: str, root: dict):
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref: {ref}")
    node = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[part]
    return node


def schema_errors(value, schema: dict, root: dict, path: str = "$", depth: int = 0) -> list[Issue]:
    """Validate a JSON value against the subset used by schema.json."""
    issues: list[Issue] = []
    if depth > 40:
        return [Issue("SCHEMA", path, "schema recursion too deep")]

    if "$ref" in schema:
        return schema_errors(value, _resolve_ref(schema["$ref"], root), root, path, depth + 1)

    if "const" in schema and value != schema["const"]:
        issues.append(Issue("SCHEMA", path, f"must equal {schema['const']!r}, got {value!r}"))
    if "enum" in schema and value not in schema["enum"]:
        issues.append(Issue("SCHEMA", path, f"must be one of {schema['enum']}, got {value!r}"))

    if "anyOf" in schema:
        if not any(not schema_errors(value, s, root, path, depth + 1) for s in schema["anyOf"]):
            issues.append(Issue("SCHEMA", path, "does not match any allowed shape"))
        return issues
    if "oneOf" in schema:
        matches = sum(1 for s in schema["oneOf"] if not schema_errors(value, s, root, path, depth + 1))
        if matches != 1:
            issues.append(Issue("SCHEMA", path, f"must match exactly one shape, matched {matches}"))
        return issues

    expected_type = schema.get("type")
    if expected_type is not None:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_type_ok(value, t) for t in types):
            issues.append(Issue("SCHEMA", path, f"expected type {types}, got {type(value).__name__}"))
            return issues

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            issues.append(Issue("SCHEMA", path, f"string shorter than minLength {schema['minLength']}"))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            issues.append(Issue("SCHEMA", path, f"does not match pattern {schema['pattern']!r}"))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            issues.append(Issue("SCHEMA", path, f"value {value} below minimum {schema['minimum']}"))
        if "maximum" in schema and value > schema["maximum"]:
            issues.append(Issue("SCHEMA", path, f"value {value} above maximum {schema['maximum']}"))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            issues.append(Issue("SCHEMA", path, f"array has {len(value)} items, needs >= {schema['minItems']}"))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            issues.append(Issue("SCHEMA", path, f"array has {len(value)} items, needs <= {schema['maxItems']}"))
        if "items" in schema:
            for i, item in enumerate(value):
                issues.extend(schema_errors(item, schema["items"], root, f"{path}[{i}]", depth + 1))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                issues.append(Issue("SCHEMA", path, f"missing required key {key!r}", f"required by {schema.get('$id', 'schema')}"))
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in value:
                issues.extend(schema_errors(value[key], sub, root, f"{path}.{key}", depth + 1))
        additional = schema.get("additionalProperties", True)
        for key, val in value.items():
            if key in props:
                continue
            if additional is False:
                issues.append(Issue("SCHEMA", f"{path}.{key}", f"unknown key {key!r}"))
            elif isinstance(additional, dict):
                issues.extend(schema_errors(val, additional, root, f"{path}.{key}", depth + 1))
        if "minProperties" in schema and len(value) < schema["minProperties"]:
            issues.append(Issue("SCHEMA", path, f"object has {len(value)} keys, needs >= {schema['minProperties']}"))
    return issues


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def text_of(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("text", ""))
    return ""


def walk(value, path="$"):
    yield path, value
    if isinstance(value, dict):
        for k, v in value.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk(v, f"{path}[{i}]")


def strings(value, path="$"):
    for p, v in walk(value, path):
        if isinstance(v, str):
            yield p, v


def find_section(data: dict, index: str):
    for s in data.get("report", {}).get("sections", []):
        if s.get("index") == index:
            return s
    return None


def all_exhibits(data: dict) -> list[tuple[str, dict]]:
    out = []
    for s in data.get("report", {}).get("sections", []):
        for b in s.get("blocks", []):
            if b.get("type") == "exhibit":
                out.append((s.get("index", "?"), b))
    return out


# ---------------------------------------------------------------------------
# Data validation
# ---------------------------------------------------------------------------
def validate_data(data: dict, schema_path: Path = SCHEMA_PATH) -> Suite:
    suite = Suite()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    # Structural schema -----------------------------------------------------
    issues = schema_errors(data, schema, schema)
    suite.add("SCHEMA", "report-data.json matches schema.json", issues)

    report = data.get("report", {})
    evidence = data.get("evidence", {})
    claims = report.get("claims", [])
    claims_by_id = {c.get("claim_id"): c for c in claims}
    mode = data.get("report_mode")
    gate_map = {g.get("gate_id"): g.get("status") for g in evidence.get("gate", {}).get("gates", [])}
    g7 = gate_map.get("G7")

    # Hero: ratio or gap only ----------------------------------------------
    hero_issues = []
    hero = report.get("hero", {})
    proofs = hero.get("proofs", [])
    known_numbers = set()
    for c in claims:
        for n in c.get("numbers", []):
            if isinstance(n.get("value"), (int, float)):
                known_numbers.add(n["value"])
    for key, cb in walk(evidence.get("coverage", {})):
        if isinstance(cb, dict) and "value" in cb and isinstance(cb["value"], (int, float)):
            known_numbers.add(cb["value"])
    if len(proofs) != 4:
        hero_issues.append(Issue("HERO-01", "$.report.hero.proofs", f"must contain exactly 4 proofs, got {len(proofs)}"))
    for i, p in enumerate(proofs):
        ok, reason = C.is_ratio_or_gap(p.get("value", ""))
        if not ok:
            hero_issues.append(Issue("HERO-01", f"$.report.hero.proofs[{i}].value", reason,
                                     "把总量改成比值（3 / 27）或缺口（250 → 248）；总量不能进 Hero"))
        for token in re.findall(r"\d+", str(p.get("value", ""))):
            if int(token) not in known_numbers:
                hero_issues.append(Issue("HERO-02", f"$.report.hero.proofs[{i}].value",
                                         f"number {token} does not appear in claims[].numbers or coverage",
                                         "Hero 数字必须能回到证据"))
    h1 = text_of(hero.get("h1"))
    accent = hero.get("h1_accent", "")
    if accent and h1.count(accent) != 1:
        hero_issues.append(Issue("HERO-03", "$.report.hero.h1_accent", f"accent {accent!r} appears {h1.count(accent)} times in h1"))
    if "?" in h1 or "？" in h1:
        hero_issues.append(Issue("HERO-04", "$.report.hero.h1", "h1 must be a conclusion sentence, not a question"))
    compass_labels = [x.get("label") for x in hero.get("compass", [])]
    if compass_labels != ["Protect", "Resolve", "Prove"]:
        hero_issues.append(Issue("HERO-05", "$.report.hero.compass", f"compass must be Protect/Resolve/Prove, got {compass_labels}"))
    suite.add("HERO", "hero proofs are ratios or gaps", hero_issues)

    # Decision: answer cites at least two claims ---------------------------
    dec_issues = []
    answer = text_of(report.get("decision", {}).get("answer"))
    cited = sorted(set(re.findall(r"C\d{2}", answer)))
    if len(cited) < 2:
        dec_issues.append(Issue("DEC-01", "$.report.decision.answer", f"answer cites {len(cited)} claim ids; needs >= 2"))
    for cid in cited:
        if cid not in claims_by_id:
            dec_issues.append(Issue("DEC-02", "$.report.decision.answer", f"cites unknown claim {cid}"))
    for key in ("protect", "resolve", "prove"):
        if not report.get("decision", {}).get(key):
            dec_issues.append(Issue("DEC-03", f"$.report.decision.{key}", "must not be empty"))
    suite.add("DEC", "decision answer cites evidence", dec_issues)

    # Sections -------------------------------------------------------------
    sec_issues = []
    sections = report.get("sections", [])
    present_ids = [s.get("id") for s in sections]
    expected_subsequence = [sid for sid in C.SECTION_ORDER if sid in present_ids]
    if present_ids != expected_subsequence:
        sec_issues.append(Issue("SEC-01", "$.report.sections", f"section order must follow the frozen 11-section order; got {present_ids}"))
    if len(set(present_ids)) != len(present_ids):
        sec_issues.append(Issue("SEC-02", "$.report.sections", "duplicate section ids"))
    for s in sections:
        idx, sid = s.get("index"), s.get("id")
        spec = C.SECTION_BY_INDEX.get(idx)
        if not spec or spec["id"] != sid:
            sec_issues.append(Issue("SEC-03", f"$.report.sections[{idx}]", f"index/id mismatch: {idx}/{sid}"))
        title = text_of(s.get("title"))
        if title in {"概览", "小结", "结论", "背景", "方法", "目录", "附录"}:
            sec_issues.append(Issue("SEC-04", f"$.report.sections[{idx}].title", f"generic title {title!r} is banned"))
        if len(title) < 15:
            sec_issues.append(Issue("SEC-05", f"$.report.sections[{idx}].title", f"title is {len(title)} chars; needs >= 15"))
        blocks = s.get("blocks", [])
        if not blocks:
            sec_issues.append(Issue("SEC-06", f"$.report.sections[{idx}].blocks", "must contain at least 1 block"))
        has_gap = any(b.get("type") == "gap" for b in blocks)
        has_data = any(b.get("type") != "gap" for b in blocks)
        if s.get("status") == "ok" and has_gap:
            sec_issues.append(Issue("SEC-07", f"$.report.sections[{idx}].status", "status=ok but contains gap block"))
        if s.get("status") == "partial" and not (has_gap and has_data):
            sec_issues.append(Issue("SEC-08", f"$.report.sections[{idx}].status", "status=partial requires both data and gap blocks"))
    suite.add("SEC", "sections are ordered, titled, and complete", sec_issues)

    # Claims ---------------------------------------------------------------
    claim_issues = []
    if not claims:
        claim_issues.append(Issue("CLM-00", "$.report.claims", "at least one claim is required"))
    seen = set()
    for i, c in enumerate(claims):
        cid = c.get("claim_id", f"#{i}")
        p = f"$.report.claims[{i}]"
        if cid in seen:
            claim_issues.append(Issue("CLM-01", p + ".claim_id", f"duplicate claim id {cid}"))
        seen.add(cid)
        for key, minlen in (("observed", 8), ("interpretation", 12), ("counterevidence", 12), ("decision_implication", 12)):
            txt = text_of(c.get(key))
            if not txt.strip():
                claim_issues.append(Issue("CLM-02", f"{p}.{key}", "four-question field is empty", "四问缺一 = FAIL_BUILD"))
            elif len(txt) < minlen:
                claim_issues.append(Issue("CLM-02", f"{p}.{key}", f"text is {len(txt)} chars; needs >= {minlen}"))
        ce = text_of(c.get("counterevidence"))
        if not (any(x in ce for x in ("如果", "若", "除非", "一旦")) or "没有找到反证" in ce):
            claim_issues.append(Issue("CLM-03", p + ".counterevidence", "must state what would overturn it (如果/若/除非/一旦)"))
        di = text_of(c.get("decision_implication"))
        if di and not di.startswith(ACTION_VERBS):
            claim_issues.append(Issue("CLM-04", p + ".decision_implication", f"must start with an action verb, got {di[:12]!r}"))
        grade = c.get("grade")
        if grade not in C.GRADES:
            claim_issues.append(Issue("CLM-05", p + ".grade", f"unknown grade {grade!r}"))
        else:
            ok, reason = grade_is_consistent(grade, c.get("grade_inputs", {}))
            if not ok:
                claim_issues.append(Issue("CLM-06", p + ".grade_inputs", f"grade {grade!r} not supported by inputs: {reason}"))
            label = C.STATUS_LABEL[grade]
            if not str(c.get("status", "")).lower().startswith(label.lower()):
                claim_issues.append(Issue("CLM-07", p + ".status", f"status must start with {label!r} for grade {grade!r}"))
        if not c.get("numbers"):
            claim_issues.append(Issue("CLM-08", p + ".numbers", "at least one NumberRef is required"))
        for j, n in enumerate(c.get("numbers", [])):
            np = f"{p}.numbers[{j}]"
            if not n.get("source_path"):
                claim_issues.append(Issue("CLM-09", np + ".source_path", "missing source_path"))
            if not n.get("basis") or len(n.get("basis", "")) < 8:
                claim_issues.append(Issue("CLM-09", np + ".basis", "basis must be >= 8 chars"))
            name = str(n.get("name", ""))
            if C.NET_SCORE_PATTERN.search(name):
                claim_issues.append(Issue("AP-03", np + ".name", f"net-score metric name {name!r} is banned"))
            if "mapping_confidence" in name and ("denominator" in name or "sample" in name or name == "n"):
                claim_issues.append(Issue("AP-08", np + ".name", "mapping_confidence cannot be a sample size"))
    suite.add("CLM", "claims carry four questions, grades, and sources", claim_issues)

    # Exhibits -------------------------------------------------------------
    ex_issues = []
    exhibits = all_exhibits(data)
    numbers_seen = []
    for sec_idx, ex in exhibits:
        num = ex.get("number", "?")
        p = f"$.report.sections[{sec_idx}].blocks[exhibit {num}]"
        numbers_seen.append(num)
        for key in ("title", "scope", "evidence_status", "chart", "readout", "source_foot", "drawer", "data_table", "definitions"):
            if key not in ex:
                ex_issues.append(Issue("EX-01", p, f"missing seven-piece key {key!r}", "七件套缺一 = FAIL_BUILD"))
        title = text_of(ex.get("title"))
        if len(title) < 20:
            ex_issues.append(Issue("EX-02", p + ".title", f"exhibit title is {len(title)} chars; needs >= 20"))
        if not re.search(r"\d", title):
            ex_issues.append(Issue("EX-03", p + ".title", "exhibit title must contain a number and a denominator/range"))
        scope = ex.get("scope", "")
        if len(scope) < 8 or scope.strip() in {"全部数据", "所有数据"}:
            ex_issues.append(Issue("EX-04", p + ".scope", "scope must name unit, N, and frame/method"))
        st = ex.get("evidence_status", {})
        st_status = st.get("status")
        if st_status not in C.GRADES:
            ex_issues.append(Issue("EX-05", p + ".evidence_status.status", f"invalid status {st_status!r}"))
        else:
            badge = st.get("badge", "")
            if not badge.upper().startswith(C.STATUS_LABEL[st_status].upper() + " ·"):
                ex_issues.append(Issue("EX-06", p + ".evidence_status.badge", f"badge must be '{C.STATUS_LABEL[st_status]} · SCOPE', got {badge!r}"))
        chart = ex.get("chart", {})
        ctype = chart.get("type")
        if ctype not in C.CHART_TYPES:
            ex_issues.append(Issue("EX-07", p + ".chart.type", f"unknown chart type {ctype!r}"))
        if chart.get("unit") not in C.UNITS:
            ex_issues.append(Issue("EX-08", p + ".chart.unit", f"invalid unit {chart.get('unit')!r}"))
        if chart.get("encoding") not in C.ENCODINGS:
            ex_issues.append(Issue("EX-09", p + ".chart.encoding", f"invalid encoding {chart.get('encoding')!r}"))
        if not chart.get("basis") or len(chart.get("basis", "")) < 8:
            ex_issues.append(Issue("EX-10", p + ".chart.basis", "chart basis must name denominator/source"))
        if not chart.get("frame_scope"):
            ex_issues.append(Issue("EX-11", p + ".chart.frame_scope", "frame_scope needs at least one frame"))
        if not chart.get("notes"):
            ex_issues.append(Issue("EX-12", p + ".chart.notes", "at least one misread boundary note is required"))
        if chart.get("encoding") in {"share_with_denominator", "percent"}:
            den = chart.get("denominator")
            if not isinstance(den, int) or den <= 0:
                ex_issues.append(Issue("AP-04", p + ".chart.denominator", "share/percent requires a positive denominator"))
            if len(chart.get("frame_scope", [])) > 1:
                ex_issues.append(Issue("AP-05", p + ".chart.frame_scope", "cross-frame percentage comparison is banned"))
        if ctype == "coverage_bars":
            basis = chart.get("basis", "")
            if not (("覆盖" in basis or "coverage" in basis.lower()) and ("不是漏斗" in basis or "not funnel" in basis.lower())):
                ex_issues.append(Issue("AP-06", p + ".chart.basis", "coverage_bars basis must say coverage, not funnel/覆盖，不是漏斗"))
        ex_issues.extend(readout_issues(ex.get("readout"), p + ".readout"))
        ex_issues.extend(source_foot_issues(ex.get("source_foot"), p + ".source_foot"))
        drawer = ex.get("drawer", {})
        if not drawer.get("summary") or not drawer.get("content"):
            ex_issues.append(Issue("EX-13", p + ".drawer", "drawer summary and content must both be non-empty"))
        if not ex.get("definitions"):
            ex_issues.append(Issue("EX-14", p + ".definitions", "at least one definition is required"))
    expected = 10 if mode != "progress_snapshot" else 1
    if len(exhibits) < expected:
        ex_issues.append(Issue("AP-23", "$.report.sections", f"progress snapshot needs >= {expected} exhibit, got {len(exhibits)}"))
    if len(numbers_seen) != len(set(numbers_seen)):
        ex_issues.append(Issue("EX-15", "$.report.sections", f"duplicate exhibit numbers: {numbers_seen}"))
    suite.add("EX", "exhibits implement the seven-piece shell", ex_issues)

    # Gap blocks -----------------------------------------------------------
    gap_issues = []
    for s in sections:
        for b in s.get("blocks", []):
            if b.get("type") != "gap":
                continue
            p = f"$.report.sections[{s.get('index')}].gap"
            if not b.get("reason"):
                gap_issues.append(Issue("GAP-01", p + ".reason", "gap reason is required"))
            gap_issues.extend(readout_issues(b.get("readout"), p + ".readout"))
            gap_issues.extend(source_foot_issues(b.get("source_foot"), p + ".source_foot"))
    suite.add("GAP", "gap blocks carry four questions and four keys", gap_issues)

    # Status legend --------------------------------------------------------
    legend_issues = []
    legends = [b for s in sections for b in s.get("blocks", []) if b.get("type") == "status_legend"]
    if len(legends) != 1:
        legend_issues.append(Issue("LEG-01", "$.report.sections", f"exactly one status_legend block is required, got {len(legends)}"))
    for legend in legends:
        statuses = [x.get("status") for x in legend.get("statuses", [])]
        if statuses != C.STATUS_ORDER:
            legend_issues.append(Issue("LEG-02", "$.status_legend.statuses", f"must be the six statuses in order, got {statuses}"))
    suite.add("LEG", "six-level evidence legend is complete", legend_issues)

    # Prohibited outputs ---------------------------------------------------
    po_issues = []
    pos = report.get("prohibited_outputs", [])
    if not pos:
        po_issues.append(Issue("PO-01", "$.report.prohibited_outputs", "at least one prohibited output is required"))
    ids = [p.get("id") for p in pos]
    if len(ids) != len(set(ids)):
        po_issues.append(Issue("PO-02", "$.report.prohibited_outputs", "duplicate prohibited output ids"))
    joined = " ".join(f"{p.get('label','')} {p.get('reason','')}" for p in pos)
    categories = {
        "总体情绪率/满意率": ("总体情绪", "满意率", "情绪率"),
        "饼图百分比": ("饼图", "百分比"),
        "NPS": ("NPS", "净推荐"),
        "ROI 排名": ("ROI", "排名"),
        "净值打分": ("净值",),
        "覆盖当漏斗": ("漏斗", "覆盖"),
        "百分比跨 frame": ("跨 frame", "跨frame", "跨镜头"),
    }
    for name, kws in categories.items():
        if not any(k.lower() in joined.lower() for k in kws):
            po_issues.append(Issue("PO-03", "$.report.prohibited_outputs", f"missing ban category: {name}"))
    suite.add("PO", "prohibited outputs cover all seven anti-patterns", po_issues)

    # Unknowns -------------------------------------------------------------
    unk_issues = []
    for i, u in enumerate(report.get("unknowns", [])):
        if not (u.startswith("[Evidence gap]") or u.startswith("[BLOCKED: ")):
            unk_issues.append(Issue("UNK-01", f"$.report.unknowns[{i}]", f"unknown must start with [Evidence gap] or [BLOCKED: , got {u[:30]!r}"))
    suite.add("UNK", "unknowns are explicit", unk_issues)

    # Gate / metric rows fail-closed --------------------------------------
    gate_issues = []
    metric_rows = evidence.get("corpus", {}).get("metric_rows", {}).get("value", 0)
    if metric_rows and g7 != "PASS":
        gate_issues.append(Issue("INV-26", "$.evidence.corpus.metric_rows", f"metric_rows={metric_rows} while G7={g7}"))
    if mode != "progress_snapshot" and g7 != "PASS":
        gate_issues.append(Issue("INV-25", "$.evidence.gate.gates", f"report_mode={mode} requires G7=PASS, got {g7}"))
    for c in claims:
        if c.get("grade") == "blocked":
            gi = c.get("grade_inputs", {})
            if not gi.get("required_gate") or gi.get("gate_status") == "PASS":
                gate_issues.append(Issue("AP-16", f"$.report.claims[{c.get('claim_id')}]", "blocked claim needs required_gate with non-PASS status"))
    suite.add("GATE", "gate and metric rows fail closed", gate_issues)

    # Anti-patterns --------------------------------------------------------
    suite.add("AP", "anti-pattern scan", anti_pattern_issues(data))

    # Numeric invariants ---------------------------------------------------
    suite.add("INV", "count and matrix invariants", invariant_issues(data))

    # Artifacts and source paths ------------------------------------------
    suite.add("ART", "artifacts are relative and hashed", artifact_issues(data))

    return suite


def readout_issues(readout, path: str) -> list[Issue]:
    issues: list[Issue] = []
    if not isinstance(readout, dict):
        return [Issue("RO-01", path, "readout must be an object with four keys")]
    for key, minlen in (("observed", 8), ("interpretation", 12), ("counterevidence", 12), ("decision_implication", 12)):
        txt = text_of(readout.get(key))
        if not txt.strip():
            issues.append(Issue("RO-02", f"{path}.{key}", "missing four-question column", "缺栏必须渲染 EVIDENCE INCOMPLETE，构建失败"))
        elif len(txt) < minlen:
            issues.append(Issue("RO-02", f"{path}.{key}", f"text is {len(txt)} chars; needs >= {minlen}"))
    obs = text_of(readout.get("observed"))
    interp = text_of(readout.get("interpretation"))
    if obs and obs == interp:
        issues.append(Issue("RO-03", path + ".interpretation", "interpretation must not repeat observed"))
    ce = text_of(readout.get("counterevidence"))
    if ce and not (any(x in ce for x in ("如果", "若", "除非", "一旦")) or "没有找到反证" in ce):
        issues.append(Issue("RO-04", path + ".counterevidence", "must state what would overturn it"))
    di = text_of(readout.get("decision_implication"))
    if di and not di.startswith(ACTION_VERBS):
        issues.append(Issue("RO-05", path + ".decision_implication", f"must start with an action verb, got {di[:12]!r}"))
    return issues


def source_foot_issues(sf, path: str) -> list[Issue]:
    issues: list[Issue] = []
    if not isinstance(sf, dict):
        return [Issue("SF-01", path, "source_foot must be an object with four keys")]
    for key in ("basis", "unit", "limit", "status"):
        val = sf.get(key)
        if not isinstance(val, str) or not val.strip():
            issues.append(Issue("SF-02", f"{path}.{key}", f"missing source-foot key {key!r}", "四键缺一 = FAIL_BUILD"))
    limit = str(sf.get("limit", ""))
    if limit.strip() in {"仅供参考", "数据有限", "样本较小", "暂无数据"}:
        issues.append(Issue("SF-03", path + ".limit", f"empty limitation phrase {limit!r} is banned"))
    return issues


def grade_is_consistent(grade: str, gi: dict) -> tuple[bool, str]:
    if grade == "confirmed":
        if gi.get("is_direct_fact") is not True:
            return False, "is_direct_fact must be true"
        if not re.fullmatch(r"[0-9a-f]{64}", str(gi.get("artifact_sha256", ""))):
            return False, "artifact_sha256 must be 64 hex chars"
        if gi.get("exact_identity") is not True:
            return False, "exact_identity must be true"
        if gi.get("inference") is not False:
            return False, "inference must be false"
        return True, ""
    if grade == "directional":
        n = gi.get("n_independent", 0)
        a = gi.get("n_authors", 0)
        share = gi.get("direction_share", 0)
        if n >= 8 and a >= 2 and share >= 0.70 and gi.get("single_coded") is True:
            return True, ""
        return False, "needs n_independent>=8, n_authors>=2, direction_share>=0.70, single_coded=true"
    if grade == "hypothesis":
        n = gi.get("n_independent", 0)
        a = gi.get("n_authors", 0)
        share = gi.get("direction_share", 0)
        if (3 <= n < 8) or (0.55 <= share < 0.70) or a == 1:
            return True, ""
        return False, "needs 3<=n<8, or 0.55<=share<0.70, or n_authors==1"
    if grade == "blocked":
        if gi.get("required_gate") and gi.get("gate_status") != "PASS":
            return True, ""
        return False, "needs required_gate with non-PASS gate_status"
    if grade == "not_authorized":
        if gi.get("topic") in {"medical_efficacy", "safety", "causality", "diagnosis"}:
            return True, ""
        return False, "topic must be medical_efficacy/safety/causality/diagnosis"
    if grade == "evidence_gap":
        if gi.get("required_cell_count") == 0 or gi.get("required_field_missing_rate") == 1.0:
            return True, ""
        return False, "needs required_cell_count==0 or required_field_missing_rate==1.0"
    return False, "unknown grade"


def anti_pattern_issues(data: dict) -> list[Issue]:
    issues: list[Issue] = []
    report = data.get("report", {})
    # 1. banned terms, skipping prohibited_outputs.
    scan = dict(data)
    scan_report = dict(report)
    scan_report.pop("prohibited_outputs", None)
    scan["report"] = scan_report
    for path, s in strings(scan):
        for term in C.BANNED_TERMS:
            start = 0
            while True:
                idx = s.find(term, start)
                if idx < 0:
                    break
                start = idx + len(term)
                window = s[max(0, idx - 24): idx + len(term) + 24]
                if any(term == allowed and re.search(pat, window) for pat, allowed in C.NEGATION_ALLOW):
                    continue
                issues.append(Issue("AP-01", path, f"banned term {term!r} in: {s[max(0, idx-20):idx+len(term)+20]!r}",
                                    "禁用词只能出现在 prohibited_outputs，或显式否定句式中"))
    # 2. chart structural anti-patterns.
    for path, v in walk(data):
        if not isinstance(v, dict):
            continue
        if v.get("type") in {"pie", "donut", "doughnut"}:
            issues.append(Issue("AP-02", path + ".type", "pie/donut charts are banned"))
        mid = str(v.get("metric_id", ""))
        if mid and C.NET_SCORE_PATTERN.search(mid):
            issues.append(Issue("AP-03", path + ".metric_id", f"net-score metric id {mid!r} is banned"))
        for key in ("denominator", "sample_n", "n"):
            if key in v and isinstance(v[key], (int, float)) and v.get("mapping_confidence") == v[key]:
                issues.append(Issue("AP-08", path + "." + key, "mapping_confidence is not a sample size"))
    # 3. mixed matrix sum
    mixed = data.get("evidence", {}).get("mixed")
    if mixed:
        total = sum(int(x) for row in mixed.get("matrix", {}).values() for x in row.values())
        expected = mixed.get("mixed_records", {}).get("value")
        if total != expected:
            issues.append(Issue("AP-09", "$.evidence.mixed.matrix", f"matrix cells sum to {total}, mixed_records={expected}"))
    # 4. entry metric ids
    for path, s in strings(data):
        if C.NET_SCORE_PATTERN.search(s) and any(x in path for x in ("metric_id", "name")):
            issues.append(Issue("AP-03", path, f"net-score name {s!r} is banned"))
    return issues


def invariant_issues(data: dict) -> list[Issue]:
    issues: list[Issue] = []
    ev = data.get("evidence", {})
    corpus = ev.get("corpus", {})
    cov = ev.get("coverage", {})

    # reconciliation
    for i, r in enumerate(corpus.get("reconciliation", [])):
        reasons = r.get("reasons", {})
        if sum(int(v) for v in reasons.values()) != r.get("deducted"):
            issues.append(Issue("INV-01", f"$.evidence.corpus.reconciliation[{i}]", "sum(reasons) != deducted"))
        if r.get("input_count", 0) - r.get("deducted", 0) != r.get("output_count"):
            issues.append(Issue("INV-02", f"$.evidence.corpus.reconciliation[{i}]", "input - deducted != output"))
    ro = corpus.get("raw_objects", {}).get("value", 0)
    oc = corpus.get("occurrences", {}).get("value", 0)
    cr = corpus.get("canonical_records", {}).get("value", 0)
    fm = corpus.get("frame_memberships", {}).get("value", 0)
    if not (cr <= oc <= ro):
        issues.append(Issue("INV-03", "$.evidence.corpus", f"canonical {cr} <= occurrences {oc} <= raw {ro} fails"))
    if fm < cr:
        issues.append(Issue("INV-04", "$.evidence.corpus", f"frame_memberships {fm} < canonical {cr}"))

    # aspect sums
    aspect_total = cov.get("aspect_annotation_count", {}).get("value")
    for key in ("aspect_code_counts", "aspect_polarity_counts"):
        m = cov.get(key, {})
        if m:
            s = sum(int(v.get("value", 0)) for v in m.values())
            if aspect_total is not None and s != aspect_total:
                issues.append(Issue("INV-05", f"$.evidence.coverage.{key}", f"{key} sums to {s}, aspect_annotation_count={aspect_total}"))
    # expectation gap partition
    eg = ev.get("journey", {}).get("expectation_gap_counts") if ev.get("journey") else None
    if eg:
        s = sum(int(v.get("value", 0)) for v in eg.values())
        if s != cov.get("independent_content_units", {}).get("value"):
            issues.append(Issue("INV-08", "$.evidence.journey.expectation_gap_counts", f"sum {s} != independent_content_units"))
    # variants
    variants = ev.get("variants")
    if variants and variants.get("items"):
        identity = ev.get("identity", {})
        if len(variants["items"]) != identity.get("family_children"):
            issues.append(Issue("INV-10", "$.evidence.variants.items", f"{len(variants['items'])} items != family_children {identity.get('family_children')}"))
        targets = [v for v in variants["items"] if v.get("is_target")]
        if len(targets) != 1:
            issues.append(Issue("INV-11", "$.evidence.variants.items", f"{len(targets)} targets; exactly 1 required"))
        elif variants.get("target_key") != targets[0].get("variant_key"):
            issues.append(Issue("AP-13", "$.evidence.variants.target_key", "target_key does not match the unique is_target item"))
    # taxonomy codes
    tax = ev.get("taxonomy", {})
    if tax.get("code_count") != len(tax.get("codes", [])):
        issues.append(Issue("INV-07", "$.evidence.taxonomy.code_count", "code_count != len(codes)"))
    known_codes = {c.get("code") for c in tax.get("codes", [])}
    for i, ka in enumerate(ev.get("key_aspects") or []):
        if ka.get("code") not in known_codes:
            issues.append(Issue("INV-13", f"$.evidence.key_aspects[{i}].code", f"unknown taxonomy code {ka.get('code')!r}"))
    # key_aspects count
    kas = ev.get("key_aspects")
    if kas is not None and len(kas) != 12:
        issues.append(Issue("INV-13B", "$.evidence.key_aspects", f"key_aspects must contain 12 items, got {len(kas)}"))
    # cluster lenses
    lenses = ev.get("cluster_lenses")
    if lenses is not None:
        ids = [x.get("id") for x in lenses]
        if len(ids) != 3 or set(ids) != {"natural", "diagnostic", "qualitative_seed"}:
            issues.append(Issue("INV-14", "$.evidence.cluster_lenses", f"three lenses required, got {ids}"))
    # need states
    needs = ev.get("need_states")
    if needs is not None:
        ids = [x.get("id") for x in needs]
        if len(ids) != 4 or len(set(ids)) != 4:
            issues.append(Issue("INV-15", "$.evidence.need_states", f"four unique need states required, got {ids}"))
        for i, n in enumerate(needs):
            if not re.match(r"^Q[1-4] · ", n.get("quadrant", "")):
                issues.append(Issue("INV-15", f"$.evidence.need_states[{i}].quadrant", "quadrant must match ^Q[1-4] · "))
    # claim maturity
    cm = report_maturity = data.get("report", {}).get("claim_maturity") or []
    claims = data.get("report", {}).get("claims", [])
    if cm:
        if len(cm) != len(claims):
            issues.append(Issue("INV-16B", "$.report.claim_maturity", f"{len(cm)} rows != {len(claims)} claims"))
        by_id = {c.get("claim_id"): c for c in claims}
        for i, row in enumerate(cm):
            c = by_id.get(row.get("claim_id"))
            if not c or row.get("status") != c.get("grade"):
                issues.append(Issue("INV-16B", f"$.report.claim_maturity[{i}]", "status must equal claim grade"))
    return issues


def artifact_issues(data: dict) -> list[Issue]:
    issues: list[Issue] = []
    artifacts = {a.get("path"): a for a in data.get("artifacts", [])}
    for i, a in enumerate(data.get("artifacts", [])):
        p = a.get("path", "")
        if p.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", p) or ".." in Path(p).parts:
            issues.append(Issue("ART-01", f"$.artifacts[{i}].path", f"artifact path must be run-relative: {p!r}"))
        if not re.fullmatch(r"[0-9a-f]{64}", str(a.get("sha256", ""))):
            issues.append(Issue("ART-02", f"$.artifacts[{i}].sha256", "sha256 must be 64 lower-case hex"))
    # every source_path file should be present in artifacts
    for path, s in strings(data):
        if "#" not in s:
            continue
        head = s.split("#", 1)[0]
        if head.endswith((".json", ".jsonl", ".csv")) and "/" not in head:
            if head not in artifacts:
                issues.append(Issue("ART-03", path, f"source_path references {head!r}, which is not in artifacts",
                                    "被引用的 artifact 必须带 sha256"))
    gate_shas = data.get("evidence", {}).get("gate", {}).get("artifact_sha256", {})
    for p, sha in gate_shas.items():
        if p not in artifacts:
            issues.append(Issue("ART-04", "$.evidence.gate.artifact_sha256", f"gate references unknown artifact {p!r}"))
        elif artifacts[p].get("sha256") != sha:
            issues.append(Issue("ART-04", "$.evidence.gate.artifact_sha256", f"sha mismatch for {p!r}"))
    return issues


# ---------------------------------------------------------------------------
# HTML validation
# ---------------------------------------------------------------------------
EXTERNAL_PATTERNS = [
    (r"<link\b", "<link>"),
    (r"<script\b[^>]*\bsrc\s*=", "<script src>"),
    (r"@import\b", "@import"),
    (r"@font-face\b", "@font-face"),
    (r"url\s*\(", "url()"),
    (r"https?://", "http(s) URL"),
    (r"<img\b", "<img>"),
    (r"<iframe\b", "<iframe>"),
    (r"<canvas\b", "<canvas>"),
    (r"<svg\b", "<svg>"),
]


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s)


def figure_blocks(html: str) -> list[str]:
    """Return every figure.exhibit block, including the opening tag."""
    out = []
    for m in re.finditer(r'<figure\b[^>]*class="[^"]*\bexhibit\b[^"]*"[^>]*>', html):
        start = m.start()
        depth = 0
        for t in re.finditer(r"</?figure\b[^>]*>", html[start:]):
            depth += -1 if t.group(0).startswith("</") else 1
            if depth == 0:
                out.append(html[start:start + t.end()])
                break
    return out


def section_blocks(html: str) -> list[str]:
    out = []
    for m in re.finditer(r'<section\b[^>]*class="[^"]*\breport-section\b[^"]*"[^>]*>', html):
        start = m.end()
        depth = 1
        for t in re.finditer(r"</?section\b[^>]*>", html[start:]):
            depth += -1 if t.group(0).startswith("</") else 1
            if depth == 0:
                out.append(html[start:start + t.start()])
                break
    return out


def claim_blocks(html: str) -> list[str]:
    out = []
    for m in re.finditer(r'<article\b[^>]*class="[^"]*\bclaim\b[^"]*"[^>]*>', html):
        start = m.end()
        depth = 1
        for t in re.finditer(r"</?article\b[^>]*>", html[start:]):
            depth += -1 if t.group(0).startswith("</") else 1
            if depth == 0:
                out.append(html[start:start + t.start()])
                break
    return out


def validate_html(html: str, data: dict | None = None) -> Suite:
    suite = Suite()
    report = (data or {}).get("report", {})
    claims = report.get("claims", [])
    rendered_sections = [s for s in report.get("sections", [])]
    expected_exhibits = [b for s in rendered_sections for b in s.get("blocks", []) if b.get("type") == "exhibit"]

    # External resources ---------------------------------------------------
    issues = []
    for pat, label in EXTERNAL_PATTERNS:
        if re.search(pat, html, re.I):
            issues.append(Issue("V-10", "$", f"external resource pattern found: {label}"))
    if re.search(r"\bon(?:click|load|error|change|input|submit)\s*=", html, re.I):
        issues.append(Issue("V-19", "$", "inline event handler found"))
    suite.add("V-10", "zero external resources and zero inline events", issues)

    # Tokens / paths -------------------------------------------------------
    issues = []
    tokens = re.findall(r"\{\{[A-Za-z0-9_]+\}\}", html)
    if tokens:
        issues.append(Issue("V-11", "$", f"{len(tokens)} unresolved tokens: {tokens[:5]}"))
    for abs_path in ("/Users/", "/opt/", "C:\\"):
        if abs_path in html:
            issues.append(Issue("V-20B", "$", f"absolute path leaked: {abs_path}"))
    suite.add("V-11", "no unresolved tokens or absolute paths", issues)

    # h1 / sections / h2 ---------------------------------------------------
    issues = []
    h1 = re.findall(r"<h1\b[^>]*>(.*?)</h1>", html, re.S)
    if len(h1) != 1:
        issues.append(Issue("V-01", "$", f"expected exactly 1 h1, got {len(h1)}"))
    secs = section_blocks(html)
    if len(secs) != len(rendered_sections):
        issues.append(Issue("V-02", "$", f"rendered {len(secs)} report sections; data has {len(rendered_sections)}"))
    h2s = re.findall(r'<div class="section-head">.*?<h2\b[^>]*>(.*?)</h2>', html, re.S)
    if len(h2s) != len(rendered_sections):
        issues.append(Issue("V-02", "$", f"section h2 count {len(h2s)} != {len(rendered_sections)}"))
    for i, s in enumerate(rendered_sections):
        anchor = f'id="{s.get("id")}"'
        if anchor not in html:
            issues.append(Issue("V-13", "$", f"missing section anchor {anchor}"))
    suite.add("V-02", "one h1 and one h2 per rendered section", issues)

    # Exhibits -------------------------------------------------------------
    issues = []
    figs = figure_blocks(html)
    if len(figs) != len(expected_exhibits):
        issues.append(Issue("V-03", "$", f"figure.exhibit count {len(figs)} != expected {len(expected_exhibits)}"))
    parts = ["exhibit-head", "exhibit-scope", "evidence-badge", "exhibit-body",
             "exhibit-readout", "source-foot", "evidence-drawer"]
    for i, fig in enumerate(figs, 1):
        for part in parts:
            if part not in fig:
                issues.append(Issue("V-04", f"exhibit {i}", f"missing part {part!r}"))
        n_readouts = len(re.findall(r'class="[^"]*\breadout-item\b', fig))
        if n_readouts != 4:
            issues.append(Issue("V-05", f"exhibit {i}", f"expected 4 readout items, got {n_readouts}"))
        sf = re.search(r'<div class="source-foot">(.*?)</div>', fig, re.S)
        if not sf:
            issues.append(Issue("V-06", f"exhibit {i}", "missing source-foot"))
        else:
            keys = set(re.findall(r"<b>(.*?)</b>", sf.group(1)))
            missing = {"Basis", "Unit", "Limit", "Status"} - keys
            if missing:
                issues.append(Issue("V-06", f"exhibit {i}", f"source-foot missing keys {sorted(missing)}"))
        if not re.search(r'<details class="evidence-drawer"', fig):
            issues.append(Issue("V-07", f"exhibit {i}", "missing evidence-drawer details"))
        for attr in ("data-basis", "data-unit", "data-limit", "data-status"):
            m = re.search(attr + r'="([^"]*)"', fig)
            if not m or not m.group(1).strip() or m.group(1).strip().upper() == "UNKNOWN":
                issues.append(Issue("V-15", f"exhibit {i}", f"{attr} must be non-empty"))
    suite.add("V-03", "exhibits are complete and numbered", issues)

    # Claims ---------------------------------------------------------------
    issues = []
    cards = claim_blocks(html)
    if len(cards) < len(claims):
        issues.append(Issue("V-05B", "$", f"claim cards {len(cards)} < claims {len(claims)}"))
    for i, card in enumerate(cards, 1):
        n = len(re.findall(r'class="[^"]*\breadout-item\b', card))
        if n != 4:
            issues.append(Issue("V-05B", f"claim {i}", f"expected 4 readout items, got {n}"))
        if "EVIDENCE INCOMPLETE" in card:
            issues.append(Issue("V-05B", f"claim {i}", "rendered EVIDENCE INCOMPLETE placeholder"))
    suite.add("V-05B", "claims carry four-question readouts", issues)

    # Charts ---------------------------------------------------------------
    issues = []
    charts = re.findall(r'<div class="chart"\b[^>]*>', html)
    metas = re.findall(r'<div class="chart-meta">(.*?)</div>', html, re.S)
    if len(metas) < len(charts):
        issues.append(Issue("V-16B", "$", f"{len(charts)} charts but {len(metas)} chart-meta rows"))
    for i, meta in enumerate(metas, 1):
        if len(re.findall(r'class="chart-meta-item', meta)) != 4:
            issues.append(Issue("V-16B", f"chart {i}", "chart-meta must have 4 items"))
    for i, ch in enumerate(charts, 1):
        if "aria-label" not in ch:
            issues.append(Issue("V-16", f"chart {i}", "chart is missing aria-label"))
        if 'data-chart-type' not in ch:
            issues.append(Issue("V-16", f"chart {i}", "chart is missing data-chart-type"))
    suite.add("V-16", "charts carry role, aria-label, and four basis rows", issues)

    # Legend / prohibited / order -----------------------------------------
    issues = []
    for status in C.STATUS_ORDER:
        if C.STATUS_LABEL[status] not in html:
            issues.append(Issue("V-08", "$", f"status legend missing {status}"))
    # prohibited block must be the last <section> before footer
    footer_pos = html.find('<footer class="report-footer"')
    if footer_pos < 0:
        issues.append(Issue("V-09", "$", "missing report footer"))
    else:
        before = html[:footer_pos]
        last_section = before.rfind("<section")
        if last_section < 0 or "prohibited-block" not in before[last_section:last_section + 200]:
            issues.append(Issue("V-09", "$", "prohibited_outputs is not the last substantive block before the footer"))
    suite.add("V-08", "six-level legend and prohibited block position", issues)

    # Print / tabular ------------------------------------------------------
    issues = []
    if "details>div" not in html and "details > div" not in html:
        issues.append(Issue("V-18", "$", "print CSS does not force details content visible"))
    if "tabular-nums" not in html:
        issues.append(Issue("V-20", "$", "numeric styling (tabular-nums) is missing"))
    suite.add("V-18", "print and numeric rules are present", issues)

    # Variant order (single DOM) ------------------------------------------
    issues = []
    variant_keys = re.findall(r'data-variant-key="([^"]+)"', html)
    if variant_keys:
        variants = (data or {}).get("evidence", {}).get("variants", {}) or {}
        expected = [v.get("variant_key") for v in variants.get("items", [])]
        if variant_keys != expected:
            issues.append(Issue("V-17", "$", "variant grid order differs from the data order"))
    suite.add("V-17", "variant grid uses one stable DOM order", issues)

    # Banned words in rendered text (excluding prohibited block) ----------
    issues = []
    scrub = html
    m = re.search(r'<section\b[^>]*class="[^"]*\bprohibited-block\b[^"]*"[^>]*>', scrub)
    if m:
        start = m.start()
        end = scrub.find("</section>", start)
        if end > start:
            scrub = scrub[:start] + scrub[end + len("</section>"):]
    text = strip_tags(scrub)
    for term in C.BANNED_TERMS:
        if term in text:
            # negation-aware exception
            ok = any(term == allowed and re.search(pat, text) for pat, allowed in C.NEGATION_ALLOW)
            if not ok:
                issues.append(Issue("V-12", "$", f"banned term {term!r} in rendered text"))
    suite.add("V-12", "no banned terms outside prohibited block", issues)

    return suite


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fail-closed validator for VOC report data / HTML")
    ap.add_argument("--data", help="path to report-data.json")
    ap.add_argument("--html", help="path to report.html")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = ap.parse_args(argv)

    if not args.data and not args.html:
        ap.error("provide --data and/or --html")

    rc = 0
    payload = {}
    if args.data:
        data = json.loads(Path(args.data).read_text(encoding="utf-8"))
        suite = validate_data(data)
        payload["data"] = suite.as_dict()
        if not args.json:
            suite.print_human(f"DATA {args.data}")
        rc = 0 if suite.passed else 1
    if args.html:
        html = Path(args.html).read_text(encoding="utf-8")
        data = json.loads(Path(args.data).read_text(encoding="utf-8")) if args.data else None
        suite = validate_html(html, data)
        payload["html"] = suite.as_dict()
        payload["html_sha256"] = hashlib.sha256(html.encode("utf-8")).hexdigest()
        payload["html_bytes"] = len(html.encode("utf-8"))
        if not args.json:
            suite.print_human(f"HTML {args.html}")
        rc = 1 if (rc or not suite.passed) else 0
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())
