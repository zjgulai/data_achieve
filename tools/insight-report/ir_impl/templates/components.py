#!/usr/bin/env python3
"""Shared HTML components for the report templates.

All text is HTML-escaped here. Templates never interpolate raw data directly.
Missing four-question columns render a red `EVIDENCE INCOMPLETE` placeholder;
the validator rejects such data before a build can write a final report.
"""
from __future__ import annotations

import html
from typing import Any

import ir_contract as C


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text", ""))
    return "" if value is None else str(value)


def provenance_note(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    refs = value.get("data_refs") or []
    author = value.get("authored_by", "")
    bits = []
    if author:
        bits.append(f"authored_by={author}")
    if value.get("claim_id"):
        bits.append(f"claim={value['claim_id']}")
    if refs:
        bits.append("refs=" + ", ".join(str(r) for r in refs[:3]))
    return f'<small class="provenance">{" · ".join(bits)}</small>' if bits else ""


def split_accent(title: str, accent: str) -> str:
    """Escape title and wrap the first accent occurrence in <strong>."""
    safe = esc(title)
    safe_accent = esc(accent)
    if not accent or safe.count(safe_accent) != 1:
        return safe
    return safe.replace(safe_accent, f'<strong class="accent">{safe_accent}</strong>', 1)


def section_head(spec: dict, title: Any, deck: Any = None) -> str:
    index = spec["index"]
    kicker = spec["kicker"]
    zh = spec["zh"]
    deck_html = f'<p class="section-deck">{esc(text(deck))}</p>' if text(deck) else ""
    return (
        '<div class="section-head">'
        f'<div class="section-index">{index} / {kicker} · {zh}</div>'
        f"<h2>{esc(text(title))}</h2>"
        f"{deck_html}"
        "</div>"
    )


def section_shell(spec: dict, title: Any, deck: Any, body: str, status: str = "ok") -> str:
    return (
        f'<section id="{spec["id"]}" class="report-section" data-section="{spec["index"]}" '
        f'data-section-status="{esc(status)}">'
        f'<div class="shell">{section_head(spec, title, deck)}{body}</div></section>'
    )


def badge(status_obj: dict) -> str:
    if not isinstance(status_obj, dict) or status_obj.get("status") not in C.STATUS_LABEL:
        return '<div class="evidence-badge gap">EVIDENCE INCOMPLETE · NO STATUS</div>'
    status = status_obj["status"]
    label = C.STATUS_LABEL[status]
    scope = str(status_obj.get("badge", "")).split("·", 1)[-1].strip() if "·" in str(status_obj.get("badge", "")) else "UNKNOWN"
    badge_text = str(status_obj.get("badge") or f"{label} · {scope}")
    return f'<div class="evidence-badge {C.STATUS_CLASS[status]}">{esc(badge_text)}</div>'


READOUT_LABELS = [
    ("observed", "Observed"),
    ("interpretation", "Interpretation"),
    ("counterevidence", "Counterevidence"),
    ("decision_implication", "Decision implication"),
]


def readout(obj: dict, block_label: str = "") -> str:
    items = []
    for key, label in READOUT_LABELS:
        value = text(obj.get(key)) if isinstance(obj, dict) else ""
        if value.strip():
            items.append(f'<div class="readout-item"><b>{label}</b><p>{esc(value)}</p></div>')
        else:
            items.append(
                f'<div class="readout-item readout-incomplete"><b>{label}</b>'
                f'<p class="evidence-incomplete">EVIDENCE INCOMPLETE · {esc(block_label)} 缺 {key}</p></div>'
            )
    return '<div class="exhibit-readout">' + "".join(items) + "</div>"


def source_foot(obj: dict) -> str:
    rows = []
    for label, key in (("Basis", "basis"), ("Unit", "unit"), ("Limit", "limit"), ("Status", "status")):
        value = obj.get(key) if isinstance(obj, dict) else None
        if value is None or not str(value).strip():
            rows.append(f'<span class="source-missing"><b>{label}</b> <em>UNKNOWN</em></span>')
        else:
            rows.append(f'<span><b>{label}</b> {esc(value)}</span>')
    extra = []
    if isinstance(obj, dict):
        for key in ("scale", "unknown", "rule", "forbidden", "partition", "target", "confidence"):
            if obj.get(key):
                extra.append(f'<span class="source-extra"><b>{esc(key)}</b> {esc(obj[key])}</span>')
    return '<div class="source-foot">' + "".join(rows + extra) + "</div>"


def data_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    body = "".join(
        f'<tr><td>{esc(r.get("label", ""))}</td><td class="num">{esc(r.get("value", ""))}</td>'
        f'<td>{esc(r.get("unit", ""))}</td></tr>'
        for r in rows
    )
    return (
        '<div class="table-wrap"><table class="data-table"><caption>数据表</caption>'
        '<thead><tr><th>label</th><th>value</th><th>unit</th></tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def definitions(items: list[str]) -> str:
    if not items:
        return ""
    return '<ul class="exhibit-definitions">' + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>"


def drawer(obj: dict) -> str:
    summary = esc(obj.get("summary") or "查看定义与误读边界")
    content = obj.get("content") or ""
    return f'<details class="evidence-drawer"><summary>{summary}</summary><div>{esc(content)}</div></details>'


def number_table(numbers: list[dict]) -> str:
    if not numbers:
        return ""
    rows = []
    for n in numbers:
        rows.append(
            "<tr>"
            f'<td>{esc(n.get("name"))}</td>'
            f'<td class="num">{esc(n.get("value"))}</td>'
            f'<td>{esc(n.get("unit"))}</td>'
            f'<td>{esc(n.get("basis"))}</td>'
            f'<td class="source-path">{esc(n.get("source_path"))}</td>'
            "</tr>"
        )
    return (
        '<details class="claim-numbers"><summary>查看来源数字（'
        f"{len(numbers)} 条）</summary>"
        '<div class="table-wrap"><table class="data-table"><thead><tr><th>name</th><th>value</th><th>unit</th><th>basis</th><th>source_path</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div></details>'
    )


def claim_card(claim: dict) -> str:
    grade = claim.get("grade", "evidence_gap")
    status = {
        "status": grade,
        "badge": claim.get("status") or f"{C.STATUS_LABEL.get(grade, 'Evidence gap')} · UNKNOWN",
        "reason_code": "CLAIM_GRADE",
        "inputs": claim.get("grade_inputs", {}),
    }
    return (
        f'<article class="claim" data-claim-id="{esc(claim.get("claim_id"))}" data-grade="{esc(grade)}">'
        f'<div class="claim-head"><div class="claim-id">{esc(claim.get("claim_id"))}</div>'
        f'<h3 class="claim-headline">{esc(claim.get("headline"))}</h3>{badge(status)}</div>'
        f"{readout(claim, claim.get('claim_id', 'claim'))}"
        f"{source_foot({'basis': claim.get('basis'), 'unit': claim.get('unit'), 'limit': claim.get('limit'), 'status': claim.get('status')})}"
        f"{number_table(claim.get('numbers', []))}"
        "</article>"
    )


def status_counts(claims: list[dict]) -> dict:
    counts = {s: 0 for s in C.STATUS_ORDER}
    for c in claims:
        g = c.get("grade")
        if g in counts:
            counts[g] += 1
    return counts


def evidence_band(claims: list[dict]) -> str:
    counts = status_counts(claims)
    cells = "".join(
        f'<div class="band-cell {C.STATUS_CLASS[s]}"><b>{C.STATUS_LABEL[s]}</b>'
        f'<span class="num">{counts[s]}</span><small>{C.STATUS_RULE[s]}</small></div>'
        for s in C.STATUS_ORDER
    )
    return f'<div class="confidence-band" aria-label="结论证据等级分布">{cells}</div>'
