#!/usr/bin/env python3
"""Exhibit renderer — the mandatory seven-piece shell.

    <figure class="exhibit">
      figcaption.exhibit-head
        .exhibit-number + h3.exhibit-title
        .exhibit-scope + .evidence-badge
      .exhibit-body
      .exhibit-readout (exactly 4 .readout-item)
      .source-foot (Basis / Unit / Limit / Status)
      details.evidence-drawer
"""
from __future__ import annotations

from charts import render_chart
from templates import components as c


def render_exhibit(block: dict) -> str:
    number = str(block.get("number", "??"))
    title = c.text(block.get("title"))
    scope = block.get("scope", "UNKNOWN")
    status = block.get("evidence_status", {})
    chart = block.get("chart", {})
    sf = block.get("source_foot", {})
    drawer = block.get("drawer", {})
    body = render_chart(chart)
    definitions = c.definitions(block.get("definitions", []))
    table = c.data_table(block.get("data_table", []))
    drawer_content = (
        f'<div class="drawer-content">{c.esc(drawer.get("content", ""))}</div>'
        f"{table}{definitions}"
    )
    return (
        f'<figure class="exhibit" id="exhibit-{c.esc(number)}" aria-labelledby="exhibit-title-{c.esc(number)}" '
        f'data-exhibit="{c.esc(number)}" '
        f'data-basis="{c.esc(sf.get("basis", "UNKNOWN"))}" '
        f'data-unit="{c.esc(sf.get("unit", "UNKNOWN"))}" '
        f'data-limit="{c.esc(sf.get("limit", "UNKNOWN"))}" '
        f'data-status="{c.esc(sf.get("status", "UNKNOWN"))}">'
        '<figcaption class="exhibit-head"><div>'
        f'<div class="exhibit-number">EXHIBIT {c.esc(number)}</div>'
        f'<h3 class="exhibit-title" id="exhibit-title-{c.esc(number)}">{c.esc(title)}</h3>'
        f'</div><div class="exhibit-scope">{c.esc(scope)}{c.badge(status)}</div></figcaption>'
        f'<div class="exhibit-body chart-{c.esc(chart.get("type", "unknown"))}">{body}</div>'
        f'{c.readout(block.get("readout", {}), "EXHIBIT " + number)}'
        f'{c.source_foot(sf)}'
        f'<details class="evidence-drawer"><summary>{c.esc(drawer.get("summary") or "查看定义与误读边界")}</summary>'
        f"<div>{drawer_content}</div></details>"
        "</figure>"
    )
