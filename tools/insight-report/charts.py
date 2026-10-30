#!/usr/bin/env python3
"""charts.py — ten pure-CSS chart renderers.

Every public function has the same signature:

    chart_xxx(data: dict) -> str

`data` is the `chart` object from report-data.json. Each chart:

  * is pure HTML + CSS (no SVG, canvas, images, JS, or network)
  * carries `data-chart-type`, `data-unit`, `role`, and `aria-label`
  * appends a Basis / Unit / Limit / Status row; a missing parameter renders
    as `UNKNOWN` instead of disappearing
  * appends at least one misread-boundary note

Unknown chart types raise ValueError. Missing numeric data raises ValueError
rather than silently plotting zero.
"""
from __future__ import annotations

import html
from typing import Any


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _num(value: Any) -> str:
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _esc(value)


def _pct(part: float, whole: float) -> float:
    if not whole or whole <= 0:
        raise ValueError(f"chart denominator must be positive, got {whole!r}")
    return max(0.0, min(100.0, part / whole * 100.0))


def _four_rows(chart: dict) -> str:
    labels = (("Basis", "basis"), ("Unit", "unit"), ("Limit", "limit"), ("Status", "status"))
    items = []
    for label, key in labels:
        value = chart.get(key)
        if value is None or str(value).strip() == "":
            items.append(
                f'<span class="chart-meta-item chart-meta-unknown"><b>{label}</b> UNKNOWN</span>'
            )
        else:
            items.append(f'<span class="chart-meta-item"><b>{label}</b> {_esc(value)}</span>')
    return '<div class="chart-meta">' + "".join(items) + "</div>"


def _notes(chart: dict) -> str:
    notes = chart.get("notes") or ["读图边界未提供：按绝对值阅读，不作总体推断。"]
    return '<ul class="chart-notes">' + "".join(f"<li>{_esc(n)}</li>" for n in notes) + "</ul>"


def _shell(chart: dict, aria: str, body: str, role: str = "img") -> str:
    ctype = chart.get("type", "unknown")
    unit = chart.get("unit", "unknown")
    return (
        f'<div class="chart" data-chart-type="{_esc(ctype)}" data-unit="{_esc(unit)}" '
        f'role="{role}" aria-label="{_esc(aria)}">'
        f'<div class="chart-canvas">{body}</div>'
        f"{_notes(chart)}{_four_rows(chart)}</div>"
    )


def _require(value, name: str):
    if value is None:
        raise ValueError(f"chart data missing required field: {name}")
    return value


# ---------------------------------------------------------------------------
# 1. nested_bar (E01)
# ---------------------------------------------------------------------------
def chart_nested_bar(data: dict) -> str:
    series = _require(data.get("series"), "series")
    rows = []
    aria_bits = []
    for item in series:
        group = item.get("group", "unknown")
        n = item.get("n")
        with_friction = item.get("with_friction")
        without = item.get("without_friction")
        if n in (None, 0) or with_friction is None or item.get("status") == "evidence_gap":
            rows.append(
                f'<div class="nested-row is-gap"><div class="nested-label"><b>{_esc(group)}</b>'
                f'<span>[Evidence gap]</span></div>'
                f'<div class="nested-track nested-gap">该组共现未计算</div>'
                f'<div class="nested-counts">—</div></div>'
            )
            aria_bits.append(f"{group} 的共现未计算，标为 Evidence gap")
            continue
        n = int(n)
        with_friction = int(with_friction)
        if without is None:
            without = n - with_friction
        width = _pct(with_friction, n)
        inline = f"{with_friction} 同时有摩擦" if width >= 20 else ""
        rest_label = f"{int(without)} 未观察到"
        rows.append(
            f'<div class="nested-row"><div class="nested-label"><b>{_esc(group)}</b>'
            f'<span>{n} records</span></div>'
            f'<div class="nested-track"><span class="nested-fill" style="width:{width:.2f}%">'
            f"{inline}</span><span class=\"nested-rest\">{_esc(rest_label)}</span></div>"
            f'<div class="nested-counts"><b>{with_friction} / {n}</b></div></div>'
        )
        aria_bits.append(f"{n} 条 {group} 记录中 {with_friction} 条同时有核心摩擦")
    aria = "；".join(aria_bits) + "。宽度表示组内共现，不是跨组百分比。"
    return _shell(data, aria, "".join(rows))


# ---------------------------------------------------------------------------
# 2. diverging_bar (E02)
# ---------------------------------------------------------------------------
def chart_diverging_bar(data: dict) -> str:
    series = _require(data.get("series"), "series")
    axis = data.get("axis") or {}
    vmax = axis.get("max")
    vmin = axis.get("min", -vmax if isinstance(vmax, (int, float)) else None)
    if not isinstance(vmax, (int, float)) or vmax <= 0:
        raise ValueError("diverging_bar needs axis.max > 0")
    rows = []
    for item in series:
        code = item.get("code", "unknown")
        pos = int(item.get("positive") or 0)
        neg = int(item.get("negative") or 0)
        pos_w = _pct(pos, vmax)
        neg_w = _pct(abs(neg), abs(vmin) if isinstance(vmin, (int, float)) and vmin else vmax)
        rows.append(
            f'<div class="diverge-row"><div class="diverge-label"><b>{_esc(code)}</b></div>'
            f'<div class="diverge-half diverge-neg"><span class="diverge-bar neg" style="width:{neg_w:.2f}%">'
            f'{neg if neg else ""}</span></div>'
            f'<div class="diverge-zero" aria-hidden="true"></div>'
            f'<div class="diverge-half diverge-pos"><span class="diverge-bar pos" style="width:{pos_w:.2f}%">'
            f'{pos if pos else ""}</span></div>'
            f'<div class="diverge-value">+{pos} / −{neg}</div></div>'
        )
    axis_html = (
        f'<div class="diverge-axis"><span>{_num(vmin)}</span><span>0</span><span>{_num(vmax)}</span></div>'
    )
    aria = f"正负标注绝对值对比，轴范围 {vmin} 到 {vmax}；每行同一轴，净分不显示。"
    return _shell(data, aria, axis_html + "".join(rows))


# ---------------------------------------------------------------------------
# 3. frame_grid (E03)
# ---------------------------------------------------------------------------
def _lens_list(items, cls: str) -> str:
    if not items:
        return f'<p class="{cls} empty">[Evidence gap] 该镜头没有可列出的编码。</p>'
    lis = []
    for item in items:
        codes = item.get("codes") or []
        lis.append(
            f'<li><span>{_esc(item.get("label", ""))}</span>'
            f'<b class="num">{_num(item.get("count", 0))}</b>'
            f'<small>{_esc(", ".join(codes))}</small></li>'
        )
    return f'<ul class="{cls}">' + "".join(lis) + "</ul>"


def chart_frame_grid(data: dict) -> str:
    lenses = _require(data.get("lenses"), "lenses")
    cards = []
    for lens in lenses:
        n = lens.get("n")
        n_value = n.get("value") if isinstance(n, dict) else n
        cards.append(
            f'<article class="lens-card"><div class="lens-head"><b>{_esc(lens.get("name", lens.get("id", "")))}</b>'
            f'<span class="num">N={_num(n_value)}</span></div>'
            f'<div class="lens-block"><h4>Love（正向）</h4>{_lens_list(lens.get("love"), "lens-list love")}</div>'
            f'<div class="lens-block"><h4>Complaint（负向）</h4>{_lens_list(lens.get("complaint"), "lens-list complaint")}</div>'
            f'<p class="lens-note">{_esc(lens.get("note", ""))}</p></article>'
        )
    aria = "三个样本镜头并排展示绝对计数；镜头回答不同问题，不能合并，也不能跨镜头比较比例。"
    return _shell(data, aria, '<div class="frame-grid">' + "".join(cards) + "</div>")


# ---------------------------------------------------------------------------
# 4. co_occurrence_matrix (E04)
# ---------------------------------------------------------------------------
def chart_co_occurrence_matrix(data: dict) -> str:
    matrix = _require(data.get("matrix"), "matrix")
    positives = list(matrix.keys())
    negatives = []
    for row in matrix.values():
        for col in row.keys():
            if col not in negatives:
                negatives.append(col)
    header = "".join(f'<th scope="col">{_esc(n)}</th>' for n in negatives)
    rows = []
    col_totals = {n: 0 for n in negatives}
    for p in positives:
        cells = []
        row_total = 0
        for n in negatives:
            v = int(matrix.get(p, {}).get(n, 0))
            row_total += v
            col_totals[n] += v
            heat = min(8, max(0, v))
            label = f"{p} positive family × {n} negative family = {v} records"
            cells.append(
                f'<td role="cell" class="heat heat-{heat}" data-v="{v}" aria-label="{_esc(label)}">'
                f'{v if v else "·"}</td>'
            )
        cells.append(f'<td role="cell" class="row-total">{row_total}</td>')
        rows.append(f'<tr role="row"><th scope="row">{_esc(p)}</th>' + "".join(cells) + "</tr>")
    totals = "".join(f'<td role="cell" class="col-total">{col_totals[n]}</td>' for n in negatives)
    table = (
        '<table class="matrix" role="table" aria-label="正负体验家族共现矩阵，计数为记录级">'
        f'<thead><tr role="row"><th scope="col">positive \\ negative</th>{header}<th scope="col">行合计</th></tr></thead>'
        f'<tbody>{"".join(rows)}<tr role="row" class="totals-row"><th scope="row">列合计</th>{totals}<td role="cell" class="grand-total">'
        f'{sum(col_totals.values())}</td></tr></tbody></table>'
    )
    aria = "记录级共现矩阵；每个混合记录只投影一个代表家族对，完整代码列表见 pairs；不是百分比。"
    return _shell(data, aria, table, role="table")


# ---------------------------------------------------------------------------
# 5. quadrant_2x2 (E05)
# ---------------------------------------------------------------------------
def _need_text(value) -> str:
    if isinstance(value, dict):
        return str(value.get("text", ""))
    return str(value or "")


def chart_quadrant_2x2(data: dict) -> str:
    needs = _require(data.get("need_states"), "need_states")
    axes = data.get("axes") or {}
    by_q = {}
    for n in needs:
        q = str(n.get("quadrant", "")).split("·", 1)[0].strip()
        by_q.setdefault(q, []).append(n)
    cells = []
    # DOM order Q2/Q4/Q1/Q3; CSS grid areas place them visually.
    for q in ("Q2", "Q4", "Q1", "Q3"):
        items = by_q.get(q, [])
        if not items:
            cells.append(f'<div class="quad-cell quad-{q.lower()} empty" role="group" aria-label="{q} 无场景">'
                         f'<span class="quad-code">{q}</span><p>[Evidence gap]</p></div>')
            continue
        for n in items:
            cells.append(
                f'<div class="quad-cell quad-{q.lower()}" role="group" aria-label="{_esc(n.get("name", ""))}，象限 {q}">'
                f'<div class="quad-meta"><span class="quad-code">{q}</span>'
                f'<span class="quad-badge">HYPOTHESIS</span></div>'
                f'<h4>{_esc(n.get("name", ""))}</h4>'
                f'<p>{_esc(_need_text(n.get("summary")))}</p>'
                f'<p class="quad-signal">{_esc(_need_text(n.get("signal")))}</p></div>'
            )
    axis_html = (
        f'<div class="quad-y">Y 轴：{_esc(axes.get("y", "适配复杂度"))} ↑</div>'
        '<div class="quad-wrap"><div class="quad-grid">' + "".join(cells) + "</div></div>"
        f'<div class="quad-x">X 轴：{_esc(axes.get("x", "支撑需求强度"))} →</div>'
    )
    aria = "四个需求场景放在支撑需求与适配复杂度轴上；象限位置是假设，不是人群规模，也不是满意率。"
    return _shell(data, aria, axis_html)


# ---------------------------------------------------------------------------
# 6. coverage_bars (E06)
# ---------------------------------------------------------------------------
def chart_coverage_bars(data: dict) -> str:
    stages = _require(data.get("stage_counts"), "stage_counts")
    display_max = data.get("display_max")
    if not isinstance(display_max, (int, float)) or display_max <= 0:
        display_max = max([int(s.get("value", 0)) for s in stages] or [1])
    rows = []
    for s in stages:
        value = int(s.get("value", 0))
        width = _pct(value, display_max)
        rows.append(
            f'<div class="coverage-row"><div class="coverage-label"><b>{_esc(s.get("label", s.get("code", "")))}</b>'
            f'<span class="num">{value}</span></div>'
            f'<div class="coverage-track"><span style="width:{width:.2f}%"></span></div></div>'
        )
    unknown = data.get("unknown")
    unknown_html = ""
    if unknown is not None:
        uv = unknown.get("value") if isinstance(unknown, dict) else unknown
        unknown_html = (
            f'<p class="coverage-unknown">未进入任何阶段的记录：<b class="num">{_num(uv)}</b>'
            f'（单独列出，不并入负向，也不从总数中扣除）。</p>'
        )
    caption = (
        f'<div class="chart-caption">覆盖，不是漏斗 · 显示上限 {_num(display_max)} · '
        f'真实分母 {_num(data.get("denominator"))}</div>'
    )
    aria = f"覆盖，不是漏斗。各阶段绝对计数按显示上限 {display_max} 归一；阶段可重叠，阶段和不等于 100%。"
    return _shell(data, aria, caption + "".join(rows) + unknown_html)


# ---------------------------------------------------------------------------
# 7. social_flow (E07)
# ---------------------------------------------------------------------------
def chart_social_flow(data: dict) -> str:
    records = _require(data.get("records"), "records")
    total = records.get("value") if isinstance(records, dict) else records
    partition = data.get("partition") or []
    psum = sum(int(p.get("value", 0)) for p in partition)
    if int(total) != psum:
        raise ValueError(f"social_flow partition sums to {psum}, records={total}")
    chips = "".join(
        f'<div class="flow-chip"><b>{_esc(p.get("label", ""))}</b><span class="num">{_num(p.get("value", 0))}</span></div>'
        for p in partition
    )
    metric_rows = data.get("metric_rows", 0)
    return _shell(
        data,
        "社媒池按内容角色、商业性和可用性分流；分区和等于记录总数；metric rows 单独列出。",
        f'<div class="social-flow"><div class="flow-total"><span>社媒记录</span><b class="num">{_num(total)}</b></div>'
        f'<div class="flow-parts">{chips}</div>'
        f'<div class="flow-metric"><span>正式 metric rows</span><b class="num">{_num(metric_rows)}</b></div></div>'
        '<p class="chart-caption">社媒池只作上下文，不能代表自然消费者口碑。</p>',
    )


# ---------------------------------------------------------------------------
# 8. variant_grid (E08)
# ---------------------------------------------------------------------------
def _count_cell(v) -> str:
    if isinstance(v, dict) and v.get("value") is not None:
        return f'<span class="num">{_num(v.get("value"))}</span>'
    return '<span class="missing">[Evidence gap]</span>'


def chart_variant_grid(data: dict) -> str:
    variants = _require(data.get("variants"), "variants")
    ordered = sorted(
        variants,
        key=lambda v: (str(v.get("color") or ""), str(v.get("size") or ""), str(v.get("variant_key") or "")),
    )
    cards = []
    for v in ordered:
        target = ' <span class="target-tag">TARGET</span>' if v.get("is_target") else ""
        conf = v.get("mapping_confidence")
        conf_text = "UNKNOWN" if conf is None else f"{float(conf):.2f}"
        cards.append(
            f'<article class="variant-card{" is-target" if v.get("is_target") else ""}" '
            f'data-variant-key="{_esc(v.get("variant_key"))}">'
            f'<div class="variant-head"><b>{_esc(v.get("color") or "UNKNOWN")} / {_esc(v.get("size") or "UNKNOWN")}</b>{target}</div>'
            f'<div class="variant-id">{_esc(v.get("asin") or v.get("sku_id") or v.get("variant_key"))}</div>'
            f'<dl class="variant-facts">'
            f'<div><dt>mapping</dt><dd class="num">{_esc(conf_text)}</dd></div>'
            f'<div><dt>review_count</dt><dd>{_count_cell(v.get("review_count"))}</dd></div>'
            f'<div><dt>rating</dt><dd>{_count_cell(v.get("rating"))}</dd></div>'
            f'<div><dt>verified</dt><dd>{_count_cell(v.get("verified_count"))}</dd></div>'
            f"</dl></article>"
        )
    aria = f"变体网格共 {len(ordered)} 个 ASIN；按颜色、尺码稳定排序；缺失计数写 Evidence gap，不补零；不跨源合并 SKU 与 ASIN。"
    return _shell(data, aria, '<div class="variant-grid">' + "".join(cards) + "</div>")


# ---------------------------------------------------------------------------
# 9. maturity_matrix (E09)
# ---------------------------------------------------------------------------
def chart_maturity_matrix(data: dict) -> str:
    rows = _require(data.get("rows"), "rows")
    header = "".join(f'<th scope="col">{_esc(C_LABEL[s])}</th>' for s in _STATUS_ORDER)
    body = []
    for row in rows:
        status = row.get("status")
        cells = []
        for s in _STATUS_ORDER:
            if s == status:
                cells.append(
                    f'<td role="cell" class="status-cell active {s.replace("_", "-")}">'
                    f'<span class="dot"></span>{"当前" if row.get("current") else ""}</td>'
                )
            else:
                cells.append('<td role="cell" class="status-cell"></td>')
        body.append(
            f'<tr role="row"><th scope="row"><b>{_esc(row.get("claim_id"))}</b><span>{_esc(row.get("label"))}</span></th>'
            + "".join(cells) + "</tr>"
        )
    table = (
        '<table class="maturity" role="table" aria-label="Claim 成熟度矩阵：每行一个 claim，六列证据状态">'
        f'<thead><tr role="row"><th scope="col">claim</th>{header}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>'
    )
    return _shell(data, "每条 claim 当前只占一个证据状态列；状态是门禁结果，不是绩效分。", table, role="table")


# ---------------------------------------------------------------------------
# 10. lineage_waterfall (E10)
# ---------------------------------------------------------------------------
def chart_lineage_waterfall(data: dict) -> str:
    groups = data.get("groups")
    if not groups:
        steps = _require(data.get("steps"), "steps or groups")
        groups = [{"name": data.get("name", "lineage"), "steps": steps}]
    blocks = []
    for group in groups:
        steps = group.get("steps") or []
        values = [abs(int(s.get("value", 0))) for s in steps] or [1]
        gmax = max(values) or 1
        rows = []
        for s in steps:
            value = int(s.get("value", 0))
            width = _pct(abs(value), gmax)
            delta = s.get("delta")
            if delta is None:
                delta_html = '<span class="delta flat">起点</span>'
            else:
                d = int(delta)
                cls = "up" if d > 0 else "down" if d < 0 else "flat"
                sign = "+" if d > 0 else ""
                delta_html = f'<span class="delta {cls}">{sign}{d}</span>'
            reason = f'<small class="delta-reason">{_esc(s.get("reason", ""))}</small>' if s.get("reason") else ""
            rows.append(
                f'<div class="lineage-row"><div class="lineage-label">{_esc(s.get("label", ""))}</div>'
                f'<div class="lineage-track"><span style="width:{width:.2f}%"></span></div>'
                f'<div class="lineage-value num">{value}</div>{delta_html}{reason}</div>'
            )
        blocks.append(
            f'<div class="lineage-group"><h4>{_esc(group.get("name", "lineage"))}'
            f'<small>组内独立刻度，最大 {gmax}</small></h4>{"".join(rows)}</div>'
        )
    return _shell(
        data,
        "血缘瀑布按组独立刻度；每一步是计数与扣减原因，不是转化率，也不是漏斗。",
        "".join(blocks),
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
C_LABEL = {
    "confirmed": "Confirmed",
    "directional": "Directional",
    "hypothesis": "Supported hypothesis",
    "evidence_gap": "Evidence gap",
    "blocked": "Blocked",
    "not_authorized": "Not authorized",
}
_STATUS_ORDER = ["confirmed", "directional", "hypothesis", "evidence_gap", "blocked", "not_authorized"]

CHART_RENDERERS = {
    "nested_bar": chart_nested_bar,
    "diverging_bar": chart_diverging_bar,
    "frame_grid": chart_frame_grid,
    "co_occurrence_matrix": chart_co_occurrence_matrix,
    "quadrant_2x2": chart_quadrant_2x2,
    "coverage_bars": chart_coverage_bars,
    "social_flow": chart_social_flow,
    "variant_grid": chart_variant_grid,
    "maturity_matrix": chart_maturity_matrix,
    "lineage_waterfall": chart_lineage_waterfall,
}


def render_chart(chart: dict) -> str:
    ctype = chart.get("type")
    fn = CHART_RENDERERS.get(ctype)
    if fn is None:
        raise ValueError(f"unknown chart type: {ctype!r}; allowed: {sorted(CHART_RENDERERS)}")
    return fn(chart)
