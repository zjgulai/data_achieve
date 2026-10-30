"""Render report-data.json to a single-file, zero-request report.html.

Implements SOP skill ``voc-interactive-report``.  The renderer reads only the
report object passed by build_report.py; it never reads raw payloads or
ref/.  All CSS is inline.  Charts are CSS/HTML only: no SVG, images, canvas,
fonts, scripts or external URLs.

The output keeps the seven-piece exhibit shell required by the render
contract: exhibit-head, exhibit-scope, evidence-badge, exhibit-body,
exhibit-readout, source-foot, evidence-drawer.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from . import contract

STATUS_CLASS = {
    "confirmed": "confirmed",
    "directional": "directional",
    "hypothesis": "hypothesis",
    "evidence_gap": "evidence-gap",
    "blocked": "blocked",
    "not_authorized": "not-authorized",
}

READOUT_LABELS = [
    ("observed", "Observed"),
    ("interpretation", "Interpretation"),
    ("counterevidence", "Counterevidence"),
    ("decision_implication", "Decision implication"),
]


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text", ""))
    return str(value or "")


def _e(value: Any) -> str:
    return contract.escape(value)


def _num(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return _e(value)


def _status_badge(status: dict[str, Any]) -> str:
    grade = status.get("status", "evidence_gap")
    return (
        f'<span class="evidence-badge {STATUS_CLASS.get(grade, "evidence-gap")}">'
        f"{_e(status.get('badge', grade))}</span>"
    )


def _readout_block(readout: dict[str, Any]) -> str:
    items = []
    for key, label in READOUT_LABELS:
        items.append(
            f'<div class="readout-item"><span class="readout-label">{label}</span>'
            f'<p>{_e(_text(readout.get(key, "")))}</p></div>'
        )
    return "".join(items)


def _source_foot(foot: dict[str, Any]) -> str:
    return (
        '<div class="source-foot">'
        f"<span><b>Basis</b> {_e(foot.get('basis', ''))}</span>"
        f"<span><b>Unit</b> {_e(foot.get('unit', ''))}</span>"
        f"<span><b>Limit</b> {_e(foot.get('limit', ''))}</span>"
        f"<span><b>Status</b> {_e(foot.get('status', ''))}</span>"
        "</div>"
    )


def _data_table(rows: Iterable[dict[str, Any]]) -> str:
    rows = list(rows or [])
    if not rows:
        return ""
    keys = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    head = "".join(f"<th>{_e(key)}</th>" for key in keys)
    body = []
    for row in rows:
        cells = []
        for key in keys:
            value = row.get(key)
            if value is None:
                cells.append('<td class="gap-cell">[Evidence gap]</td>')
            else:
                cells.append(f"<td>{_num(value) if isinstance(value, (int, float)) else _e(value)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table class="data-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


# ---------------------------------------------------------------------------
# charts
# ---------------------------------------------------------------------------
def _chart_nested_bar(chart: dict[str, Any]) -> str:
    rows = []
    for item in chart.get("series", []):
        n = item.get("n")
        with_friction = item.get("with_friction")
        if with_friction is None or not n:
            rows.append(
                f'<div class="nb-row"><div class="nb-label">{_e(item.get("label", item.get("group", "")))}</div>'
                f'<div class="nb-track gap-track"><span class="gap-mark">[Evidence gap]</span></div>'
                f'<div class="nb-value num">n={_num(n)}</div></div>'
            )
            continue
        share = round(100.0 * with_friction / n, 1)
        rows.append(
            f'<div class="nb-row"><div class="nb-label">{_e(item.get("label", item.get("group", "")))}</div>'
            f'<div class="nb-track"><span class="nb-fill" style="width:{share}%"></span></div>'
            f'<div class="nb-value num">{_num(with_friction)} / {_num(n)}</div></div>'
        )
    return f'<div class="chart nested-bar" role="img" aria-label="nested bar chart">{ "".join(rows) }</div>'


def _chart_diverging_bar(chart: dict[str, Any]) -> str:
    series = chart.get("series", [])
    axis = chart.get("axis") or {}
    max_value = max(1, int(axis.get("max") or max((max(s.get("positive", 0), s.get("negative", 0)) for s in series), default=1)))
    rows = []
    for item in series:
        positive = int(item.get("positive", 0))
        negative = int(item.get("negative", 0))
        pos_width = round(100.0 * positive / max_value, 1)
        neg_width = round(100.0 * negative / max_value, 1)
        rows.append(
            f'<div class="div-row"><div class="div-label">{_e(item.get("label", item.get("code", "")))}</div>'
            f'<div class="div-neg"><span style="width:{neg_width}%"></span></div>'
            f'<div class="div-pos"><span style="width:{pos_width}%"></span></div>'
            f'<div class="div-values num">+{_num(positive)} / -{_num(negative)}</div></div>'
        )
    return f'<div class="chart diverging" role="img" aria-label="diverging bar chart">{ "".join(rows) }</div>'


def _chart_frame_grid(chart: dict[str, Any]) -> str:
    cards = []
    for lens in chart.get("series", []):
        love = "".join(
            f'<li>{_e(item.get("label", ""))} <span class="num">{_num(item.get("count", 0))}</span></li>'
            for item in lens.get("love", [])
        )
        complaint = "".join(
            f'<li>{_e(item.get("label", ""))} <span class="num">{_num(item.get("count", 0))}</span></li>'
            for item in lens.get("complaint", [])
        )
        cards.append(
            f'<div class="frame-card"><div class="frame-name">{_e(lens.get("name", lens.get("id", "")))}</div>'
            f'<div class="frame-n num">n = {_num(lens.get("n", {}).get("value", 0))}</div>'
            f'<div class="frame-cols"><div><h4>正向</h4><ul>{love or "<li>[Evidence gap]</li>"}</ul></div>'
            f'<div><h4>负向</h4><ul>{complaint or "<li>[Evidence gap]</li>"}</ul></div></div></div>'
        )
    return f'<div class="chart frame-grid" role="img" aria-label="frame grid">{ "".join(cards) }</div>'


def _chart_matrix(chart: dict[str, Any]) -> str:
    matrix = chart.get("matrix") or {}
    families = list(matrix.keys())
    if not families:
        return '<div class="chart matrix">[Evidence gap]</div>'
    head = "<th></th>" + "".join(f"<th>{_e(name)}</th>" for name in families)
    body = []
    for positive in families:
        cells = []
        for negative in families:
            value = int(matrix.get(positive, {}).get(negative, 0))
            level = min(8, value)
            cells.append(f'<td class="heat heat-{level}" data-v="{level}">{_num(value)}</td>')
        body.append(f"<tr><th>{_e(positive)}</th>{''.join(cells)}</tr>")
    return (
        f'<div class="chart matrix" role="img" aria-label="co-occurrence matrix">'
        f'<table class="matrix-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    )


def _chart_quadrant(chart: dict[str, Any]) -> str:
    series = chart.get("series", [])
    order = {"Q2": 0, "Q4": 1, "Q1": 2, "Q3": 3}
    ordered = sorted(series, key=lambda item: order.get(str(item.get("quadrant", ""))[:2], 9))
    cells = []
    for item in ordered:
        cells.append(
            f'<div class="quad-cell"><div class="quad-tag">{_e(item.get("quadrant", ""))}</div>'
            f'<div class="quad-name">{_e(item.get("name", item.get("id", "")))}</div>'
            f'<div class="quad-values num">需求 {_num(item.get("demand", 0))} · 摩擦 {_num(item.get("friction", 0))}</div></div>'
        )
    axes = chart.get("axes") or {}
    return (
        f'<div class="chart quadrant" role="img" aria-label="quadrant 2x2">'
        f'<div class="axis-label axis-x">{_e((axes.get("x") or {}).get("label", ""))}</div>'
        f'<div class="axis-label axis-y">{_e((axes.get("y") or {}).get("label", ""))}</div>'
        f'<div class="quad-grid">{"".join(cells)}</div></div>'
    )


def _chart_coverage_bars(chart: dict[str, Any]) -> str:
    display_max = max(1, int(chart.get("display_max") or 1))
    rows = []
    for item in chart.get("series", []):
        value = int(item.get("value", 0))
        width = round(100.0 * value / display_max, 1)
        rows.append(
            f'<div class="cov-row"><div class="cov-label">{_e(item.get("label", item.get("stage", "")))}</div>'
            f'<div class="cov-track"><span style="width:{width}%"></span></div>'
            f'<div class="cov-value num">{_num(value)}</div></div>'
        )
    return f'<div class="chart coverage" role="img" aria-label="coverage bars">{ "".join(rows) }</div>'


def _chart_variant_grid(chart: dict[str, Any]) -> str:
    rows = []
    for item in chart.get("series", []):
        review = item.get("review_count")
        review_text = '[Evidence gap]' if review is None else _num(review)
        target = " target" if item.get("is_target") else ""
        rows.append(
            f'<tr class="variant-row{target}"><td class="mono">{_e(item.get("variant_key", ""))}</td>'
            f'<td>{_e(item.get("color") or "—")}</td><td>{_e(item.get("size") or "—")}</td>'
            f'<td>{"target" if item.get("is_target") else ""}</td><td class="num">{review_text}</td></tr>'
        )
    return (
        f'<div class="chart variant-grid" role="img" aria-label="variant grid">'
        f'<table class="variant-table"><thead><tr><th>ASIN</th><th>Color</th><th>Size</th><th>Target</th><th>Reviews</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _chart_maturity(chart: dict[str, Any]) -> str:
    rows = chart.get("series", [])
    statuses = ["confirmed", "directional", "hypothesis", "evidence_gap", "blocked", "not_authorized"]
    head = "<th>Claim</th>" + "".join(f"<th>{_e(status)}</th>" for status in statuses)
    body = []
    for row in rows:
        cells = []
        for status in statuses:
            mark = "●" if row.get("status") == status else ""
            cells.append(f'<td class="maturity-cell">{mark}</td>')
        body.append(f'<tr><th>{_e(row.get("claim_id", ""))}</th>{"".join(cells)}</tr>')
    return (
        f'<div class="chart maturity" role="img" aria-label="claim maturity matrix">'
        f'<table class="maturity-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    )


def _chart_lineage(chart: dict[str, Any]) -> str:
    series = chart.get("series", [])
    peak = max((int(item.get("value", 0)) for item in series), default=1) or 1
    rows = []
    for item in series:
        value = int(item.get("value", 0))
        width = round(100.0 * value / peak, 1)
        delta = item.get("delta")
        delta_text = "—" if delta is None else f"{delta:+d}"
        zero = " zero-step" if value == 0 else ""
        rows.append(
            f'<div class="lin-row{zero}"><div class="lin-label">{_e(item.get("label", item.get("step", "")))}</div>'
            f'<div class="lin-track"><span style="width:{width}%"></span></div>'
            f'<div class="lin-value num">{_num(value)}</div><div class="lin-delta num">{_e(delta_text)}</div></div>'
        )
    return f'<div class="chart lineage" role="img" aria-label="lineage waterfall">{ "".join(rows) }</div>'


CHART_RENDERERS = {
    "nested_bar": _chart_nested_bar,
    "diverging_bar": _chart_diverging_bar,
    "frame_grid": _chart_frame_grid,
    "co_occurrence_matrix": _chart_matrix,
    "quadrant_2x2": _chart_quadrant,
    "coverage_bars": _chart_coverage_bars,
    "variant_grid": _chart_variant_grid,
    "maturity_matrix": _chart_maturity,
    "lineage_waterfall": _chart_lineage,
}


def _chart(chart: dict[str, Any]) -> str:
    renderer = CHART_RENDERERS.get(chart.get("type"))
    if not renderer:
        return f'<div class="chart gap-track">[Evidence gap] unsupported chart: {_e(chart.get("type", ""))}</div>'
    return renderer(chart)


# ---------------------------------------------------------------------------
# blocks
# ---------------------------------------------------------------------------
def _exhibit(block: dict[str, Any]) -> str:
    status = block.get("evidence_status") or {}
    foot = block.get("source_foot") or {}
    drawer = block.get("drawer") or {}
    grade = status.get("status", "evidence_gap")
    data_table = _data_table(block.get("data_table") or [])
    definitions = "".join(f"<li>{_e(item)}</li>" for item in (block.get("definitions") or []))
    return (
        f'<figure class="exhibit" id="exhibit-{_e(block.get("number", ""))}" '
        f'data-basis="{_e(foot.get("basis", ""))}" data-unit="{_e(foot.get("unit", ""))}" '
        f'data-limit="{_e(foot.get("limit", ""))}" data-status="{_e(foot.get("status", ""))}">'
        '<div class="exhibit-head">'
        f'<div class="exhibit-number">EXHIBIT {_e(block.get("number", ""))}</div>'
        f'<h3 class="exhibit-title">{_e(_text(block.get("title", "")))}</h3>'
        f'<div class="exhibit-scope">{_e(block.get("scope", ""))}</div>'
        f'{_status_badge(status)}'
        "</div>"
        f'<div class="exhibit-body">{_chart(block.get("chart") or {})}</div>'
        f'<div class="exhibit-readout">{_readout_block(block.get("readout") or {})}</div>'
        f'{_source_foot(foot)}'
        f'<details class="evidence-drawer"><summary>{_e(drawer.get("summary", "查看定义与误读边界"))}</summary>'
        f'<div class="drawer-body"><p>{_e(drawer.get("content", ""))}</p>'
        f'<h4>Data table</h4>{data_table}<h4>Definitions</h4><ul>{definitions}</ul></div></details>'
        "</figure>"
    )


def _claim(claim: dict[str, Any]) -> str:
    grade = claim.get("grade", "evidence_gap")
    numbers = "".join(
        f'<tr><td>{_e(n.get("name", ""))}</td><td class="num">{_num(n.get("value", ""))}</td>'
        f'<td>{_e(n.get("unit", ""))}</td><td>{_e(n.get("source_path", ""))}</td></tr>'
        for n in claim.get("numbers", [])
    )
    return (
        f'<article class="claim" id="claim-{_e(claim.get("claim_id", ""))}" data-grade="{_e(grade)}">'
        '<div class="claim-head">'
        f'<span class="claim-id">{_e(claim.get("claim_id", ""))}</span>'
        f'<h3 class="claim-headline">{_e(claim.get("headline", ""))}</h3>'
        f'<span class="evidence-badge {STATUS_CLASS.get(grade, "evidence-gap")}">{_e(claim.get("status", grade))}</span>'
        "</div>"
        f'<div class="readout">{_readout_block(claim)}</div>'
        f'{_source_foot({"basis": claim.get("basis", ""), "unit": claim.get("unit", ""), "limit": claim.get("limit", ""), "status": claim.get("status", "")})}'
        f'<details class="evidence-drawer"><summary>查看 claim 元数据</summary>'
        f'<div class="drawer-body"><table class="data-table"><thead><tr><th>Number</th><th>Value</th><th>Unit</th><th>Source</th></tr></thead>'
        f"<tbody>{numbers}</tbody></table></div></details>"
        "</article>"
    )


def _gap(block: dict[str, Any]) -> str:
    foot = block.get("source_foot") or {}
    return (
        f'<div class="gap-block" data-basis="{_e(foot.get("basis", ""))}">'
        f'<h3 class="gap-title">{_e(block.get("title", "[Evidence gap]"))}</h3>'
        f'<p class="gap-reason">{_e(block.get("reason", ""))}</p>'
        f'<div class="readout">{_readout_block(block.get("readout") or {})}</div>'
        f'{_source_foot(foot)}</div>'
    )


def _answer_stack(block: dict[str, Any], report: dict[str, Any]) -> str:
    decision = report.get("decision") or {}
    claim_refs = "".join(f'<span class="claim-ref">{_e(cid)}</span>' for cid in block.get("claim_ids", []))
    protect = "".join(f"<li>{_e(item)}</li>" for item in decision.get("protect", []))
    resolve = "".join(f"<li>{_e(item)}</li>" for item in decision.get("resolve", []))
    prove = "".join(f"<li>{_e(item)}</li>" for item in decision.get("prove", []))
    return (
        '<div class="answer-stack">'
        f'<div class="decision-question">{_e(decision.get("decision_question", ""))}</div>'
        f'<p class="decision-answer">{_e(_text(decision.get("answer", "")))}</p>'
        f'<div class="compass-grid"><div><h4>Protect</h4><ul>{protect}</ul></div>'
        f'<div><h4>Resolve</h4><ul>{resolve}</ul></div><div><h4>Prove</h4><ul>{prove}</ul></div></div>'
        f'<div class="claim-refs">引用 claim：{claim_refs}</div></div>'
    )


def _experiments(block: dict[str, Any], report: dict[str, Any]) -> str:
    by_id = {item["id"]: item for item in report.get("experiments", [])}
    cards = []
    for experiment_id in block.get("experiment_ids", []):
        item = by_id.get(experiment_id)
        if not item:
            continue
        cards.append(
            f'<div class="experiment"><div class="exp-head"><span class="exp-lane">{_e(item.get("lane", ""))}</span>'
            f'<h4>{_e(item.get("name", ""))}</h4><span class="exp-status">{_e(item.get("status", ""))}</span></div>'
            f'<p><b>Trigger</b> {_e(", ".join(item.get("trigger_evidence_refs", [])))}</p>'
            f'<p><b>Minimum test</b> {_e(item.get("minimum_test", ""))}</p>'
            f'<p><b>KPI</b> {_e(item.get("kpi", ""))}</p>'
            f'<p><b>Guardrail</b> {_e(item.get("guardrail", ""))}</p>'
            f'<p><b>Decision</b> {_e(item.get("decision", ""))}</p>'
            f'<p><b>Stop</b> {_e(item.get("stop", ""))}</p></div>'
        )
    return f'<div class="experiment-sequence">{"".join(cards)}</div>'


def _status_legend(block: dict[str, Any]) -> str:
    rows = []
    for item in block.get("statuses", []):
        rows.append(
            f'<tr><td><span class="evidence-badge {STATUS_CLASS.get(item.get("status", ""), "evidence-gap")}">{_e(item.get("label", ""))}</span></td>'
            f'<td>{_e(item.get("rule", ""))}</td><td>{_e(item.get("may_use", ""))}</td><td>{_e(item.get("may_not_use", ""))}</td></tr>'
        )
    return (
        f'<div class="legend-wrap"><h3 class="legend-title">{_e(block.get("title", "六级证据状态"))}</h3>'
        f'<table class="status-legend"><thead><tr><th>Status</th><th>Rule</th><th>May use</th><th>May not use</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _prose(block: dict[str, Any]) -> str:
    return f'<p class="prose">{_e(_text(block.get("text", "")))}</p>'


def _block(block: dict[str, Any], report: dict[str, Any], claims_by_id: dict[str, dict[str, Any]]) -> str:
    block_type = block.get("type")
    if block_type == "exhibit":
        return _exhibit(block)
    if block_type == "claim":
        claim = claims_by_id.get(block.get("claim_id"))
        return _claim(claim) if claim else _gap({"title": "[Evidence gap] missing claim", "reason": block.get("claim_id", "")})
    if block_type == "gap":
        return _gap(block)
    if block_type == "answer_stack":
        return _answer_stack(block, report)
    if block_type == "experiment_sequence":
        return _experiments(block, report)
    if block_type == "status_legend":
        return _status_legend(block)
    if block_type == "prose":
        return _prose(block)
    return f'<div class="gap-block">[Evidence gap] unsupported block: {_e(block_type)}</div>'


# ---------------------------------------------------------------------------
# page shell
# ---------------------------------------------------------------------------
def _hero(report: dict[str, Any]) -> str:
    hero = report.get("hero") or {}
    h1 = _text(hero.get("h1", ""))
    accent = hero.get("h1_accent", "")
    if accent and accent in h1:
        h1_html = _e(h1).replace(_e(accent), f'<span class="accent">{_e(accent)}</span>', 1)
    else:
        h1_html = _e(h1)
    actions = "".join(
        f'<a class="button {"primary" if action.get("primary") else ""}" href="{_e(action.get("href", "#main"))}">{_e(action.get("label", ""))}</a>'
        for action in hero.get("actions", [])
    )
    compass = "".join(
        f'<div class="compass-item"><div class="compass-label">{_e(item.get("label", ""))}</div>'
        f'<div class="compass-title">{_e(item.get("title", ""))}</div><p>{_e(item.get("note", ""))}</p></div>'
        for item in hero.get("compass", [])
    )
    ribbon = hero.get("truth_ribbon") or {}
    cells = "".join(
        f'<div class="ribbon-cell"><div class="ribbon-value">{_e(cell.get("value", ""))}</div>'
        f'<div class="ribbon-note">{_e(cell.get("note", ""))}</div></div>'
        for cell in ribbon.get("cells", [])
    )
    proofs = "".join(
        f'<div class="proof"><div class="proof-value num">{_e(item.get("value", ""))}</div>'
        f'<div class="proof-label">{_e(item.get("label", ""))}</div><div class="proof-note">{_e(item.get("note", ""))}</div></div>'
        for item in hero.get("proofs", [])
    )
    return (
        '<section class="hero">'
        f'<div class="eyebrow">{_e(hero.get("eyebrow", ""))}</div>'
        f"<h1>{h1_html}</h1>"
        f'<p class="hero-lead">{_e(_text(hero.get("lead", "")))}</p>'
        f'<div class="hero-actions">{actions}</div>'
        f'<div class="decision-compass">{compass}</div>'
        f'<div class="truth-ribbon"><div class="ribbon-label">{_e(ribbon.get("label", ""))}</div><div class="ribbon-grid">{cells}</div></div>'
        f'<div class="decision-evidence">{proofs}</div>'
        "</section>"
    )


def _section(section: dict[str, Any], report: dict[str, Any], claims_by_id: dict[str, dict[str, Any]]) -> str:
    blocks = "".join(_block(block, report, claims_by_id) for block in section.get("blocks", []))
    return (
        f'<section class="section" id="{_e(section.get("id", ""))}" data-index="{_e(section.get("index", ""))}">'
        '<div class="section-head">'
        f'<div class="section-index">{_e(section.get("index", ""))} · {_e(section.get("kicker", ""))}</div>'
        f'<h2>{_e(_text(section.get("title", "")))}</h2>'
        "</div>"
        f'<div class="section-body">{blocks}</div></section>'
    )


def _prohibited(report: dict[str, Any]) -> str:
    items = []
    for item in report.get("prohibited_outputs", []):
        items.append(
            f'<li><span class="po-id">{_e(item.get("id", ""))}</span>'
            f'<span class="po-label">{_e(item.get("label", ""))}</span>'
            f'<span class="po-reason">{_e(item.get("reason", ""))}</span>'
            f'<span class="po-gate">{_e(item.get("gate", ""))}</span></li>'
        )
    return (
        '<section class="prohibited" id="prohibited-outputs">'
        '<div class="prohibited-head"><div class="section-index">PROHIBITED OUTPUTS</div>'
        '<p class="prohibited-title">以下结论本轮禁止输出：违反任何一条，报告即视为失败。</p></div>'
        f'<ol class="prohibited-list">{"".join(items)}</ol></section>'
    )


def _unknowns(report: dict[str, Any]) -> str:
    items = "".join(f"<li>{_e(item)}</li>" for item in report.get("unknowns", []))
    return f'<div class="unknowns"><h3>Unknowns</h3><ul>{items}</ul></div>'


def _footer(report: dict[str, Any]) -> str:
    return (
        '<footer class="report-footer">'
        f'<div>{_e(report.get("report_id", ""))}</div>'
        f'<div>as_of {_e(report.get("as_of", ""))} · generated {_e(report.get("generated_at", ""))}</div>'
        f'<div>schema {_e(report.get("schema_version", ""))} · validator {_e(contract.VALIDATOR_VERSION)}</div>'
        "</footer>"
    )


CSS = """
:root{
  --paper:#fbfaf8;--surface:#fff;--surface-2:#f5f2ef;
  --ink:#252321;--ink-2:#625c58;--ink-3:#7c746f;
  --line:#e3ddd8;--line-strong:#cec4bd;
  --brand:#9b626c;--brand-deep:#744650;--brand-ink:#52323a;--brand-soft:#f7ecee;
  --love:#547867;--love-soft:#eaf1ed;--risk:#a55b52;--risk-soft:#f8ebe8;
  --amber:#a87332;--amber-soft:#f7f0e4;--blue:#4f6f84;--blue-soft:#eaf0f4;
  --positive:#3f6b57;--positive-soft:#e8f0eb;--negative:#a5534b;--negative-soft:#f7e9e6;
  --chart-grid:#ded7d1;--radius:18px;--shadow:0 18px 50px rgba(62,43,39,.08);
  --nav:64px;--width:1220px;
}
@media (prefers-color-scheme:dark){
  :root{--paper:#1e1b1a;--surface:#292523;--surface-2:#332e2b;--ink:#f7f3ef;--ink-2:#d0c6c0;--ink-3:#aa9d95;
  --line:#443c38;--line-strong:#5b4f49;--brand-soft:#402d32;--love-soft:#283b32;--risk-soft:#432d2a;
  --amber-soft:#403426;--blue-soft:#293943;--positive-soft:#283b32;--negative-soft:#432d2a;--chart-grid:#443c38;
  --shadow:0 18px 55px rgba(0,0,0,.22);}
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:calc(var(--nav) + 16px)}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.66 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",Arial,sans-serif;font-variant-numeric:tabular-nums}
h1,h2,h3,h4{line-height:1.16;letter-spacing:-.025em;margin:0 0 .5em}
h1{font-size:clamp(38px,5vw,62px);letter-spacing:-.04em}
h2{font-size:clamp(28px,3.6vw,44px)}
h3{font-size:clamp(21px,2.4vw,29px)}
h4{font-size:15px;letter-spacing:0}
p{margin:0 0 1em}
a{color:var(--brand-deep)}
.skip{position:absolute;left:-9999px;top:0;background:var(--brand-deep);color:#fff;padding:10px 14px;z-index:99}
.skip:focus{left:12px;top:12px}
.topbar{position:sticky;top:0;z-index:20;height:var(--nav);display:flex;align-items:center;justify-content:space-between;padding:0 max(24px,calc((100% - var(--width))/2));background:color-mix(in srgb,var(--paper) 92%,transparent);border-bottom:1px solid var(--line);backdrop-filter:blur(10px)}
.brand{font-weight:800;letter-spacing:.06em;text-transform:lowercase;color:var(--brand-deep)}
.navlinks{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;font-weight:650}
.navlinks a{color:var(--ink-2);text-decoration:none;padding:5px 2px;border-bottom:1px solid transparent}
.navlinks a:hover{border-color:var(--brand)}
main{width:min(var(--width),calc(100% - 48px));margin:0 auto}
.hero{padding:72px 0 42px;border-bottom:1px solid var(--line)}
.eyebrow{font-size:12px;font-weight:800;letter-spacing:.13em;text-transform:uppercase;color:var(--brand-deep);margin-bottom:14px}
.accent{color:var(--brand-deep);position:relative;white-space:nowrap}
.hero-lead{font-size:clamp(16px,2vw,21px);color:var(--ink-2);max-width:820px;margin-top:18px}
.hero-actions{display:flex;gap:12px;margin:26px 0 30px;flex-wrap:wrap}
.button{display:inline-block;padding:11px 18px;border:1px solid var(--line-strong);border-radius:999px;text-decoration:none;font-size:13px;font-weight:700;color:var(--ink)}
.button.primary{background:var(--brand-deep);border-color:var(--brand-deep);color:#fff}
.decision-compass{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:28px 0}
.compass-item{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px;box-shadow:var(--shadow)}
.compass-label{font-size:11px;font-weight:850;letter-spacing:.14em;color:var(--brand);text-transform:uppercase}
.compass-title{font-weight:750;margin:4px 0 6px}
.compass-item p{font-size:13px;color:var(--ink-2);margin:0}
.truth-ribbon{background:var(--brand-soft);border:1px solid color-mix(in srgb,var(--brand) 25%,var(--line));border-radius:var(--radius);padding:18px 20px;margin:26px 0}
.ribbon-label{font-size:11px;font-weight:850;letter-spacing:.14em;color:var(--brand-deep);margin-bottom:10px}
.ribbon-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.ribbon-value{font-size:18px;font-weight:800;letter-spacing:-.02em}
.ribbon-note{font-size:11px;color:var(--ink-2)}
.decision-evidence{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:28px 0 8px}
.proof{border-top:2px solid var(--brand);padding-top:12px}
.proof-value{font-size:clamp(28px,3.4vw,38px);font-weight:800;letter-spacing:-.04em}
.proof-label{font-size:12px;font-weight:700;color:var(--ink-2)}
.proof-note{font-size:11px;color:var(--ink-3)}
.section{padding:64px 0;border-bottom:1px solid var(--line)}
.section-head{display:grid;grid-template-columns:minmax(0,1fr) minmax(240px,420px);gap:28px;align-items:end;margin-bottom:34px}
.section-head h2{grid-column:2;margin:0;font-size:clamp(24px,3vw,36px)}
.section-index{grid-column:1;font-size:12px;font-weight:850;letter-spacing:.14em;color:var(--brand-deep);text-transform:uppercase;align-self:start;padding-top:8px}
.section-body{display:flex;flex-direction:column;gap:30px}
.exhibit{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:26px 26px 20px;margin:0}
.exhibit-head{display:grid;grid-template-columns:1fr auto;gap:8px 16px;align-items:start;margin-bottom:18px}
.exhibit-number{grid-column:1;font-size:11px;font-weight:850;letter-spacing:.14em;color:var(--brand-deep)}
.exhibit-title{grid-column:1;margin:0;font-size:clamp(20px,2.4vw,28px)}
.exhibit-scope{grid-column:1;font-size:12px;color:var(--ink-3);margin-top:2px}
.evidence-badge{display:inline-block;font-size:10px;font-weight:850;letter-spacing:.08em;line-height:1.3;padding:5px 9px;border-radius:999px;border:1px solid var(--line-strong);color:var(--ink-2);background:var(--surface-2);white-space:nowrap}
.exhibit-head .evidence-badge{grid-column:2;grid-row:1/span 3;align-self:start;justify-self:end}
.evidence-badge.confirmed{color:var(--positive);border-color:color-mix(in srgb,var(--positive) 45%,var(--line));background:var(--positive-soft)}
.evidence-badge.directional{color:var(--brand-deep);border-color:color-mix(in srgb,var(--brand) 45%,var(--line));background:var(--brand-soft)}
.evidence-badge.hypothesis{color:var(--blue);border-color:color-mix(in srgb,var(--blue) 45%,var(--line));background:var(--blue-soft)}
.evidence-badge.evidence-gap{color:var(--amber);border-color:color-mix(in srgb,var(--amber) 45%,var(--line));background:var(--amber-soft)}
.evidence-badge.blocked{color:var(--negative);border-color:color-mix(in srgb,var(--negative) 45%,var(--line));background:var(--negative-soft)}
.evidence-badge.not-authorized{color:#7b4a78;border-color:#c9a8c7;background:#f3eaf2}
.exhibit-body{margin:10px 0 18px}
.chart{font-size:13px}
.nb-row,.div-row,.cov-row,.lin-row{display:grid;gap:10px;align-items:center;margin:8px 0}
.nb-row{grid-template-columns:minmax(160px,1.4fr) minmax(120px,3fr) 90px}
.nb-track,.cov-track,.lin-track{height:16px;background:var(--surface-2);border:1px solid var(--line);border-radius:999px;overflow:hidden;position:relative}
.nb-fill{display:block;height:100%;background:linear-gradient(90deg,var(--brand),var(--brand-deep))}
.nb-value,.cov-value,.lin-value,.lin-delta{text-align:right;font-weight:750}
.gap-track{display:flex;align-items:center;justify-content:flex-start;padding:0 8px;color:var(--ink-3);font-size:11px;background:repeating-linear-gradient(135deg,var(--surface-2),var(--surface-2) 6px,var(--surface) 6px,var(--surface) 12px)}
.gap-mark{font-size:10px;color:var(--amber)}
.div-row{grid-template-columns:minmax(150px,1.2fr) minmax(100px,2fr) minmax(100px,2fr) 110px}
.div-neg,.div-pos{height:14px;background:var(--surface-2);border:1px solid var(--line);border-radius:999px;overflow:hidden;display:flex}
.div-neg{justify-content:flex-end}
.div-neg span{display:block;height:100%;background:var(--negative)}
.div-pos span{display:block;height:100%;background:var(--positive)}
.div-values{text-align:right;font-weight:750;font-size:12px}
.div-label{font-weight:650}
.frame-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.frame-card{background:var(--surface-2);border:1px solid var(--line);border-radius:14px;padding:16px}
.frame-name{font-weight:800;font-size:15px}
.frame-n{font-size:11px;color:var(--ink-3);margin:2px 0 10px}
.frame-cols{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.frame-cols ul{margin:4px 0 0;padding-left:16px;font-size:12px}
.frame-cols li{margin:2px 0}
.matrix-table,.variant-table,.maturity-table,.data-table,.status-legend{width:100%;border-collapse:collapse;font-size:12px}
.matrix-table th,.matrix-table td,.variant-table th,.variant-table td,.maturity-table th,.maturity-table td,.data-table th,.data-table td,.status-legend th,.status-legend td{border:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}
.matrix-table th,.variant-table th,.maturity-table th,.data-table th,.status-legend th{background:var(--surface-2);font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:var(--ink-2)}
.heat{text-align:center;font-weight:750;min-width:54px}
.heat-0{background:var(--surface-2);color:var(--ink-3)}
.heat-1{background:#f1e8e9}.heat-2{background:#e6d4d7}.heat-3{background:#d6b9be}.heat-4{background:#c5969e}
.heat-5{background:#b9828d}.heat-6{background:#ac6f7c}.heat-7{background:#9f5f6e}.heat-8{background:var(--brand);color:#fff}
.quadrant{position:relative;padding:28px 0 0 46px}
.quad-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.quad-cell{min-height:120px;background:var(--surface-2);border:1px solid var(--line);border-radius:14px;padding:14px}
.quad-tag{font-size:10px;font-weight:850;letter-spacing:.1em;color:var(--brand-deep);text-transform:uppercase}
.quad-name{font-weight:800;margin:5px 0}
.quad-values{font-size:11px;color:var(--ink-2)}
.axis-label{position:absolute;font-size:10px;font-weight:750;letter-spacing:.08em;color:var(--ink-3);text-transform:uppercase}
.axis-x{left:46px;bottom:-6px}
.axis-y{left:0;top:90px;transform:rotate(-90deg);transform-origin:left top}
.cov-row{grid-template-columns:minmax(150px,1.2fr) minmax(140px,3fr) 70px}
.cov-track span,.lin-track span{display:block;height:100%;background:var(--brand)}
.variant-row.target{background:var(--brand-soft);font-weight:750}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px}
.maturity-cell{text-align:center;font-size:16px;color:var(--brand-deep)}
.lin-row{grid-template-columns:minmax(150px,1.1fr) minmax(140px,3fr) 80px 60px}
.lin-track span{background:linear-gradient(90deg,var(--blue),var(--brand))}
.zero-step .lin-track span{background:var(--negative-soft);border:1px dashed var(--negative)}
.exhibit-readout{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;border-top:1px solid var(--line);padding-top:16px}
.readout-item{background:var(--surface-2);border-radius:12px;padding:12px 13px}
.readout-label{display:block;font-size:10px;font-weight:850;letter-spacing:.12em;color:var(--brand-deep);text-transform:uppercase;margin-bottom:5px}
.readout-item p{margin:0;font-size:12px;line-height:1.5;color:var(--ink-2)}
.source-foot{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px;padding-top:12px;border-top:1px dashed var(--line);font-size:10.5px;color:var(--ink-3)}
.source-foot b{display:block;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-2)}
details.evidence-drawer{margin-top:14px;border-top:1px solid var(--line);padding-top:10px}
details.evidence-drawer summary{cursor:pointer;font-size:12px;font-weight:750;color:var(--brand-deep)}
.drawer-body{padding-top:10px;font-size:12px;color:var(--ink-2)}
.drawer-body h4{margin-top:14px}
.claim{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--brand);border-radius:14px;padding:18px 20px;box-shadow:var(--shadow)}
.claim-head{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:start}
.claim-id{font-size:11px;font-weight:850;letter-spacing:.08em;color:var(--brand-deep);padding-top:4px}
.claim-headline{margin:0;font-size:17px;line-height:1.35}
.claim .readout,.gap-block .readout{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:14px}
.gap-block{background:var(--amber-soft);border:1px solid color-mix(in srgb,var(--amber) 35%,var(--line));border-radius:14px;padding:18px 20px}
.gap-title{margin:0 0 6px;font-size:17px;color:var(--amber)}
.gap-reason{margin:0 0 12px;font-size:12px;color:var(--ink-2)}
.answer-stack{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:24px;box-shadow:var(--shadow)}
.decision-question{font-size:12px;font-weight:850;letter-spacing:.1em;text-transform:uppercase;color:var(--brand-deep);margin-bottom:10px}
.decision-answer{font-size:clamp(18px,2.2vw,24px);font-weight:700;line-height:1.35;margin-bottom:18px}
.compass-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.compass-grid h4{color:var(--brand-deep);text-transform:uppercase;letter-spacing:.1em;font-size:11px}
.compass-grid ul{margin:4px 0 0;padding-left:16px;font-size:12px;color:var(--ink-2)}
.claim-refs{font-size:11px;color:var(--ink-3);margin-top:14px}
.claim-ref{display:inline-block;border:1px solid var(--line-strong);border-radius:999px;padding:2px 8px;margin-right:6px;font-weight:750;color:var(--brand-deep)}
.experiment-sequence{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.experiment{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:var(--shadow)}
.exp-head{display:flex;flex-direction:column;gap:3px;margin-bottom:10px}
.exp-lane{font-size:10px;font-weight:850;letter-spacing:.1em;text-transform:uppercase;color:var(--brand-deep)}
.exp-head h4{margin:0;font-size:15px}
.exp-status{font-size:10px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.1em}
.experiment p{font-size:11.5px;margin:0 0 6px;color:var(--ink-2)}
.experiment p b{color:var(--ink)}
.legend-wrap{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px;overflow:auto}
.legend-title{font-size:14px;margin-bottom:10px}
.status-legend{font-size:11px}
.status-legend .evidence-badge{white-space:normal}
.unknowns{background:var(--surface-2);border:1px solid var(--line);border-radius:14px;padding:16px 20px}
.unknowns h3{font-size:14px;margin-bottom:8px}
.unknowns ul{margin:0;padding-left:18px;font-size:12px;color:var(--ink-2)}
.unknowns li{margin:3px 0}
.prohibited{padding:64px 0;border-top:3px solid var(--negative)}
.prohibited-head{margin-bottom:20px}
.prohibited-title{font-size:clamp(20px,2.4vw,28px);font-weight:800;letter-spacing:-.02em;margin:0}
.prohibited-list{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:10px}
.prohibited-list li{background:var(--negative-soft);border:1px solid color-mix(in srgb,var(--negative) 30%,var(--line));border-radius:12px;padding:12px 14px;display:grid;grid-template-columns:auto 1fr;gap:4px 10px}
.po-id{font-size:10px;font-weight:850;letter-spacing:.08em;color:var(--negative)}
.po-label{font-weight:750;font-size:13px}
.po-reason{grid-column:2;font-size:11px;color:var(--ink-2)}
.po-gate{grid-column:2;font-size:10px;font-weight:750;letter-spacing:.08em;color:var(--negative)}
.report-footer{padding:34px max(24px,calc((100% - var(--width))/2));display:flex;gap:18px;justify-content:space-between;flex-wrap:wrap;font-size:10.5px;color:var(--ink-3);border-top:1px solid var(--line)}
.prose{color:var(--ink-2);max-width:76ch}
.data-table{margin-top:8px}
.gap-cell{color:var(--amber)}
@media (max-width:900px){
  .decision-compass,.decision-evidence,.ribbon-grid,.exhibit-readout,.claim .readout,.gap-block .readout,.source-foot,.frame-grid,.experiment-sequence,.compass-grid,.prohibited-list{grid-template-columns:1fr 1fr}
  .section-head{grid-template-columns:1fr}
  .section-head h2,.section-index{grid-column:1}
  .div-row,.nb-row,.cov-row,.lin-row{grid-template-columns:1fr 2fr 70px}
  .div-values,.lin-delta{display:none}
}
@media (max-width:620px){
  main{width:calc(100% - 24px)}
  .decision-compass,.decision-evidence,.ribbon-grid,.exhibit-readout,.claim .readout,.gap-block .readout,.source-foot,.frame-grid,.experiment-sequence,.compass-grid,.prohibited-list{grid-template-columns:1fr}
  .topbar{height:auto;padding:10px 12px;flex-direction:column;gap:6px}
  .navlinks{justify-content:center}
  .hero{padding-top:40px}
  .exhibit,.claim,.answer-stack{padding:16px}
  .claim-head{grid-template-columns:1fr}
  .claim-head .evidence-badge{justify-self:start}
  .div-row,.nb-row,.cov-row,.lin-row{grid-template-columns:1fr}
  .div-neg,.div-pos{height:12px}
}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important;animation:none!important}}
@media print{
  .topbar,.hero-actions,.navlinks,.skip{display:none}
  .section,.exhibit,.claim{break-inside:avoid;box-shadow:none}
  details{display:block}
  details>*{display:block}
  .report-footer{position:static}
}
"""


def render_report(report: dict[str, Any]) -> str:
    claims_by_id = {claim["claim_id"]: claim for claim in report.get("report", {}).get("claims", [])}
    sections = "".join(_section(section, report["report"], claims_by_id) for section in report["report"]["sections"])
    exhibit_numbers = [
        block.get("number")
        for section in report["report"]["sections"]
        for block in section.get("blocks", [])
        if block.get("type") == "exhibit"
    ]
    # The data island is audit-only and deliberately compact: the full report
    # JSON includes prohibited conclusions, which must not leak into the
    # rendered page's word scan.
    island = {
        "schema_version": report.get("schema_version"),
        "report_id": report.get("report_id"),
        "as_of": report.get("as_of"),
        "report_mode": report.get("report_mode"),
        "claims": [{"claim_id": c.get("claim_id"), "grade": c.get("grade")} for c in report.get("report", {}).get("claims", [])],
        "exhibits": exhibit_numbers,
        "sections": [section.get("id") for section in report["report"]["sections"]],
        "prohibited_output_ids": [item.get("id") for item in report.get("report", {}).get("prohibited_outputs", [])],
        "unknowns_count": len(report.get("report", {}).get("unknowns", [])),
    }
    data_island = json.dumps(island, ensure_ascii=False).replace("</", "<\\/")
    nav = "".join(
        f'<a href="#{_e(section["id"])}">{_e(section["index"])}</a>' for section in report["report"]["sections"]
    ) + '<a href="#prohibited-outputs">PO</a>'
    return (
        '<!doctype html>\n<html lang="zh-CN" data-theme="light">\n<head>\n'
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        f'<title>{_e(report["report"]["meta"].get("title", "VOC Insight Report"))}</title>\n'
        f'<style>{CSS}</style>\n</head>\n<body>\n'
        '<a class="skip" href="#main">跳到正文</a>\n'
        f'<header class="topbar"><div class="brand">{_e(report["report"]["meta"].get("brand_wordmark", "voc"))}</div>'
        f'<nav class="navlinks">{nav}</nav></header>\n<main id="main">\n'
        f'{_hero(report["report"])}\n{sections}\n{_unknowns(report["report"])}\n{_prohibited(report["report"])}\n'
        "</main>\n"
        f'{_footer(report)}\n'
        f'<script type="application/json" id="data-island">{data_island}</script>\n'
        "</body>\n</html>\n"
    )
